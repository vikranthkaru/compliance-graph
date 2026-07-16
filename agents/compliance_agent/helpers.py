import os, json, yaml, html, re, hashlib
from datetime import datetime, timezone
from typing import List
from pathlib import Path
from tavily import TavilyClient
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from llama_index.core.schema import TextNode
from llm.factory import ( get_chat_model, get_structured_chat_model )
from services.vector_service import ingest_data_pinecone
from agents.compliance_agent.schemas import (
    RouteComplianceDecision,
    RouteComplianceStatus,
    SourceRerankResponse
)
from agents.compliance_agent.prompts import (
    SOURCE_RERANKER_PROMPT
)
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
DOMAIN_CONFIG_FILE = CONFIG_DIR / "regulatory_domains.yaml"
RANKING_CONFIG_FILE = CONFIG_DIR / "source_ranking.yaml"
_RANKING_CONFIG: dict | None = None
_DOMAIN_CONFIG: dict | None = None

def load_regulatory_domains() -> dict:
    global _DOMAIN_CONFIG
    if _DOMAIN_CONFIG is None:
        with open(
            DOMAIN_CONFIG_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            _DOMAIN_CONFIG = yaml.safe_load(file) or {}

    return _DOMAIN_CONFIG

def load_source_ranking() -> dict:
    global _RANKING_CONFIG
    if _RANKING_CONFIG is None:
        with open(
            RANKING_CONFIG_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            _RANKING_CONFIG = yaml.safe_load(file) or {}

    return _RANKING_CONFIG


def get_domain_rules(country: str) -> tuple[list[str], list[str]]:
    config = load_regulatory_domains()

    global_rules = config.get("global", {})
    countries = config.get("countries", {})
    country_rules = config.get("countries", {}).get(country, {})

    include_domains = list(
        dict.fromkeys(
            global_rules.get("trusted", [])
            + country_rules.get("trusted", [])
        )
    )

    exclude_domains = list(
        dict.fromkeys(
            global_rules.get("excluded", [])
            + country_rules.get("excluded", [])
        )
    )

    return include_domains, exclude_domains

def calculate_source_rank(
    result: dict,
    route_type: str,
    regulation_topics: list[str],
) -> float:
    config = load_source_ranking()

    weights = config["weights"]
    route_keywords = config.get("route_keywords", {})
    topic_keywords = config.get("topic_keywords", {})
    specificity_terms = config.get(
        "document_specificity_terms",
        [],
    )

    searchable_text = " ".join(
        [
            result.get("title", ""),
            result.get("content", ""),
            result.get("url", ""),
        ]
    ).lower()

    tavily_score = float(result.get("score") or 0.0)

    route_match = 0.0

    route_match = float(
        any(
            keyword.lower() in searchable_text
            for keyword in route_keywords.get(route_type, [])
        )
    )
    matched_topics = 0

    for topic in regulation_topics:
        keywords = topic_keywords.get(
            topic,
            [topic.lower()],
        )

        if any(
            keyword.lower() in searchable_text
            for keyword in keywords
        ):
            matched_topics += 1

    topic_coverage = (
        matched_topics / len(regulation_topics)
        if regulation_topics
        else 0.0
    )

    document_specificity = float(
        any(
            term.lower() in searchable_text
            for term in specificity_terms
        )
    )

    final_score = (
        tavily_score * weights["tavily_score"]
        + route_match * weights["route_match"]
        + topic_coverage * weights["topic_coverage"]
        + document_specificity
        * weights["document_specificity"]
    )

    return round(final_score, 4)

def rank_regulatory_sources(
    results: list[dict],
    route_type: str,
    regulation_topics: list[str],
) -> list[dict]:

    ranked_results = [
        {
            **result,
            "rank_score": calculate_source_rank(
                result=result,
                route_type=route_type,
                regulation_topics=regulation_topics,
            ),
        }
        for result in results
    ]

    return sorted(
        ranked_results,
        key=lambda item: item["rank_score"],
        reverse=True,
    )

def helper_build_regulation_search_query(
    country: str,
    route_type: str,
    regulation_topics: list[str],
    shipment_context: dict,
) -> str:
    product = shipment_context["product"]

    route_action = {
        "Origin": "export",
        "Transit": "transit",
        "Destination": "import",
    }.get(route_type, route_type.lower())

    parts = [
        "official government",
        country,
        route_action,
        product["productName"],
        product["drugCategory"],
        *regulation_topics,
    ]

    return " ".join(
        str(part).strip()
        for part in parts
        if part
    )

def helper_rerank_regulatory_sources(
    ranked_results: list[dict],
    country: str,
    route_type: str,
    regulation_topics: list[str],
    why_this_applies: str | list[str],
    top_k: int = 3,
    minimum_score: float = 0.60,
) -> list[dict]:
    """
    Uses an LLM to semantically rerank already filtered and ranked
    Tavily results.

    The LLM evaluates only the supplied snippets. It does not crawl URLs.
    """

    if not ranked_results:
        return []

    candidate_sources = []

    for source_index, result in enumerate(ranked_results):
        candidate_sources.append(
            {
                "source_index": source_index,
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": result.get("content", ""),
                "rank_score": result.get("rank_score", 0.0),
            }
        )

    llm = get_structured_chat_model(SourceRerankResponse)

    response = llm.invoke(
        SOURCE_RERANKER_PROMPT.format(
            country=country,
            route_type=route_type,
            regulation_topics=regulation_topics,
            why_this_applies=why_this_applies,
            candidate_sources=candidate_sources,
        )
    )

    rerank_response = response.model_dump(mode="json")

    evaluation_by_index = {
        item["source_index"]: item
        for item in rerank_response.get("results", [])
    }

    reranked_sources = []

    for source_index, source in enumerate(ranked_results):
        evaluation = evaluation_by_index.get(source_index)

        if not evaluation:
            continue

        enriched_source = {
            **source,
            "rerank_score": evaluation["relevance_score"],
            "country_match": evaluation["country_match"],
            "route_match": evaluation["route_match"],
            "topic_match": evaluation["topic_match"],
            "rerank_selected": evaluation["selected"],
            "rerank_reason": evaluation["reason"],
        }

        if (
            evaluation["selected"]
            and evaluation["relevance_score"] >= minimum_score
        ):
            reranked_sources.append(enriched_source)

    reranked_sources.sort(
        key=lambda item: item["rerank_score"],
        reverse=True,
    )

    return reranked_sources[:top_k]

def helper_search_regulatory_sources(
    search_query: str,
    search_country: str,
    route_type: str,
    regulation_topics: list[str],
) -> list[dict]:
    client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    include_domains, exclude_domains = get_domain_rules(search_country)

    response = client.search(
        query=search_query,
        search_depth="advanced",
        max_results=10,
        chunks_per_source=5,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        country=search_country.lower(),
    )

    filtered_results = []
    seen_urls = set()
    for result in response.get("results", []):
        url = result.get("url")

        if not url:
            continue

        normalized_url = url.rstrip("/").lower()

        if normalized_url in seen_urls:
            continue

        seen_urls.add(normalized_url)

        filtered_results.append(result)
    
    
    return rank_regulatory_sources(
        results=filtered_results,
        route_type=route_type,
        regulation_topics=regulation_topics,
    )



def clean_extracted_content(raw_text: str) -> str:
    """
    Deterministically cleans extracted webpage or PDF content before
    chunking and embedding.
    """

    if not raw_text:
        return ""

    cleaned_text = html.unescape(raw_text)

    # Remove script and style sections.
    cleaned_text = re.sub(
        r"<script\b[^>]*>.*?</script>",
        " ",
        cleaned_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    cleaned_text = re.sub(
        r"<style\b[^>]*>.*?</style>",
        " ",
        cleaned_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Remove HTML comments.
    cleaned_text = re.sub(
        r"<!--.*?-->",
        " ",
        cleaned_text,
        flags=re.DOTALL,
    )

    # Remove remaining HTML tags.
    cleaned_text = re.sub(
        r"<[^>]+>",
        " ",
        cleaned_text,
    )

    boilerplate_patterns = [
        r"accept all cookies",
        r"manage cookie preferences",
        r"cookie policy",
        r"privacy policy",
        r"terms and conditions",
        r"skip to main content",
        r"subscribe to our newsletter",
        r"all rights reserved",
    ]

    for pattern in boilerplate_patterns:
        cleaned_text = re.sub(
            pattern,
            " ",
            cleaned_text,
            flags=re.IGNORECASE,
        )

    # Normalize line endings.
    cleaned_text = cleaned_text.replace("\r\n", "\n")
    cleaned_text = cleaned_text.replace("\r", "\n")

    # Collapse repeated spaces but preserve useful line breaks.
    cleaned_text = re.sub(r"[ \t]+", " ", cleaned_text)
    cleaned_text = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned_text)

    return cleaned_text.strip()


def remove_duplicate_chunks(
    chunks: list[dict],
) -> list[dict]:
    """
    Removes exact duplicates after normalizing case and whitespace.

    A deterministic hash is attached to each retained chunk.
    """

    unique_chunks = []
    seen_hashes: set[str] = set()

    for chunk in chunks:
        chunk_text = chunk.get("chunk_text", "").strip()

        if not chunk_text:
            continue

        normalized_text = " ".join(
            chunk_text.lower().split()
        )

        chunk_hash = hashlib.sha256(
            normalized_text.encode("utf-8")
        ).hexdigest()

        if chunk_hash in seen_hashes:
            continue

        seen_hashes.add(chunk_hash)

        unique_chunks.append(
            {
                **chunk,
                "chunk_text": chunk_text,
                "chunk_hash": chunk_hash,
            }
        )

    return unique_chunks

def validate_chunks(
    chunks: list[dict],
    min_characters: int = 200,
    max_characters: int = 4000,
) -> list[dict]:
    """
    Removes chunks that are empty, too short, too large, or contain
    insufficient readable text.
    """
    valid_chunks = []

    for chunk in chunks:
        chunk_text = chunk.get("chunk_text", "").strip()

        if not chunk_text:
            continue

        if len(chunk_text) < min_characters:
            continue

        if len(chunk_text) > max_characters:
            continue
        
        # Reject chunks containing almost no alphabetic content.
        alphabetic_count = sum(
            character.isalpha()
            for character in chunk_text
        )

        if alphabetic_count < 100:
            continue

        valid_chunks.append(chunk)

    return valid_chunks

def split_large_document(
    cleaned_text: str,
    chunk_size: int = 12000,
    chunk_overlap: int = 500,
) -> list[str]:
    """
    Splits a large extracted document into manageable sections before
    LLM semantic cleaning.
    """

    if not cleaned_text:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    return splitter.split_text(cleaned_text)

def helper_extract_url_content_and_ingest(
    sources: list[dict],
    country: str,
    role: str,
    regulation_topics: list[str],
    why_this_applies: str | list[str],
    shipment_id: str,
    namespace: str,
) -> None:
    """
    Extracts, cleans, chunks, validates, enriches, and embeds regulatory
    content selected by the source reranker.
    """

    client = TavilyClient(
        api_key=os.getenv("TAVILY_API_KEY")
    )

    for source in sources:
        url = source.get("url")

        if not url:
            continue

        source_title = source.get("title", "")
        tavily_score = source.get("score")
        rank_score = source.get("rank_score")
        rerank_score = source.get("rerank_score")
        rerank_reason = source.get("rerank_reason", "")

        try:
            extraction = client.extract(
                urls=[url],
            )

            extraction_results = extraction.get(
                "results",
                [],
            )

            if not extraction_results:
                print(
                    f"No content extracted from source: {url}"
                )
                continue

            raw_text = extraction_results[0].get(
                "raw_content",
                "",
            )

            if not raw_text:
                print(
                    f"Extracted content was empty: {url}"
                )
                continue

            cleaned_text = clean_extracted_content(
                raw_text
            )

            if not cleaned_text:
                print(
                    f"No usable content after cleaning: {url}"
                )
                continue

            print(
                f"Content cleaning for {url}: "
                f"{len(raw_text)} → "
                f"{len(cleaned_text)} characters"
            )

            document_sections = split_large_document(cleaned_text)
            generated_chunks = []
            for section_number, section_text in enumerate(
                document_sections,
                start=1,
            ):
                try:
                    section_chunks = llm_cleaner_helper(
                        raw_text=section_text,
                        country=country,
                        role=role,
                        regulation_topics=regulation_topics,
                        why_this_applies=why_this_applies,
                    )

                    for chunk in section_chunks:
                        generated_chunks.append(
                            {
                                **chunk,
                                "source_section": section_number,
                            }
                        )

                except Exception as exc:
                    print(
                        f"Unable to process section {section_number} "
                        f"for {url}: {exc}"
                    )

            unique_chunks = remove_duplicate_chunks(
                generated_chunks
            )

            print(
                f"Duplicate removal for {url}: "
                f"{len(generated_chunks)} → "
                f"{len(unique_chunks)} chunks"
            )

            validated_chunks = validate_chunks(
                chunks=unique_chunks,
                min_characters=200,
                max_characters=4000,
            )

            print(
                f"Chunk validation for {url}: "
                f"{len(unique_chunks)} → "
                f"{len(validated_chunks)} chunks"
            )

            if not validated_chunks:
                print(
                    f"No valid chunks available for ingestion: {url}"
                )
                continue

            ingested_at = datetime.now(
                timezone.utc
            ).isoformat()

            rag_nodes = []

            for chunk_index, chunk in enumerate(
                validated_chunks,
                start=1,
            ):
                node = TextNode(
                    id_=chunk["chunk_hash"],
                    text=chunk["chunk_text"],
                )

                node.metadata = {
                    # Execution context
                    "shipment_id": shipment_id,
                    "namespace": namespace,

                    # Route context
                    "country": country,
                    "role": role,

                    # Regulatory context
                    "regulation_topics": regulation_topics,
                    "why_this_applies": (
                                            "\n".join(why_this_applies)
                                            if isinstance(why_this_applies, list)
                                            else why_this_applies
                                        ),

                    # Source traceability
                    "source_type": "government_regulation",
                    "source_url": url,
                    "document_title": source_title,

                    # Retrieval scoring
                    "tavily_score": tavily_score,
                    "rank_score": rank_score,
                    "rerank_score": rerank_score,
                    "rerank_reason": rerank_reason,

                    # Chunk traceability
                    "chunk_hash": chunk["chunk_hash"],
                    "chunk_index": chunk_index,
                    "chunk_character_count": len(
                        chunk["chunk_text"]
                    ),

                    # Audit metadata
                    "ingested_at": ingested_at,
                }

                rag_nodes.append(node)

            ingest_data_pinecone(
                rag_nodes=rag_nodes,
                namespace=namespace,
            )

            print(
                f"Ingested {len(rag_nodes)} chunks "
                f"for {country} / {role} from {url}"
            )

        except Exception as exc:
            print(
                f"Error processing URL {url}: {exc}"
            )
            continue


def llm_cleaner_helper(
    raw_text: str,
    country: str,
    role: str,
    regulation_topics: list[str],
    why_this_applies: list[str],
) -> list[dict]:
    """
    Splits regulatory content into semantic chunks and enriches
    each chunk with route-specific regulatory context.

    Falls back to recursive character chunking if LLM processing fails.
    """

    llm = get_chat_model()

    topic_text = ", ".join(regulation_topics)
    why_this_applies_text = "\n".join(
        f"- {reason}"
        for reason in why_this_applies
    )

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
Regulation topics: {regulation_topics}
Reason this information applies:
{why_this_applies}

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
                "regulation_topics": topic_text,
                "why_this_applies": why_this_applies_text,
            }
        )

        clean_content = response.content.strip()
        clean_content = clean_content.removeprefix("```json")
        clean_content = clean_content.removeprefix("```")
        clean_content = clean_content.removesuffix("```").strip()

        chunks = json.loads(clean_content)

        if not isinstance(chunks, list):
            raise ValueError(
                "LLM cleaner response is not a JSON array"
            )

        valid_chunks = [
            {
                **chunk,
                "chunk_text": chunk["chunk_text"].strip(),
            }
            for chunk in chunks
            if (
                isinstance(chunk, dict)
                and isinstance(
                    chunk.get("chunk_text"),
                    str,
                )
                and chunk["chunk_text"].strip()
            )
        ]

        if not valid_chunks:
            raise ValueError(
                "LLM cleaner returned no valid chunks"
            )

        return valid_chunks

    except Exception as exc:
        print(
            f"LLM chunking failed: {exc}. "
            "Falling back to recursive chunking."
        )

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            separators=["\n\n", "\n", " ", ""],
        )

        raw_chunks = text_splitter.split_text(raw_text)

        context_header = (
            f"Country: {country}; "
            f"Route role: {role}; "
            f"Topics: {topic_text}"
        )

        return [
            {
                "chunk_text": (
                    f"{context_header}\n\n{chunk.strip()}"
                )
            }
            for chunk in raw_chunks
            if chunk.strip()
        ]


def helper_stringify_list(values: list | None) -> str:
    return "\n".join(str(value) for value in (values or []))


def helper_get_route_check_status(
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
