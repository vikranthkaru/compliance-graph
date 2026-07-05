import os
import json
from typing import List

from tavily import TavilyClient
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter

from llama_index.core.schema import TextNode

from llm.factory import get_chat_model
from services.vector_service import ingest_data_pinecone
def search_regulatory_sources(
    search_query: str,
    authority_types: list[str],
    regulation_topics: list[str],
) -> list[str]:
    client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

    enhanced_query = (
        f"{search_query} "
        f"{' '.join(authority_types)} "
        f"{' '.join(regulation_topics)}"
    ).strip()

    response = client.search(
        query=enhanced_query,
        search_depth="advanced",
        max_results=5,
    )

    urls = []

    for result in response.get("results", []):
        url = result.get("url")

        if not url:
            continue

        urls.append(url)

    return urls

def extract_url_content_and_ingest(
    urls: list[str],
    country: str,
    role: str,
    regulation_need: str,
    authority_types: list[str],
    regulation_topics: list[str],
    why_this_applies: str,
    shipment_id: str,
    namespace: str,
) -> None:
    client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

    for url in urls:
        try:
            extraction = client.extract(urls=[url])

            results = extraction.get("results", [])
            if not results:
                continue

            raw_text = results[0].get("raw_content", "")
            if not raw_text:
                continue

            clean_chunks = llm_cleaner_helper(
                raw_text=raw_text,
                country=country,
                role=role,
                regulation_need=regulation_need,
                authority_types=authority_types,
                regulation_topics=regulation_topics,
                why_this_applies=why_this_applies,
            )

            rag_nodes = []

            for chunk in clean_chunks:
                node = TextNode(text=chunk["chunk_text"])
                node.metadata = {
                    "url": url,
                    "country": country,
                    "role": role,
                    "regulation_need": regulation_need,
                    "authority_types": authority_types,
                    "regulation_topics": regulation_topics,
                    "why_this_applies": why_this_applies,
                    "source_type": "government_regulation",
                }
                rag_nodes.append(node)

            ingest_data_pinecone(rag_nodes,shipment_id,namespace)

        except Exception as e:
            print(f"Error processing URL {url}: {str(e)}")
            continue

def llm_cleaner_helper(
    raw_text: str,
    country: str,
    role: str,
    auth_name: str
) -> List[dict]:
    """
    Uses LLM to split regulation content into semantic chunks.
    Falls back to normal recursive chunking if LLM chunking fails.
    """

    llm = get_chat_model()

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            """
You are an AI data enrichment node in a pharmaceutical regulatory ingestion pipeline.

Your input is text extracted from an official or regulatory webpage.

Tasks:
1. Split the text into logical, standalone semantic chunks.
2. For each chunk, generate a short context header.
3. The context must be specific to:
   - Country: {country}
   - Route role: {role}
   - Regulatory authority: {auth_name}

Return strictly a valid JSON array.
Do not include markdown.
Do not include code fences.

Each object must follow this format:
{{"chunk_text": "Context for {role} in {country} under {auth_name}: [summary]. Actual chunk content here..."}}
"""
        ),
        (
            "human",
            "Analyze and segment this webpage content:\n\n{text}"
        )
    ])

    chain = prompt | llm

    try:
        response = chain.invoke({
            "text": raw_text,
            "country": country,
            "role": role,
            "auth_name": auth_name
        })

        clean_content = response.content.strip()
        clean_content = clean_content.removeprefix("```json").removeprefix("```")
        clean_content = clean_content.removesuffix("```").strip()

        chunks = json.loads(clean_content)

        return chunks

    except Exception as e:
        print(f"LLM chunking failed: {str(e)}. Falling back to recursive chunking.")

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            separators=["\n\n", "\n", " ", ""]
        )

        langchain_chunks = text_splitter.split_text(raw_text)

        return [
            {
                "chunk_text": (
                    f"Context for {role} in {country} under {auth_name}: {chunk}"
                )
            }
            for chunk in langchain_chunks
        ]


# def resume_graph(graph, config, resume_payload):
#     return graph.invoke(
#         Command(resume=resume_payload),
#         config=config
#     )