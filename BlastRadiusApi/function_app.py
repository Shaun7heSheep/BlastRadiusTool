"""Azure Functions app — HTTP triggers for the Blast Radius Tool."""

import json
import logging
import os

import azure.functions as func
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

import graph_utils
import signalr_utils

logger = logging.getLogger(__name__)
app = func.FunctionApp()

CONTAINER_NAME = "graph-data"
GRAPH_BLOB = "services.json"
RESULT_BLOB = "blast-result.json"
HUB_NAME = "blastradius"


def get_blob_service_client() -> BlobServiceClient:
    """Return a BlobServiceClient.

    On Azure: uses BlobStorageAccountUrl + Managed Identity.
    Locally: falls back to AzureWebJobsStorage connection string (Azurite).
    """
    account_url = os.environ.get("BlobStorageAccountUrl", "")
    if account_url:
        return BlobServiceClient(account_url, credential=DefaultAzureCredential())
    conn_str = os.environ.get("AzureWebJobsStorage", "UseDevelopmentStorage=true")
    return BlobServiceClient.from_connection_string(conn_str)


def _load_blob_bytes(blob_name: str) -> bytes:
    """Download a blob from the graph-data container and return its raw bytes."""
    svc = get_blob_service_client()
    container = svc.get_container_client(CONTAINER_NAME)
    blob_client = container.get_blob_client(blob_name)
    return blob_client.download_blob().readall()


@app.route(route="blast_radius", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def blast_radius(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/blast_radius — compute blast radius from an Azure Monitor alert."""
    # 1. Parse request body as JSON
    try:
        payload = json.loads(req.get_body())
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("Malformed JSON body: %s", exc)
        return func.HttpResponse(
            json.dumps({"error": "Malformed JSON body"}),
            status_code=400,
            mimetype="application/json",
        )

    # 2. Extract the failed node ID from alertTargetIDs[0] last path segment
    try:
        target_ids = payload["data"]["essentials"]["alertTargetIDs"]
        node_id = target_ids[0].rstrip("/").split("/")[-1]
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("Missing alertTargetIDs in payload: %s", exc)
        return func.HttpResponse(
            json.dumps({"error": "Missing or invalid alertTargetIDs in payload"}),
            status_code=400,
            mimetype="application/json",
        )

    # 3. Load services.json from Blob
    svc = get_blob_service_client()
    container = svc.get_container_client(CONTAINER_NAME)
    graph_bytes = container.get_blob_client(GRAPH_BLOB).download_blob().readall()
    graph_data = graph_utils.load_graph(graph_bytes.decode())

    # 4. Compute blast radius — raises ValueError for unknown nodes
    try:
        result = graph_utils.compute_blast_radius(graph_data, node_id)
    except ValueError as exc:
        logger.warning("Unknown node in blast radius request: %s", exc)
        return func.HttpResponse(
            json.dumps({"error": str(exc)}),
            status_code=400,
            mimetype="application/json",
        )

    # 5. Serialise result (adds UTC timestamp)
    serialised = graph_utils.serialise_result(result)

    # 6. Write blast-result.json to Blob
    result_blob_client = container.get_blob_client(RESULT_BLOB)
    result_blob_client.upload_blob(data=serialised, overwrite=True)

    # 7. Broadcast via SignalR — fire-and-forget (invariant 7)
    try:
        sr_conn_str = os.environ.get("AzureSignalRConnectionString", "")
        signalr_utils.broadcast(sr_conn_str, HUB_NAME, result)
    except Exception as exc:  # noqa: BLE001
        logger.error("SignalR broadcast failed (non-fatal): %s", exc)

    # 8. Return 200 with the result
    return func.HttpResponse(
        serialised,
        status_code=200,
        mimetype="application/json",
    )


@app.route(route="graph", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def graph(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/graph — return the current services.json graph."""
    svc = get_blob_service_client()
    container = svc.get_container_client(CONTAINER_NAME)
    content = container.get_blob_client(GRAPH_BLOB).download_blob().readall()
    return func.HttpResponse(
        content,
        status_code=200,
        mimetype="application/json",
    )


@app.route(route="blast_result", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def blast_result(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/blast_result — return the latest blast-result.json, or 204."""
    svc = get_blob_service_client()
    container = svc.get_container_client(CONTAINER_NAME)
    try:
        content = container.get_blob_client(RESULT_BLOB).download_blob().readall()
    except ResourceNotFoundError:
        logger.info("No blast result blob found — returning 204")
        return func.HttpResponse(status_code=204)
    return func.HttpResponse(
        content,
        status_code=200,
        mimetype="application/json",
    )


@app.route(route="signalr_negotiate", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def signalr_negotiate(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/signalr_negotiate — return SignalR client URL and access token."""
    sr_conn_str = os.environ.get("AzureSignalRConnectionString", "")
    negotiate_result = signalr_utils.negotiate(sr_conn_str, HUB_NAME)
    return func.HttpResponse(
        json.dumps(negotiate_result),
        status_code=200,
        mimetype="application/json",
    )