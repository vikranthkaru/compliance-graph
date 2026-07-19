from langchain_openai import ChatOpenAI
from langchain_qwq import ChatQwen
from config.settings import settings
def get_chat_model():
    #Sprint(f"settings.chat_provider==>{settings.chat_provider}")
    if settings.chat_provider ==  "qwen":
        return ChatQwen(
            model=settings.chat_model,
            api_key=settings.chat_api_key,
            max_retries=2,
            base_url=settings.chat_base_url or None,
            temperature=0
        )

    elif settings.chat_provider == "openai":
        return ChatOpenAI(
            model=settings.chat_model,
            api_key=settings.chat_api_key,
            max_retries=2,
            base_url=settings.chat_base_url or None,
            temperature=0
        )

    raise ValueError(f"Unsupported provider: {settings.chat_provider}")

def get_structured_chat_model(schema):
    return get_chat_model().with_structured_output(schema)

from langchain.agents import create_agent
def get_react_agent(tools, system_prompt: str):
    return create_agent(
        model=get_chat_model(),
        tools=tools,
        system_prompt=system_prompt,
    )

# from inspect import signature
from llama_index.embeddings.openai import OpenAIEmbedding
def get_embedding_model():
    if settings.embedding_provider not in ("openai", "qwen"):
        raise ValueError(
            f"Unsupported embedding provider: {settings.embedding_provider}"
        )

    return OpenAIEmbedding(
        model_name=settings.embedding_model,
        api_key=settings.embedding_api_key,
        api_base=settings.embedding_base_url or None,
        embed_batch_size=8,
        dimensions=1024,
    )
    
