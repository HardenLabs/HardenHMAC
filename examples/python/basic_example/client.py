"""Basic client that signs requests with HardenHMAC."""

import base64
import json

import httpx

from hardenlabs_hmac.client import sign_request_headers
from hardenlabs_hmac.config import HmacConfig, SignedHeadersConfig

# Same shared secret as the server
shared_secret = base64.b64encode(b"my-shared-secret-key-32-bytes!!").decode()

config = HmacConfig(
    shared_secret_base64=shared_secret,
    signed_headers=SignedHeadersConfig.default(),
)

BASE_URL = "http://localhost:8000"


def signed_get(path: str) -> httpx.Response:
    """Send a signed GET request."""
    headers = sign_request_headers(config, "GET", path)
    return httpx.get(f"{BASE_URL}{path}", headers=headers)


def signed_post(path: str, data: dict) -> httpx.Response:
    """Send a signed POST request."""
    body = json.dumps(data)
    existing_headers = {"Content-Type": "application/json"}
    hmac_headers = sign_request_headers(
        config, "POST", path, body, existing_headers
    )
    all_headers = {**existing_headers, **hmac_headers}
    return httpx.post(f"{BASE_URL}{path}", content=body, headers=all_headers)


if __name__ == "__main__":
    print("GET /api/hello:")
    resp = signed_get("/api/hello")
    print(f"  Status: {resp.status_code}")
    print(f"  Body:   {resp.json()}")

    print("\nPOST /api/echo:")
    resp = signed_post("/api/echo", {"greeting": "Hello, world!"})
    print(f"  Status: {resp.status_code}")
    print(f"  Body:   {resp.json()}")
