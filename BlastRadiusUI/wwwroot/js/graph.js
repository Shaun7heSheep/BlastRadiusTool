/**
 * 3d-force-graph interop module for the Blast Radius Tool.
 *
 * Loaded as an ES module via Blazor IJSObjectReference:
 *   _jsModule = await JS.InvokeAsync<IJSObjectReference>("import", "./js/graph.js");
 *
 * ForceGraph3D is a UMD global set by <script src="https://unpkg.com/3d-force-graph">
 * in index.html. Do NOT import it as an ES module.
 */

// ---------------------------------------------------------------------------
// Module-scoped state
// ---------------------------------------------------------------------------
let _graph = null;
let _resizeHandler = null;

// ---------------------------------------------------------------------------
// Colour palette
// ---------------------------------------------------------------------------

/** Map azureType to a distinct colour so healthy nodes are visually grouped. */
const TYPE_COLORS = {
    "service-bus":          "#F472B6",   // Muted Pink
    "function-app":         "#60A5FA",   // Sky Blue
    "cosmos-db":            "#3B82F6",   // Medium Blue
    "sql-database":         "#818CF8",   // Indigo (Changed from Red-Pink to avoid conflict)
    "api-management":       "#34D399",   // Emerald (Muted Portal)
    "application-insights": "#A78BFA",   // Light Purple
    "key-vault":            "#FBBF24",   // Amber-Gold
    "storage-account":      "#22D3EE",   // Cyan
};

const DEFAULT_NODE_COLOR  = "#64748B";  // Slate gray (fallback)
const DEFAULT_LINK_COLOR  = "#ffffff"; // White
const DEFAULT_PARTICLE_COLOR = "#60A5FA";  // Sky blue
const FAILED_NODE_COLOR   = "#F59E0B";  // High-visibility Amber/Orange for the root cause
const AFFECTED_NODE_COLOR = "#EF4444";  // Pure Neon Red for cascading impacts

// ---------------------------------------------------------------------------
// Exported functions (called from Blazor via IJSObjectReference)
// ---------------------------------------------------------------------------

/**
 * Initialise the 3D force-directed graph inside the given container element.
 *
 * @param {string} elementId   - DOM id of the container div.
 * @param {object} graphData   - { nodes: [...], edges: [...] } from the API.
 *   Nodes carry { id, label, azureType, app, criticality }.
 *   Edges carry { source, target } where source depends on target.
 *
 * Blazor serialises C# records to camelCase via System.Text.Json defaults,
 * so property names arrive as camelCase here.
 */
export function initGraph(elementId, graphData) {
    const container = document.getElementById(elementId);
    if (!container) {
        console.error(`[graph.js] Container element #${elementId} not found.`);
        return;
    }

    // 3d-force-graph expects a "links" array, not "edges".
    const data = {
        nodes: graphData.nodes.map(n => ({ ...n })),
        links: graphData.edges.map(e => ({ source: e.source, target: e.target })),
    };

    _graph = ForceGraph3D()(container)
        .graphData(data)
        .nodeId("id")
        .nodeLabel(node => node.label || node.id)
        .nodeColor(node => TYPE_COLORS[node.azureType] || DEFAULT_NODE_COLOR)
        .nodeVal(node => (node.criticality === "high" ? 8 : 5))
        .nodeOpacity(0.95)
        .linkSource("source")
        .linkTarget("target")
        .linkColor(() => DEFAULT_LINK_COLOR)
        .linkWidth(1.75)
        .linkDirectionalArrowLength(4)
        .linkDirectionalArrowRelPos(1)
        .linkDirectionalParticles(1)
        .linkDirectionalParticleSpeed(0.005)
        .linkDirectionalParticleWidth(2)
        .linkDirectionalParticleColor(() => DEFAULT_PARTICLE_COLOR)
        .backgroundColor("#0B0F19")
        .width(container.clientWidth)
        .height(container.clientHeight);

    // Keep graph sized to its container on window resize.
    _resizeHandler = () => {
        if (_graph && container) {
            _graph.width(container.clientWidth).height(container.clientHeight);
        }
    };
    window.addEventListener("resize", _resizeHandler);
}

/**
 * Highlight nodes and edges that are part of a blast radius result.
 *
 * @param {object} result - { failedNode, affectedNodes, affectedEdges, timestamp }
 *   Property names are camelCase (Blazor serialisation of C# records).
 */
export function highlightBlastRadius(result) {
    if (!_graph) return;

    const failedId    = result.failedNode;
    const affectedIds = new Set(result.affectedNodes || []);

    // Build a set of affected edge keys for O(1) lookup.
    const affectedEdgeKeys = new Set();
    if (result.affectedEdges) {
        for (const e of result.affectedEdges) {
            affectedEdgeKeys.add(_edgeKey(e.source, e.target));
        }
    }

    _graph
        .nodeColor(node => {
            if (node.id === failedId)       return FAILED_NODE_COLOR;
            if (affectedIds.has(node.id))   return AFFECTED_NODE_COLOR;
            return TYPE_COLORS[node.azureType] || DEFAULT_NODE_COLOR;
        })
        .linkColor(link => {
            const key = _linkKey(link);
            return affectedEdgeKeys.has(key) ? AFFECTED_NODE_COLOR : DEFAULT_LINK_COLOR;
        })
        .linkWidth(link => {
            const key = _linkKey(link);
            return affectedEdgeKeys.has(key) ? 3.0 : 0.5;
        })
        .linkDirectionalParticles(link => {
            const key = _linkKey(link);
            return affectedEdgeKeys.has(key) ? 6 : 0;
        });
}

/**
 * Reset all node and link colours back to the healthy-state defaults.
 */
export function resetHighlights() {
    if (!_graph) return;

    _graph
        .nodeColor(node => TYPE_COLORS[node.azureType] || DEFAULT_NODE_COLOR)
        .linkColor(() => DEFAULT_LINK_COLOR)
        .linkWidth(1.75)
        .linkDirectionalParticles(1)
        .linkDirectionalParticleColor(() => DEFAULT_PARTICLE_COLOR);
}

/**
 * Tear down the graph and release WebGL/Three.js resources.
 */
export function disposeGraph() {
    if (_resizeHandler) {
        window.removeEventListener("resize", _resizeHandler);
        _resizeHandler = null;
    }

    if (_graph) {
        // ForceGraph3D exposes _destructor for cleanup.
        if (typeof _graph._destructor === "function") {
            _graph._destructor();
        }
        _graph = null;
    }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Build a deterministic string key for an edge given source and target IDs.
 */
function _edgeKey(sourceId, targetId) {
    return sourceId + "->" + targetId;
}

/**
 * Extract the string IDs from a 3d-force-graph link object.
 * After force simulation, link.source/target become node objects rather
 * than plain strings.
 */
function _linkKey(link) {
    const srcId = typeof link.source === "object" ? link.source.id : link.source;
    const tgtId = typeof link.target === "object" ? link.target.id : link.target;
    return _edgeKey(srcId, tgtId);
}
