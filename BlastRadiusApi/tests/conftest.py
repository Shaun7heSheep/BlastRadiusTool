import json
import os

import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def simple_graph_data():
    """A→B→C chain: api-management → order-function → payments-servicebus."""
    return {
        "applications": [
            {"id": "SHARED", "title": "Shared Infrastructure"},
            {"id": "INT-ORD-01", "title": "Order Management"},
            {"id": "INT-PAY-01", "title": "Payment Processing"},
        ],
        "nodes": [
            {"id": "api-management", "label": "API Management", "azureType": "api-management", "appIds": ["SHARED"], "criticality": "high"},
            {"id": "order-function", "label": "Order Function", "azureType": "function-app", "appIds": ["INT-ORD-01"], "criticality": "high"},
            {"id": "payments-servicebus", "label": "Payments Service Bus", "azureType": "service-bus", "appIds": ["INT-PAY-01"], "criticality": "high"},
        ],
        "edges": [
            {"source": "api-management", "target": "order-function"},
            {"source": "order-function", "target": "payments-servicebus"},
        ],
    }


@pytest.fixture
def diamond_graph_data():
    """Diamond: api-management → order-function/inventory-function → cosmos-db."""
    return {
        "applications": [
            {"id": "SHARED", "title": "Shared Infrastructure"},
            {"id": "INT-ORD-01", "title": "Order Management"},
            {"id": "INT-INV-01", "title": "Inventory Management"},
        ],
        "nodes": [
            {"id": "api-management", "label": "API Management", "azureType": "api-management", "appIds": ["SHARED"], "criticality": "high"},
            {"id": "order-function", "label": "Order Function", "azureType": "function-app", "appIds": ["INT-ORD-01"], "criticality": "high"},
            {"id": "inventory-function", "label": "Inventory Function", "azureType": "function-app", "appIds": ["INT-INV-01"], "criticality": "high"},
            {"id": "cosmos-db", "label": "Cosmos DB", "azureType": "cosmos-db", "appIds": ["SHARED"], "criticality": "high"},
        ],
        "edges": [
            {"source": "api-management", "target": "order-function"},
            {"source": "api-management", "target": "inventory-function"},
            {"source": "order-function", "target": "cosmos-db"},
            {"source": "inventory-function", "target": "cosmos-db"},
        ],
    }


@pytest.fixture
def single_node_graph_data():
    """Single isolated node, no edges."""
    return {
        "applications": [
            {"id": "INT-PAY-01", "title": "Payment Processing"},
        ],
        "nodes": [
            {"id": "payments-servicebus", "label": "Payments Service Bus", "azureType": "service-bus", "appIds": ["INT-PAY-01"], "criticality": "high"},
        ],
        "edges": [],
    }


@pytest.fixture
def sample_alert_payload():
    """Azure Monitor common alert schema targeting payments-servicebus."""
    with open(os.path.join(FIXTURES_DIR, "sample_alert_payload.json")) as f:
        return json.load(f)
