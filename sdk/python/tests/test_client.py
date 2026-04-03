"""Tests for client-side signing transport and factory (client.py)."""

from __future__ import annotations

import time

import httpx
import pytest

from hardenlabs_hmac.canonical import build_canonical_string
from hardenlabs_hmac.client import (
    HmacAsyncTransport,
    HmacClientFactory,
    HmacTransport,
    sign_request_headers,
)
from hardenlabs_hmac.config import (
    CLIENT_ID_HEADER,
    SIGNATURE_HEADER,
    SIGNED_HEADERS_HEADER,
    TIMESTAMP_HEADER,
    HmacConfig,
    HmacTargetConfig,
    SignedHeadersConfig,
)
from hardenlabs_hmac.signing import sign
from hardenlabs_hmac.validation import validate_request

TEST_SECRET = "dGVzdC1zZWNyZXQta2V5LTMyLWJ5dGVzISEhISE="
OTHER_SECRET = "b3RoZXItc2VjcmV0LWtleS0zMi1ieXRlcyEhISEh"


def _make_config(
    secret: str = TEST_SECRET,
    targets: dict[str, HmacTargetConfig] | None = None,
    signed_headers: SignedHeadersConfig | None = None,
) -> HmacConfig:
    return HmacConfig(
        shared_secret_base64=secret,
        targets=targets or {},
        signed_headers=signed_headers or SignedHeadersConfig.none(),
    )


def _echo_transport(request: httpx.Request) -> httpx.Response:
    """Mock transport that echoes back all request headers as JSON."""
    headers = dict(request.headers)
    import json

    return httpx.Response(200, json=headers)


class TestSignRequestHeaders:
    def test_returns_signature_and_timestamp(self) -> None:
        config = _make_config()
        headers = sign_request_headers(config, "GET", "/api/test", "")
        assert SIGNATURE_HEADER in headers
        assert TIMESTAMP_HEADER in headers
        assert headers[SIGNATURE_HEADER] != ""
        assert headers[TIMESTAMP_HEADER] != ""

    def test_uses_explicit_timestamp(self) -> None:
        config = _make_config()
        headers = sign_request_headers(
            config, "GET", "/api/test", "", timestamp=1700000000
        )
        assert headers[TIMESTAMP_HEADER] == "1700000000"

    def test_includes_signed_headers_header_when_headers_present(self) -> None:
        config = _make_config(
            signed_headers=SignedHeadersConfig(
                include_authorization=True, include_x_headers=True
            )
        )
        headers = sign_request_headers(
            config,
            "GET",
            "/api/test",
            "",
            request_headers={"Authorization": "Bearer tok"},
        )
        assert SIGNED_HEADERS_HEADER in headers

    def test_no_signed_headers_header_when_none_selected(self) -> None:
        config = _make_config(signed_headers=SignedHeadersConfig.none())
        headers = sign_request_headers(config, "GET", "/api/test", "")
        assert SIGNED_HEADERS_HEADER not in headers


class TestHmacTransport:
    """Tests for the sync HmacTransport wrapper."""

    def test_adds_signature_headers(self) -> None:
        config = _make_config()
        inner = httpx.MockTransport(_echo_transport)
        transport = HmacTransport(config, inner)

        client = httpx.Client(transport=transport, base_url="https://example.com")
        response = client.get("/api/test")
        echoed = response.json()

        assert SIGNATURE_HEADER.lower() in echoed
        assert TIMESTAMP_HEADER.lower() in echoed
        client.close()

    def test_adds_client_id_when_set(self) -> None:
        config = _make_config()
        inner = httpx.MockTransport(_echo_transport)
        transport = HmacTransport(config, inner, client_id="my-service")

        client = httpx.Client(transport=transport, base_url="https://example.com")
        response = client.get("/api/test")
        echoed = response.json()

        assert echoed.get(CLIENT_ID_HEADER.lower()) == "my-service"
        client.close()

    def test_no_client_id_when_none(self) -> None:
        config = _make_config()
        inner = httpx.MockTransport(_echo_transport)
        transport = HmacTransport(config, inner, client_id=None)

        client = httpx.Client(transport=transport, base_url="https://example.com")
        response = client.get("/api/test")
        echoed = response.json()

        assert CLIENT_ID_HEADER.lower() not in echoed
        client.close()

    def test_signs_post_with_body(self) -> None:
        config = _make_config()
        inner = httpx.MockTransport(_echo_transport)
        transport = HmacTransport(config, inner)

        client = httpx.Client(transport=transport, base_url="https://example.com")
        response = client.post("/api/test", content='{"key":"value"}')
        echoed = response.json()

        assert SIGNATURE_HEADER.lower() in echoed
        client.close()

    def test_signature_validates_server_side(self) -> None:
        """Round-trip: sign with transport, validate with validate_request."""
        config = _make_config()
        captured: list[httpx.Request] = []

        def capture_transport(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200)

        inner = httpx.MockTransport(capture_transport)
        transport = HmacTransport(config, inner)

        client = httpx.Client(transport=transport, base_url="https://example.com")
        client.get("/api/items?page=1")
        client.close()

        req = captured[0]
        headers = dict(req.headers)
        validate_request(
            config,
            method="GET",
            path="/api/items?page=1",
            body="",
            signature_header=headers[SIGNATURE_HEADER.lower()],
            timestamp_header=headers[TIMESTAMP_HEADER.lower()],
            request_headers=headers,
        )


class TestHmacAsyncTransport:
    """Tests for the async HmacAsyncTransport wrapper."""

    async def test_adds_signature_headers(self) -> None:
        config = _make_config()

        async def async_echo(request: httpx.Request) -> httpx.Response:
            import json

            headers = dict(request.headers)
            return httpx.Response(200, json=headers)

        inner = httpx.MockTransport(async_echo)
        transport = HmacAsyncTransport(config, inner)

        async with httpx.AsyncClient(
            transport=transport, base_url="https://example.com"
        ) as client:
            response = await client.get("/api/test")
            echoed = response.json()

        assert SIGNATURE_HEADER.lower() in echoed
        assert TIMESTAMP_HEADER.lower() in echoed

    async def test_adds_client_id_when_set(self) -> None:
        config = _make_config()

        async def async_echo(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=dict(request.headers))

        inner = httpx.MockTransport(async_echo)
        transport = HmacAsyncTransport(config, inner, client_id="async-svc")

        async with httpx.AsyncClient(
            transport=transport, base_url="https://example.com"
        ) as client:
            response = await client.get("/api/test")
            echoed = response.json()

        assert echoed.get(CLIENT_ID_HEADER.lower()) == "async-svc"

    async def test_signature_validates_server_side(self) -> None:
        config = _make_config()
        captured: list[httpx.Request] = []

        async def capture_transport(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200)

        inner = httpx.MockTransport(capture_transport)
        transport = HmacAsyncTransport(config, inner)

        async with httpx.AsyncClient(
            transport=transport, base_url="https://example.com"
        ) as client:
            await client.post("/api/items", content='{"name":"widget"}')

        req = captured[0]
        headers = dict(req.headers)
        validate_request(
            config,
            method="POST",
            path="/api/items",
            body='{"name":"widget"}',
            signature_header=headers[SIGNATURE_HEADER.lower()],
            timestamp_header=headers[TIMESTAMP_HEADER.lower()],
            request_headers=headers,
        )


class TestHmacClientFactory:
    """Tests for the HmacClientFactory create methods."""

    def _factory_config(self) -> HmacConfig:
        return HmacConfig(
            shared_secret_base64=TEST_SECRET,
            signed_headers=SignedHeadersConfig.none(),
            targets={
                "my-service": HmacTargetConfig(
                    base_url="https://api.example.com",
                    shared_secret=TEST_SECRET,
                ),
                "other-service": HmacTargetConfig(
                    base_url="https://other.example.com",
                    shared_secret=OTHER_SECRET,
                    signed_headers=SignedHeadersConfig.default(),
                    timestamp_tolerance_seconds=60,
                ),
            },
        )

    def test_get_target_raises_for_unknown(self) -> None:
        factory = HmacClientFactory(self._factory_config())
        with pytest.raises(KeyError, match="nonexistent"):
            factory._get_target("nonexistent")

    def test_get_target_error_lists_available(self) -> None:
        factory = HmacClientFactory(self._factory_config())
        with pytest.raises(KeyError, match="my-service"):
            factory._get_target("nonexistent")

    def test_create_sync_client_returns_httpx_client(self) -> None:
        factory = HmacClientFactory(self._factory_config())
        client = factory.create_sync_client("my-service")
        assert isinstance(client, httpx.Client)
        client.close()

    def test_create_sync_client_sets_base_url(self) -> None:
        factory = HmacClientFactory(self._factory_config())
        client = factory.create_sync_client("my-service")
        assert str(client.base_url) == "https://api.example.com"
        client.close()

    def test_create_sync_client_uses_hmac_transport(self) -> None:
        factory = HmacClientFactory(self._factory_config())
        client = factory.create_sync_client("my-service")
        transport = client._transport
        assert isinstance(transport, HmacTransport)
        assert transport._client_id == "my-service"
        client.close()

    def test_create_client_returns_async_client(self) -> None:
        factory = HmacClientFactory(self._factory_config())
        client = factory.create_client("my-service")
        assert isinstance(client, httpx.AsyncClient)
        # Can't await close in sync test, just check the type
        # Use sync close
        import asyncio

        asyncio.get_event_loop().run_until_complete(client.aclose())

    def test_create_client_sets_base_url(self) -> None:
        factory = HmacClientFactory(self._factory_config())
        client = factory.create_client("my-service")
        assert str(client.base_url) == "https://api.example.com"
        import asyncio

        asyncio.get_event_loop().run_until_complete(client.aclose())

    def test_create_client_uses_async_transport(self) -> None:
        factory = HmacClientFactory(self._factory_config())
        client = factory.create_client("my-service")
        transport = client._transport
        assert isinstance(transport, HmacAsyncTransport)
        assert transport._client_id == "my-service"
        import asyncio

        asyncio.get_event_loop().run_until_complete(client.aclose())

    def test_create_client_raises_for_unknown_target(self) -> None:
        factory = HmacClientFactory(self._factory_config())
        with pytest.raises(KeyError, match="bad-target"):
            factory.create_client("bad-target")

    def test_create_sync_client_raises_for_unknown_target(self) -> None:
        factory = HmacClientFactory(self._factory_config())
        with pytest.raises(KeyError, match="bad-target"):
            factory.create_sync_client("bad-target")

    def test_create_requests_session_raises_for_unknown_target(self) -> None:
        factory = HmacClientFactory(self._factory_config())
        with pytest.raises(KeyError, match="bad-target"):
            factory.create_requests_session("bad-target")

    def test_create_sync_client_uses_target_overrides(self) -> None:
        factory = HmacClientFactory(self._factory_config())
        client = factory.create_sync_client("other-service")
        transport = client._transport
        assert isinstance(transport, HmacTransport)
        # Verify the effective config uses the target-specific secret
        assert transport._config.shared_secret_base64 == OTHER_SECRET
        assert transport._config.signed_headers == SignedHeadersConfig.default()
        assert transport._config.timestamp_tolerance_seconds == 60
        client.close()
