# Implementation Plan — Azure Service Blast Radius Tool

## Context

Phase 0 foundation is **complete and validated**. All scaffolding is in place. Four Azure Function endpoints are registered as "Hello, name" stubs. `graph_utils.py`, `signalr_utils.py`, and `seed_graph.py` are empty stubs ready for implementation. The Blazor frontend is a "Hello, world!" stub with all NuGet packages installed. Test infrastructure (pytest + xUnit v3) is configured. Graph data (`services.json`) and alert fixture are authored and validated.

This plan sequences the full implementation across 5 agents (`architect`, `backend`, `frontend`, `graph-data`, `tester`) using TDD (RED-GREEN-REFACTOR) and respecting the 9 non-negotiable invariants defined in the architect agent.

---

## Agent Roster

| Agent | Domain | Key files |
|---|---|---|
| **backend** | `BlastRadiusApi/` — endpoints, Blob I/O, SignalR | `function_app.py`, `signalr_utils.py` |
| **graph-data** | Graph model, schema, seeding | `data/services.json`, `seed_graph.py`, `sample_alert_payload.json` |
| **tester** | All test files across both stacks | `tests/*`, `BlastRadiusUI.Tests/*` |
| **frontend** | `BlastRadiusUI/` — Blazor dashboard, JS interop | `Home.razor`, `Models/`, `graph.js`, `Program.cs` |

---

## Phase 0 — Foundation (COMPLETE ✅)

> **Status**: All steps validated and passing. Three post-validation fixes applied in commit `e75e4f6`.

### Step 0.1 — Python test scaffolding ✅
**Agent**: tester
**Files**: `BlastRadiusApi/pyproject.toml`, `BlastRadiusApi/tests/__init__.py`, `BlastRadiusApi/tests/conftest.py`
- `pyproject.toml` with `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `pythonpath = ["."]`
- `tests/__init__.py` (empty package marker)
- `tests/conftest.py` with fixtures: `simple_graph_data`, `diamond_graph_data`, `single_node_graph_data`, `sample_alert_payload`
- **Post-validation fix**: Node IDs changed from placeholders (A/B/C/D) to realistic Azure resource names (api-management, order-function, payments-servicebus, cosmos-db, inventory-function)
- **Post-validation fix**: `sample_alert_payload` now reads from `tests/fixtures/sample_alert_payload.json` instead of inline duplication
- **Post-validation fix**: `azureType` values in fixtures use kebab-case icon keys (function-app, service-bus) instead of ARM strings
- **Verified**: `python -m pytest --collect-only` — exits cleanly, rootdir and testpaths correct

### Step 0.2 — Python dependencies ✅
**Agent**: backend
**File**: `BlastRadiusApi/requirements.txt`
- Contains: `azure-functions`, `networkx`, `azure-storage-blob`, `azure-identity`, `requests`, `pytest`
- **Note for later**: versions are unpinned — pin before production deployment

### Step 0.3 — Graph data + alert fixture ✅
**Agent**: graph-data
**Files**: `BlastRadiusApi/data/services.json`, `BlastRadiusApi/tests/fixtures/sample_alert_payload.json`
- `services.json` — 10 nodes, 12 edges. All required services present.
- `sample_alert_payload.json` — full Azure Monitor common alert schema targeting `payments-servicebus`
- **Post-validation fix**: `azureType` values remapped from ARM resource-provider strings to kebab-case icon keys (e.g. `Microsoft.Web/sites` → `function-app`)
- **Invariants verified**: 1 (node id == resource name), 2 (edge direction: consumer → dependency)
- **Validated**: No dangling edge refs, no orphan nodes, all IDs unique

### Step 0.4 — Local settings template ✅
**Agent**: backend
**File**: `BlastRadiusApi/local.settings.json.example`
- Contains: `FUNCTIONS_WORKER_RUNTIME`, `AzureWebJobsStorage`, `AzureSignalRConnectionString`, `BlobStorageAccountUrl`, CORS for localhost:5178/7206

### Step 0.5 — C# NuGet packages + cleanup ✅
**Agent**: frontend
**Files**: `BlastRadiusUI/BlastRadiusUI.csproj`, `BlastRadiusUI.Tests/UnitTest1.cs`
- NuGet packages installed: `Microsoft.AspNetCore.SignalR.Client 10.0.9`, `Microsoft.FluentUI.AspNetCore.Components 4.14.2`, `Microsoft.FluentUI.AspNetCore.Components.Icons 4.14.2`
- `UnitTest1.cs` deleted
- Tests project: xUnit v3 (3.2.2), project reference to BlastRadiusUI
- **Verified**: `dotnet build` — both projects succeed, 0 warnings, 0 errors

### Implementation notes carried forward
- `function_app.py`: 4 routes registered but HTTP methods not yet constrained (all accept GET+POST) — fix in Phase 4
- `Program.cs`: `#if DEBUG` localhost:7071 HttpClient pattern not yet present — add in Phase 6

---

## Phase 1 — Pure Graph Engine (TDD, zero Azure dependencies) — NEXT UP

### Step 1.1 — RED: graph_utils unit tests
**Agent**: tester
**File**: `BlastRadiusApi/tests/test_graph_utils.py`
**Depends on**: 0.1 ✅, 0.2 ✅
- Write all tests before implementation:
  - `test_load_graph_valid_json` — returns dict with `nodes`/`edges`
  - `test_load_graph_malformed_json` — raises `json.JSONDecodeError`
  - `test_build_nx_graph_node_count` / `_edge_count` / `_edge_direction`
  - `test_compute_blast_radius_transitive_chain` — fail payments-servicebus → {api-management, order-function}
  - `test_compute_blast_radius_single_hop` — fail order-function → {api-management}
  - `test_compute_blast_radius_leaf_node` — fail api-management → []
  - `test_compute_blast_radius_diamond_no_duplicates` — fail cosmos-db → exactly 3, no dupes
  - `test_compute_blast_radius_unknown_node` → `ValueError`
  - `test_compute_blast_radius_excludes_failed_node`
  - `test_compute_blast_radius_affected_nodes_are_strings`
  - `test_compute_blast_radius_affected_edges`
  - `test_serialise_result_valid_json` / `_has_timestamp`
  - `test_single_node_no_edges`
- **Verify**: `python -m pytest tests/test_graph_utils.py -v` — all RED

### Step 1.2 — GREEN: Implement graph_utils.py
**Agent**: backend
**File**: `BlastRadiusApi/graph_utils.py`
**Depends on**: 1.1
- `load_graph(blob_content: str) -> dict` — `json.loads`
- `build_nx_graph(graph_data: dict) -> nx.DiGraph` — add nodes + edges
- `compute_blast_radius(graph_data: dict, failed_node_id: str) -> dict` — build graph, validate node, `G.reverse()`, BFS via `nx.bfs_tree()`, exclude root, collect affected edges
- `serialise_result(result: dict) -> str` — add UTC ISO 8601 `timestamp`, `json.dumps`
- **Invariants**: 2 (edge direction), 6 (no Azure SDK imports)
- **Verify**: `python -m pytest tests/test_graph_utils.py -v` — all GREEN

---

## Phase 2 — C# Model Types (TDD, parallel with Phase 1)

### Step 2.1 — RED: C# model tests
**Agent**: tester
**Files**: `BlastRadiusUI.Tests/ModelDeserializationTests.cs`, `BlastRadiusUI.Tests/BlastRadiusResultTests.cs`
**Depends on**: 0.5 ✅
- `ModelDeserializationTests` — deserialise snake_case JSON → `BlastRadiusResult` with `JsonSerializerDefaults.Web`
- `BlastRadiusResultTests` — construct record directly, assert `AffectedNodes` is `List<string>`
- `GraphDataDeserializationTests` — deserialise `GraphData` with nodes/edges
- **Verify**: `dotnet test` — RED (build error: namespace not found)

### Step 2.2 — GREEN: Create Models/GraphData.cs
**Agent**: frontend
**File**: `BlastRadiusUI/Models/GraphData.cs`
**Depends on**: 2.1
- `record GraphData(List<ServiceNode> Nodes, List<DependencyEdge> Edges)`
- `record ServiceNode(string Id, string Label, string AzureType, string App, string Criticality)`
- `record DependencyEdge(string Source, string Target)`
- `record BlastRadiusResult(string FailedNode, List<string> AffectedNodes, List<DependencyEdge> AffectedEdges, DateTimeOffset Timestamp)`
- `record SignalRNegotiateResponse(string Url, string AccessToken)`
- **Verify**: `dotnet test` — GREEN

---

## Phase 3 — SignalR Utilities (parallel with Phase 2)

### Step 3.1 — RED: signalr_utils tests
**Agent**: tester
**File**: `BlastRadiusApi/tests/test_signalr_utils.py`
**Depends on**: 0.1 ✅, 0.2 ✅
- `test_broadcast_calls_correct_endpoint` — mock `requests.post`
- `test_broadcast_sends_correct_payload` — target `"blastRadius"`, arguments `[result]`
- `test_broadcast_swallows_exceptions` — raise in mock → no exception propagated
- `test_negotiate_returns_url_and_token`
- `test_negotiate_url_format`
- **Verify**: `python -m pytest tests/test_signalr_utils.py -v` — RED

### Step 3.2 — GREEN: Implement signalr_utils.py
**Agent**: backend
**File**: `BlastRadiusApi/signalr_utils.py`
**Depends on**: 3.1
- `broadcast(connection_string, hub_name, result)` — parse conn string, sign JWT, POST to REST API, try/except+log
- `negotiate(connection_string, hub_name, user_id=None)` — generate short-lived JWT, return `{url, accessToken}`
- **Invariant**: 7 (fire-and-forget)
- **Verify**: `python -m pytest tests/test_signalr_utils.py -v` — GREEN

---

## Phase 4 — Azure Function Endpoints (integration tests, mocked I/O)

### Step 4.1 — RED: function_app integration tests
**Agent**: tester
**File**: `BlastRadiusApi/tests/test_function_app.py`
**Depends on**: 1.2, 3.2
- Mock `get_blob_service_client` and `signalr_utils.broadcast`
- Tests:
  - `test_blast_radius_valid_alert` → 200 + correct JSON
  - `test_blast_radius_malformed_json` → 400
  - `test_blast_radius_unknown_node` → 400 with error message
  - `test_blast_radius_signalr_failure_still_200` → 200 despite SignalR error
  - `test_blast_radius_writes_blob` → upload_blob called
  - `test_graph_returns_services_json` → 200
  - `test_blast_result_returns_latest` → 200
  - `test_blast_result_returns_204_when_missing` → 204
  - `test_signalr_negotiate_returns_token` → 200 with url/accessToken
- **Verify**: `python -m pytest tests/test_function_app.py -v` — RED

### Step 4.2 — GREEN: Implement function_app.py
**Agent**: backend
**File**: `BlastRadiusApi/function_app.py`
**Depends on**: 4.1
- Add `get_blob_service_client()` — `DefaultAzureCredential` on Azure, connection string locally
- `blast_radius` — parse alert → extract node ID → load Blob → `graph_utils.compute_blast_radius` → write Blob → `signalr_utils.broadcast` (try/except) → 200
- `graph` — load `services.json` → return JSON
- `blast_result` — load `blast-result.json` → return JSON, or 204 if missing
- `signalr_negotiate` — call `signalr_utils.negotiate` → return JSON
- Error handling: malformed JSON → 400, unknown node → 400, missing Blob → 503, SignalR failure → log+continue
- Add HTTP methods constraints: `blast_radius` POST-only, others GET-only
- **Invariants**: 3, 4, 5, 7
- **Verify**: `python -m pytest -v` — ALL GREEN

---

## Phase 5 — Seed Script + Static Web App Config

### Step 5.1 — Implement seed_graph.py
**Agent**: graph-data
**File**: `BlastRadiusApi/scripts/seed_graph.py`
**Depends on**: 4.2
- Read `data/services.json`, validate (edge refs exist, unique IDs)
- Upload to Blob `graph-data/services.json`
- Auth: `BlobStorageAccountUrl` + `DefaultAzureCredential`, fallback to `AzureWebJobsStorage`
- **Verify**: Manual — run against Azurite

### Step 5.2 — staticwebapp.config.json
**Agent**: frontend
**File**: `staticwebapp.config.json`
**Depends on**: 2.2
- Entra ID auth, route fallback, API proxy

---

## Phase 6 — Blazor Frontend

### Step 6.1 — Program.cs + index.html + _Imports.razor
**Agent**: frontend
**Depends on**: 2.2
- `Program.cs` — `#if DEBUG` HttpClient to `http://localhost:7071`, register Fluent UI services
- `index.html` — add `<script src="https://unpkg.com/3d-force-graph"></script>`, Fluent UI CSS
- `_Imports.razor` — add `@using BlastRadiusUI.Models`, `@using Microsoft.FluentUI.AspNetCore.Components`

### Step 6.2 — graph.js (JS interop module)
**Agent**: frontend
**File**: `BlastRadiusUI/wwwroot/js/graph.js`
**Depends on**: 6.1
- `export function initGraph(elementId, graphData)` — 3d-force-graph, Azure icon sprites, edge styling
- `export function highlightBlastRadius(result)` — amber (failed), red (affected), blue (healthy)
- `export function resetHighlights()` — all blue
- `export function disposeGraph()` — WebGL cleanup

### Step 6.3 — Home.razor
**Agent**: frontend
**File**: `BlastRadiusUI/Pages/Home.razor`
**Depends on**: 6.1, 6.2
- `@implements IAsyncDisposable`
- `OnInitializedAsync` — GET `/api/graph`, GET `/api/blast_result`, SignalR negotiate + connect
- `OnAfterRenderAsync(firstRender)` — import `graph.js`, `initGraph`, apply existing blast result
- `blastRadius` handler — update state, `highlightBlastRadius`, `StateHasChanged`
- Razor markup — Fluent UI header, LIVE badge, alert banner, `<div id="graph-container">`, stats footer
- `DisposeAsync` — dispose hub + JS module
- **Invariant**: 8 (read-only)

### Step 6.4 — Azure Architecture Icons
**Agent**: frontend
**Files**: `BlastRadiusUI/wwwroot/icons/*.svg`
- Download SVGs for: `service-bus`, `function-app`, `sql-database`, `cosmos-db`, `storage-account`, `key-vault`, `api-management`, `app-service`, `application-insights`, `event-hub`

### Step 6.5 — MainLayout + styling
**Agent**: frontend
**Files**: `BlastRadiusUI/Layout/MainLayout.razor`, `BlastRadiusUI/wwwroot/css/app.css`
- `MainLayout.razor` — Fluent UI dark theme wrapper
- `app.css` — dark background `#1a1a2e`, full-viewport graph container, status bar, blast radius animations

---

## Phase 7 — End-to-End Verification

### Step 7.1 — Full test suite
**Agent**: tester
```powershell
cd BlastRadiusApi && python -m pytest -v --tb=short
dotnet test --verbosity normal
```
All GREEN. No skips.

### Step 7.2 — Local smoke test
1. Start Azurite: `azurite --silent`
2. Seed: `cd BlastRadiusApi && python scripts/seed_graph.py`
3. Start Function: `func start`
4. Start Blazor: `dotnet watch --project BlastRadiusUI`
5. Browser → `http://localhost:5178` → 3D graph renders
6. POST sample alert → graph highlights in real time

---

## Dependency Graph

```
Phase 0 (COMPLETE ✅) ───┐
                          ├── Phase 1 (graph_utils TDD)  ──┐
                          ├── Phase 2 (C# models TDD)      ├── Phase 4 (function_app TDD)
                          ├── Phase 3 (signalr_utils TDD) ─┘         │
                          │                                    Phase 5 (seed + SWA config)
                          │                                    Phase 6 (Blazor UI)
                          └──────────────────────────────────── Phase 7 (E2E verify)
```

**Critical path**: ~~Phase 0~~ → Phase 1 → Phase 4 → Phase 6 → Phase 7
**Parallel**: Phase 2 ∥ Phase 1, Phase 3 ∥ Phase 2
**Next parallel batch**: Phase 1 (Step 1.1), Phase 2 (Step 2.1), Phase 3 (Step 3.1) — all dependencies satisfied

---

## Verification Checklist

- [x] Phase 0 foundation scaffolding — all files exist, builds pass
- [x] Graph fixtures use realistic Azure resource names (invariant 1)
- [x] `azureType` uses kebab-case icon keys (UI-compatible)
- [x] `sample_alert_payload` reads from fixture file (no duplication)
- [x] Edge direction correct in all fixtures (invariant 2)
- [x] No credentials in any committed file (invariant 4)
- [ ] `python -m pytest -v` — all Python tests GREEN
- [ ] `dotnet test` — all C# tests GREEN
- [ ] `graph_utils.py` has zero `import azure` lines (invariant 6)
- [ ] `affected_nodes` is `list[str]` / `List<string>` everywhere
- [ ] Failed node excluded from `affected_nodes`
- [ ] SignalR broadcast failure does not fail the HTTP response (invariant 7)
- [ ] Local smoke test: alert → 3D graph highlights in browser
