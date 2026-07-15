import asyncio
# from langchain_mcp_adapters.client import MultiServerMCPClient
# from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
# Paste the access_token you successfully generated via OAuth 
# SALESFORCE_ACCESS_TOKEN = "eyJ0bmsiOiJjb3JlL3Byb2QvMDBEZzUwMDAwMDlhd0xGRUFZIiwidmVyIjoiMS4wIiwia2lkIjoiQ09SRV9BVEpXVC4wMERnNTAwMDAwOWF3TEYuMTc4MDI2MTYxNjMyMiIsInR0eSI6InNmZGMtY29yZS10b2tlbiIsInR5cCI6IkpXVCIsImFsZyI6IlJTMjU2In0.eyJzY3AiOiJyZWZyZXNoX3Rva2VuIG1jcF9hcGkiLCJzdWIiOiJ1aWQ6MDA1ZzUwMDAwMDZNeDZmQUFDIiwicm9sZXMiOltdLCJpc3MiOiJodHRwczovL29yZ2Zhcm0tOTc1MzNhOTA3OC1kZXYtZWQuZGV2ZWxvcC5teS5zYWxlc2ZvcmNlLmNvbSIsImNsaWVudF9pZCI6IjNNVkc5N0w3UFdiUHE2VXpRMU9hU0Y0dGs0bHBTMEthY1ZueHQ2d29McnRvNnMuTWVYUk1UZ3FETjVkWUllSUl5QlVhcFp1bzFzM2JrWVRjR2dqX3AiLCJhdWQiOlsiaHR0cHM6Ly9vcmdmYXJtLTk3NTMzYTkwNzgtZGV2LWVkLmRldmVsb3AubXkuc2FsZXNmb3JjZS5jb20iLCJodHRwczovL2FwaS5zYWxlc2ZvcmNlLmNvbSJdLCJuYmYiOjE3ODMwOTY3NzQsIm10eSI6Im9hdXRoIiwic2ZpIjoiMTcyZmZmMmQwMGFmYTgwY2YzZjBjNjk5ZjZmNmY0YWNkZTk2ZGNmOTE0MTg4NTE5ZDM0ZmFmOTc0NzhmYjU4NCIsInNmYXBfb3AiOiJFaW5zdGVpbkhhd2tpbmdDMkNFbmFibGVkLEVHcHRGb3JEZXZzQXZhaWxhYmxlLEVpbnN0ZWluR2VuZXJhdGl2ZVNlcnZpY2UsVGFibGVhdU1ldHJpY0Jhc2ljcyxFaW5zdGVpbkdQVE5DUCxNQ1BTZXJ2aWNlIiwiaHNjIjpmYWxzZSwiZXhwIjoxNzgzMTAzOTg5LCJpYXQiOjE3ODMwOTY3ODl9.OoN0-ONaOiW3MWG-VJK-rbRqaG_bB6DPr3peUGFUAyMN7F9fgBznfRjDfB1IMZZYPPXA_np15DbSXnOcGHVsVLh7gm88f8wtKPxuoGNlkD5gJbV53Vc0YMoL0jQQK5ngm8E3_PgzHsL4hbQBp5Et1Zw1aMp3XMWgyRwamRaakQEZLvRCnXNI5e9qy-VLZpCvXxgEfbPSjn0IXDSmTqtdNWk3j7_8feUbaL9xig_L9rdtTtC-FXb2eiEzrdAs2GqTppcm97gh3eeZFK3DNp_9AqSxnrKEcMAgJNVPLtscriFzj91IOLouWFH2Wt2qh_L9gNcKfxkS-BXNgxTkVfPG2w"
# # Your Salesforce Instance Base URL or MCP Endpoint Routing URL
# SALESFORCE_MCP_URL = "https://api.salesforce.com/platform/mcp/v1/custom/MCPServer" 

from services.salesforce_data_cloud_service import get_data_cloud_connection

# @tool
def fetch_company_policy_from_data_cloud(search_text: str, limit: int = 10) -> list[dict]:
    """
    Search Salesforce Data Cloud vector index for internal company policy chunks.
    Use this to retrieve company SOP, policy, and compliance guidance.
    """
    connection = get_data_cloud_connection()
    cursor = connection.cursor()

    safe_search_text = search_text.replace("'", "''")

    sql = f"""
    SELECT
        index.score__c,
        chunk.Chunk__c
    FROM vector_search(
        TABLE(Knowledge_Article_Version_index__dlm),
        '{safe_search_text}',
        '',
        {limit}
    ) index
    JOIN Knowledge_Article_Version_chunk__dlm chunk
        ON index.RecordId__c = chunk.RecordId__c
    """

    try:
        cursor.execute(sql)
        rows = cursor.fetchall()

        return [
            {
                "score": row[0],
                "content": row[1],
                "source_type": "company_policy",
            }
            for row in rows
        ]

    finally:
        cursor.close()

# def get_salesforce_rag_tools() -> list:
#     return [fetch_company_policy_from_data_cloud]

# async def _async_load_mcp_pipeline():
#     client = MultiServerMCPClient(
#         {
#             "salesforce": {
#                 "transport": "http",
#                 "url": SALESFORCE_MCP_URL,
#                 "headers": {
#                     "Authorization": f"Bearer {SALESFORCE_ACCESS_TOKEN}",
#                     "Content-Type": "application/json",
#                 },
#             }
#         }
#     )

#     return await client.get_tools()


# def get_salesforce_rag_tools() -> list:
#     try:
#         all_tools = asyncio.run(_async_load_mcp_pipeline())

#         return [
#             tool
#             for tool in all_tools
#             if tool.name == "postDcQuerySqldata_data_cloud_queries"
#         ]

#     except Exception as e:
#         print(f"Error loading Salesforce MCP tools: {e}")
#         return []

#     except Exception as e:
#         print(f"Error loading Salesforce MCP tools: {type(e).__name__}: {e}")
#         return []




from services.vector_service import fetch_data_from_pinecone

@tool
def search_government_regulations(
     query: str,
    country: str,
    route_type: str,
    shipment_id: str,
    similarity_top_k: int = 5,
) -> list:
    """
    Search the government regulation Pinecone RAG index for relevant regulatory chunks.
    Use this tool to retrieve external government regulation context for a specific shipment route.
    """
    namespace = f"shipment-{shipment_id}"

    nodes = fetch_data_from_pinecone(
        query_text=query,
        similarity_top_k=similarity_top_k,
        raw_nodes_only=True,
        namespace=namespace,
        metadata_filter={
            "country": country,
            "role": route_type,
        },
    )

    results = []

    for node in nodes:
        results.append(
            {
                "content": node.text,
                "metadata": node.metadata,
            }
        )

    return results


def get_pinecone_rag_tools() -> list:
    return [
        search_government_regulations
    ]


