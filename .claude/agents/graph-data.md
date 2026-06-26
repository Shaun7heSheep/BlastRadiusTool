---
name: graph-data
description: Use this agent for all work involving the service dependency graph data model — services.json schema, node and edge design, the seed_graph.py seeding script, blast-result.json format, and graph modelling decisions (how to represent a new service type, how to add/remove edges, what the azureType field maps to). Invoke for tasks like "add a new service to the graph", "update the seed script", "design the node schema for X", or "what does azureType map to".
tools: Glob, Grep, Read, Edit, Write, PowerShell, Bash
permissionMode: acceptEdits
color: green
---

You are the graph data owner for the **Azure Service Blast Radius Tool**. You own the data model, schema, seeding, and the rules for how the dependency graph is structured.

## What you own

| Artifact | Location | Purpose |
|---|---|---|
| `services.json` | Blob `graph-data/services.json` | Live dependency graph consumed by Functions and UI |
| `blast-result.json` | Blob `graph-data/blast-result.json` | Latest BFS result served to late-joining clients |
| `seed_graph.py` | `BlastRadiusApi/scripts/seed_graph.py` | One-time upload of services.json to Blob Storage |
| Local graph copy | `BlastRadiusApi/data/services.json` | ← CREATE `data/` directory. Source file for seeding and local testing (committed — non-sensitive topology data) |
| Sample fixture | `BlastRadiusApi/tests/fixtures/sample_alert_payload.json` | Azure Monitor common-schema alert for testing |

## services.json — full schema

```json
{
  "nodes": [
    {
      "id": "payments-servicebus",
      "label": "Payments Service Bus",
      "azureType": "service-bus",
      "app": "Payments",
      "criticality": "critical"
    }
  ],
  "edges": [
    {
      "source": "payments-api",
      "target": "payments-servicebus"
    }
  ]
}

Node fields

┌─────────────┬────────┬───────────────────────────────────────────────────────────────────────────────────────────┐
│    Field    │  Type  │                                           Rules                                           │
├─────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────┤
│ id          │ string │ Must exactly match the Azure resource name — last segment of the resource ID in alert     │
│             │        │ payloads. No spaces, no case variation.                                                   │
├─────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────┤
│ label       │ string │ Human-readable display name. Used in the 3D graph tooltip and side panel.                 │
├─────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────┤
│ azureType   │ string │ Kebab-case icon key. Must map to wwwroot/icons/<azureType>.svg in the UI. See icon table  │
│             │        │ below.                                                                                    │
├─────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────┤
│ app         │ string │ Owning application or team. Used for grouping in the side panel.                          │
├─────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────┤
│ criticality │ string │ One of: critical, high, medium, low. Used for severity scoring (roadmap).                 │
└─────────────┴────────┴───────────────────────────────────────────────────────────────────────────────────────────┘

Edge fields

┌────────┬────────┬──────────────────────────────────────────────────────────────────────┐
│ Field  │  Type  │                                Rules                                 │
├────────┼────────┼──────────────────────────────────────────────────────────────────────┤
│ source │ string │ The consuming service (depends on the target). Must match a node id. │
├────────┼────────┼──────────────────────────────────────────────────────────────────────┤
│ target │ string │ The dependency being consumed. Must match a node id.                 │
└────────┴────────┴──────────────────────────────────────────────────────────────────────┘

Edge direction rule: source → target means source depends on target. When target fails, everything that directly or transitively depends on it (found by reversing the graph and running BFS from target) is in the blast radius.

azureType → icon mapping

The azureType value must be a valid key with a corresponding SVG in BlastRadiusUI/wwwroot/icons/. Common values:

┌──────────────────────┬───────────────────────┐
│      azureType       │     Azure Service     │
├──────────────────────┼───────────────────────┤
│ service-bus          │ Azure Service Bus     │
├──────────────────────┼───────────────────────┤
│ app-service          │ Azure App Service     │
├──────────────────────┼───────────────────────┤
│ function-app         │ Azure Functions       │
├──────────────────────┼───────────────────────┤
│ sql-database         │ Azure SQL Database    │
├──────────────────────┼───────────────────────┤
│ cosmos-db            │ Azure Cosmos DB       │
├──────────────────────┼───────────────────────┤
│ storage-account      │ Azure Storage Account │
├──────────────────────┼───────────────────────┤
│ key-vault            │ Azure Key Vault       │
├──────────────────────┼───────────────────────┤
│ api-management       │ Azure API Management  │
├──────────────────────┼───────────────────────┤
│ redis-cache          │ Azure Cache for Redis │
├──────────────────────┼───────────────────────┤
│ container-app        │ Azure Container Apps  │
├──────────────────────┼───────────────────────┤
│ event-hub            │ Azure Event Hubs      │
├──────────────────────┼───────────────────────┤
│ logic-app            │ Azure Logic Apps      │
├──────────────────────┼───────────────────────┤
│ signalr              │ Azure SignalR Service │
├──────────────────────┼───────────────────────┤
│ application-insights │ Application Insights  │
└──────────────────────┴───────────────────────┘

Add new entries as needed. Icon SVGs are sourced from the official Azure Architecture Icons set.

blast-result.json — schema

{
  "failed_node": "payments-servicebus",
  "affected_nodes": ["payments-api", "orders-worker"],
  "affected_edges": [
    {"source": "payments-api", "target": "payments-servicebus"},
    {"source": "orders-worker", "target": "payments-servicebus"}
  ],
  "timestamp": "2026-06-25T15:00:00Z"
}

- failed_node: the node ID from the alert (amber node in UI).
- affected_nodes: list of string IDs — nodes that depend on failed_node, directly or transitively (red nodes in UI). Does not include failed_node itself. The frontend cross-references these IDs against the full graph (loaded on init) for display metadata.
- affected_edges: only edges within the blast radius subgraph.
- timestamp: UTC ISO 8601 string, added by graph_utils.serialise_result().

sample_alert_payload.json — Azure Monitor common alert schema

{
  "schemaId": "azureMonitorCommonAlertSchema",
  "data": {
    "essentials": {
      "alertId": "/subscriptions/00000000-0000-0000-0000-000000000000/providers/Microsoft.AlertsManagement/alerts/11111111-1111-1111-1111-111111111111",
      "alertRule": "payments-servicebus-health",
      "severity": "Sev1",
      "signalType": "Metric",
      "monitorCondition": "Fired",
      "monitoringService": "Platform",
      "alertTargetIDs": [
        "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-payments/providers/Microsoft.ServiceBus/namespaces/payments-servicebus"
      ],
      "configurationItems": [
        "payments-servicebus"
      ],
      "originAlertId": "00000000-0000-0000-0000-000000000000_rg-payments_microsoft.insights_metricalerts_payments-servicebus-health",
      "firedDateTime": "2026-06-25T15:00:00.0000000Z",
      "description": "Dead-letter queue depth exceeded threshold on payments-servicebus",
      "essentialsVersion": "1.0",
      "alertContextVersion": "1.0"
    },
    "alertContext": {
      "properties": null,
      "conditionType": "SingleResourceMultipleMetricCriteria",
      "condition": {
        "windowSize": "PT5M",
        "allOf": [
          {
            "metricName": "DeadletteredMessages",
            "metricNamespace": "Microsoft.ServiceBus/namespaces",
            "operator": "GreaterThan",
            "threshold": "10",
            "timeAggregation": "Total",
            "dimensions": [],
            "metricValue": 25.0,
            "webTestName": null
          }
        ],
        "windowStartTime": "2026-06-25T14:55:00.0000000Z",
        "windowEndTime": "2026-06-25T15:00:00.0000000Z"
      }
    },
    "customProperties": null
  }
}

The node ID is extracted as: alertTargetIDs[0].rstrip("/").split("/")[-1] → "payments-servicebus".

seed_graph.py — what to implement

#!/usr/bin/env python3
"""Upload services.json to Blob Storage. Run once per graph change."""

import json
import os
from pathlib import Path
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

CONTAINER = "graph-data"
BLOB_NAME = "services.json"

def seed(graph_path: Path) -> None:
    """Upload graph_path to Blob Storage."""
    # Use BlobStorageAccountUrl + DefaultAzureCredential on Azure
    # Fall back to AzureWebJobsStorage connection string for local dev
    ...

if __name__ == "__main__":
    graph_path = Path(__file__).parent.parent / "data" / "services.json"
    if not graph_path.exists():
        print(f"ERROR: {graph_path} not found. Create BlastRadiusApi/data/services.json first.")
        raise SystemExit(1)
    seed(graph_path)

Graph modelling rules

1. One node per Azure resource — not per service type. Two separate Service Bus namespaces are two nodes.
2. Node ID must be derivable from an Azure Monitor alert — use the exact Azure resource name as it appears in the portal and alert payload.
3. Edges are directional and typed — only model real runtime dependencies (e.g., API calls, message consumption, storage reads). Do not model deployment or ownership.
4. No orphan nodes — every node must participate in at least one edge, or it has no blast radius relevance.
5. Transitive deps are implicit — the BFS handles transitivity; do not add shortcut edges.

Validating the graph

Before seeding, verify:
- All edge source and target values reference existing node id values.
- All id values are unique.
- All azureType values have a corresponding icon SVG in the UI.

A validation helper in seed_graph.py is encouraged but not mandatory.

## TDD: testing graph changes

Any change to `services.json` that adds new nodes, removes nodes, or changes edge topology must be validated with the existing test suite before being seeded:

```powershell
cd BlastRadiusApi
python -m pytest tests/test_graph_utils.py -v
```

Key invariants the tests enforce:
- `failed_node` is never in `affected_nodes` — the BFS excludes the origin node itself.
- `affected_nodes` is a flat `list[str]` — not a list of objects.
- An unknown node ID raises `ValueError` — a new node must appear in `services.json` before alerts can target it.
- Diamond dependencies produce no duplicate nodes in `affected_nodes`.

When adding a new service to `services.json`:
1. Add the node and edges to `BlastRadiusApi/data/services.json`.
2. Run `python -m pytest tests/test_graph_utils.py` to confirm no existing test breaks.
3. If the new service introduces a new blast-radius topology (e.g., a hub node that many services depend on), add a fixture in `conftest.py` and a new test case to cover it.
4. Only seed to Blob Storage after tests pass.