from enum import Enum
from typing import List
from pydantic import BaseModel, Field


class RegulationRequirement(BaseModel):
    country: str = Field(description="Country for which regulations must be checked")
    route_type: str = Field(description="Origin, Transit or Destination")
    regulation_topics: List[str] = Field(description="Specific regulatory topics that must be searched, such as Export, Import, Transit, Prescription Medicine, Cold Chain, Controlled Substance, Hazardous Material, GDP, GMP, or Dangerous Goods")
    why_this_applies: list[str] = Field(description="Reason these regulatory requirements apply based on the shipment, product, transport mode, and route")


class RegulationSearchPlan(BaseModel):
    regulation_requirements: List[RegulationRequirement]

class RouteComplianceStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NON_COMPLIANT = "NON_COMPLIANT"
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
        description="COMPLIANT, REVIEW_REQUIRED, NON_COMPLIANT, or BLOCKED"
    )

    overall_risk_level: str = Field(
        description="LOW, MEDIUM, HIGH, or CRITICAL"
    )

    confidence_score: float

    human_review_required: bool

    summary: str

    ai_reasoning: str

    route_summary: List[dict]

    blocking_issues: List[str]

    missing_documents: List[str]

    evidence_summary: List[str]

    recommended_next_action: str


class SourceRerankResult(BaseModel):
    source_index: int

    relevance_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall relevance score between 0 and 1",
    )

    country_match: bool
    route_match: bool
    topic_match: bool

    selected: bool
    reason: str

class SourceRerankResponse(BaseModel):
    results: list[SourceRerankResult]