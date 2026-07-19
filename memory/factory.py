from config.settings import settings
from memory.mongodb import get_mongodb_memory

def get_memory():
    """
    Returns the configured LangGraph memory implementation.
    """

    if settings.memory_provider == "mongodb":
        return get_mongodb_memory(
            connection_string=settings.mongodb_uri,
            database_name=settings.mongodb_database,
        )

    raise ValueError(
        f"Unsupported memory provider: {settings.memory_provider}"
    )