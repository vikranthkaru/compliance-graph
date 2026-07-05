# from langchain_core.tools import tool
# from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper
# from typing import Type
# from pydantic import BaseModel, Field

# from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper

# class UnifiedComplianceTools:
    
#     @tool
#     def search_regulatory_sources(query: str):
#         """ 
#         MANDATORY TOOL: Use this to search for REAL-TIME pharmaceutical regulations.
#         Internal knowledge is strictly prohibited.
#         """
#         try:
#             wrapper = TavilySearchAPIWrapper()
#             raw_data = wrapper.results(query=query, max_results=5, search_depth="advanced")

#             formatted_results = [
#                 f"Title: {r.get('title')}\nURL: {r.get('url')}\nContent: {r.get('content')}"
#                 for r in raw_data
#             ]
#             return "\n\n".join(formatted_results)
#         except Exception as e:
#             return f"Tool execution failed: {str(e)}"