from agents.compliance_agent.state import ComplianceState,RouteComplianceWorkerState
from langgraph.types import Command,interrupt
from langgraph.constants import END
from typing import Literal

from llm.factory import get_structured_chat_model, get_react_agent
from agents.compliance_agent.schemas import (
    RegulationSearchPlan,
    RouteComplianceDecision,
    ShipmentComplianceDecision
)

from agents.compliance_agent.prompts import (
    IDENTIFY_REGULATION_REQUIREMENTS_PROMPT,
    SALESFORCE_POLICY_RETRIEVAL_PROMPT,
    PINECONE_REGULATION_RETRIEVAL_PROMPT,
    ROUTE_ANALYZER_PROMPT,
    FINAL_COMPLIANCE_SUMMARY_PROMPT
)

from agents.compliance_agent.helpers import (
    search_regulatory_sources,
    extract_url_content_and_ingest,
)

from services.vector_service import fetch_data_from_pinecone

#node-1
def validate_shipment_context(state: ComplianceState) -> ComplianceState:
    next_destination = state.get("next_action")
    shipment_context = state.get("shipment_context", {}) 
    errors = []

    shipment = shipment_context.get("shipment")
    product = shipment_context.get("product")
    route = shipment_context.get("route")
    documents = shipment_context.get("documents")

    if not shipment:
        errors.append("Shipment details are missing")
    if not product:
        errors.append("Product details are missing")

    if route is None or not isinstance(route, list) or len(route) == 0:
        errors.append("Shipment route is missing")

    if documents is None or not isinstance(documents, list):
        errors.append("Shipment documents are missing")

    if shipment:
        if not shipment.get("shipmentId"):
            errors.append("Shipment ID is missing")

        if shipment.get("shipmentStatus") != "Pending Compliance":
            errors.append("Shipment status is not Pending Compliance")

        if shipment.get("complianceStatus") != "Pending":
            errors.append("Compliance status is not Pending")

    if route and isinstance(route, list):
        route_types = {stop.get("routeType") for stop in route}

        if "Origin" not in route_types:
            errors.append("Origin country route is missing")

        if "Destination" not in route_types:
            errors.append("Destination country route is missing")

    return {
        "errors": errors
    }

#decider or router node
def identify_regulation_requirements(state:ComplianceState) -> ComplianceState:
    llm = get_structured_chat_model(RegulationSearchPlan)

    response = llm.invoke(
        IDENTIFY_REGULATION_REQUIREMENTS_PROMPT.format(
            shipment_context=state["shipment_context"]
        )
    )
    print(f"Regulation Search Plan: {response.model_dump()}")
    return {
         "regulation_search_plan": response.model_dump()
    }

#node-2
def index_regulation_content(state:ComplianceState):
    """
    Node 3:
    Reads regulation_search_plan from state, searches/crawls official regulation content,
    chunks/enriches it, and stores it in Pinecone.

    This node performs a side-effect only.
    It does not update LangGraph state.
    """

    country: str = Field(description="Country for which regulations must be checked")
    route_type: str = Field(description="Origin, Transit or Destination")
    regulation_need: str = Field(description="Type of regulation that needs to be verified")
    authority_types: List[str] = Field(description="Types of official government or regulatory authorities responsible for the applicable regulations, such as Drug Regulatory Authority, Customs Authority, Ministry of Health, Civil Aviation Authority, or Dangerous Goods Authority")
    regulation_topics: List[str] = Field(description="Specific regulatory topics that must be searched, such as Export, Import, Transit, Prescription Medicine, Cold Chain, Controlled Substance, Hazardous Material, GDP, GMP, or Dangerous Goods")
    search_query: str = Field(description="Optimized search query that will be used by the retrieval agent to discover official government regulatory sources")
    why_this_applies: str = Field(description="Reason these regulatory requirements apply based on the shipment, product, transport mode, and route")
    shipment_id = state["shipment_context"]["shipment"]["shipmentId"]
    namespace = f"shipment-{shipment_id}"


    search_plan = state["regulation_search_plan"]
    requirements = search_plan.get("regulation_requirements", [])
    for req in requirements:
        country = req.get("country")
        route_type = req.get("route_type")
        regulation_need = req.get("regulation_need")
        authority_types = req.get("authority_types")
        regulation_topics = req.get("regulation_topics")
        search_query = req.get("search_query")
        why_this_applies = req.get("why_this_applies", [])

        urls = search_regulatory_sources(
            search_query=search_query,
            authority_types=authority_types,
            regulation_topics=regulation_topics,
        )

        extract_url_content_and_ingest(
            urls=urls,
            country=country,
            role=route_type,
            regulation_need=regulation_need,
            authority_types=authority_types,
            regulation_topics=regulation_topics,
            why_this_applies=why_this_applies,
            shipment_id=shipment_id,
            namespace=namespace
        )

    return {}

#test-node
def test_regulation_retrieval(state) -> dict:
    shipment_context = state["shipment_context"]
    product = shipment_context["product"]
    route = shipment_context["route"]

    queries = []

    for stop in route:
        country = stop["country"]
        route_type = stop["routeType"]

        query = (
            f"{country} {route_type} regulations for "
            f"{product['productName']} {product['drugCategory']} "
            f"{product['storageType']} pharmaceutical shipment"
        )

        queries.append(query)

    retrieval_results = {}

    for query in queries:
        nodes = fetch_data_from_pinecone(
            query_text=query,
            similarity_top_k=3,
            raw_nodes_only=True
        )

        retrieval_results[query] = [
            {
                "text": node.text[:500],
                "metadata": node.metadata
            }
            for node in nodes
        ]

    return {
        "retrieval_test_result": retrieval_results
    }


def final_compliance_summary_node(state):
    shipment_context = state["shipment_context"]
    route_results = state.get("route_compliance_results", {})

    llm = get_structured_chat_model(ShipmentComplianceDecision)

    response = llm.invoke(
        FINAL_COMPLIANCE_SUMMARY_PROMPT.format(
            shipment_context=shipment_context,
            route_compliance_results=route_results,
        )
    )

    return {
        "compliance_result": response.model_dump()
    }

#---------------------------Sub Graphs----------#
from tools.rag_tools import ( get_salesforce_rag_tools, get_pinecone_rag_tools )

def fetch_company_policy_context_node(state:RouteComplianceWorkerState) -> dict:
    shipment_context = state["shipment_context"]
    requirement = state["regulation_requirement"]

    payload = {
        "country": requirement["country"],
        "route_role": requirement["route_type"],
        "regulation_need": requirement["regulation_need"],
        "regulation_topics": requirement["regulation_topics"],
        "product_name": shipment_context["product"]["productName"],
        "product_category": shipment_context["product"]["drugCategory"],
        "is_cold_chain": shipment_context["product"]["requiresColdChain"],
        "transport_mode": shipment_context["shipment"]["transportMode"],
    }

    tools = get_salesforce_rag_tools()
    agent = get_react_agent(
            tools=tools,
            system_prompt=SALESFORCE_POLICY_RETRIEVAL_PROMPT,
    )
    response = agent.invoke(
        {
            "messages": [
                (
                    "user",
                    f"Retrieve internal company policies for this shipment route. Payload: {payload}"
                )
            ]
        }
    )

    
    return {
        "company_policy_context": [
            {
                "source_type": "company_policy",
                "raw_content": str(response),
                "metadata": {
                    "country": requirement["country"],
                    "route_role": requirement["route_type"],
                    "regulation_topics": requirement["regulation_topics"],
                },
            }
        ],
        "internal_policy_fetched": True,
    }

def fetch_external_policy_context_node(state: RouteComplianceWorkerState) -> dict:
    shipment_context = state["shipment_context"]
    req = state["regulation_requirement"]

    product = shipment_context["product"]
    shipment = shipment_context["shipment"]

    payload = {
        "country": req["country"],
        "route_role": req["route_type"],
        "regulation_need": req["regulation_need"],
        "regulation_topics": req["regulation_topics"],
        "product_name": product["productName"],
        "product_category": product["drugCategory"],
        "storage_type": product["storageType"],
        "is_cold_chain": product["requiresColdChain"],
        "transport_mode": shipment["transportMode"],
    }

    tools = get_pinecone_rag_tools()

    agent = get_react_agent(
        tools=tools,
        system_prompt=PINECONE_REGULATION_RETRIEVAL_PROMPT
    )

    response = agent.invoke(
        {
            "messages": [
                (
                    "user",
                    f"Retrieve external regulations for this shipment route. Payload: {payload}"
                )
            ]
        }
    )

    
    return {
        "government_regulation_context": [
            {
                "source_type": "government_regulation",
                "raw_content": str(response),
                "metadata": {
                    "country": req["country"],
                    "route_role": req["route_type"],
                    "regulation_topics": req["regulation_topics"],
                    "regulation_need": req["regulation_need"],
                    "search_query": req["search_query"]
                },
            }
        ],
        "external_policy_fetched": True,
    }


def analyzer_node(state:RouteComplianceWorkerState) -> Command[Literal["human_intervention_node"]]:
    """Processes worker state and appends its data to the orchestrator lists."""
    iteration_count = state.get("iteration_count", 0) + 1

    req = state["regulation_requirement"]
    shipment_context = state["shipment_context"]

    country = req["country"]
    route_type = req["route_type"]

    if iteration_count > 3:
        return Command(
            update={
                "iteration_count": iteration_count,
                "route_decision": {
                    "country": country,
                    "route_type": route_type,
                    "compliance_status": "REVIEW_REQUIRED",
                    "confidence_level": "LOW",
                    "confidence_score": 0.3,
                    "human_intervention_required": True,
                    "risk_level": "HIGH",
                    "summary": "Maximum human review iterations reached.",
                    "reason": f"Unable to finalize compliance decision for {country} after 3 review attempts.",
                    "missing_documents": [],
                    "policy_conflicts": [],
                    "regulatory_concerns": [
                        "Manual compliance escalation required"
                    ],
                    "recommended_action": "Escalate to compliance officer for final decision.",
                    "evidence_sources": [],
                },
                "errors": state.get("errors", []) + [
                    f"FAILED_MAX_ITERATIONS for {country}"
                ],
            },
            goto=END,
        )

    payload = {
        "country": country,
        "route_type": route_type,
        "regulation_requirement": req,
        "shipment_context": shipment_context,
        "company_policy_context": state.get("company_policy_context", []),
        "government_regulation_context": state.get("government_regulation_context", []),
        "human_feedback": state.get("human_feedback"),
        "iteration_count": iteration_count,
    }

    llm = get_structured_chat_model(RouteComplianceDecision)

    result = llm.invoke(
        ROUTE_ANALYZER_PROMPT.format(
            payload=payload
        )
    )

    decision = result.model_dump()

    worker_update = {
        "iteration_count": iteration_count,
        "route_decision": decision,
    }

    if decision.get("human_intervention_required"):
        return Command(
            update=worker_update,
            goto="human_intervention_node",
        )


    return Command(
        update=worker_update,
        goto=END,
    )
    

def human_intervention_node(state: RouteComplianceWorkerState) -> Command[Literal["analyzer_node"]]:
    req = state["regulation_requirement"]
    decision = state.get("route_decision", {})

    human_feedback = interrupt(
        {
            "message": "Human compliance review required.",
            "country": req["country"],
            "route_type": req["route_type"],
            "current_decision": decision,
            "question": "Please provide clarification, approval, missing document details, or exception approval."
        }
    )

    feedback_entry = {
        "human_input": human_feedback,
    }

    existing_feedback = state.get("human_feedback")

    if existing_feedback:
        updated_feedback = f"{existing_feedback}\n\n{feedback_entry}"
    else:
        updated_feedback = str(feedback_entry)

    return Command(
        update={
            "human_feedback": updated_feedback,
        },
        goto="analyzer_node",
    )


def subgraph_reducer_node(state: RouteComplianceWorkerState):
    """Maps the final validated sub-graph state of each fan to the parent's array structure."""
    req = state["regulation_requirement"]

    country = req["country"]
    route_type = req["route_type"]

    route_key = f"{country}_{route_type}"

    route_decision = state.get("route_decision")

    if hasattr(route_decision, "model_dump"):
        route_decision = route_decision.model_dump()

    final_data = {
        "country": country,
        "route_type": route_type,
        "regulation_requirement": req,
        "route_decision": route_decision,
        "human_feedback": state.get("human_feedback"),
        "iteration_count": state.get("iteration_count", 0),
        "internal_policy_fetched": state.get("internal_policy_fetched", False),
        "external_policy_fetched": state.get("external_policy_fetched", False),
        "errors": state.get("errors", []),
    }

    return {
        "route_compliance_results": {
            route_key: final_data
        }
    }
