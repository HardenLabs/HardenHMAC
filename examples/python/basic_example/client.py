"""Client that signs requests with HardenHMAC using the multi-target factory."""

import base64
import json

from hardenlabs_hmac.client import HmacClientFactory
from hardenlabs_hmac.config import HmacConfig, HmacTargetConfig, SignedHeadersConfig

# Same secrets as the server — in production, load from environment/secrets manager
orders_secret = base64.b64encode(b"orders-secret-key-32-bytes!!!!!").decode()
payments_secret = base64.b64encode(b"payments-secret-key-32-bytes!!").decode()

config = HmacConfig(
    signed_headers=SignedHeadersConfig.default(),
    targets={
        "order-service": HmacTargetConfig(
            base_url="http://localhost:8000",
            shared_secret=orders_secret,
        ),
        "payment-service": HmacTargetConfig(
            base_url="http://localhost:8000",
            shared_secret=payments_secret,
            timestamp_tolerance_seconds=60,
        ),
    },
)

factory = HmacClientFactory(config)


def main() -> None:
    # Each client has base_url and signing pre-configured from the target
    with factory.create_sync_client("order-service") as orders:
        resp = orders.get("/api/hello")
        print(f"GET order-service /api/hello: {resp.status_code} {resp.json()}")

    with factory.create_sync_client("payment-service") as payments:
        body = json.dumps({"amount": 100})
        resp = payments.post(
            "/api/echo",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        print(f"POST payment-service /api/echo: {resp.status_code} {resp.json()}")


if __name__ == "__main__":
    main()
