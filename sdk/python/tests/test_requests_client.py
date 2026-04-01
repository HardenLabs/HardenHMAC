"""Tests for requests library integration (HmacAuth + HmacRequestsClient)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

requests = pytest.importorskip("requests")

from hardenlabs_hmac.client import (
    HmacAuth,
    HmacClientFactory,
    HmacRequestsClient,
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
from hardenlabs_hmac.validation import validate_request

TEST_SECRET = "dGVzdC1zZWNyZXQta2V5LTMyLWJ5dGVzISEhISE="
OTHER_SECRET = "b3RoZXItc2VjcmV0LWtleS0zMi1ieXRlcyEhISEh"


def _make_config(
    secret: str = TEST_SECRET,
    targets: dict[str, HmacTargetConfig] | None = None,
) -> HmacConfig:
    return HmacConfig(
        shared_secret_base64=secret,
        targets=targets or {},
    )


def _make_prepared_request(
    method: str = "GET",
    url: str = "https://api.example.com/v1/items?page=1",
    body: str | bytes | None = None,
    headers: dict[str, str] | None = None,
) -> requests.PreparedRequest:
    """Build a PreparedRequest for testing."""
    req = requests.Request(method=method, url=url, headers=headers or {})
    if body is not None:
        req.data = body
    prepared = req.prepare()
    return prepared


class TestHmacAuth:
    """Tests for the HmacAuth requests auth adapter."""

    def test_adds_signature_headers(self) -> None:
        config = _make_config()
        auth = HmacAuth(config)
        prepared = _make_prepared_request()

        result = auth(prepared)

        assert SIGNATURE_HEADER in result.headers
        assert TIMESTAMP_HEADER in result.headers
        assert result.headers[SIGNATURE_HEADER] != ""
        assert result.headers[TIMESTAMP_HEADER] != ""

    def test_adds_client_id_when_set(self) -> None:
        config = _make_config()
        auth = HmacAuth(config, client_id="order-service")
        prepared = _make_prepared_request()

        result = auth(prepared)

        assert result.headers[CLIENT_ID_HEADER] == "order-service"

    def test_no_client_id_when_none(self) -> None:
        config = _make_config()
        auth = HmacAuth(config, client_id=None)
        prepared = _make_prepared_request()

        result = auth(prepared)

        assert CLIENT_ID_HEADER not in result.headers

    def test_signs_post_with_body(self) -> None:
        config = _make_config()
        auth = HmacAuth(config)
        prepared = _make_prepared_request(
            method="POST",
            url="https://api.example.com/v1/items",
            body='{"name": "widget"}',
        )

        result = auth(prepared)

        assert SIGNATURE_HEADER in result.headers

    def test_signs_request_with_bytes_body(self) -> None:
        config = _make_config()
        auth = HmacAuth(config)
        prepared = _make_prepared_request(
            method="POST",
            url="https://api.example.com/v1/items",
            body=b'{"name": "widget"}',
        )

        result = auth(prepared)

        assert SIGNATURE_HEADER in result.headers

    def test_rejects_unsupported_body_type(self) -> None:
        config = _make_config()
        auth = HmacAuth(config)
        prepared = _make_prepared_request()
        # Force a file-like body
        prepared.body = MagicMock()  # type: ignore[assignment]

        with pytest.raises(TypeError, match="Unsupported request body type"):
            auth(prepared)

    def test_extracts_path_and_query(self) -> None:
        """Verify the correct path+query is signed, not the full URL."""
        config = _make_config()
        ts = int(time.time())
        auth = HmacAuth(config)
        prepared = _make_prepared_request(
            url="https://api.example.com/v1/items?page=2&size=10"
        )

        result = auth(prepared)

        # Validate by reproducing the same signature server-side
        validate_request(
            config,
            method="GET",
            path="/v1/items?page=2&size=10",
            body="",
            signature_header=result.headers[SIGNATURE_HEADER],
            timestamp_header=result.headers[TIMESTAMP_HEADER],
            request_headers=dict(result.headers),
        )

    def test_path_without_query(self) -> None:
        config = _make_config()
        auth = HmacAuth(config)
        prepared = _make_prepared_request(url="https://api.example.com/v1/items")

        result = auth(prepared)

        validate_request(
            config,
            method="GET",
            path="/v1/items",
            body="",
            signature_header=result.headers[SIGNATURE_HEADER],
            timestamp_header=result.headers[TIMESTAMP_HEADER],
            request_headers=dict(result.headers),
        )

    def test_empty_url_defaults_to_root_path(self) -> None:
        config = _make_config()
        auth = HmacAuth(config)
        prepared = _make_prepared_request(url="https://api.example.com")

        result = auth(prepared)

        assert SIGNATURE_HEADER in result.headers


class TestHmacRequestsClient:
    """Tests for the HmacRequestsClient wrapper."""

    def test_context_manager(self) -> None:
        session = MagicMock(spec=requests.Session)
        client = HmacRequestsClient(session, "https://api.example.com")

        with client as c:
            assert c is client

        session.close.assert_called_once()

    def test_close(self) -> None:
        session = MagicMock(spec=requests.Session)
        client = HmacRequestsClient(session, "https://api.example.com")

        client.close()

        session.close.assert_called_once()

    def test_base_url_stripped_trailing_slash(self) -> None:
        session = MagicMock(spec=requests.Session)
        client = HmacRequestsClient(session, "https://api.example.com/")

        assert client.base_url == "https://api.example.com"

    def test_get_prepends_base_url(self) -> None:
        session = MagicMock(spec=requests.Session)
        client = HmacRequestsClient(session, "https://api.example.com")

        client.get("/v1/items", params={"page": 1})

        session.get.assert_called_once_with(
            "https://api.example.com/v1/items", params={"page": 1}
        )

    def test_post_prepends_base_url(self) -> None:
        session = MagicMock(spec=requests.Session)
        client = HmacRequestsClient(session, "https://api.example.com")

        client.post("/v1/items", json={"name": "widget"})

        session.post.assert_called_once_with(
            "https://api.example.com/v1/items", json={"name": "widget"}
        )

    def test_put_prepends_base_url(self) -> None:
        session = MagicMock(spec=requests.Session)
        client = HmacRequestsClient(session, "https://api.example.com")

        client.put("/v1/items/1", json={"name": "updated"})

        session.put.assert_called_once_with(
            "https://api.example.com/v1/items/1", json={"name": "updated"}
        )

    def test_patch_prepends_base_url(self) -> None:
        session = MagicMock(spec=requests.Session)
        client = HmacRequestsClient(session, "https://api.example.com")

        client.patch("/v1/items/1", json={"name": "patched"})

        session.patch.assert_called_once_with(
            "https://api.example.com/v1/items/1", json={"name": "patched"}
        )

    def test_delete_prepends_base_url(self) -> None:
        session = MagicMock(spec=requests.Session)
        client = HmacRequestsClient(session, "https://api.example.com")

        client.delete("/v1/items/1")

        session.delete.assert_called_once_with(
            "https://api.example.com/v1/items/1",
        )

    def test_head_prepends_base_url(self) -> None:
        session = MagicMock(spec=requests.Session)
        client = HmacRequestsClient(session, "https://api.example.com")

        client.head("/v1/items")

        session.head.assert_called_once_with(
            "https://api.example.com/v1/items",
        )

    def test_options_prepends_base_url(self) -> None:
        session = MagicMock(spec=requests.Session)
        client = HmacRequestsClient(session, "https://api.example.com")

        client.options("/v1/items")

        session.options.assert_called_once_with(
            "https://api.example.com/v1/items",
        )


class TestHmacClientFactoryRequests:
    """Tests for HmacClientFactory.create_requests_session."""

    def test_returns_hmac_requests_client(self) -> None:
        config = HmacConfig(
            targets={
                "my-service": HmacTargetConfig(
                    base_url="https://api.example.com",
                    shared_secret=TEST_SECRET,
                ),
            },
        )
        factory = HmacClientFactory(config)

        client = factory.create_requests_session("my-service")

        assert isinstance(client, HmacRequestsClient)
        assert client.base_url == "https://api.example.com"
        client.close()

    def test_session_has_hmac_auth(self) -> None:
        config = HmacConfig(
            targets={
                "my-service": HmacTargetConfig(
                    base_url="https://api.example.com",
                    shared_secret=TEST_SECRET,
                ),
            },
        )
        factory = HmacClientFactory(config)

        client = factory.create_requests_session("my-service")

        assert isinstance(client.session.auth, HmacAuth)
        assert client.session.auth.client_id == "my-service"
        client.close()

    def test_raises_for_unknown_target(self) -> None:
        config = HmacConfig(
            targets={
                "known-service": HmacTargetConfig(
                    base_url="https://api.example.com",
                    shared_secret=TEST_SECRET,
                ),
            },
        )
        factory = HmacClientFactory(config)

        with pytest.raises(KeyError, match="unknown-service"):
            factory.create_requests_session("unknown-service")

    def test_uses_effective_config_with_overrides(self) -> None:
        config = HmacConfig(
            shared_secret_base64=TEST_SECRET,
            signed_headers=SignedHeadersConfig.default(),
            targets={
                "my-service": HmacTargetConfig(
                    base_url="https://api.example.com",
                    shared_secret=OTHER_SECRET,
                    signed_headers=SignedHeadersConfig.none(),
                ),
            },
        )
        factory = HmacClientFactory(config)

        client = factory.create_requests_session("my-service")

        auth = client.session.auth
        assert isinstance(auth, HmacAuth)
        # Should use the target-specific secret, not the global one
        assert auth.config.shared_secret_base64 == OTHER_SECRET
        # Should use the target-specific signed_headers override
        assert auth.config.signed_headers == SignedHeadersConfig.none()
        client.close()


class TestRoundTrip:
    """Integration-style: sign with HmacAuth, validate with validate_request."""

    def test_get_round_trip(self) -> None:
        config = _make_config()
        auth = HmacAuth(config)
        prepared = _make_prepared_request(
            method="GET",
            url="https://api.example.com/v1/widgets?active=true",
        )

        signed = auth(prepared)

        # Server-side validation should pass
        validate_request(
            config,
            method="GET",
            path="/v1/widgets?active=true",
            body="",
            signature_header=signed.headers[SIGNATURE_HEADER],
            timestamp_header=signed.headers[TIMESTAMP_HEADER],
            request_headers=dict(signed.headers),
        )

    def test_post_round_trip(self) -> None:
        config = _make_config()
        auth = HmacAuth(config)
        body = '{"name": "test-widget", "count": 42}'
        prepared = _make_prepared_request(
            method="POST",
            url="https://api.example.com/v1/widgets",
            body=body,
        )

        signed = auth(prepared)

        validate_request(
            config,
            method="POST",
            path="/v1/widgets",
            body=body,
            signature_header=signed.headers[SIGNATURE_HEADER],
            timestamp_header=signed.headers[TIMESTAMP_HEADER],
            request_headers=dict(signed.headers),
        )

    def test_wrong_secret_fails_validation(self) -> None:
        sign_config = _make_config(secret=TEST_SECRET)
        verify_config = _make_config(secret=OTHER_SECRET)

        auth = HmacAuth(sign_config)
        prepared = _make_prepared_request()

        signed = auth(prepared)

        from hardenlabs_hmac.exceptions import HmacValidationError

        with pytest.raises(HmacValidationError, match="signature"):
            validate_request(
                verify_config,
                method="GET",
                path="/v1/items?page=1",
                body="",
                signature_header=signed.headers[SIGNATURE_HEADER],
                timestamp_header=signed.headers[TIMESTAMP_HEADER],
                request_headers=dict(signed.headers),
            )

    def test_signed_headers_round_trip(self) -> None:
        """Custom headers included in signed_headers survive the round trip."""
        config = HmacConfig(
            shared_secret_base64=TEST_SECRET,
            signed_headers=SignedHeadersConfig(
                include_authorization=True,
                include_x_headers=True,
            ),
        )
        auth = HmacAuth(config)
        prepared = _make_prepared_request(
            method="GET",
            url="https://api.example.com/v1/items",
            headers={"Authorization": "Bearer tok123", "X-Request-Id": "abc"},
        )

        signed = auth(prepared)

        assert SIGNED_HEADERS_HEADER in signed.headers

        validate_request(
            config,
            method="GET",
            path="/v1/items",
            body="",
            signature_header=signed.headers[SIGNATURE_HEADER],
            timestamp_header=signed.headers[TIMESTAMP_HEADER],
            request_headers=dict(signed.headers),
        )
