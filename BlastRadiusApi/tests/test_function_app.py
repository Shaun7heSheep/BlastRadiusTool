"""Phase 4.1 — Integration tests for function_app.py endpoints.

RED phase: all 9 tests fail against the Hello World stub.
GREEN phase: all 9 tests pass once Phase 4.2 is implemented.

Mocking strategy
----------------
- ``function_app.get_blob_service_client`` — patched with ``create=True`` so it
  works before the helper exists in the module; the mock returns an in-memory
  ``BlobServiceClient`` stand-in.
- ``function_app.signalr_utils`` — the entire module reference is replaced with
  a ``MagicMock`` so that both ``broadcast`` and ``negotiate`` are controllable.
- Environment variables — injected per-test via ``monkeypatch.setenv`` so no
  real Azure connection is required.
"""

import json
from unittest.mock import MagicMock, call, patch

import azure.functions as func
import pytest
from azure.core.exceptions import ResourceNotFoundError

# Import the four handlers directly — they exist in the stub.
from function_app import blast_radius, blast_result, graph, signalr_negotiate

# ─────────────────────────────────────────────────────────────────────────────
# Module-level test constants
# ─────────────────────────────────────────────────────────────────────────────

_FAKE_SIGNALR_CONN = (
    "Endpoint=https://test.service.signalr.net;"
    "AccessKey=dGVzdGtleTE=;"
    "Version=1.0;"
)
_FAKE_STORAGE_CONN = "UseDevelopmentStorage=true"

_ENV = {
    "AzureSignalRConnectionString": _FAKE_SIGNALR_CONN,
    "AzureWebJobsStorage": _FAKE_STORAGE_CONN,
}

_STORED_RESULT = {
    "failedNode": "payments-servicebus",
    "affectedNodes": ["order-function", "api-management"],
    "affectedEdges": [
        {"source": "order-function", "target": "payments-servicebus"},
        {"source": "api-management", "target": "order-function"},
    ],
    "timestamp": "2026-06-26T17:00:00+00:00",
}


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_blob_service_mock(graph_data: dict) -> MagicMock:
    """Return a BlobServiceClient mock that serves *graph_data* as bytes from
    ``download_blob().readall()``.

    ``get_blob_client()`` always returns the same child mock regardless of the
    blob name, so ``upload_blob`` assertions target that same object.
    """
    mock_svc = MagicMock()
    blob_bytes = json.dumps(graph_data).encode()
    (
        mock_svc
        .get_container_client.return_value
        .get_blob_client.return_value
        .download_blob.return_value
        .readall.return_value
    ) = blob_bytes
    return mock_svc


def _make_result_blob_service_mock(result_data: dict) -> MagicMock:
    """Return a BlobServiceClient mock that serves *result_data* JSON bytes.

    Used for ``blast_result`` endpoint tests where only the result blob is read.
    """
    mock_svc = MagicMock()
    (
        mock_svc
        .get_container_client.return_value
        .get_blob_client.return_value
        .download_blob.return_value
        .readall.return_value
    ) = json.dumps(result_data).encode()
    return mock_svc


def _make_missing_blob_service_mock() -> MagicMock:
    """Return a BlobServiceClient mock whose ``download_blob`` raises
    ``ResourceNotFoundError`` — simulates a missing blob.
    """
    mock_svc = MagicMock()
    (
        mock_svc
        .get_container_client.return_value
        .get_blob_client.return_value
        .download_blob
        .side_effect
    ) = ResourceNotFoundError("The specified blob does not exist.")
    return mock_svc


def _post_request(payload: dict) -> func.HttpRequest:
    """Construct a POST HttpRequest with a JSON body."""
    return func.HttpRequest(
        method="POST",
        url="http://localhost/api/blast_radius",
        headers={"Content-Type": "application/json"},
        params={},
        body=json.dumps(payload).encode("utf-8"),
    )


def _get_request(route: str) -> func.HttpRequest:
    """Construct a GET HttpRequest for *route*."""
    return func.HttpRequest(
        method="GET",
        url=f"http://localhost/api/{route}",
        headers={},
        params={},
        body=b"",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — POST valid alert → 200 + blast result JSON shape
# ─────────────────────────────────────────────────────────────────────────────


def test_blast_radius_valid_alert(simple_graph_data, sample_alert_payload, monkeypatch):
    """POST valid alert payload → 200, response JSON has failedNode,
    affectedNodes (list of strings), and affectedEdges.
    """
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)

    mock_svc = _make_blob_service_mock(simple_graph_data)

    with (
        patch("function_app.get_blob_service_client", return_value=mock_svc, create=True),
        patch("function_app.signalr_utils", create=True) as mock_sr,
    ):
        mock_sr.broadcast = MagicMock()
        response = blast_radius(_post_request(sample_alert_payload))

    assert response.status_code == 200

    body = json.loads(response.get_body().decode())
    assert "failedNode" in body, "Response JSON must contain 'failedNode'"
    assert "affectedNodes" in body, "Response JSON must contain 'affectedNodes'"
    assert "affectedEdges" in body, "Response JSON must contain 'affectedEdges'"

    # affectedNodes must be a flat list of string IDs, not nested objects
    assert isinstance(body["affectedNodes"], list)
    assert all(
        isinstance(n, str) for n in body["affectedNodes"]
    ), "Each affectedNode must be a string ID, not an object"


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — POST malformed JSON → 400
# ─────────────────────────────────────────────────────────────────────────────


def test_blast_radius_malformed_json(monkeypatch):
    """POST invalid JSON body → 400 Bad Request."""
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)

    req = func.HttpRequest(
        method="POST",
        url="http://localhost/api/blast_radius",
        headers={"Content-Type": "application/json"},
        params={},
        body=b"this is { not valid ] json >>>",
    )

    with (
        patch("function_app.get_blob_service_client", create=True),
        patch("function_app.signalr_utils", create=True),
    ):
        response = blast_radius(req)

    assert response.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — POST alert with unknown node → 400 with error message
# ─────────────────────────────────────────────────────────────────────────────


def test_blast_radius_unknown_node(simple_graph_data, monkeypatch):
    """POST alert targeting a node that is not in the graph → 400 with an
    error message that identifies the unknown node.
    """
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)

    mock_svc = _make_blob_service_mock(simple_graph_data)

    # "nonexistent-service" is not in simple_graph_data
    payload = {
        "schemaId": "azureMonitorCommonAlertSchema",
        "data": {
            "essentials": {
                "alertTargetIDs": [
                    "/subscriptions/x/resourceGroups/y"
                    "/providers/Microsoft.ServiceBus/namespaces/nonexistent-service"
                ]
            }
        },
    }

    with (
        patch("function_app.get_blob_service_client", return_value=mock_svc, create=True),
        patch("function_app.signalr_utils", create=True) as mock_sr,
    ):
        mock_sr.broadcast = MagicMock()
        response = blast_radius(_post_request(payload))

    assert response.status_code == 400
    body_text = response.get_body().decode().lower()
    assert "not found" in body_text or "nonexistent-service" in body_text, (
        "400 body must mention the unknown node or 'not found'"
    )
    mock_sr.broadcast.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 — POST valid alert with SignalR failure → still 200 (invariant 7)
# ─────────────────────────────────────────────────────────────────────────────


def test_blast_radius_signalr_failure_still_200(
    simple_graph_data, sample_alert_payload, monkeypatch
):
    """POST valid alert but SignalR broadcast raises → response is still 200
    with a valid blast result body (fire-and-forget, invariant 7).
    """
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)

    mock_svc = _make_blob_service_mock(simple_graph_data)

    with (
        patch("function_app.get_blob_service_client", return_value=mock_svc, create=True),
        patch("function_app.signalr_utils", create=True) as mock_sr,
    ):
        mock_sr.broadcast.side_effect = Exception("SignalR unavailable")
        response = blast_radius(_post_request(sample_alert_payload))

    assert response.status_code == 200

    # The response must still contain a valid blast result, not just a 200 stub
    body = json.loads(response.get_body().decode())
    assert "failedNode" in body, (
        "Even with SignalR failure, the response body must contain 'failedNode'"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 5 — POST valid alert → result blob is written
# ─────────────────────────────────────────────────────────────────────────────


def test_blast_radius_writes_blob(simple_graph_data, sample_alert_payload, monkeypatch):
    """POST valid alert → ``upload_blob`` is called on the blob client,
    with ``overwrite=True``.
    """
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)

    mock_svc = _make_blob_service_mock(simple_graph_data)
    # The same mock is returned by get_blob_client() for any blob name,
    # so upload_blob assertions target this object.
    mock_blob_client = (
        mock_svc
        .get_container_client.return_value
        .get_blob_client.return_value
    )

    with (
        patch("function_app.get_blob_service_client", return_value=mock_svc, create=True),
        patch("function_app.signalr_utils", create=True) as mock_sr,
    ):
        mock_sr.broadcast = MagicMock()
        blast_radius(_post_request(sample_alert_payload))

    mock_blob_client.upload_blob.assert_called_once()
    upload_kwargs = mock_blob_client.upload_blob.call_args.kwargs
    assert upload_kwargs.get("overwrite") is True, (
        "upload_blob must be called with overwrite=True to replace the result blob"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 6 — GET /api/graph → services.json content
# ─────────────────────────────────────────────────────────────────────────────


def test_graph_returns_services_json(simple_graph_data, monkeypatch):
    """GET /api/graph → 200, body is valid JSON containing 'nodes' and 'edges'."""
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)

    mock_svc = _make_blob_service_mock(simple_graph_data)

    with patch("function_app.get_blob_service_client", return_value=mock_svc, create=True):
        response = graph(_get_request("graph"))

    assert response.status_code == 200

    body = json.loads(response.get_body().decode())
    assert "nodes" in body, "Graph response must contain 'nodes'"
    assert "edges" in body, "Graph response must contain 'edges'"
    assert isinstance(body["nodes"], list)
    assert isinstance(body["edges"], list)


# ─────────────────────────────────────────────────────────────────────────────
# Test 7 — GET /api/blast_result when blob exists → 200 + result body
# ─────────────────────────────────────────────────────────────────────────────


def test_blast_result_returns_latest(monkeypatch):
    """GET /api/blast_result when the result blob exists → 200,
    body has 'failedNode'.
    """
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)

    mock_svc = _make_result_blob_service_mock(_STORED_RESULT)

    with patch("function_app.get_blob_service_client", return_value=mock_svc, create=True):
        response = blast_result(_get_request("blast_result"))

    assert response.status_code == 200

    body = json.loads(response.get_body().decode())
    assert "failedNode" in body, "blast_result body must contain 'failedNode'"


# ─────────────────────────────────────────────────────────────────────────────
# Test 8 — GET /api/blast_result when blob missing → 204
# ─────────────────────────────────────────────────────────────────────────────


def test_blast_result_returns_204_when_missing(monkeypatch):
    """GET /api/blast_result when the result blob does not yet exist → 204
    No Content (no result has been computed yet).
    """
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)

    mock_svc = _make_missing_blob_service_mock()

    with patch("function_app.get_blob_service_client", return_value=mock_svc, create=True):
        response = blast_result(_get_request("blast_result"))

    assert response.status_code == 204


# ─────────────────────────────────────────────────────────────────────────────
# Test 9 — GET /api/signalr_negotiate → url + accessToken
# ─────────────────────────────────────────────────────────────────────────────


def test_signalr_negotiate_returns_token(monkeypatch):
    """GET /api/signalr_negotiate → 200, body JSON contains 'url' and
    'accessToken' fields.
    """
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)

    fake_negotiate_result = {
        "url": "https://test.service.signalr.net/client/?hub=blastradius",
        "accessToken": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.payload.sig",
    }

    with patch("function_app.signalr_utils", create=True) as mock_sr:
        mock_sr.negotiate.return_value = fake_negotiate_result
        response = signalr_negotiate(_get_request("signalr_negotiate"))

    assert response.status_code == 200

    body = json.loads(response.get_body().decode())
    assert "url" in body, "Negotiate response must contain 'url'"
    assert "accessToken" in body, "Negotiate response must contain 'accessToken'"
    assert body["url"].startswith("https://"), "url must be an HTTPS endpoint"
    assert len(body["accessToken"]) > 0, "accessToken must be non-empty"
