# from typing import List
# from pydantic import BaseModel, Field


# class RegulationRequirement(BaseModel):
#     country: str = Field(description="Country for which regulations must be checked")
#     route_type: str = Field(description="Origin, Transit or Destination")
#     regulation_need: str = Field(description="Type of regulation that needs to be verified")
#     regulatory_authority: str = Field(description="Primary government or regulatory authority")
#     preferred_domains: List[str] = Field(description="Official domains to prioritize")
#     search_query: str = Field(description="Search query for the retrieval tool")


# class RegulationSearchPlan(BaseModel):
#     regulation_requirements: List[RegulationRequirement]