"""Python HMAC integration test client."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

# Ensure the SDK is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "sdk" / "python" / "src"))

from hardenlabs_hmac.client import sign_request_headers
from hardenlabs_hmac.config import CLIENT_ID_HEADER, HmacConfig

CLIENT_ID = "python-client"

# Load config.json
config_path = Path(__file__).resolve().parents[2] / "config.json"
with open(config_path) as f:
    raw_config = json.load(f)

my_secret = raw_config["clients"][CLIENT_ID]["sharedSecret"]
ports = raw_config["ports"]

hmac_config = HmacConfig(shared_secret_base64=my_secret)

results: list[str] = []
servers = ["csharp", "python", "typescript", "go"]

for server in servers:
    port = ports.get(server)
    if port is None:
        continue

    server_name = f"{server}-server"
    base_url = f"http://localhost:{port}"

    # GET /api/hello
    try:
        path = "/api/hello"
        headers = {CLIENT_ID_HEADER: CLIENT_ID}
        sig_headers = sign_request_headers(hmac_config, "GET", path, "", headers)
        headers.update(sig_headers)

        resp = httpx.get(f"{base_url}{path}", headers=headers)
        status = resp.status_code
        if status == 200:
            results.append(f"PASS {CLIENT_ID} -> {server_name} GET /api/hello ({status})")
        else:
            results.append(f"FAIL {CLIENT_ID} -> {server_name} GET /api/hello ({status}): {resp.text}")
    except Exception as e:
        results.append(f"FAIL {CLIENT_ID} -> {server_name} GET /api/hello (ERR): {e}")

    # POST /api/echo
    try:
        path = "/api/echo"
        body = json.dumps({"from": CLIENT_ID, "test": "integration"})
        headers = {
            CLIENT_ID_HEADER: CLIENT_ID,
            "Content-Type": "application/json",
        }
        sig_headers = sign_request_headers(hmac_config, "POST", path, body, headers)
        headers.update(sig_headers)

        resp = httpx.post(f"{base_url}{path}", content=body, headers=headers)
        status = resp.status_code
        if status == 200:
            results.append(f"PASS {CLIENT_ID} -> {server_name} POST /api/echo ({status})")
        else:
            results.append(f"FAIL {CLIENT_ID} -> {server_name} POST /api/echo ({status}): {resp.text}")
    except Exception as e:
        results.append(f"FAIL {CLIENT_ID} -> {server_name} POST /api/echo (ERR): {e}")

for result in results:
    print(result)

sys.exit(1 if any(r.startswith("FAIL") for r in results) else 0)
