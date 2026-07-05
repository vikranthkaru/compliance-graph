from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    chat_provider: str = "qwen"
    chat_model: str
    chat_api_key: str
    chat_base_url: str = ""

    embedding_provider: str = "openai"
    embedding_model: str
    embedding_api_key: str
    embedding_base_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )

settings = Settings()