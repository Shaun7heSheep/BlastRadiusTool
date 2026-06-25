# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

The **Azure Service Blast Radius Tool** visualises the downstream impact of an Azure service failure in real time. When Azure Monitor fires an alert, a serverless Python function traverses a pre-built dependency graph (BFS on the reversed edge set) and broadcasts the result via SignalR to every connected Blazor browser client simultaneously.

## Repo Structure

```
BlastRadiusApi/          # Python Azure Functions — serverless backend
BlastRadiusUI/           # Blazor WebAssembly (.NET 10 LTS) — frontend
BlastRadiusUI.Tests/     # xUnit v3 tests for the Blazor project
BlastRadiusTool.slnx     # .NET solution file
```

## Development Commands

### API (Python Azure Functions)

```powershell
cd BlastRadiusApi

# Install dependencies
pip install -r requirements.txt

# Run locally (requires Azure Functions Core Tools)
func start

# Seed the dependency graph into Blob Storage
python scripts/seed_graph.py
```

Copy `local.settings.json.example` to `local.settings.json` before running locally. This file holds connection strings and app settings — never commit it.

### UI (Blazor WebAssembly)

```powershell
# Run with hot reload
dotnet watch --project BlastRadiusUI

# Run without hot reload
dotnet run --project BlastRadiusUI
# Serves at http://localhost:5178 / https://localhost:7206
```

### Tests

```powershell
# Run all tests
dotnet test

# Run a single test
dotnet test --filter "FullyQualifiedName~TestName"

# Run with coverage
dotnet test --collect "Code Coverage"
```

## Architecture

### Data flow

1. Azure Monitor alert fires → Action Group webhook → `POST /api/blast_radius`
2. Function loads `services.json` from Blob Storage (`graph-data` container), reverses the edge direction, runs BFS from the failed node
3. Result written to `blast-result.json` in Blob and broadcast via SignalR to all connected clients
4. `GET /api/graph` — serves the full graph on initial UI load
5. `GET /api/blast_result` — serves the latest result to clients joining mid-incident
6. `GET /api/signalr_negotiate` — issues a SignalR token to the Blazor client

### Graph model

- **Node `id`** must exactly match the Azure resource name in alert payloads — this is how the function resolves an alert to a graph node without any manual mapping
- **Edge direction**: `source` **depends on** `target` (consumer → dependency). The graph is reversed before BFS so the algorithm finds everything downstream of the failure
- Graph computation uses **NetworkX** (Python); add it to `requirements.txt` when implementing

### Key modules (stubs to implement)

| File | Purpose |
|---|---|
| `BlastRadiusApi/function_app.py` | Four HTTP trigger endpoints (scaffold stubs) |
| `BlastRadiusApi/graph_utils.py` | Graph load, BFS traversal, result serialisation |
| `BlastRadiusApi/signalr_utils.py` | SignalR broadcast helpers |
| `BlastRadiusApi/scripts/seed_graph.py` | One-time graph seeding to Blob Storage |
| `BlastRadiusUI/Pages/Home.razor` | 3D graph dashboard (scaffold stub) |

### Authentication

- **Blob Storage**: Managed Identity with `Storage Blob Data Contributor` — no connection strings in code
- **Webhook (Action Group → Function)**: Azure Function host key scoped to the endpoint
- **UI**: Microsoft Entra ID via Azure Static Web Apps built-in auth — tenant-restricted
- **SignalR negotiate**: short-lived token issued by the Function, consumed by the Blazor SignalR client

### Blob Storage layout

Container name: `graph-data`

| Blob | Contents |
|---|---|
| `services.json` | Full dependency graph (nodes + edges) |
| `blast-result.json` | Latest blast radius result for late-joining clients |

## Local Settings

`BlastRadiusApi/local.settings.json` (gitignored) must contain at minimum:
- `AzureWebJobsStorage` — storage account connection string or `UseDevelopmentStorage=true`
- `AzureSignalRConnectionString` — SignalR Service connection string
- Blob Storage account details for the `graph-data` container
