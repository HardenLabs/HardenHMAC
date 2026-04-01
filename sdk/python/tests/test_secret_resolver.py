"""Tests for middleware secret_resolver callback."""

import time
from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from hardenlabs_hmac.canonical import build_canonical_string
from hardenlabs_hmac.config import HmacConfig, SignedHeadersConfig
from hardenlabs_hmac.middleware.fastapi import HardenHmacMiddleware
from hardenlabs_hmac.signing import sign

DEFAULT_SECRET = "ZGVmYXVsdC1zZWNyZXQta2V5LTMyLWJ5dGVzISEhISE="
TENANT_A_SECRET = "dGVuYW50LWEtc2VjcmV0LWtleS0zMi1ieXRlcyEhIQ=="
TENANT_B_SECRET = "dGVuYW50LWItc2VjcmV0LWtleS0zMi1ieXRlcyEhIQ=="


async def _secret_resolver(request: Request) -> Optional[str]:
    """Look up secret by X-Client-Id header."""
    client_id = request.headers.get("x-client-id")
    if client_id == "tenant-a":
        return TENANT_A_SECRET
    if client_id == "tenant-b":
        return TENANT_B_SECRET
    return None  # fall back to config default


@pytest.fixture()
def resolver_app() -> FastAPI:
    """Create a FastAPI app with secret resolver middleware."""
    config = HmacConfig(
        shared_secret_base64=DEFAULT_SECRET,
        signed_headers=SignedHeadersConfig.none(),
        timestamp_tolerance_seconds=30,
    )
    application = FastAPI()
    application.add_middleware(
        HardenHmacMiddleware,
        config=config,
        secret_resolver=_secret_resolver,
    )

    @application.get("/api/test")
    async def get_test() -> dict[str, str]:
        return {"message": "ok"}

    return application


@pytest.fixture()
def resolver_client(resolver_app: FastAPI) -> TestClient:
    return TestClient(resolver_app, raise_server_exceptions=False)


def _sign_for_secret(
    secret: str, method: str, path: str, body: str = ""
) -> tuple[str, str]:
    """Sign a request with the given secret, returning (signature, timestamp_str)."""
    now = int(time.time())
    canonical = build_canonical_string(
        method, path, body, now, SignedHeadersConfig.none()
    )
    return sign(secret, canonical), str(now)


class TestSecretResolver:
    def test_tenant_a_valid_signature(self, resolver_client: TestClient) -> None:
        sig, ts = _sign_for_secret(TENANT_A_SECRET, "GET", "/api/test")
        response = resolver_client.get(
            "/api/test",
            headers={
                "X-Client-Id": "tenant-a",
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": ts,
            },
        )
        assert response.status_code == 200

    def test_tenant_b_valid_signature(self, resolver_client: TestClient) -> None:
        sig, ts = _sign_for_secret(TENANT_B_SECRET, "GET", "/api/test")
        response = resolver_client.get(
            "/api/test",
            headers={
                "X-Client-Id": "tenant-b",
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": ts,
            },
        )
        assert response.status_code == 200

    def test_wrong_secret_returns_401(self, resolver_client: TestClient) -> None:
        # Sign with default secret but send as tenant-a
        sig, ts = _sign_for_secret(DEFAULT_SECRET, "GET", "/api/test")
        response = resolver_client.get(
            "/api/test",
            headers={
                "X-Client-Id": "tenant-a",
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": ts,
            },
        )
        assert response.status_code == 401

    def test_no_client_id_falls_back_to_default(
        self, resolver_client: TestClient
    ) -> None:
        sig, ts = _sign_for_secret(DEFAULT_SECRET, "GET", "/api/test")
        response = resolver_client.get(
            "/api/test",
            headers={
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": ts,
            },
        )
        assert response.status_code == 200


class TestMiddlewareNoSecret:
    def test_no_secret_returns_401(self) -> None:
        """Middleware returns 401 when no secret is configured and resolver returns None."""
        config = HmacConfig(
            shared_secret_base64="",
            signed_headers=SignedHeadersConfig.none(),
        )

        async def null_resolver(request: Request) -> Optional[str]:
            return None

        app = FastAPI()
        app.add_middleware(
            HardenHmacMiddleware,
            config=config,
            secret_resolver=null_resolver,
        )

        @app.get("/api/test")
        async def get_test() -> dict[str, str]:
            return {"message": "ok"}

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/api/test",
            headers={
                "X-Harden-Signature": "a" * 64,
                "X-Harden-Timestamp": str(int(time.time())),
            },
        )
        assert response.status_code == 401
        assert response.json()["error"] == "no_secret"
