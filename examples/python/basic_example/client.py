"""Client that signs requests with HardenHMAC — single-secret and multi-target modes."""

import base64
import json

import httpx

from hardenlabs_hmac.client import HmacClientFactory, sign_request_headers
from hardenlabs_hmac.config import HmacConfig, HmacTargetConfig, SignedHeadersConfig

# ── Option A: Single-secret mode (backwards-compatible) ──
shared_secret = base64.b64encode(b"my-shared-secret-key-32-bytes!!").decode()

single_config = HmacConfig(
    shared_secret_base64=shared_secret,
    signed_headers=SignedHeadersConfig.default(),
)

# ── Option B: Multi-target mode ──
orders_secret = base64.b64encode(b"orders-secret-key-32-bytes!!!!!").decode()
payments_secret = base64.b64encode(b"payments-secret-key-32-bytes!!!").decode()

multi_config = HmacConfig(
    shared_secret_base64=shared_secret,  # server-side default
    targets={
        "order-service": HmacTargetConfig(
            base_url="http://localhost:8001",
            shared_secret=orders_secret,
        ),
        "payment-service": HmacTargetConfig(
            base_url="http://localhost:8002",
            shared_secret=payments_secret,
            timestamp_tolerance_seconds=60,
        ),
    },
)


def demo_single_secret() -> None:
    """Send signed requests using single-secret mode."""
    BASE_URL = "http://localhost:8000"

    print("=== Single-secret mode ===")
    headers = sign_request_headers(single_config, "GET", "/api/hello")
    resp = httpx.get(f"{BASE_URL}/api/hello", headers=headers)
    print(f"GET /api/hello: {resp.status_code} {resp.json()}")


def demo_multi_target() -> None:
    """Send signed requests using multi-target client factory."""
    print("\n=== Multi-target mode (factory) ===")
    factory = HmacClientFactory(multi_config)

    # Each client has the correct base_url and auto-signs with the target's secret
    with factory.create_sync_client("order-service") as orders:
        resp = orders.get("/api/orders")
        print(f"GET order-service /api/orders: {resp.status_code}")

    with factory.create_sync_client("payment-service") as payments:
        body = json.dumps({"amount": 100})
        resp = payments.post(
            "/api/charge",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        print(f"POST payment-service /api/charge: {resp.status_code}")


def demo_env_loading() -> None:
    """Load config from environment variables."""
    print("\n=== Environment variable loading ===")
    # In production, set these env vars:
    #   HARDEN_HMAC_TARGETS__ORDER_SERVICE__BASE_URL=https://orders.example.com
    #   HARDEN_HMAC_TARGETS__ORDER_SERVICE__SHARED_SECRET=base64-key
    # Then:
    #   config = HmacConfig.from_env()
    #   factory = HmacClientFactory(config)
    print("  Set HARDEN_HMAC_* env vars, then call HmacConfig.from_env()")


if __name__ == "__main__":
    demo_single_secret()
    # demo_multi_target()  # Uncomment when target servers are running
    demo_env_loading()
