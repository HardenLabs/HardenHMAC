"""FastAPI server with HardenHMAC validation — single-secret, multi-client, and multi-tenant modes."""

import base64
from typing import Optional

from fastapi import FastAPI
from starlette.requests import Request

from hardenlabs_hmac.config import HmacClientIdentity, HmacConfig, SignedHeadersConfig
from hardenlabs_hmac.middleware.fastapi import HardenHmacMiddleware

# Secrets (in production, load from environment/secrets manager)
default_secret = base64.b64encode(b"my-shared-secret-key-32-bytes!!").decode()
orders_secret = base64.b64encode(b"orders-secret-key-32-bytes!!!!!").decode()
payments_secret = base64.b64encode(b"payments-secret-key-32-bytes!!").decode()


# ── Option A: Multi-client server with named clients ──
# Each client identifies itself via X-Harden-Client-Id header.
# The middleware looks up the secret from the Clients dictionary.
multi_client_config = HmacConfig(
    shared_secret_base64=default_secret,  # fallback when no client ID
    signed_headers=SignedHeadersConfig.default(),
    timestamp_tolerance_seconds=30,
    clients={
        "order-service": HmacClientIdentity(shared_secret=orders_secret),
        "payment-service": HmacClientIdentity(shared_secret=payments_secret),
    },
)

simple_app = FastAPI()
simple_app.add_middleware(HardenHmacMiddleware, config=multi_client_config)


@simple_app.get("/api/hello")
async def hello() -> dict[str, str]:
    return {"message": "Hello from HardenHMAC!"}


@simple_app.post("/api/echo")
async def echo(body: dict) -> dict:
    return {"echo": body}


# ── Option B: Multi-tenant server with secret resolver ──
TENANT_SECRETS = {
    "tenant-a": base64.b64encode(b"tenant-a-secret-key-32-bytes!!").decode(),
    "tenant-b": base64.b64encode(b"tenant-b-secret-key-32-bytes!!").decode(),
}


async def resolve_tenant_secret(request: Request) -> Optional[str]:
    """Look up the shared secret by X-Client-Id header."""
    client_id = request.headers.get("x-client-id")
    if client_id and client_id in TENANT_SECRETS:
        return TENANT_SECRETS[client_id]
    return None  # fall back to config.shared_secret_base64


multi_tenant_app = FastAPI()
multi_tenant_app.add_middleware(
    HardenHmacMiddleware,
    config=config,
    secret_resolver=resolve_tenant_secret,
)


@multi_tenant_app.get("/api/hello")
async def mt_hello() -> dict[str, str]:
    return {"message": "Hello from multi-tenant HardenHMAC!"}


if __name__ == "__main__":
    import uvicorn

    # Run simple server by default; change to multi_tenant_app for multi-tenant mode
    uvicorn.run(simple_app, host="0.0.0.0", port=8000)
