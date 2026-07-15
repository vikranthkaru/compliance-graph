from xml.parsers.expat import errors

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
    # SALESFORCE_POLICY_RETRIEVAL_PROMPT,
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
def validate_shipment_context(state: ComplianceState) -> dict:
    shipment_context = state.get("shipment_context") or {}
    errors: list[str] = []

    shipment = shipment_context.get("shipment")
    product = shipment_context.get("product")
    routes = shipment_context.get("route")
    documents = shipment_context.get("documents")

    if not isinstance(shipment, dict) or not shipment:
        errors.append("Shipment details are missing")

    if not isinstance(product, dict) or not product:
        errors.append("Product details are missing")

    if not isinstance(routes, list) or not routes:
        errors.append("Shipment route is missing")

    if not isinstance(documents, list):
        errors.append("Shipment documents are missing")

    if isinstance(shipment, dict) and shipment:
        if not shipment.get("shipmentId"):
            errors.append("Shipment ID is missing")

        if shipment.get("shipmentStatus") != "Pending Compliance":
            errors.append("Shipment status is not Pending Compliance")

        if shipment.get("complianceStatus") != "Pending":
            errors.append("Compliance status is not Pending")

    if isinstance(routes, list) and routes:
        route_types = {
            route.get("routeType")
            for route in routes
            if isinstance(route, dict)
        }

        if "Origin" not in route_types:
            errors.append("Origin country route is missing")

        if "Destination" not in route_types:
            errors.append("Destination country route is missing")

        for index, route in enumerate(routes, start=1):
            if not isinstance(route, dict):
                errors.append(f"Route {index} has an invalid structure")
                continue

            if not route.get("routeId"):
                errors.append(f"Route {index} ID is missing")

            if not route.get("country"):
                errors.append(f"Route {index} country is missing")

            if not route.get("routeType"):
                errors.append(f"Route {index} type is missing")

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
    search_plan = response.model_dump(mode="json")
    print(f"Regulation Search Plan: {search_plan}")

    return {
        "regulation_search_plan": search_plan
    }

#node-2
def index_regulation_content(state:ComplianceState)-> dict:
    """
    Node 3:
    Reads regulation_search_plan from state, searches/crawls official regulation content,
    chunks/enriches it, and stores it in Pinecone.

    This node performs a side-effect only.
    It does not update LangGraph state.
    """
    
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
        why_this_applies = req.get("why_this_applies", "")

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
#removing agent from salesforce node as Your Data Cloud vector index already performs semantic retrieval, so the node only needs to construct a focused search string and call the tool function directly.
from tools.rag_tools import ( fetch_company_policy_from_data_cloud, get_pinecone_rag_tools, search_government_regulations )

def fetch_company_policy_context_node(
    state: RouteComplianceWorkerState,
) -> dict:
    shipment_context = state["shipment_context"]
    requirement = state["regulation_requirement"]

    product = shipment_context["product"]
    shipment = shipment_context["shipment"]

    search_text = " ".join(
        [
            requirement["country"],
            requirement["route_type"],
            requirement["regulation_need"],
            product["productName"],
            product["drugCategory"],
            "cold chain" if product["requiresColdChain"] else "",
            shipment["transportMode"],
            *requirement.get("regulation_topics", []),
        ]
    ).strip()

    try:
        company_policy_context = (
            fetch_company_policy_from_data_cloud(
                    search_text=search_text,
                    limit=10,
            )
        )
        print(f"Salesforce company-policy retrieval successful for {requirement['country']}: {company_policy_context} results found.")
        return {
            "company_policy_context": company_policy_context,
            "internal_policy_fetched": True,
        }

    except Exception as exc:
        return {
            "company_policy_context": [],
            "internal_policy_fetched": False,
            "errors": state.get("errors", [])
            + [
                "Salesforce company-policy retrieval failed for "
                f"{requirement['country']}: {exc}"
            ],
        }


def fetch_external_policy_context_node(
    state: RouteComplianceWorkerState,
) -> dict:
    shipment_context = state["shipment_context"]
    req = state["regulation_requirement"]

    shipment_id = state["shipment_id"]
    country = req["country"]
    route_type = req["route_type"]

    query = req["search_query"]

    try:
        government_regulation_context = search_government_regulations(
            query=query,
            country=country,
            route_type=route_type,
            shipment_id=shipment_id,
            similarity_top_k=5,
        )

        return {
            "government_regulation_context": government_regulation_context,
            "external_policy_fetched": bool(
                government_regulation_context
            ),
        }

    except Exception as exc:
        return {
            "government_regulation_context": [],
            "external_policy_fetched": False,
            "errors": state.get("errors", [])
            + [
                "Government regulation retrieval failed for "
                f"{country} {route_type}: {exc}"
            ],
        }
# Subgraph starts
# → Insert_New_Iteration
# → iteration 1 created as In Progress

# Analyzer requires human review
# → Update_human_intervention
# → iteration 1 updated to Review Required

# Human responds
# → Salesforce changes iteration 1 to Retriggered
# → graph resumes

# Analyzer requires another review
# → Insert_New_Iteration
# → iteration 1 changed to Failed
# → iteration 2 created as In Progress

# Human intervention node
# → Update_human_intervention
# → iteration 2 changed to Review Required
from services.salesforce_service import save_route_check
from agents.compliance_agent.helpers import get_route_check_status,stringify_list

def analyzer_node(state:RouteComplianceWorkerState) -> Command[Literal["human_intervention_node"]]:
    """Processes worker state and appends its data to the orchestrator lists."""
    iteration_count = state.get("iteration_count", 0) + 1


    req = state["regulation_requirement"]
    shipment_context = state["shipment_context"]

    country = req["country"]
    route_type = req["route_type"]
    route_id = state["route_id"]

   # Insert_New_Iteration --> call salesforce class with iteration count this will be like 1st iteration only insert, 2nd interatoon (1st iteratioon failed, 2nd iteration new), 3rd iteration (2nd iteration failed, 3rd iteration new)
    if iteration_count > 3:
        # Do not create iteration 4. and update iteration 3 to blocked
        max_iteration_decision = {
            "shipmentRouteId": route_id,
            "country": country,
            "routeType": route_type,
            "iterationNumber" : 3,
            "operation" : "Update_Current_Iteration",
            "complianceStatus": "Blocked",
            "riskLevel": "HIGH",
            "confidenceScore": 0.3,
            "regulationSummary": f"Maximum human-review iterations reached. Unable to finalize compliance for {country} after three analysis iterations.",
            "recommended_action": "Escalate the route to a senior compliance officer."
        }
        save_route_check({"identifier": "ROUTE_COMPLIANCE", "routeCheck": max_iteration_decision})
        #update 3rd iteration to compliance status maximum iteration failure
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

    
    # Create the current iteration before performing analysis. and old iteratioon to failed 
    insert_response = save_route_check(
        {
            "identifier": "ROUTE_COMPLIANCE",
            "routeCheck": {
                "operation": "Insert_New_Iteration",
                "shipmentRouteId": route_id,
                "country": country,
                "routeType": route_type,
                "iterationNumber": iteration_count,
                "complianceStatus": "In Progress",
            },
        }
    )
    if not insert_response.get("success"):
        return Command(
            update={
                "iteration_count": iteration_count,
                "errors": state.get("errors", [])
                + [
                    f"Unable to create route-check iteration "
                    f"{iteration_count} for {country}: "
                    f"{insert_response.get('message')}"
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

    #analysis
    llm = get_structured_chat_model(RouteComplianceDecision)

    result = llm.invoke(
        ROUTE_ANALYZER_PROMPT.format(
            payload=payload
        )
    )

    decision = result.model_dump(mode="json")

    worker_update = {
        "iteration_count": iteration_count,
        "route_decision": decision,
    }

    if decision.get("human_intervention_required"):
        return Command(
            update=worker_update,
            goto="human_intervention_node",
        )
   

    #If analysis shows no human review required: complete the current iteration.
    final_status = get_route_check_status(decision)
    update_response = save_route_check(
        {
            "identifier": "ROUTE_COMPLIANCE",
            "routeCheck": {
                "operation": "Update_Current_Iteration",
                "shipmentRouteId": route_id,
                "country": country,
                "routeType": route_type,
                "iterationNumber": iteration_count,
                "complianceStatus": final_status,
                "riskLevel": decision["risk_level"],
                "confidenceScore": decision["confidence_score"],
                "requiredDocuments": stringify_list(
                    decision.get("required_documents", [])
                ),
                "missingDocuments": stringify_list(
                    decision.get("missing_documents", [])
                ),
                "regulationSummary": decision["summary"],
                "companyPolicyResult": stringify_list(
                    decision.get("policy_conflicts", [])
                ),
                "evidenceReference": stringify_list(
                    decision.get("evidence_sources", [])
                ),
                "recommendedAction": decision[
                    "recommended_action"
                ],
            },
        }
    )

    if not update_response.get("success"):
        worker_update["errors"] = state.get("errors", []) + [
            f"Unable to complete route-check iteration "
            f"{iteration_count} for {country}: "
            f"{update_response.get('message')}"
        ]


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
            "shipment_id": state["shipment_id"],
            "shipment_route_id": state["route_id"],
            "thread_id": state["shipment_id"],
            "iteration_number": state["iteration_count"],
            "country": req["country"],
            "route_type": req["route_type"],
            "current_decision": decision,
            "question": (
                "Please provide clarification, approval, missing "
                "document details, or exception approval."
            ),
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


