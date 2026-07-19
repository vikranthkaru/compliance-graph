import os
import json
import time
from typing import List
from pinecone import Pinecone, ServerlessSpec
from llama_index.core import VectorStoreIndex, Settings, StorageContext
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llm.factory import get_embedding_model
from llama_index.core import Settings
from dotenv import load_dotenv
from llama_index.core.vector_stores import (
    MetadataFilters,
    ExactMatchFilter
)

load_dotenv()

_INDEX_REGISTRY = {}
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "my-rag-index")
PINECONE_DIMENSION = int(os.getenv("PINECONE_DIMENSION", "1536"))
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

from pinecone import Pinecone, ServerlessSpec
from pinecone.exceptions import PineconeApiException
import os
import time


def ensure_pinecone_index(index_name: str = INDEX_NAME):
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

    existing_indexes = pc.list_indexes().names()

    if index_name not in existing_indexes:
        try:
            pc.create_index(
                name=index_name,
                dimension=PINECONE_DIMENSION,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud=PINECONE_CLOUD,
                    region=PINECONE_REGION
                )
            )
        except PineconeApiException as e:
            if getattr(e, "status", None) != 409:
                raise

        while not pc.describe_index(index_name).status["ready"]:
            time.sleep(1)

    return pc.Index(index_name)

def get_registry_key(
    index_name: str,
    namespace: str | None) -> str:
    return f"{index_name}:{namespace or 'default'}"

def get_rag_index(index_name: str = INDEX_NAME, namespace: str | None = None,):
    registry_key = get_registry_key(index_name, namespace)
    if registry_key not in _INDEX_REGISTRY:
        Settings.embed_model = get_embedding_model()

        pinecone_index = ensure_pinecone_index(index_name)
        vector_store = PineconeVectorStore(pinecone_index=pinecone_index, namespace=namespace,)

        _INDEX_REGISTRY[registry_key] = VectorStoreIndex.from_vector_store(
            vector_store=vector_store
        )

    return _INDEX_REGISTRY[registry_key]


def ingest_data_pinecone(rag_nodes: list, namespace: str | None = None):
    """
    Accepts pre-chunked LlamaIndex TextNodes, provisions Pinecone if missing,
    generates embeddings, and upserts them securely into the cloud vector store.
    """
    if not rag_nodes:
        return None
    Settings.embed_model = get_embedding_model()
    pinecone_index = ensure_pinecone_index(INDEX_NAME)

    vector_store = PineconeVectorStore(
        pinecone_index=pinecone_index,  namespace=namespace
    )

    storage_context = StorageContext.from_defaults(
        vector_store=vector_store
    )

    index = VectorStoreIndex(
        nodes=rag_nodes,
        storage_context=storage_context
    )

    registry_key = get_registry_key(INDEX_NAME, namespace)
    _INDEX_REGISTRY[registry_key] = index

    return index


async def  afetch_data_from_pinecone(query_text: str, similarity_top_k: int = 3, raw_nodes_only: bool = False):
    """
    Connects to the existing Pinecone index, embeds the query text,
    and fetches either the LLM-synthesized answer or the raw source nodes.
    """
    # 1. Maintain consistent global settings from ingestion
    Settings.embed_model = get_embedding_model()
    
    # 2. Connect to the existing Pinecone index
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index_name = "my-rag-index"
    pinecone_index = pc.Index(index_name)
    
    # 3. Reconstruct the vector store index context
    vector_store = PineconeVectorStore(pinecone_index=pinecone_index)
    index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
    
    # 4. Fetch Strategy selection
    if raw_nodes_only:
        # Strategy A: Get raw text chunks without calling the LLM
        retriever = index.as_retriever(similarity_top_k=similarity_top_k)
        retrieved_nodes = retriever.retrieve(query_text)
        return retrieved_nodes
    else:
        # Strategy B: Use GPT-4o-mini to synthesize a natural language answer
        query_engine = index.as_query_engine(similarity_top_k=similarity_top_k)
        response = query_engine.query(query_text)
        return response

def fetch_data_from_pinecone(
    query_text: str,
    similarity_top_k: int = 3,
    raw_nodes_only: bool = True,
    index_name: str = INDEX_NAME,
    namespace: str | None = None,
    metadata_filter: dict | None = None,
):
    """
    Fetches relevant regulation chunks from Pinecone.

    Supports:
    - shipment-specific namespace
    - optional metadata filtering
    - raw node retrieval or synthesized response
    """

    Settings.embed_model = get_embedding_model()

    pinecone_index = ensure_pinecone_index(index_name)

    vector_store = PineconeVectorStore(
        pinecone_index=pinecone_index,
        namespace=namespace,
    )

    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store
    )

    filters = None

    if metadata_filter:
        filters = MetadataFilters(
            filters=[
                ExactMatchFilter(key=key, value=value)
                for key, value in metadata_filter.items()
                if value is not None
            ]
        )

    if raw_nodes_only:
        retriever = index.as_retriever(
            similarity_top_k=similarity_top_k,
            filters=filters,
        )

        return retriever.retrieve(query_text)

    query_engine = index.as_query_engine(
        similarity_top_k=similarity_top_k,
        filters=filters,
    )

    return query_engine.query(query_text)


def delete_shipment_namespace( namespace: str | None = None,) -> None:
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    existing_indexes = pc.list_indexes().names()
    if INDEX_NAME in existing_indexes:
        pinecone_index = pc.Index(INDEX_NAME)
        
    pinecone_index.delete(
        delete_all=True,
        namespace=namespace,
    )