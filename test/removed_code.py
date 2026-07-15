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
    print("===== SALESFORCE AGENT RESPONSE =====")
    print(response)
    print(type(response))
    print("====================================")
    messages = response.get("messages", [])
    company_policy_context = []
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue

        try:
            chunks = json.loads(message.content)

            if isinstance(chunks, list):
                company_policy_context.extend(chunks)

        except Exception as e:
            print(f"Unable to parse ToolMessage: {e}")
    return {
        "company_policy_context": company_policy_context,
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
