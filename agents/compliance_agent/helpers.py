import os
import json
from typing import List

from tavily import TavilyClient
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter

from llama_index.core.schema import TextNode

from llm.factory import get_chat_model
from services.vector_service import ingest_data_pinecone

from agents.compliance_agent.schemas import (
    RouteComplianceDecision,
    RouteComplianceStatus,
)


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
                    "shipment_id": shipment_id,
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

            ingest_data_pinecone(rag_nodes, namespace)

        except Exception as e:
            print(f"Error processing URL {url}: {str(e)}")
            continue


def llm_cleaner_helper(
    raw_text: str,
    country: str,
    role: str,
    regulation_need: str,
    authority_types: list[str],
    regulation_topics: list[str],
    why_this_applies: str,
) -> list[dict]:
    """
    Splits regulatory content into semantic chunks and enriches
    each chunk with route-specific regulatory context.

    Falls back to recursive character chunking if LLM processing fails.
    """

    llm = get_chat_model()

    authority_text = ", ".join(authority_types)
    topic_text = ", ".join(regulation_topics)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You are an AI data-enrichment component in a pharmaceutical regulatory ingestion pipeline.

Your input is text extracted from a potentially relevant regulatory webpage.

Create logical, standalone semantic chunks from the supplied text.

For each chunk:

- Preserve only content relevant to the regulatory requirement.
- Add a concise context header.
- Do not invent regulations or requirements.
- Do not claim that the source is official unless the supplied content supports that conclusion.
- Exclude navigation menus, cookie notices, unrelated promotional content, and duplicate text.

Route context:

Country: {country}
Route role: {role}
Regulation need: {regulation_need}
Authority types being searched: {authority_types}
Regulation topics: {regulation_topics}
Reason this information applies: {why_this_applies}

Return strictly a valid JSON array.
Do not return Markdown or code fences.

Each object must have exactly this structure:

{{
    "chunk_text": "Context header. Relevant regulatory content."
}}
""",
            ),
            (
                "human",
                "Analyze and segment this webpage content:\n\n{text}",
            ),
        ]
    )

    chain = prompt | llm

    try:
        response = chain.invoke(
            {
                "text": raw_text,
                "country": country,
                "role": role,
                "regulation_need": regulation_need,
                "authority_types": authority_text,
                "regulation_topics": topic_text,
                "why_this_applies": why_this_applies,
            }
        )

        clean_content = response.content.strip()
        clean_content = clean_content.removeprefix("```json")
        clean_content = clean_content.removeprefix("```")
        clean_content = clean_content.removesuffix("```").strip()

        chunks = json.loads(clean_content)

        if not isinstance(chunks, list):
            raise ValueError("LLM cleaner response is not a JSON array")

        valid_chunks = [
            chunk
            for chunk in chunks
            if (
                isinstance(chunk, dict)
                and isinstance(chunk.get("chunk_text"), str)
                and chunk["chunk_text"].strip()
            )
        ]

        if not valid_chunks:
            raise ValueError("LLM cleaner returned no valid chunks")

        return valid_chunks

    except Exception as exc:
        print(f"LLM chunking failed: {exc}. " "Falling back to recursive chunking.")

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            separators=["\n\n", "\n", " ", ""],
        )

        raw_chunks = text_splitter.split_text(raw_text)

        context_header = (
            f"Country: {country}; "
            f"Route role: {role}; "
            f"Regulation need: {regulation_need}; "
            f"Topics: {topic_text}"
        )

        return [
            {"chunk_text": f"{context_header}\n\n{chunk}"}
            for chunk in raw_chunks
            if chunk.strip()
        ]


def stringify_list(values: list | None) -> str:
    return "\n".join(str(value) for value in (values or []))


def get_route_check_status(
    decision: RouteComplianceDecision,
) -> str:
    if decision.human_intervention_required:
        return "Review Required"

    if decision.compliance_status == RouteComplianceStatus.COMPLIANT:
        return "Passed"

    if decision.compliance_status in (
        RouteComplianceStatus.NON_COMPLIANT,
        RouteComplianceStatus.BLOCKED,
    ):
        return "Blocked"

    return "Failed"
