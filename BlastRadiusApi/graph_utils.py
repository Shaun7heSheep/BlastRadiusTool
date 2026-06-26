"""Pure graph logic — no Azure SDK imports."""

import json
from datetime import datetime, timezone

import networkx as nx


def load_graph(blob_content: str) -> dict:
    """Parse services.json string. Returns raw dict with 'nodes' and 'edges'."""
    return json.loads(blob_content)


def build_nx_graph(graph_data: dict) -> nx.DiGraph:
    """Build DiGraph where edge source→target means source depends on target."""
    g = nx.DiGraph()
    for node in graph_data["nodes"]:
        g.add_node(node["id"])
    for edge in graph_data["edges"]:
        g.add_edge(edge["source"], edge["target"])
    return g


def compute_blast_radius(graph_data: dict, failed_node_id: str) -> dict:
    """
    Reverse the DiGraph, BFS from failed_node_id.
    Raises ValueError if failed_node_id not in graph.
    Returns:
    {
      "failedNode": str,
      "affectedNodes": [str, ...],   # node IDs only, excludes failed_node itself
      "affectedEdges": [{"source": str, "target": str}, ...]
    }
    """
    g = build_nx_graph(graph_data)

    if failed_node_id not in g.nodes:
        raise ValueError(f"Node '{failed_node_id}' not found in graph")

    g_rev = g.reverse(copy=True)
    bfs_tree = nx.bfs_tree(g_rev, failed_node_id)
    affected_nodes = [n for n in bfs_tree.nodes if n != failed_node_id]

    subgraph_nodes = set(affected_nodes) | {failed_node_id}
    affected_edges = [
        {"source": u, "target": v}
        for u, v in g.edges
        if u in subgraph_nodes and v in subgraph_nodes
    ]

    return {
        "failedNode": failed_node_id,
        "affectedNodes": affected_nodes,
        "affectedEdges": affected_edges,
    }


def serialise_result(result: dict) -> str:
    """JSON-serialise result dict. Adds 'timestamp' (UTC ISO 8601)."""
    result_copy = dict(result)
    result_copy["timestamp"] = datetime.now(timezone.utc).isoformat()
    return json.dumps(result_copy)
