import pytest


@pytest.fixture
def simple_graph_data():
    return {
        "nodes": [
            {"id": "A", "label": "Service A", "azureType": "Microsoft.Web/sites", "app": "app-a", "criticality": "high"},
            {"id": "B", "label": "Service B", "azureType": "Microsoft.Web/sites", "app": "app-b", "criticality": "medium"},
            {"id": "C", "label": "Service C", "azureType": "Microsoft.Web/sites", "app": "app-c", "criticality": "low"},
        ],
        "edges": [
            {"source": "A", "target": "B"},
            {"source": "B", "target": "C"},
        ],
    }


@pytest.fixture
def diamond_graph_data():
    return {
        "nodes": [
            {"id": "A", "label": "Service A", "azureType": "Microsoft.Web/sites", "app": "app-a", "criticality": "high"},
            {"id": "B", "label": "Service B", "azureType": "Microsoft.Web/sites", "app": "app-b", "criticality": "medium"},
            {"id": "C", "label": "Service C", "azureType": "Microsoft.Web/sites", "app": "app-c", "criticality": "medium"},
            {"id": "D", "label": "Service D", "azureType": "Microsoft.Web/sites", "app": "app-d", "criticality": "low"},
        ],
        "edges": [
            {"source": "A", "target": "B"},
            {"source": "A", "target": "C"},
            {"source": "B", "target": "D"},
            {"source": "C", "target": "D"},
        ],
    }


@pytest.fixture
def single_node_graph_data():
    return {
        "nodes": [
            {"id": "A", "label": "Service A", "azureType": "Microsoft.Web/sites", "app": "app-a", "criticality": "high"},
        ],
        "edges": [],
    }


@pytest.fixture
def sample_alert_payload():
    return {
        "schemaId": "azureMonitorCommonAlertSchema",
        "data": {
            "essentials": {
                "alertId": "/subscriptions/00000000-0000-0000-0000-000000000000/providers/Microsoft.AlertsManagement/alerts/12345678-1234-1234-1234-123456789012",
                "alertRule": "ServiceBus High Error Rate",
                "severity": "Sev1",
                "signalType": "Metric",
                "monitorCondition": "Fired",
                "monitoringService": "Platform",
                "alertTargetIDs": [
                    "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/blast-radius-rg/providers/Microsoft.ServiceBus/namespaces/payments-servicebus"
                ],
                "configurationItems": ["payments-servicebus"],
                "originAlertId": "00000000-0000-0000-0000-000000000000_microsoft.servicebus/namespaces_payments-servicebus",
                "firedDateTime": "2026-06-26T10:00:00.000Z",
                "description": "Service Bus error rate exceeded threshold",
                "essentialsVersion": "1.0",
                "alertContextVersion": "1.0",
            },
            "alertContext": {
                "properties": None,
                "conditionType": "SingleResourceMultipleMetricCriteria",
                "condition": {
                    "windowSize": "PT5M",
                    "allOf": [
                        {
                            "metricName": "ServerErrors",
                            "metricNamespace": "Microsoft.ServiceBus/namespaces",
                            "operator": "GreaterThan",
                            "threshold": "10",
                            "timeAggregation": "Total",
                            "dimensions": [],
                            "metricValue": 25,
                        }
                    ],
                },
            },
        },
    }
