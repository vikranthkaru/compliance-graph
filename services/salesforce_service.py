def fetch_shipment_context(shipment_id: str) -> dict:
    """
    Temporary mock function.
    Later this will call Salesforce API using shipment_id.
    For now, it returns hardcoded shipment context JSON.
    """

    return {
        "shipment": {
            "shipmentId": shipment_id,
            "shipmentNumber": "SHP-000001",
            "shipmentStatus": "Pending Compliance",
            "complianceStatus": "Pending",
            "finalDecision": "Pending",
            "transportMode": "Air",
            "shipmentDate": "2026-07-05",
            "expectedDeliveryDate": "2026-07-09",
            "quantity": 5000,
            "unitOfMeasure": "Vials"
        },
        "product": {
            "productId": "01tXXXXXXXXXXXX",
            "productName": "Insulin Glargine",
            "productCode": "INS-GLA-100",
            "drugCategory": "Insulin",
            "storageType": "Refrigerated (2°C - 8°C)",
            "temperatureMin": 2.0,
            "temperatureMax": 8.0,
            "controlledSubstance": False,
            "hazardousMaterial": False,
            "requiresColdChain": True,
            "hsCode": "30043100",
            "regulatoryClass": "Prescription",
            "shelfLifeDays": 365
        },
        "route": [
            {
                "routeId": "a02XXXXXXXXXXXX",
                "sequence": 1,
                "routeType": "Origin",
                "country": "India",
                "arrivalDate": None,
                "departureDate": "2026-07-05"
            },
            {
                "routeId": "a02XXXXXXXXXXXY",
                "sequence": 2,
                "routeType": "Transit",
                "country": "UAE",
                "arrivalDate": "2026-07-05",
                "departureDate": "2026-07-06"
            },
            {
                "routeId": "a02XXXXXXXXXXXZ",
                "sequence": 3,
                "routeType": "Destination",
                "country": "Germany",
                "arrivalDate": "2026-07-09",
                "departureDate": None
            }
        ],
        "documents": [
            {
                "documentId": "a03XXXXXXXXXXXX",
                "documentType": "Export License",
                "documentStatus": "Uploaded",
                "country": "India",
                "documentNumber": "EXP-IND-2026-001",
                "issueDate": "2026-06-01",
                "expiryDate": "2026-12-31",
                "isMandatory": True,
                "fileUrl": "https://example.com/export-license.pdf",
                "aiValidationStatus": "Not Checked"
            },
            {
                "documentId": "a03XXXXXXXXXXXY",
                "documentType": "Cold Chain Certificate",
                "documentStatus": "Uploaded",
                "country": "All",
                "documentNumber": "CCC-2026-005",
                "issueDate": "2026-06-15",
                "expiryDate": "2026-07-20",
                "isMandatory": True,
                "fileUrl": "https://example.com/cold-chain.pdf",
                "aiValidationStatus": "Not Checked"
            },
            {
                "documentId": "a03XXXXXXXXXXXZ",
                "documentType": "Import Permit",
                "documentStatus": "Missing",
                "country": "Germany",
                "documentNumber": None,
                "issueDate": None,
                "expiryDate": None,
                "isMandatory": True,
                "fileUrl": None,
                "aiValidationStatus": "Not Checked"
            }
        ]
    }




