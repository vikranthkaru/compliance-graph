from enum import Enum
from typing import TypedDict, Dict, Any, List, Optional
from agents.compliance_agent.schemas import RouteComplianceDecision

# ===========================
# Main Graph State
# ===========================
class ComplianceState(TypedDict):
    event: Dict[str, Any]
    shipment_context: Dict[str, Any]

     # Output of Node 2
    regulation_search_plan: Dict | None

    # Aggregated route decisions after fan-in
    route_compliance_results: Dict[str, Dict[str, Any]]

    compliance_result: Dict | None

    # Temporary retrieval testing (can remove later)
    retrieval_test_result: dict | None


    errors: List[str]


# ===========================
# Worker Graph State
# ===========================
class RouteComplianceWorkerState(TypedDict): 
    shipment_id: str
    shipment_context: Dict[str, Any]

    # One regulation requirement assigned to this worker
    regulation_requirement: Dict[str, Any]

     # RAG Retrieval Results
    company_policy_context: List[Dict[str, Any]]
    government_regulation_context: List[Dict[str, Any]]

    internal_policy_fetched: bool
    external_policy_fetched: bool
    human_intervention_required: bool

    # LLM Decision
    route_decision: Optional[RouteComplianceDecision]


    # Human-in-the-loop
    human_feedback: Optional[str]
    iteration_count: int

     # Worker Errors
    errors: List[str]

