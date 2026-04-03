"""Tests for FastAPI/Starlette HardenHMAC middleware."""

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from hardenlabs_hmac.canonical import build_canonical_string
from hardenlabs_hmac.config import HmacConfig, SignedHeadersConfig
from hardenlabs_hmac.middleware.fastapi import HardenHmacMiddleware
from hardenlabs_hmac.signing import sign

TEST_SECRET = "dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24="


@pytest.fixture()
def app() -> FastAPI:
    """Create a FastAPI app with HardenHMAC middleware."""
    config = HmacConfig(
        shared_secret_base64=TEST_SECRET,
        signed_headers=SignedHeadersConfig.none(),
        timestamp_tolerance_seconds=30,
    )
    application = FastAPI()
    application.add_middleware(HardenHmacMiddleware, config=config)

    @application.get("/api/test")
    async def get_test() -> dict[str, str]:
        return {"message": "ok"}

    @application.post("/api/test")
    async def post_test() -> dict[str, str]:
        return {"message": "ok"}

    return application


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _sign_request(
    method: str, path: str, body: str, timestamp: int
) -> tuple[str, str]:
    """Compute signature and return (signature, timestamp_str)."""
    canonical = build_canonical_string(
        method, path, body, timestamp, SignedHeadersConfig.none()
    )
    return sign(TEST_SECRET, canonical), str(timestamp)


class TestMiddlewareValidRequest:
    def test_valid_get_passes(self, client: TestClient) -> None:
        now = int(time.time())
        sig, ts = _sign_request("GET", "/api/test", "", now)
        response = client.get(
            "/api/test",
            headers={
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": ts,
            },
        )
        assert response.status_code == 200
        assert response.json() == {"message": "ok"}

    def test_valid_post_with_body(self, client: TestClient) -> None:
        body = '{"name":"Alice"}'
        now = int(time.time())
        sig, ts = _sign_request("POST", "/api/test", body, now)
        response = client.post(
            "/api/test",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": ts,
            },
        )
        assert response.status_code == 200
        assert response.json() == {"message": "ok"}


class TestMiddlewareMissingSignature:
    def test_missing_signature_returns_400(self, client: TestClient) -> None:
        now = int(time.time())
        response = client.get(
            "/api/test",
            headers={"X-Harden-Timestamp": str(now)},
        )
        assert response.status_code == 400
        body = response.json()
        assert body["error"] == "missing_signature"

    def test_missing_timestamp_returns_400(self, client: TestClient) -> None:
        response = client.get(
            "/api/test",
            headers={"X-Harden-Signature": "a" * 64},
        )
        assert response.status_code == 400
        body = response.json()
        assert body["error"] == "missing_timestamp"


class TestMiddlewareInvalidSignature:
    def test_wrong_signature_returns_401(self, client: TestClient) -> None:
        now = int(time.time())
        response = client.get(
            "/api/test",
            headers={
                "X-Harden-Signature": "0" * 64,
                "X-Harden-Timestamp": str(now),
            },
        )
        assert response.status_code == 401
        body = response.json()
        assert body["error"] == "signature_invalid"


class TestMiddlewareExpiredTimestamp:
    def test_expired_timestamp_returns_401(self, client: TestClient) -> None:
        old_ts = int(time.time()) - 60
        sig, ts = _sign_request("GET", "/api/test", "", old_ts)
        response = client.get(
            "/api/test",
            headers={
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": ts,
            },
        )
        assert response.status_code == 401
        body = response.json()
        assert body["error"] == "timestamp_expired"


# ---------------------------------------------------------------------------
# Edge-case tests for middleware dispatch paths (fastapi.py)
# ---------------------------------------------------------------------------


class TestHmacMiddlewareEdgeCases:
    """Tests covering uncovered paths in the HardenHmacMiddleware dispatch."""

    def test_invalid_utf8_body_returns_400(self, client: TestClient) -> None:
        """Non-UTF-8 body should be rejected with invalid_body_encoding."""
        # Send raw bytes that are not valid UTF-8
        response = client.post(
            "/api/test",
            content=b"\x80\x81\x82\xff",
            headers={
                "Content-Type": "application/octet-stream",
                "X-Harden-Signature": "a" * 64,
                "X-Harden-Timestamp": str(int(time.time())),
            },
        )
        assert response.status_code == 400
        body = response.json()
        assert body["error"] == "invalid_body_encoding"

    def test_query_string_included_in_path(self) -> None:
        """Signature must cover path + query string."""
        config = HmacConfig(
            shared_secret_base64=TEST_SECRET,
            signed_headers=SignedHeadersConfig.none(),
            timestamp_tolerance_seconds=30,
        )
        app = FastAPI()
        app.add_middleware(HardenHmacMiddleware, config=config)

        @app.get("/api/search")
        async def search() -> dict[str, str]:
            return {"message": "ok"}

        tc = TestClient(app, raise_server_exceptions=False)

        now = int(time.time())
        # Sign with the full path including query
        sig, ts = _sign_request("GET", "/api/search?q=hello&page=2", "", now)
        response = tc.get(
            "/api/search?q=hello&page=2",
            headers={
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": ts,
            },
        )
        assert response.status_code == 200

    def test_query_string_mismatch_fails_validation(self) -> None:
        """Signing path without query but sending with query should fail."""
        config = HmacConfig(
            shared_secret_base64=TEST_SECRET,
            signed_headers=SignedHeadersConfig.none(),
            timestamp_tolerance_seconds=30,
        )
        app = FastAPI()
        app.add_middleware(HardenHmacMiddleware, config=config)

        @app.get("/api/search")
        async def search() -> dict[str, str]:
            return {"message": "ok"}

        tc = TestClient(app, raise_server_exceptions=False)

        now = int(time.time())
        # Sign without query
        sig, ts = _sign_request("GET", "/api/search", "", now)
        # Send with query - signature should not match
        response = tc.get(
            "/api/search?q=hello",
            headers={
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": ts,
            },
        )
        assert response.status_code == 401
        assert response.json()["error"] == "signature_invalid"

    def test_secret_resolver_callback(self) -> None:
        """Async secret resolver returns a secret that is used for validation."""
        resolver_secret = "cmVzb2x2ZXItc2VjcmV0LWtleS0zMi1ieXRlcyEhIQ=="

        async def resolver(request: Request) -> str | None:
            return resolver_secret

        config = HmacConfig(
            shared_secret_base64="",  # No default secret
            signed_headers=SignedHeadersConfig.none(),
            timestamp_tolerance_seconds=30,
        )
        app = FastAPI()
        app.add_middleware(
            HardenHmacMiddleware, config=config, secret_resolver=resolver
        )

        @app.get("/api/test")
        async def get_test() -> dict[str, str]:
            return {"message": "ok"}

        tc = TestClient(app, raise_server_exceptions=False)

        now = int(time.time())
        canonical = build_canonical_string(
            "GET", "/api/test", "", now, SignedHeadersConfig.none()
        )
        sig = sign(resolver_secret, canonical)

        response = tc.get(
            "/api/test",
            headers={
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": str(now),
            },
        )
        assert response.status_code == 200

    def test_client_id_lookup_succeeds(self) -> None:
        """X-Harden-Client-Id header resolves to the correct client secret."""
        from hardenlabs_hmac.config import HmacClientIdentity

        client_secret = "Y2xpZW50LXNlY3JldC1rZXktMzItYnl0ZXMhISEhIQ=="
        config = HmacConfig(
            shared_secret_base64="",
            signed_headers=SignedHeadersConfig.none(),
            timestamp_tolerance_seconds=30,
            clients={
                "service-a": HmacClientIdentity(shared_secret=client_secret),
            },
        )
        app = FastAPI()
        app.add_middleware(HardenHmacMiddleware, config=config)

        @app.get("/api/test")
        async def get_test() -> dict[str, str]:
            return {"message": "ok"}

        tc = TestClient(app, raise_server_exceptions=False)

        now = int(time.time())
        # The client-id header is included in signing when using signed headers
        # that include x-headers. With SignedHeadersConfig.none(), it's still
        # part of request_headers for the canonical string per _select_headers
        # which always includes x-harden-client-id.
        canonical = build_canonical_string(
            "GET",
            "/api/test",
            "",
            now,
            SignedHeadersConfig.none(),
            {"x-harden-client-id": "service-a"},
        )
        sig = sign(client_secret, canonical)

        response = tc.get(
            "/api/test",
            headers={
                "X-Harden-Client-Id": "service-a",
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": str(now),
            },
        )
        assert response.status_code == 200

    def test_unknown_client_returns_401(self) -> None:
        """X-Harden-Client-Id with unknown client returns 401 unknown_client."""
        from hardenlabs_hmac.config import HmacClientIdentity

        config = HmacConfig(
            shared_secret_base64=TEST_SECRET,
            signed_headers=SignedHeadersConfig.none(),
            timestamp_tolerance_seconds=30,
            clients={
                "known-service": HmacClientIdentity(shared_secret=TEST_SECRET),
            },
        )
        app = FastAPI()
        app.add_middleware(HardenHmacMiddleware, config=config)

        @app.get("/api/test")
        async def get_test() -> dict[str, str]:
            return {"message": "ok"}

        tc = TestClient(app, raise_server_exceptions=False)

        now = int(time.time())
        sig, ts = _sign_request("GET", "/api/test", "", now)
        response = tc.get(
            "/api/test",
            headers={
                "X-Harden-Client-Id": "ghost-service",
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": ts,
            },
        )
        assert response.status_code == 401
        assert response.json()["error"] == "unknown_client"

    def test_no_secret_configured_returns_401(self) -> None:
        """No secret anywhere (empty config, no resolver, no clients) returns no_secret."""
        config = HmacConfig(
            shared_secret_base64="",
            signed_headers=SignedHeadersConfig.none(),
        )
        app = FastAPI()
        app.add_middleware(HardenHmacMiddleware, config=config)

        @app.get("/api/test")
        async def get_test() -> dict[str, str]:
            return {"message": "ok"}

        tc = TestClient(app, raise_server_exceptions=False)

        response = tc.get(
            "/api/test",
            headers={
                "X-Harden-Signature": "a" * 64,
                "X-Harden-Timestamp": str(int(time.time())),
            },
        )
        assert response.status_code == 401
        assert response.json()["error"] == "no_secret"

    def test_duplicate_header_comma_joining(self) -> None:
        """Duplicate headers should be comma-joined per RFC 9110."""
        # This is hard to test via TestClient since httpx deduplicates headers.
        # We test it by verifying the middleware's dispatch path handles it
        # correctly with a signed request that includes headers in the canonical
        # string.
        config = HmacConfig(
            shared_secret_base64=TEST_SECRET,
            signed_headers=SignedHeadersConfig(
                include_authorization=False,
                include_x_headers=True,
            ),
            timestamp_tolerance_seconds=30,
        )
        app = FastAPI()
        app.add_middleware(HardenHmacMiddleware, config=config)

        @app.get("/api/test")
        async def get_test() -> dict[str, str]:
            return {"message": "ok"}

        tc = TestClient(app, raise_server_exceptions=False)

        now = int(time.time())
        # Sign with the expected comma-joined value
        request_headers = {"x-request-id": "abc, def"}
        canonical = build_canonical_string(
            "GET",
            "/api/test",
            "",
            now,
            config.signed_headers,
            request_headers,
        )
        sig = sign(TEST_SECRET, canonical)

        # Send with a single header containing the comma-joined value
        # (TestClient cannot send true duplicate headers, but the middleware's
        # comma-joining logic still runs on this single-value header)
        response = tc.get(
            "/api/test",
            headers={
                "X-Request-Id": "abc, def",
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": str(now),
                "X-Harden-Signed-Headers": "x-request-id",
            },
        )
        assert response.status_code == 200
