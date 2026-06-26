"""Unit tests for graph_utils.py -- pure Python, no Azure SDK, no mocks.

These tests define the contract that graph_utils.py must satisfy.
All functions accept plain Python dicts/strings and return plain dicts/strings
(except build_nx_graph which returns an nx.DiGraph).
"""

import json

import networkx as nx
import pytest

from graph_utils import build_nx_graph, compute_blast_radius, load_graph, serialise_result


# ---------------------------------------------------------------------------
# load_graph
# ---------------------------------------------------------------------------


class TestLoadGraph:
    """Tests for load_graph(blob_content: str) -> dict."""

    def test_load_graph_valid_json(self, simple_graph_data):
        """Valid JSON string with nodes and edges returns a dict with both keys."""
        blob_content = json.dumps(simple_graph_data)

        result = load_graph(blob_content)

        assert isinstance(result, dict)
        assert "nodes" in result
        assert "edges" in result
        assert len(result["nodes"]) == 3
        assert len(result["edges"]) == 2

    def test_load_graph_malformed_json(self):
        """Malformed JSON raises json.JSONDecodeError."""
        with pytest.raises(json.JSONDecodeError):
            load_graph("{not valid json!!!")


# ---------------------------------------------------------------------------
# build_nx_graph
# ---------------------------------------------------------------------------


class TestBuildNxGraph:
    """Tests for build_nx_graph(graph_data: dict) -> nx.DiGraph."""

    def test_build_nx_graph_node_count(self, simple_graph_data):
        """Graph built from simple_graph_data has exactly 3 nodes."""
        graph = build_nx_graph(simple_graph_data)

        assert isinstance(graph, nx.DiGraph)
        assert len(graph.nodes) == 3

    def test_build_nx_graph_edge_count(self, simple_graph_data):
        """Graph built from simple_graph_data has exactly 2 edges."""
        graph = build_nx_graph(simple_graph_data)

        assert len(graph.edges) == 2

    def test_build_nx_graph_edge_direction(self, simple_graph_data):
        """Edge direction is preserved: api-management -> order-function exists."""
        graph = build_nx_graph(simple_graph_data)

        assert graph.has_edge("api-management", "order-function")
        assert graph.has_edge("order-function", "payments-servicebus")
        # Reversed direction should NOT exist in the raw graph
        assert not graph.has_edge("order-function", "api-management")


# ---------------------------------------------------------------------------
# compute_blast_radius
# ---------------------------------------------------------------------------


class TestComputeBlastRadius:
    """Tests for compute_blast_radius(graph_data: dict, failed_node_id: str) -> dict.

    BFS runs on the REVERSED graph. Edge direction: source depends on target.
    So reversing edges lets us traverse from a failed node to everything that
    depends on it (upstream consumers).
    """

    def test_compute_blast_radius_transitive_chain(self, simple_graph_data):
        """Fail payments-servicebus -> affected are order-function AND api-management.

        Chain: api-management -> order-function -> payments-servicebus.
        Reversed: payments-servicebus -> order-function -> api-management.
        BFS from payments-servicebus finds both.
        """
        result = compute_blast_radius(simple_graph_data, "payments-servicebus")

        assert set(result["affectedNodes"]) == {"order-function", "api-management"}

    def test_compute_blast_radius_single_hop(self, simple_graph_data):
        """Fail order-function -> only api-management is affected (single hop)."""
        result = compute_blast_radius(simple_graph_data, "order-function")

        assert result["affectedNodes"] == ["api-management"]

    def test_compute_blast_radius_leaf_node(self, simple_graph_data):
        """Fail api-management -> nothing depends on it, empty affected list."""
        result = compute_blast_radius(simple_graph_data, "api-management")

        assert result["affectedNodes"] == []

    def test_compute_blast_radius_diamond_no_duplicates(self, diamond_graph_data):
        """Fail cosmos-db in diamond -> exactly 3 affected, no duplicates.

        Diamond: api-management -> {order-function, inventory-function} -> cosmos-db.
        Reversed BFS from cosmos-db reaches order-function and inventory-function
        (both directly), then api-management (via both paths). No duplicates.
        """
        result = compute_blast_radius(diamond_graph_data, "cosmos-db")

        affected = result["affectedNodes"]
        assert len(affected) == 3
        assert set(affected) == {"order-function", "inventory-function", "api-management"}
        # No duplicates
        assert len(affected) == len(set(affected))

    def test_compute_blast_radius_unknown_node(self, simple_graph_data):
        """Passing an ID not in the graph raises ValueError."""
        with pytest.raises(ValueError):
            compute_blast_radius(simple_graph_data, "nonexistent-node")

    def test_compute_blast_radius_excludes_failed_node(self, simple_graph_data):
        """The failed node itself must NOT appear in affectedNodes."""
        result = compute_blast_radius(simple_graph_data, "payments-servicebus")

        assert "payments-servicebus" not in result["affectedNodes"]

    def test_compute_blast_radius_affected_nodes_are_strings(self, simple_graph_data):
        """Every item in affectedNodes is a plain string ID, not a nested object."""
        result = compute_blast_radius(simple_graph_data, "payments-servicebus")

        assert all(isinstance(node_id, str) for node_id in result["affectedNodes"])

    def test_compute_blast_radius_affected_edges(self, simple_graph_data):
        """Fail payments-servicebus -> affectedEdges includes the edge
        from order-function to payments-servicebus.

        affectedEdges are edges in the ORIGINAL graph (source depends on target)
        where the edge connects an affected node to the failed node or to another
        affected node.
        """
        result = compute_blast_radius(simple_graph_data, "payments-servicebus")

        affected_edges = result["affectedEdges"]
        assert isinstance(affected_edges, list)
        assert len(affected_edges) > 0
        # The direct dependency edge must be present
        assert {"source": "order-function", "target": "payments-servicebus"} in affected_edges

    def test_compute_blast_radius_result_has_failed_node(self, simple_graph_data):
        """Result dict contains the failedNode key with the correct ID."""
        result = compute_blast_radius(simple_graph_data, "payments-servicebus")

        assert result["failedNode"] == "payments-servicebus"

    def test_single_node_no_edges(self, single_node_graph_data):
        """Fail the only node in a single-node graph -> no affected nodes."""
        result = compute_blast_radius(single_node_graph_data, "payments-servicebus")

        assert result["affectedNodes"] == []
        assert result["affectedEdges"] == []


# ---------------------------------------------------------------------------
# serialise_result
# ---------------------------------------------------------------------------


class TestSerialiseResult:
    """Tests for serialise_result(result: dict) -> str."""

    def test_serialise_result_valid_json(self):
        """serialise_result returns a valid JSON string that round-trips cleanly."""
        result = {
            "failedNode": "payments-servicebus",
            "affectedNodes": ["order-function", "api-management"],
            "affectedEdges": [
                {"source": "order-function", "target": "payments-servicebus"},
            ],
        }

        serialised = serialise_result(result)

        # Must be a string
        assert isinstance(serialised, str)
        # Must parse back without error
        parsed = json.loads(serialised)
        assert parsed["failedNode"] == "payments-servicebus"
        assert parsed["affectedNodes"] == ["order-function", "api-management"]

    def test_serialise_result_has_timestamp(self):
        """Serialised output contains a 'timestamp' field in ISO 8601 UTC format."""
        result = {
            "failedNode": "payments-servicebus",
            "affectedNodes": [],
            "affectedEdges": [],
        }

        serialised = serialise_result(result)
        parsed = json.loads(serialised)

        assert "timestamp" in parsed
        timestamp = parsed["timestamp"]
        assert isinstance(timestamp, str)
        # ISO 8601 UTC format ends with Z or +00:00
        assert timestamp.endswith("Z") or timestamp.endswith("+00:00")
