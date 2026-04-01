"""Tests for multi-client server-side resolution and client-id signing."""

import time
from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from hardenlabs_hmac.canonical import build_canonical_string
from hardenlabs_hmac.config import (
    HmacClientIdentity,
    HmacConfig,
    SignedHeadersConfig,
)
from hardenlabs_hmac.middleware.fastapi import HardenHmacMiddleware
from hardenlabs_hmac.signing import sign

DEFAULT_SECRET = "ZGVmYXVsdC1zZWNyZXQta2V5LTMyLWJ5dGVzISEhISE="
ORDER_SECRET = "b3JkZXJzLXNlY3JldC1rZXktMzItYnl0ZXMhISEhIQ=="
PAYMENT_SECRET = "cGF5bWVudHMtc2VjcmV0LWtleS0zMi1ieXRlcyEhISE="


def _sign_for_secret(
    secret: str,
    method: str,
    path: str,
    body: str = "",
    request_headers: dict[str, str] | None = None,
) -> tuple[str, str]:
    now = int(time.time())
    canonical = build_canonical_string(
        method, path, body, now, SignedHeadersConfig.none(), request_headers
    )
    return sign(secret, canonical), str(now)


# -- Multi-client via config.clients --


@pytest.fixture()
def multi_client_app() -> FastAPI:
    config = HmacConfig(
        shared_secret_base64=DEFAULT_SECRET,
        signed_headers=SignedHeadersConfig.none(),
        timestamp_tolerance_seconds=30,
        clients={
            "order-service": HmacClientIdentity(shared_secret=ORDER_SECRET),
            "payment-service": HmacClientIdentity(shared_secret=PAYMENT_SECRET),
        },
    )
    app = FastAPI()
    app.add_middleware(HardenHmacMiddleware, config=config)

    @app.get("/api/test")
    async def get_test() -> dict[str, str]:
        return {"message": "ok"}

    return app


@pytest.fixture()
def multi_client(multi_client_app: FastAPI) -> TestClient:
    return TestClient(multi_client_app, raise_server_exceptions=False)


class TestMultiClientResolution:
    def test_known_client_valid_signature(self, multi_client: TestClient) -> None:
        sig, ts = _sign_for_secret(
            ORDER_SECRET, "GET", "/api/test",
            request_headers={"X-Harden-Client-Id": "order-service"},
        )
        response = multi_client.get(
            "/api/test",
            headers={
                "X-Harden-Client-Id": "order-service",
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": ts,
            },
        )
        assert response.status_code == 200

    def test_known_client_wrong_secret_returns_401(
        self, multi_client: TestClient
    ) -> None:
        sig, ts = _sign_for_secret(DEFAULT_SECRET, "GET", "/api/test")
        response = multi_client.get(
            "/api/test",
            headers={
                "X-Harden-Client-Id": "order-service",
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": ts,
            },
        )
        assert response.status_code == 401

    def test_unknown_client_returns_401_unknown_client(
        self, multi_client: TestClient
    ) -> None:
        sig, ts = _sign_for_secret(DEFAULT_SECRET, "GET", "/api/test")
        response = multi_client.get(
            "/api/test",
            headers={
                "X-Harden-Client-Id": "unknown-service",
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": ts,
            },
        )
        assert response.status_code == 401
        body = response.json()
        assert body["error"] == "unknown_client"

    def test_no_client_id_falls_back_to_default(
        self, multi_client: TestClient
    ) -> None:
        sig, ts = _sign_for_secret(DEFAULT_SECRET, "GET", "/api/test")
        response = multi_client.get(
            "/api/test",
            headers={
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": ts,
            },
        )
        assert response.status_code == 200

    def test_payment_client_uses_payment_secret(
        self, multi_client: TestClient
    ) -> None:
        sig, ts = _sign_for_secret(
            PAYMENT_SECRET, "GET", "/api/test",
            request_headers={"X-Harden-Client-Id": "payment-service"},
        )
        response = multi_client.get(
            "/api/test",
            headers={
                "X-Harden-Client-Id": "payment-service",
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": ts,
            },
        )
        assert response.status_code == 200


# -- secretResolver takes priority over clients --


@pytest.fixture()
def resolver_with_clients_app() -> FastAPI:
    resolver_secret = "cmVzb2x2ZXItc2VjcmV0LWtleS0zMi1ieXRlcyEhIQ=="

    async def resolver(request: Request) -> Optional[str]:
        if request.headers.get("x-use-resolver") == "true":
            return resolver_secret
        return None

    config = HmacConfig(
        shared_secret_base64=DEFAULT_SECRET,
        signed_headers=SignedHeadersConfig.none(),
        timestamp_tolerance_seconds=30,
        clients={
            "order-service": HmacClientIdentity(shared_secret=ORDER_SECRET),
        },
    )
    app = FastAPI()
    app.add_middleware(
        HardenHmacMiddleware, config=config, secret_resolver=resolver
    )

    @app.get("/api/test")
    async def get_test() -> dict[str, str]:
        return {"message": "ok"}

    return app


@pytest.fixture()
def resolver_with_clients(resolver_with_clients_app: FastAPI) -> TestClient:
    return TestClient(resolver_with_clients_app, raise_server_exceptions=False)


class TestResolverPriority:
    def test_resolver_wins_over_clients(
        self, resolver_with_clients: TestClient
    ) -> None:
        resolver_secret = "cmVzb2x2ZXItc2VjcmV0LWtleS0zMi1ieXRlcyEhIQ=="
        sig, ts = _sign_for_secret(
            resolver_secret, "GET", "/api/test",
            request_headers={
                "X-Harden-Client-Id": "order-service",
                "X-Use-Resolver": "true",
            },
        )
        response = resolver_with_clients.get(
            "/api/test",
            headers={
                "X-Harden-Client-Id": "order-service",
                "X-Use-Resolver": "true",
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": ts,
            },
        )
        assert response.status_code == 200

    def test_clients_used_when_resolver_returns_none(
        self, resolver_with_clients: TestClient
    ) -> None:
        sig, ts = _sign_for_secret(
            ORDER_SECRET, "GET", "/api/test",
            request_headers={"X-Harden-Client-Id": "order-service"},
        )
        response = resolver_with_clients.get(
            "/api/test",
            headers={
                "X-Harden-Client-Id": "order-service",
                "X-Harden-Signature": sig,
                "X-Harden-Timestamp": ts,
            },
        )
        assert response.status_code == 200


# -- Env loading of clients --


class TestEnvLoaderClients:
    def test_clients_from_env(self) -> None:
        env = {
            "HARDEN_HMAC_SHARED_SECRET_BASE64": DEFAULT_SECRET,
            "HARDEN_HMAC_CLIENTS__ORDER_SERVICE__SHARED_SECRET": ORDER_SECRET,
            "HARDEN_HMAC_CLIENTS__PAYMENT_SERVICE__SHARED_SECRET": PAYMENT_SECRET,
        }
        config = HmacConfig.from_env(env=env)
        assert "order-service" in config.clients
        assert config.clients["order-service"].shared_secret == ORDER_SECRET
        assert "payment-service" in config.clients
        assert config.clients["payment-service"].shared_secret == PAYMENT_SECRET
