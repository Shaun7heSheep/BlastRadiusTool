/**
 * Force-graph interop module for the Blast Radius Tool.
 *
 * Supports both 2D (ForceGraph) and 3D (ForceGraph3D) rendering modes.
 * Both are UMD globals set by script tags in index.html.
 * Three.js is loaded via import map (ES module) for custom 3D node sprites.
 *
 * Loaded as an ES module via Blazor IJSObjectReference:
 *   _jsModule = await JS.InvokeAsync<IJSObjectReference>("import", "./js/graph.js");
 */

import * as THREE from "three";

// ---------------------------------------------------------------------------
// Module-scoped state
// ---------------------------------------------------------------------------
let _graph = null;
let _resizeObserver = null;
let _mode = "3d";
let _currentData = null;
let _currentResult = null;
let _appFilter = null;
let _container = null;
let _iconCache = {};

// ---------------------------------------------------------------------------
// Colour palette
// ---------------------------------------------------------------------------

const TYPE_COLORS = {
    "service-bus":          "#F472B6",
    "function-app":         "#60A5FA",
    "logic-apps":           "#9333EA",
    "container-app":        "#10B981",
    "cosmos-db":            "#3B82F6",
    "sql-database":         "#818CF8",
    "api-management":       "#34D399",
    "application-insights": "#A78BFA",
    "key-vault":            "#FBBF24",
    "storage-account":      "#22D3EE",
};

const DEFAULT_NODE_COLOR  = "#64748B";
const DEFAULT_LINK_COLOR  = "#ffffff";
const DEFAULT_PARTICLE_COLOR = "#60A5FA";
const FAILED_NODE_COLOR   = "#F59E0B";
const AFFECTED_NODE_COLOR = "#EF4444";

// ---------------------------------------------------------------------------
// Internal: unified visual state application
// ---------------------------------------------------------------------------

function _applyVisualState() {
    if (!_graph) return;

    const failedId = _currentResult?.failedNode;
    const affectedIds = _currentResult ? new Set(_currentResult.affectedNodes || []) : new Set();
    const affectedEdgeKeys = new Set();
    if (_currentResult?.affectedEdges) {
        for (const e of _currentResult.affectedEdges) {
            affectedEdgeKeys.add(_edgeKey(e.source, e.target));
        }
    }

    _graph
        .nodeColor(node => {
            if (node.id === failedId) return FAILED_NODE_COLOR;
            if (affectedIds.has(node.id)) return AFFECTED_NODE_COLOR;
            return TYPE_COLORS[node.azureType] || DEFAULT_NODE_COLOR;
        })
        .linkColor(link => {
            const key = _linkKey(link);
            if (affectedEdgeKeys.has(key)) return AFFECTED_NODE_COLOR;

            if (_appFilter) {
                const srcId = typeof link.source === "object" ? link.source.id : link.source;
                const tgtId = typeof link.target === "object" ? link.target.id : link.target;
                const srcInFilter = _appFilter.nodeIds.has(srcId);
                const tgtInFilter = _appFilter.nodeIds.has(tgtId);
                if (!srcInFilter && !tgtInFilter) return "rgba(255,255,255,0.08)";
                if (srcInFilter || tgtInFilter) return "rgba(255,255,255,0.6)";
            }

            return DEFAULT_LINK_COLOR;
        })
        .linkWidth(link => {
            const key = _linkKey(link);
            if (_currentResult) {
                if (affectedEdgeKeys.has(key)) return 3.0;
            }
            if (_appFilter) {
                const srcId = typeof link.source === "object" ? link.source.id : link.source;
                const tgtId = typeof link.target === "object" ? link.target.id : link.target;
                if (!_appFilter.nodeIds.has(srcId) && !_appFilter.nodeIds.has(tgtId)) return 0.3;
            }
            if (_currentResult) return 0.5;
            return 1.75;
        })
        .linkDirectionalParticles(link => {
            const key = _linkKey(link);
            if (_currentResult) {
                return affectedEdgeKeys.has(key) ? 6 : 0;
            }
            if (_appFilter) {
                const srcId = typeof link.source === "object" ? link.source.id : link.source;
                const tgtId = typeof link.target === "object" ? link.target.id : link.target;
                if (!_appFilter.nodeIds.has(srcId) && !_appFilter.nodeIds.has(tgtId)) return 0;
            }
            return 1;
        })
        .linkDirectionalParticleColor(() => DEFAULT_PARTICLE_COLOR);

    if (_mode === "3d") {
        _graph.nodeThreeObject(node => _createSpriteForNode(node));
    }
}

// ---------------------------------------------------------------------------
// Internal: icon preloading
// ---------------------------------------------------------------------------

async function _preloadIcons(nodes) {
    const types = [...new Set(nodes.map(n => n.azureType).filter(Boolean))];
    const promises = types.map(type => new Promise(resolve => {
        if (_iconCache[type]) { resolve(); return; }
        const img = new Image();
        img.onload = () => { _iconCache[type] = img; resolve(); };
        img.onerror = () => { _iconCache[type] = null; resolve(); };
        img.src = `/icons/${type}.svg`;
    }));
    await Promise.all(promises);
}

// ---------------------------------------------------------------------------
// Internal: node rendering helpers
// ---------------------------------------------------------------------------

function _drawHalo(ctx, node) {
    if (!_currentResult) return;

    const failedId = _currentResult.failedNode;
    const affectedIds = new Set(_currentResult.affectedNodes || []);

    if (node.id === failedId) {
        ctx.beginPath();
        ctx.arc(32, 32, 30, 0, 2 * Math.PI);
        ctx.strokeStyle = FAILED_NODE_COLOR;
        ctx.lineWidth = 4;
        ctx.stroke();
    } else if (affectedIds.has(node.id)) {
        ctx.beginPath();
        ctx.arc(32, 32, 30, 0, 2 * Math.PI);
        ctx.strokeStyle = AFFECTED_NODE_COLOR;
        ctx.lineWidth = 4;
        ctx.stroke();
    }
}

function _createSpriteForNode(node) {
    const size = node.criticality === "high" ? 12 : 8;
    const canvas = document.createElement("canvas");
    canvas.width = 64;
    canvas.height = 64;
    const ctx = canvas.getContext("2d");

    const bgColor = TYPE_COLORS[node.azureType] || DEFAULT_NODE_COLOR;
    ctx.beginPath();
    ctx.arc(32, 32, 30, 0, 2 * Math.PI);
    ctx.fillStyle = bgColor;
    ctx.globalAlpha = 0.3;
    ctx.fill();
    ctx.globalAlpha = 1.0;

    const icon = _iconCache[node.azureType];
    if (icon) {
        ctx.drawImage(icon, 8, 8, 48, 48);
    } else {
        ctx.beginPath();
        ctx.arc(32, 32, 20, 0, 2 * Math.PI);
        ctx.fillStyle = bgColor;
        ctx.fill();
    }

    _drawHalo(ctx, node);

    let spriteOpacity = 1.0;
    if (_appFilter && !_appFilter.nodeIds.has(node.id)) {
        const isBlastAffected = _currentResult &&
            (node.id === _currentResult.failedNode ||
             (_currentResult.affectedNodes || []).includes(node.id));
        if (!isBlastAffected) {
            spriteOpacity = 0.25;
        }
    }

    const texture = new THREE.CanvasTexture(canvas);
    const material = new THREE.SpriteMaterial({ map: texture, transparent: true, opacity: spriteOpacity });
    const sprite = new THREE.Sprite(material);
    sprite.scale.set(size, size, 1);

    return sprite;
}

function _drawNodeIcon2D(node, ctx, globalScale) {
    const size = node.criticality === "high" ? 20 : 14;
    const halfSize = size / 2;
    const bgColor = TYPE_COLORS[node.azureType] || DEFAULT_NODE_COLOR;

    let opacity = 1.0;
    if (_appFilter && !_appFilter.nodeIds.has(node.id)) {
        const isBlastAffected = _currentResult &&
            (node.id === _currentResult.failedNode ||
             (_currentResult.affectedNodes || []).includes(node.id));
        if (!isBlastAffected) {
            opacity = 0.25;
        }
    }

    ctx.save();
    ctx.globalAlpha = opacity;

    ctx.beginPath();
    ctx.arc(node.x, node.y, halfSize, 0, 2 * Math.PI);
    ctx.fillStyle = bgColor;
    ctx.globalAlpha = opacity * 0.3;
    ctx.fill();
    ctx.globalAlpha = opacity;

    const icon = _iconCache[node.azureType];
    if (icon) {
        const iconSize = size * 1.2;
        ctx.drawImage(icon, node.x - iconSize / 2, node.y - iconSize / 2, iconSize, iconSize);
    } else {
        ctx.beginPath();
        ctx.arc(node.x, node.y, halfSize * 0.7, 0, 2 * Math.PI);
        ctx.fillStyle = bgColor;
        ctx.fill();
    }

    if (_currentResult) {
        const failedId = _currentResult.failedNode;
        const affectedIds = new Set(_currentResult.affectedNodes || []);

        if (node.id === failedId) {
            ctx.beginPath();
            ctx.arc(node.x, node.y, halfSize + 3, 0, 2 * Math.PI);
            ctx.strokeStyle = FAILED_NODE_COLOR;
            ctx.lineWidth = 3;
            ctx.stroke();
        } else if (affectedIds.has(node.id)) {
            ctx.beginPath();
            ctx.arc(node.x, node.y, halfSize + 3, 0, 2 * Math.PI);
            ctx.strokeStyle = AFFECTED_NODE_COLOR;
            ctx.lineWidth = 3;
            ctx.stroke();
        }
    }

    if (globalScale > 0.8) {
        const label = node.label || node.id;
        const fontSize = Math.max(3, 8 / globalScale);
        ctx.font = `${fontSize}px Segoe UI, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillStyle = "#f0f6ff";
        ctx.globalAlpha = opacity * 0.9;
        ctx.fillText(label, node.x, node.y + halfSize + 3);
    }

    ctx.restore();
}

// ---------------------------------------------------------------------------
// Exported functions (called from Blazor via IJSObjectReference)
// ---------------------------------------------------------------------------

/**
 * Initialise the force-directed graph inside the given container element.
 *
 * @param {string} elementId - DOM id of the container div.
 * @param {object} graphData - { nodes: [...], edges: [...] } from the API.
 * @param {string} [mode="3d"] - "3d" or "2d" rendering mode.
 */
export async function initGraph(elementId, graphData, mode) {
    const container = document.getElementById(elementId);
    if (!container) {
        console.error(`[graph.js] Container element #${elementId} not found.`);
        return;
    }

    _mode = mode || "3d";
    _currentData = graphData;
    _container = container;

    await _preloadIcons(graphData.nodes);

    const data = {
        nodes: graphData.nodes.map(n => ({ ...n })),
        links: graphData.edges.map(e => ({ source: e.source, target: e.target })),
    };

    if (_mode === "2d") {
        _graph = ForceGraph()(container);
    } else {
        _graph = ForceGraph3D()(container);
    }

    _graph
        .graphData(data)
        .nodeId("id")
        .nodeLabel(node => node.label || node.id)
        .nodeVal(node => (node.criticality === "high" ? 8 : 5))
        .linkSource("source")
        .linkTarget("target")
        .linkWidth(1.75)
        .linkDirectionalArrowLength(4)
        .linkDirectionalArrowRelPos(1)
        .linkDirectionalParticles(1)
        .linkDirectionalParticleSpeed(0.005)
        .linkDirectionalParticleWidth(2)
        .backgroundColor("#0B0F19")
        .width(container.clientWidth)
        .height(container.clientHeight);

    // nodeOpacity is 3D-only (not available on the 2D ForceGraph API)
    if (_mode === "3d") {
        _graph.nodeOpacity(0.95);
    }

    if (_mode === "2d") {
        _graph
            .d3Force('charge').strength(-200);
        _graph
            .d3Force('link').distance(80);
        _graph
            .d3AlphaDecay(0.02)
            .nodeCanvasObject((node, ctx, globalScale) => _drawNodeIcon2D(node, ctx, globalScale))
            .nodeCanvasObjectMode(() => "replace");
    } else {
        _graph
            .nodeThreeObject(node => _createSpriteForNode(node))
            .nodeThreeObjectExtend(false);
    }

    _applyVisualState();

    if (_resizeObserver) _resizeObserver.disconnect();
    _resizeObserver = new ResizeObserver(() => {
        if (_graph && container) {
            _graph.width(container.clientWidth).height(container.clientHeight);
        }
    });
    _resizeObserver.observe(container);
}

/**
 * Highlight nodes and edges that are part of a blast radius result.
 */
export function highlightBlastRadius(result) {
    _currentResult = result;
    _applyVisualState();
}

/**
 * Reset all node and link colours back to the healthy-state defaults.
 */
export function resetHighlights() {
    _currentResult = null;
    _applyVisualState();
}

export function highlightApp(appName, nodeIds) {
    _appFilter = { appName, nodeIds: new Set(nodeIds) };
    _applyVisualState();
}

export function clearAppFilter() {
    _appFilter = null;
    _applyVisualState();
}

/**
 * Toggle between 2D and 3D rendering modes.
 */
export async function toggleMode(newMode) {
    if (newMode === _mode || !_currentData || !_container) return;

    disposeGraph();
    await initGraph(_container.id, _currentData, newMode);
}

/**
 * Tear down the graph and release resources.
 */
export function disposeGraph() {
    if (_resizeObserver) {
        _resizeObserver.disconnect();
        _resizeObserver = null;
    }

    if (_graph) {
        if (typeof _graph._destructor === "function") {
            _graph._destructor();
        }
        _graph = null;
    }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function _edgeKey(sourceId, targetId) {
    return sourceId + "->" + targetId;
}

function _linkKey(link) {
    const srcId = typeof link.source === "object" ? link.source.id : link.source;
    const tgtId = typeof link.target === "object" ? link.target.id : link.target;
    return _edgeKey(srcId, tgtId);
}
