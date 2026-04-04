"""Python HMAC integration test client — exercises both httpx and requests adapters."""
from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import httpx
import requests

# Ensure the SDK is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "sdk" / "python" / "src"))

from hardenlabs_hmac.client import sign_request_headers, HmacAuth
from hardenlabs_hmac.config import CLIENT_ID_HEADER, HmacConfig, SignedHeadersConfig

CLIENT_ID = "python-client"

# Load config.json
config_path = Path(__file__).resolve().parents[2] / "config.json"
with open(config_path) as f:
    raw_config = json.load(f)

my_secret = raw_config["clients"][CLIENT_ID]["sharedSecret"]
ports = raw_config["ports"]
shared_secret = raw_config["sharedSecret"]
resolver_ports = raw_config.get("resolverPorts", {})
global_ports = raw_config.get("globalPorts", {})
servers = ["csharp", "python", "typescript", "go"]

hmac_config = HmacConfig(shared_secret_base64=my_secret)
none_hmac_config = HmacConfig(shared_secret_base64=my_secret, signed_headers=SignedHeadersConfig.none())

results: list[str] = []


def make_request_httpx(
    tag: str, server_name: str, base_url: str, method: str, path: str, body: str | None = None,
    config: HmacConfig | None = None,
    client_id: str | None = CLIENT_ID,
    timestamp: int | None = None,
    expect_4xx: bool = False,
) -> None:
    """Sign and send a request using httpx."""
    cfg = config or hmac_config
    try:
        headers: dict[str, str] = {}
        if client_id:
            headers[CLIENT_ID_HEADER] = client_id
        if body is not None and body != "":
            headers["Content-Type"] = "application/json"
        sig_headers = sign_request_headers(cfg, method, path, body if body is not None else "", headers, timestamp=timestamp)
        headers.update(sig_headers)

        if method == "GET":
            resp = httpx.get(f"{base_url}{path}", headers=headers)
        else:
            resp = httpx.post(f"{base_url}{path}", content=body, headers=headers)

        if expect_4xx:
            if 400 <= resp.status_code < 500:
                results.append(f"PASS {tag} -> {server_name} {method} {path} ({resp.status_code})")
            else:
                results.append(f"FAIL {tag} -> {server_name} {method} {path} (expected 4xx, got {resp.status_code}): {resp.text}")
        elif resp.status_code == 200:
            results.append(f"PASS {tag} -> {server_name} {method} {path} ({resp.status_code})")
        else:
            results.append(f"FAIL {tag} -> {server_name} {method} {path} ({resp.status_code}): {resp.text}")
    except httpx.ConnectError:
        results.append(f"SKIP {tag} -> {server_name} {method} {path} (server not running)")
    except Exception as e:
        results.append(f"FAIL {tag} -> {server_name} {method} {path} (ERR): {e}")


def make_request_requests(
    tag: str, server_name: str, base_url: str, method: str, path: str, body: str | None = None,
    config: HmacConfig | None = None,
    client_id: str | None = CLIENT_ID,
    expect_4xx: bool = False,
) -> None:
    """Sign and send a request using requests + HmacAuth."""
    cfg = config or hmac_config
    try:
        auth = HmacAuth(cfg, client_id=client_id)
        url = f"{base_url}{path}"
        headers: dict[str, str] = {}
        if body is not None and body != "":
            headers["Content-Type"] = "application/json"

        if method == "GET":
            resp = requests.get(url, auth=auth, headers=headers)
        else:
            resp = requests.post(url, data=body, auth=auth, headers=headers)

        if expect_4xx:
            if 400 <= resp.status_code < 500:
                results.append(f"PASS {tag} -> {server_name} {method} {path} ({resp.status_code})")
            else:
                results.append(f"FAIL {tag} -> {server_name} {method} {path} (expected 4xx, got {resp.status_code}): {resp.text}")
        elif resp.status_code == 200:
            results.append(f"PASS {tag} -> {server_name} {method} {path} ({resp.status_code})")
        else:
            results.append(f"FAIL {tag} -> {server_name} {method} {path} ({resp.status_code}): {resp.text}")
    except requests.ConnectionError:
        results.append(f"SKIP {tag} -> {server_name} {method} {path} (server not running)")
    except Exception as e:
        results.append(f"FAIL {tag} -> {server_name} {method} {path} (ERR): {e}")


def make_request_plain(
    tag: str, server_name: str, base_url: str, method: str, path: str,
    expected_status: int = 200,
) -> None:
    """Send a request WITHOUT HMAC headers (plain httpx).

    If expected_status is 0, any 4xx status code is accepted.
    """
    try:
        if method == "GET":
            resp = httpx.get(f"{base_url}{path}")
        else:
            resp = httpx.post(f"{base_url}{path}")

        if expected_status == 0:
            ok = 400 <= resp.status_code < 500
        else:
            ok = resp.status_code == expected_status

        if ok:
            results.append(f"PASS {tag} -> {server_name} {method} {path} ({resp.status_code})")
        else:
            expected_str = "4xx" if expected_status == 0 else str(expected_status)
            results.append(
                f"FAIL {tag} -> {server_name} {method} {path} "
                f"(expected {expected_str}, got {resp.status_code}): {resp.text}"
            )
    except httpx.ConnectError:
        results.append(f"SKIP {tag} -> {server_name} {method} {path} (server not running)")
    except Exception as e:
        results.append(f"FAIL {tag} -> {server_name} {method} {path} (ERR): {e}")


for server in servers:
    port = ports.get(server)
    if port is None:
        continue
    server_name = f"{server}-server"
    base_url = f"http://localhost:{port}"
    post_body = json.dumps({"from": CLIENT_ID, "test": "integration"})

    # httpx adapter
    make_request_httpx("python-client/httpx", server_name, base_url, "GET", "/api/hello")
    make_request_httpx("python-client/httpx", server_name, base_url, "POST", "/api/echo", post_body)

    # requests adapter
    make_request_requests("python-client/requests", server_name, base_url, "GET", "/api/hello")
    make_request_requests("python-client/requests", server_name, base_url, "POST", "/api/echo", post_body)

    # Granular validation tests (plain requests, no HMAC)
    make_request_plain(CLIENT_ID, server_name, base_url, "GET", "/health", expected_status=200)
    make_request_plain(CLIENT_ID + "/nohmac", server_name, base_url, "GET", "/api/hello", expected_status=0)  # any 4xx

    # IT-3: Fallback secret (sign with sharedSecret, NO X-Harden-Client-Id)
    fallback_config = HmacConfig(shared_secret_base64=shared_secret)
    make_request_httpx(
        "python-client/httpx/fallback", server_name, base_url, "GET", "/api/hello",
        config=fallback_config, client_id=None,
    )
    make_request_requests(
        "python-client/requests/fallback", server_name, base_url, "GET", "/api/hello",
        config=fallback_config, client_id=None,
    )

    # IT-4: Unknown client rejection
    bogus_secret = base64.b64encode(b"wrong-secret-for-unknown-client!!!").decode()
    bogus_config = HmacConfig(shared_secret_base64=bogus_secret)
    make_request_httpx(
        "python-client/httpx/unknown-client", server_name, base_url, "GET", "/api/hello",
        config=bogus_config, client_id="nonexistent-client", expect_4xx=True,
    )
    make_request_requests(
        "python-client/requests/unknown-client", server_name, base_url, "GET", "/api/hello",
        config=bogus_config, client_id="nonexistent-client", expect_4xx=True,
    )

    # IT-5: Stale timestamp (300s in the past, servers have 30s tolerance)
    stale_ts = int(time.time()) - 300
    make_request_httpx(
        "python-client/httpx/stale-ts", server_name, base_url, "GET", "/api/hello",
        timestamp=stale_ts, expect_4xx=True,
    )
    # For requests adapter, we must sign manually since HmacAuth doesn't expose timestamp
    try:
        stale_headers: dict[str, str] = {CLIENT_ID_HEADER: CLIENT_ID}
        stale_sig = sign_request_headers(hmac_config, "GET", "/api/hello", "", stale_headers, timestamp=stale_ts)
        stale_headers.update(stale_sig)
        resp = requests.get(f"{base_url}/api/hello", headers=stale_headers)
        if 400 <= resp.status_code < 500:
            results.append(f"PASS python-client/requests/stale-ts -> {server_name} GET /api/hello ({resp.status_code})")
        else:
            results.append(f"FAIL python-client/requests/stale-ts -> {server_name} GET /api/hello (expected 4xx, got {resp.status_code}): {resp.text}")
    except requests.ConnectionError:
        results.append(f"SKIP python-client/requests/stale-ts -> {server_name} GET /api/hello (server not running)")
    except Exception as e:
        results.append(f"FAIL python-client/requests/stale-ts -> {server_name} GET /api/hello (ERR): {e}")

    # IT-8: Empty body POST
    make_request_httpx(
        "python-client/httpx/empty-body", server_name, base_url, "POST", "/api/echo", body="",
    )
    make_request_requests(
        "python-client/requests/empty-body", server_name, base_url, "POST", "/api/echo", body="",
    )

    # IT-9: Wrong SignedHeaders (client uses noneSignedHeadersConfig, server uses default)
    make_request_httpx(
        "python-client/httpx/wrong-headers", server_name, base_url, "GET", "/api/hello",
        config=none_hmac_config, expect_4xx=True,
    )
    make_request_requests(
        "python-client/requests/wrong-headers", server_name, base_url, "GET", "/api/hello",
        config=none_hmac_config, expect_4xx=True,
    )

    # IT-10: Query string
    make_request_httpx(
        "python-client/httpx/query", server_name, base_url, "GET", "/api/hello?foo=bar&baz=1",
    )
    make_request_requests(
        "python-client/requests/query", server_name, base_url, "GET", "/api/hello?foo=bar&baz=1",
    )

# ============================================================
# Shared-secret server tests
# ============================================================
shared_ports = raw_config.get("sharedPorts", {})
shared_hmac_config = HmacConfig(shared_secret_base64=shared_secret)

for server in servers:
    port = shared_ports.get(server)
    if port is None:
        continue
    server_name = f"{server}-shared"
    base_url = f"http://localhost:{port}"
    post_body = json.dumps({"from": CLIENT_ID, "test": "integration-shared"})

    # httpx adapter with shared secret
    make_request_httpx(
        "python-client/shared/httpx", server_name, base_url, "GET", "/api/hello",
        config=shared_hmac_config,
    )
    make_request_httpx(
        "python-client/shared/httpx", server_name, base_url, "POST", "/api/echo", post_body,
        config=shared_hmac_config,
    )

    # requests adapter with shared secret
    make_request_requests(
        "python-client/shared/requests", server_name, base_url, "GET", "/api/hello",
        config=shared_hmac_config,
    )
    make_request_requests(
        "python-client/shared/requests", server_name, base_url, "POST", "/api/echo", post_body,
        config=shared_hmac_config,
    )

# ============================================================
# Resolver server tests (IT-6)
# ============================================================
for server in servers:
    port = resolver_ports.get(server)
    if port is None:
        continue
    server_name = f"{server}-resolver"
    base_url = f"http://localhost:{port}"
    post_body = json.dumps({"from": CLIENT_ID, "test": "integration-resolver"})

    make_request_httpx("python-client/httpx", server_name, base_url, "GET", "/api/hello")
    make_request_httpx("python-client/httpx", server_name, base_url, "POST", "/api/echo", post_body)
    make_request_requests("python-client/requests", server_name, base_url, "GET", "/api/hello")
    make_request_requests("python-client/requests", server_name, base_url, "POST", "/api/echo", post_body)

# ============================================================
# Global middleware server tests (IT-7)
# ============================================================
for server in servers:
    port = global_ports.get(server)
    if port is None:
        continue
    server_name = f"{server}-global"
    base_url = f"http://localhost:{port}"
    post_body = json.dumps({"from": CLIENT_ID, "test": "integration-global"})

    # Signed requests should succeed
    make_request_httpx("python-client/httpx", server_name, base_url, "GET", "/api/hello")
    make_request_httpx("python-client/httpx", server_name, base_url, "POST", "/api/echo", post_body)
    make_request_requests("python-client/requests", server_name, base_url, "GET", "/api/hello")
    make_request_requests("python-client/requests", server_name, base_url, "POST", "/api/echo", post_body)

    # Signed GET /health should succeed (global mode protects ALL routes)
    make_request_httpx("python-client/httpx", server_name, base_url, "GET", "/health")
    make_request_requests("python-client/requests", server_name, base_url, "GET", "/health")

    # Unsigned GET /health should be rejected (global mode protects ALL routes)
    make_request_plain(CLIENT_ID + "/nohmac", server_name, base_url, "GET", "/health", expected_status=0)

for result in results:
    print(result)

sys.exit(1 if any(r.startswith("FAIL") for r in results) else 0)
