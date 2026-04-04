"""Python multi-target HMAC integration test client — exercises HmacClientFactory."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "sdk" / "python" / "src"))

from hardenlabs_hmac.client import HmacClientFactory, sign_request_headers
from hardenlabs_hmac.config import CLIENT_ID_HEADER, HmacConfig, HmacTargetConfig

config_path = Path(__file__).resolve().parents[2] / "config.json"
with open(config_path) as f:
    raw_config = json.load(f)

# Build targets from config
targets = {}
for name, t in raw_config["multiTargetTests"]["targets"].items():
    targets[name] = HmacTargetConfig(base_url=t["baseUrl"], shared_secret=t["sharedSecret"])

config = HmacConfig(targets=targets)
factory = HmacClientFactory(config)
results: list[str] = []

# 1. Multi-target: call each server with correct target-specific secret
for target_name, target in targets.items():
    server_name = target_name.replace("-client", "-server")
    try:
        with factory.create_sync_client(target_name) as client:
            resp = client.get("/api/hello")
            if resp.status_code == 200:
                results.append(f"PASS python-multitarget -> {server_name} GET /api/hello ({resp.status_code})")
            else:
                results.append(f"FAIL python-multitarget -> {server_name} GET /api/hello ({resp.status_code}): {resp.text}")

            post_body = json.dumps({"from": target_name, "test": "multitarget"})
            resp = client.post("/api/echo", content=post_body, headers={"Content-Type": "application/json"})
            if resp.status_code == 200:
                results.append(f"PASS python-multitarget -> {server_name} POST /api/echo ({resp.status_code})")
            else:
                results.append(f"FAIL python-multitarget -> {server_name} POST /api/echo ({resp.status_code}): {resp.text}")
    except Exception as e:
        if "ConnectError" in type(e).__name__ or "ConnectionError" in type(e).__name__:
            results.append(f"SKIP python-multitarget -> {server_name} GET /api/hello (server not running)")
            results.append(f"SKIP python-multitarget -> {server_name} POST /api/echo (server not running)")
        else:
            results.append(f"FAIL python-multitarget -> {server_name} GET /api/hello (ERR): {e}")

# 2. Cross-client test: send as two different clients to the SAME server
# Pick python-server (port 9101) and send as both "csharp-client" and "go-client"
import httpx

cross_server = "python-server"
cross_base = raw_config["multiTargetTests"]["targets"]["python-client"]["baseUrl"]

for cross_id in ["csharp-client", "go-client"]:
    cross_secret = raw_config["multiTargetTests"]["targets"][cross_id]["sharedSecret"]
    cross_config = HmacConfig(shared_secret_base64=cross_secret)
    try:
        headers: dict[str, str] = {CLIENT_ID_HEADER: cross_id}
        sig_headers = sign_request_headers(cross_config, "GET", "/api/hello", "", headers)
        headers.update(sig_headers)
        resp = httpx.get(f"{cross_base}/api/hello", headers=headers)
        if resp.status_code == 200:
            results.append(f"PASS python-multitarget/cross({cross_id}) -> {cross_server} GET /api/hello ({resp.status_code})")
        else:
            results.append(f"FAIL python-multitarget/cross({cross_id}) -> {cross_server} GET /api/hello ({resp.status_code}): {resp.text}")
    except httpx.ConnectError:
        results.append(f"SKIP python-multitarget/cross({cross_id}) -> {cross_server} GET /api/hello (server not running)")
    except Exception as e:
        results.append(f"FAIL python-multitarget/cross({cross_id}) -> {cross_server} GET /api/hello (ERR): {e}")

# 3. Negative test: wrong secret for client ID -> expect 4xx
wrong_secret = raw_config["multiTargetTests"]["targets"]["go-client"]["sharedSecret"]
wrong_config = HmacConfig(shared_secret_base64=wrong_secret)  # go-client secret
try:
    headers = {CLIENT_ID_HEADER: "csharp-client"}  # claim to be csharp-client
    sig_headers = sign_request_headers(wrong_config, "GET", "/api/hello", "", headers)
    headers.update(sig_headers)
    resp = httpx.get(f"{cross_base}/api/hello", headers=headers)
    if 400 <= resp.status_code < 500:
        results.append(f"PASS python-multitarget/wrong-secret -> {cross_server} GET /api/hello ({resp.status_code})")
    else:
        results.append(f"FAIL python-multitarget/wrong-secret -> {cross_server} GET /api/hello (expected 4xx, got {resp.status_code}): {resp.text}")
except httpx.ConnectError:
    results.append(f"SKIP python-multitarget/wrong-secret -> {cross_server} GET /api/hello (server not running)")
except Exception as e:
    results.append(f"FAIL python-multitarget/wrong-secret -> {cross_server} GET /api/hello (ERR): {e}")

for r in results:
    print(r)
sys.exit(1 if any(r.startswith("FAIL") for r in results) else 0)
