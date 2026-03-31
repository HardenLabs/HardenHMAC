"""Tests for FastAPI/Starlette HardenHMAC middleware."""

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

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
