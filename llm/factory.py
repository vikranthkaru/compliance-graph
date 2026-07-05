from langchain_openai import ChatOpenAI
from langchain_qwq import ChatQwen
from llm.config import settings
def get_chat_model():
    print(f"settings.chat_provider==>{settings.chat_provider}")
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


# from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.embeddings.openai import OpenAIEmbedding
def get_embedding_model():
    if settings.embedding_provider == "openai":
        return OpenAIEmbedding(
            model=settings.embedding_model,
            api_key=settings.embedding_api_key,
            api_base=settings.embedding_base_url or None,
        )
    
    # if settings.embedding_provider == "qwen":
    #     return HuggingFaceEmbedding(
    #         model_name=settings.embedding_model,
    #         device=settings.embedding_device
    #     )
    
    raise ValueError(
        f"Unsupported embedding provider: {settings.embedding_provider}"
    )
