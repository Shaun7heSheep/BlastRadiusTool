#!/usr/bin/env python3
"""Upload services.json to Blob Storage. Run once per graph change."""

import argparse
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

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

    # Validate applications array if present (optional — skip if absent)
    applications = data.get("applications")
    if applications is not None:
        app_ids: set[str] = set()
        for app in applications:
            app_id = app.get("id", "")
            app_title = app.get("title", "")
            if not isinstance(app_id, str) or not app_id:
                errors.append(f"Application missing required string 'id': {app!r}")
            if not isinstance(app_title, str) or not app_title:
                errors.append(f"Application missing required string 'title': {app!r}")
            if app_id in app_ids:
                errors.append(f"Duplicate application id: {app_id!r}")
            app_ids.add(app_id)

        # Validate that every node's appIds reference valid application IDs
        for node in nodes:
            node_id = node.get("id", "")
            app_id_refs = node.get("appIds", [])
            for ref in app_id_refs:
                if ref not in app_ids:
                    errors.append(f"Node {node_id!r} appIds references unknown application id: {ref!r}")

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


def load_and_validate(graph_path: Path) -> str:
    """Read and validate graph_path. Exit non-zero on any validation error.

    Returns the raw file contents so callers can reuse them (e.g. to upload)
    without re-reading from disk.
    """
    raw = graph_path.read_text(encoding="utf-8")
    data = json.loads(raw)

    errors = validate_graph(data)
    if errors:
        print("ERROR: Graph validation failed:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    node_count = len(data.get("nodes", []))
    edge_count = len(data.get("edges", []))
    print(f"Graph validated: {node_count} nodes, {edge_count} edges")
    return raw


def seed(graph_path: Path) -> None:
    """Read, validate, and upload graph_path to Blob Storage."""
    # 1. Read and validate
    raw = load_and_validate(graph_path)

    # 2. Prepare blob content (UTF-8)
    blob_bytes = raw.encode("utf-8")

    # 3. Upload to Blob Storage
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
    parser = argparse.ArgumentParser(
        description="Validate and upload services.json to Blob Storage."
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the graph and exit without uploading. Use this as a CI gate.",
    )
    args = parser.parse_args()

    graph_path = Path(__file__).resolve().parent.parent / "data" / "services.json"
    if not graph_path.exists():
        print(f"ERROR: {graph_path} not found. Create BlastRadiusApi/data/services.json first.")
        raise SystemExit(1)

    if args.validate_only:
        load_and_validate(graph_path)
        print("Validation passed (no upload, --validate-only).")
    else:
        seed(graph_path)
