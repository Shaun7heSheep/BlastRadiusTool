#!/usr/bin/env python3
"""Upload services.json to Blob Storage. Run once per graph change."""

import json
import os
import sys
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

CONTAINER = "graph-data"
BLOB_NAME = "services.json"


def validate_graph(data: dict) -> list[str]:
    """Validate graph data and return a list of error messages (empty if valid)."""
    errors: list[str] = []

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    # Collect all node IDs and check for uniqueness
    seen: set[str] = set()
    for node in nodes:
        nid = node.get("id", "")
        if nid in seen:
            errors.append(f"Duplicate node id: {nid!r}")
        seen.add(nid)

    node_id_set = seen

    # Check that every edge source and target references an existing node
    for edge in edges:
        source = edge.get("source", "")
        target = edge.get("target", "")
        if source not in node_id_set:
            errors.append(f"Edge source {source!r} does not match any node id")
        if target not in node_id_set:
            errors.append(f"Edge target {target!r} does not match any node id")

    return errors


def get_blob_service_client() -> BlobServiceClient:
    """Return a BlobServiceClient using the same auth pattern as function_app.py.

    On Azure: uses BlobStorageAccountUrl + Managed Identity.
    Locally: falls back to AzureWebJobsStorage connection string (Azurite).
    """
    account_url = os.environ.get("BlobStorageAccountUrl", "")
    if account_url:
        return BlobServiceClient(account_url, credential=DefaultAzureCredential())
    conn_str = os.environ.get("AzureWebJobsStorage", "UseDevelopmentStorage=true")
    return BlobServiceClient.from_connection_string(conn_str)


def seed(graph_path: Path) -> None:
    """Read, validate, and upload graph_path to Blob Storage."""
    # 1. Read and parse
    raw = graph_path.read_text(encoding="utf-8")
    data = json.loads(raw)

    # 2. Validate
    errors = validate_graph(data)
    if errors:
        print("ERROR: Graph validation failed:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    node_count = len(data.get("nodes", []))
    edge_count = len(data.get("edges", []))
    print(f"Graph validated: {node_count} nodes, {edge_count} edges")

    # 3. Prepare blob content (compact JSON, UTF-8)
    blob_bytes = raw.encode("utf-8")

    # 4. Upload to Blob Storage
    svc = get_blob_service_client()

    # Ensure container exists
    container_client = svc.get_container_client(CONTAINER)
    try:
        container_client.create_container()
        print(f"Created container: {CONTAINER}")
    except Exception as exc:  # noqa: BLE001
        # Container already exists — Azure SDK raises ResourceExistsError,
        # but Azurite may raise a different exception type. Catch broadly
        # and only suppress "already exists" scenarios.
        if "ContainerAlreadyExists" in str(exc) or "already exists" in str(exc).lower():
            pass
        else:
            raise

    blob_client = container_client.get_blob_client(BLOB_NAME)
    blob_client.upload_blob(data=blob_bytes, overwrite=True)

    print(f"Uploaded {BLOB_NAME} to container {CONTAINER!r} ({len(blob_bytes)} bytes)")


if __name__ == "__main__":
    graph_path = Path(__file__).resolve().parent.parent / "data" / "services.json"
    if not graph_path.exists():
        print(f"ERROR: {graph_path} not found. Create BlastRadiusApi/data/services.json first.")
        raise SystemExit(1)
    seed(graph_path)
