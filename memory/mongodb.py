from pymongo import MongoClient
from langgraph.checkpoint.mongodb import MongoDBSaver

def get_mongodb_memory(
    connection_string: str,
    database_name: str,
) -> MongoDBSaver:
    client = MongoClient(connection_string)

    return MongoDBSaver(
        client=client,
        db_name=database_name,
    )