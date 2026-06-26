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
            json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    payload_data = {"aud": audience, "exp": int(time.time()) + expires_in}
    payload = (
        base64.urlsafe_b64encode(json.dumps(payload_data).encode())
        .rstrip(b"=")
        .decode()
    )
    signing_input = f"{header}.{payload}"
    key = base64.b64decode(access_key + "==")
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

    client_url = f"{endpoint}/client/?hub={hub_name}"
    token = _generate_jwt(access_key, client_url, expires_in=3600)

    return {"url": client_url, "accessToken": token}
