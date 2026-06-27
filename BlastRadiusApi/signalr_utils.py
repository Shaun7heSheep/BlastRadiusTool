"""SignalR broadcast and negotiate helpers for the Blast Radius API."""

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def _parse_connection_string(connection_string: str) -> dict[str, str]:
    """Parse a SignalR connection string into a key/value dict."""
    parts = {}
    for segment in connection_string.split(";"):
        segment = segment.strip()
        if not segment:
            continue
        idx = segment.index("=")
        key = segment[:idx]
        value = segment[idx + 1:]
        parts[key] = value
    return parts


def _generate_jwt(access_key: str, audience: str, expires_in: int = 300) -> str:
    """Generate a signed HS256 JWT using stdlib only (no PyJWT dependency)."""
    header = (
        base64.urlsafe_b64encode(
            json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    payload_data = {"aud": audience, "exp": int(time.time()) + expires_in}
    payload = (
        base64.urlsafe_b64encode(
            json.dumps(payload_data, separators=(",", ":")).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    signing_input = f"{header}.{payload}"
    # The AccessKey is the HMAC-SHA256 signing key as its RAW UTF-8 bytes.
    # Do NOT base64-decode it first. The official Azure SignalR SDK signs with
    #   new SymmetricSecurityKey(Encoding.UTF8.GetBytes(AccessKey))
    # i.e. the literal key string's UTF-8 bytes. base64-decoding produces a
    # completely different key, so the resulting signature won't match what the
    # emulator/service computes and every token is rejected with 401.
    # (This was the bug: a previous version b64-decoded access_key here.)
    key = access_key.encode("utf-8")
    signature = (
        base64.urlsafe_b64encode(
            hmac.new(key, signing_input.encode(), hashlib.sha256).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    return f"{signing_input}.{signature}"


def broadcast(
    connection_string: str,
    hub_name: str,
    result: dict,
) -> None:
    """POST a broadcast message to all SignalR clients on the given hub.

    Fire-and-forget: catches ALL exceptions, logs them, and returns None.
    Never raises.
    """
    try:
        parts = _parse_connection_string(connection_string)
        endpoint = parts["Endpoint"].rstrip("/")
        access_key = parts["AccessKey"]

        url = f"{endpoint}/api/v1/hubs/{hub_name}"
        # The JWT "aud" claim must equal the request URL exactly; the service
        # validates the token's audience against the endpoint being called.
        token = _generate_jwt(access_key, url)

        requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"target": "blastRadius", "arguments": [result]},
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("SignalR broadcast failed: %s", exc)
    return None


def negotiate(
    connection_string: str,
    hub_name: str,
    user_id: Optional[str] = None,
) -> dict:
    """Generate a SignalR client negotiate response.

    Returns:
        {"url": "<client endpoint>", "accessToken": "<jwt>"}
    """
    parts = _parse_connection_string(connection_string)
    endpoint = parts["Endpoint"].rstrip("/")
    access_key = parts["AccessKey"]

    # The "aud" claim must match the client connection URL exactly, including
    # the "?hub=" query string. A mismatch (e.g. dropping the query) makes the
    # service reject the client's negotiate token with 401.
    client_url = f"{endpoint}/client/?hub={hub_name}"
    token = _generate_jwt(access_key, client_url, expires_in=3600)

    return {"url": client_url, "accessToken": token}
