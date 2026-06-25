        new HttpClient { BaseAddress = new Uri("http://localhost:7071") });
#else
    builder.Services.AddScoped(sp =>
        new HttpClient { BaseAddress = new Uri(builder.HostEnvironment.BaseAddress) });
#endif

SignalR client pattern (Blazor WASM)

// In Home.razor @code block:
private HubConnection? _hub;

protected override async Task OnInitializedAsync()
{
    var negotiate = await Http.GetFromJsonAsync<SignalRNegotiateResponse>("/api/signalr_negotiate");

    _hub = new HubConnectionBuilder()
        .WithUrl(negotiate!.Url, opts => opts.AccessTokenProvider = () => Task.FromResult(negotiate.AccessToken)!)
        .WithAutomaticReconnect()
        .Build();

    _hub.On<BlastRadiusResult>("blastRadius", async result =>
    {
        _blastResult = result;
        await InvokeAsync(StateHasChanged);
        // Update 3d-force-graph node colours via JS interop module
        await _graphModule!.InvokeVoidAsync("highlightBlastRadius", result);
    });

    await _hub.StartAsync();
}

public async ValueTask DisposeAsync()
{
    if (_graphModule is not null) await _graphModule.DisposeAsync();
    if (_hub is not null) await _hub.DisposeAsync();
}

3d-force-graph JS interop pattern

Architecture: 3d-force-graph is loaded as a UMD global via <script> tag in index.html (sets window.ForceGraph3D). The interop module wwwroot/js/graph.js is an ES module that references the global and exports functions for Blazor.

index.html — add before the Blazor script

<!-- 3d-force-graph (includes Three.js) — only non-Microsoft library -->
<script src="https://unpkg.com/3d-force-graph"></script>

<script src="_framework/blazor.webassembly#[.{fingerprint}].js"></script>

wwwroot/js/graph.js — ES module (export functions)

let _graph = null;

export function initGraph(elementId, graphData) {
    const container = document.getElementById(elementId);
    _graph = ForceGraph3D()(container)        // ForceGraph3D is a UMD global
        .graphData({ nodes: graphData.nodes, links: graphData.edges })
        .nodeId("id")
        .nodeLabel("id")
        .nodeAutoColorBy("app")
        .nodeThreeObject(node => /* load /icons/<azureType>.svg as Three.js sprite */)
        .linkDirectionalArrowLength(3.5)
        .linkColor(() => "#888888")
        .backgroundColor("#1a1a2e");
}

export function highlightBlastRadius(result) {
    if (!_graph) return;
    const failedId = result.failed_node;
    const affectedIds = new Set(result.affected_nodes);  // string IDs
    _graph.nodeColor(node => {
        if (node.id === failedId) return '#ff9800';       // amber
        if (affectedIds.has(node.id)) return '#f44336';   // red
        return '#2196f3';                                  // blue
    });
}

export function resetHighlights() { /* reset all to blue */ }
export function onNodeClick(dotNetRef, methodName) { /* invoke .NET callback */ }
export function disposeGraph() { /* cleanup WebGL resources */ }

Blazor — load module via IJSObjectReference

// Home.razor @code block
private IJSObjectReference? _graphModule;

protected override async Task OnAfterRenderAsync(bool firstRender)
{
    if (firstRender)
    {
        _graphModule = await JS.InvokeAsync<IJSObjectReference>("import", "./js/graph.js");
        await _graphModule.InvokeVoidAsync("initGraph", "graph-container", _graphData);
    }
}

Do NOT use JS.InvokeVoidAsync("graph.initGraph", ...) — that pattern calls a global function. ES modules export functions that are only accessible via the IJSObjectReference returned by import.

Azure Architecture Icons

Store SVGs in wwwroot/icons/. File naming convention matches the node azureType field:
- azureType: "service-bus" → icons/service-bus.svg
- azureType: "app-service" → icons/app-service.svg

In the Three.js node renderer, load the icon as a sprite texture using the node's azureType.

Download from: https://learn.microsoft.com/en-us/azure/architecture/icons/

NuGet packages (BlastRadiusUI.csproj)

<!-- Blazor WebAssembly runtime -->
<PackageReference Include="Microsoft.AspNetCore.Components.WebAssembly" Version="10.0.9" />
<PackageReference Include="Microsoft.AspNetCore.Components.WebAssembly.DevServer" Version="10.0.9" PrivateAssets="all" />

<!-- SignalR client — real-time blast radius push -->
<PackageReference Include="Microsoft.AspNetCore.SignalR.Client" Version="10.0.9" />

<!-- Fluent UI Blazor — Azure Portal look and feel -->
<PackageReference Include="Microsoft.FluentUI.AspNetCore.Components" Version="4.14.2" />
<PackageReference Include="Microsoft.FluentUI.AspNetCore.Components.Icons" Version="4.14.2" />

C# model types

Create BlastRadiusUI/Models/GraphData.cs:

namespace BlastRadiusUI.Models;

public record GraphData(List<ServiceNode> Nodes, List<DependencyEdge> Edges);

public record ServiceNode(string Id, string Label, string AzureType, string App, string Criticality);

public record DependencyEdge(string Source, string Target);

public record BlastRadiusResult(
    string FailedNode,
    List<string> AffectedNodes,        // string IDs — match against full graph for metadata
    List<DependencyEdge> AffectedEdges,
    DateTimeOffset Timestamp);

public record SignalRNegotiateResponse(string Url, string AccessToken);

Note: The API returns snake_case JSON. Deserialise with PropertyNameCaseInsensitive = true or configure JsonSerializerDefaults.Web on the HttpClient (which is already the Blazor default).

Blazor conventions

- Use @implements IAsyncDisposable on Home.razor to dispose the HubConnection and IJSObjectReference.
- InvokeAsync(StateHasChanged) when updating state from SignalR callbacks (non-UI thread).
- Prefer @code blocks over code-behind files for page-level logic.
- Use Fluent UI components (<FluentCard>, <FluentBadge>, <FluentSplitter>) for side panels and status chips.
- Never write to the backend from the UI — read-only client.

Before writing code

1. Read the current file you're editing.
2. Grep for existing JS interop calls or component patterns before adding new ones.
3. Check BlastRadiusUI.csproj before adding a NuGet reference.