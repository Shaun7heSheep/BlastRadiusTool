"""RED tests for signalr_utils.py — defines the contract for broadcast() and negotiate().

All tests in this file must FAIL (RED phase) because signalr_utils.py is currently
an empty stub. These tests define the API that signalr_utils.py must satisfy.
"""

import pytest
from unittest.mock import patch, MagicMock

from signalr_utils import broadcast, negotiate


FAKE_CONNECTION_STRING = (
    "Endpoint=https://test-signalr.service.signalr.net;"
    "AccessKey=dGVzdGtleXRoYXRpc2F0bGVhc3QzMmJ5dGVzbG9uZzE=;"
    "Version=1.0;"
)
FAKE_HUB_NAME = "blastRadiusHub"


# ---------------------------------------------------------------------------
# broadcast() tests
# ---------------------------------------------------------------------------


class TestBroadcast:
    """Tests for signalr_utils.broadcast() — fire-and-forget SignalR REST API call."""

    @patch("signalr_utils.requests.post")
    def test_broadcast_calls_correct_endpoint(self, mock_post):
        """broadcast() must POST to /api/v1/hubs/{hub_name}."""
        mock_post.return_value = MagicMock(status_code=202)
        result_payload = {"failedNode": "test-service"}

        broadcast(FAKE_CONNECTION_STRING, FAKE_HUB_NAME, result_payload)

        mock_post.assert_called_once()
        actual_url = mock_post.call_args[0][0] if mock_post.call_args[0] else mock_post.call_args.kwargs.get("url", "")
        assert "/api/v1/hubs/blastRadiusHub" in actual_url

    @patch("signalr_utils.requests.post")
    def test_broadcast_sends_correct_payload(self, mock_post):
        """broadcast() must send {"target": "blastRadius", "arguments": [result]}."""
        mock_post.return_value = MagicMock(status_code=202)
        result_payload = {"failedNode": "payments-servicebus", "affectedNodes": ["api-a"]}

        broadcast(FAKE_CONNECTION_STRING, FAKE_HUB_NAME, result_payload)

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs if mock_post.call_args.kwargs else {}
        # The json kwarg may be passed positionally or as keyword
        json_body = call_kwargs.get("json") or (
            mock_post.call_args[1].get("json") if len(mock_post.call_args) > 1 else None
        )
        assert json_body is not None, "broadcast() must pass json= to requests.post"
        assert json_body["target"] == "blastRadius"
        assert json_body["arguments"] == [result_payload]

    @patch("signalr_utils.requests.post")
    def test_broadcast_sends_auth_header(self, mock_post):
        """broadcast() must include an Authorization: Bearer header."""
        mock_post.return_value = MagicMock(status_code=202)
        result_payload = {"failedNode": "test-service"}

        broadcast(FAKE_CONNECTION_STRING, FAKE_HUB_NAME, result_payload)

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs if mock_post.call_args.kwargs else {}
        headers = call_kwargs.get("headers") or (
            mock_post.call_args[1].get("headers") if len(mock_post.call_args) > 1 else None
        )
        assert headers is not None, "broadcast() must pass headers= to requests.post"
        auth_header = headers.get("Authorization", "")
        assert auth_header.startswith("Bearer "), (
            f"Authorization header must start with 'Bearer ', got: {auth_header!r}"
        )

    @patch("signalr_utils.requests.post")
    def test_broadcast_swallows_connection_errors(self, mock_post):
        """broadcast() must swallow ConnectionError — fire-and-forget (invariant 7)."""
        import requests as req_lib

        mock_post.side_effect = req_lib.exceptions.ConnectionError("SignalR unreachable")
        result_payload = {"failedNode": "test-service"}

        # Must NOT raise — broadcast is fire-and-forget
        result = broadcast(FAKE_CONNECTION_STRING, FAKE_HUB_NAME, result_payload)

        assert result is None

    @patch("signalr_utils.requests.post")
    def test_broadcast_swallows_all_exception_types(self, mock_post):
        """broadcast() must swallow ANY exception type — not just requests errors."""
        mock_post.side_effect = Exception("unexpected kaboom")
        result_payload = {"failedNode": "test-service"}

        # Must NOT raise — broadcast is fire-and-forget
        result = broadcast(FAKE_CONNECTION_STRING, FAKE_HUB_NAME, result_payload)

        assert result is None


# ---------------------------------------------------------------------------
# negotiate() tests
# ---------------------------------------------------------------------------


class TestNegotiate:
    """Tests for signalr_utils.negotiate() — generates a client negotiate response."""

    def test_negotiate_returns_url_and_token(self):
        """negotiate() must return a dict with 'url' and 'accessToken' keys."""
        result = negotiate(FAKE_CONNECTION_STRING, FAKE_HUB_NAME)

        assert isinstance(result, dict), f"negotiate() must return a dict, got {type(result)}"
        assert "url" in result, "negotiate() result must contain 'url' key"
        assert "accessToken" in result, "negotiate() result must contain 'accessToken' key"
        assert isinstance(result["url"], str) and len(result["url"]) > 0, (
            "url must be a non-empty string"
        )
        assert isinstance(result["accessToken"], str) and len(result["accessToken"]) > 0, (
            "accessToken must be a non-empty string"
        )

    def test_negotiate_url_format(self):
        """negotiate() url must contain the endpoint and hub name from the connection string."""
        result = negotiate(FAKE_CONNECTION_STRING, FAKE_HUB_NAME)

        url = result["url"]
        assert "test-signalr.service.signalr.net" in url, (
            f"URL must contain the endpoint hostname, got: {url!r}"
        )
        assert "hub=blastRadiusHub" in url or "/client/?hub=blastRadiusHub" in url, (
            f"URL must include hub=blastRadiusHub, got: {url!r}"
        )

    def test_negotiate_token_is_jwt(self):
        """negotiate() accessToken must be a JWT (three dot-separated parts)."""
        result = negotiate(FAKE_CONNECTION_STRING, FAKE_HUB_NAME)

        token = result["accessToken"]
        parts = token.split(".")
        assert len(parts) == 3, (
            f"JWT must have 3 dot-separated parts (header.payload.signature), "
            f"got {len(parts)} parts: {token!r}"
        )

    def test_negotiate_token_signed_with_raw_utf8_key(self):
        """JWT must be signed with AccessKey as raw UTF-8 bytes, not base64-decoded.

        The official Azure SignalR C# SDK signs with:
            new SymmetricSecurityKey(Encoding.UTF8.GetBytes(AccessKey))
        Our code must do the equivalent: access_key.encode("utf-8").
        """
        import base64
        import hashlib
        import hmac

        result = negotiate(FAKE_CONNECTION_STRING, FAKE_HUB_NAME)
        token = result["accessToken"]
        header_b64, payload_b64, signature_b64 = token.split(".")

        # Re-derive the expected signature using raw UTF-8 key bytes
        access_key = "dGVzdGtleXRoYXRpc2F0bGVhc3QzMmJ5dGVzbG9uZzE="
        key = access_key.encode("utf-8")  # raw UTF-8, NOT base64.b64decode
        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected_sig = (
            base64.urlsafe_b64encode(
                hmac.new(key, signing_input, hashlib.sha256).digest()
            )
            .rstrip(b"=")
            .decode()
        )
        assert signature_b64 == expected_sig, (
            "JWT signature must match HMAC-SHA256 using raw UTF-8 AccessKey bytes. "
            "If this fails, the key is probably being base64-decoded before signing."
        )
