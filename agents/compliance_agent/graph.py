from langgraph.graph import StateGraph, START, END
from agents.compliance_agent.state import ComplianceState,RouteComplianceWorkerState
from agents.compliance_agent.nodes import (
        validate_shipment_context,
        identify_regulation_requirements,
        index_regulation_content,
        fetch_company_policy_context_node,
        fetch_external_policy_context_node,
        subgraph_reducer_node,
        analyzer_node,
        human_intervention_node,
        final_compliance_summary_node
)
from agents.compliance_agent.edges import (
    route_validation_edge,
    route_splitter
)

from graphs.checkpointer import checkpointer

def build_compliance_subgraph():
    subgraph = StateGraph(RouteComplianceWorkerState)
    subgraph.add_node("salesforce_node",fetch_company_policy_context_node)
    subgraph.add_node("pinecone_node", fetch_external_policy_context_node)
    subgraph.add_node("analyzer_node", analyzer_node)
    subgraph.add_node("human_intervention_node", human_intervention_node)

    subgraph.add_edge(START, "salesforce_node")
    subgraph.add_edge("salesforce_node", "pinecone_node")
    subgraph.add_edge("pinecone_node", "analyzer_node")
    subgraph.add_edge("human_intervention_node", "analyzer_node")
    subgraph.add_edge("analyzer_node", END)

    return subgraph.compile()

def build_compliance_graph():
        graph = StateGraph(ComplianceState)
        graph.add_node("validate_shipment_context", validate_shipment_context)
        graph.add_node("identify_regulation_requirements", identify_regulation_requirements)
        graph.add_node("final_compliance_summary_node", final_compliance_summary_node)

        compliance_subgraph = build_compliance_subgraph()
        graph.add_node("compliance_parallel_subgraph", compliance_subgraph | subgraph_reducer_node)
        graph.add_edge(START, "validate_shipment_context")
        graph.add_conditional_edges(
            "validate_shipment_context",
            route_validation_edge,
            {
                "continue": "identify_regulation_requirements",
                "end": END,
            },
        )
        graph.add_conditional_edges(
            "identify_regulation_requirements", route_splitter, ["compliance_parallel_subgraph"]
        )
        graph.add_edge("compliance_parallel_subgraph", "final_compliance_summary_node")
        graph.add_edge("final_compliance_summary_node", END)
        return graph.compile(
            checkpointer=checkpointer
        )