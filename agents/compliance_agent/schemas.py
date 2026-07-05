from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class RegulationRequirement(BaseModel):
    country: str = Field(description="Country for which regulations must be checked")
    route_type: str = Field(description="Origin, Transit or Destination")
    regulation_need: str = Field(description="Type of regulation that needs to be verified")
    authority_types: List[str] = Field(description="Types of official government or regulatory authorities responsible for the applicable regulations, such as Drug Regulatory Authority, Customs Authority, Ministry of Health, Civil Aviation Authority, or Dangerous Goods Authority")
    regulation_topics: List[str] = Field(description="Specific regulatory topics that must be searched, such as Export, Import, Transit, Prescription Medicine, Cold Chain, Controlled Substance, Hazardous Material, GDP, GMP, or Dangerous Goods")
    search_query: str = Field(description="Optimized search query that will be used by the retrieval agent to discover official government regulatory sources")
    why_this_applies: str = Field(description="Reason these regulatory requirements apply based on the shipment, product, transport mode, and route")


class RegulationSearchPlan(BaseModel):
    regulation_requirements: List[RegulationRequirement]




class RouteComplianceStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    REVIEW_REQUIRED = "REVIEW REQUIRED"
    NON_COMPLIANT = "NON COMPLIANT"
    BLOCKED = "BLOCKED"

class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class RouteComplianceDecision(BaseModel):
    country: str
    route_type: str

    compliance_status: RouteComplianceStatus
    confidence_level: ConfidenceLevel
    confidence_score: float

    human_intervention_required: bool

    risk_level: RiskLevel

    summary: str
    reason: str

    missing_documents: List[str]
    policy_conflicts: List[str]
    regulatory_concerns: List[str]
    recommended_action: str
    evidence_sources: List[str]



class ShipmentComplianceDecision(BaseModel):
    shipment_id: str
    shipment_number: str

    overall_status: str = Field(
        description="Overall shipment compliance status: COMPLIANT, REVIEW_REQUIRED, NON_COMPLIANT, or BLOCKED"
    )

    overall_risk_level: str = Field(
        description="Overall shipment risk level: LOW, MEDIUM, HIGH, or CRITICAL"
    )

    summary: str

    route_summary: List[dict]

    human_review_required_routes: List[str]

    blocking_issues: List[str]

    recommended_next_action: str