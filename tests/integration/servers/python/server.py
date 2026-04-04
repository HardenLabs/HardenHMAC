"""Python HMAC integration test server."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

# Ensure the SDK is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "sdk" / "python" / "src"))

from hardenlabs_hmac.config import HmacClientIdentity, HmacConfig
from hardenlabs_hmac.middleware.depends import HmacValidate, install_hmac_exception_handler
from hardenlabs_hmac.middleware.fastapi import HardenHmacMiddleware

# Load config.json
config_path = Path(__file__).resolve().parents[2] / "config.json"
with open(config_path) as f:
    raw_config = json.load(f)

hmac_mode = os.environ.get("HMAC_MODE")

use_global_middleware = False

if hmac_mode == "shared":
    port = raw_config["sharedPorts"]["python"]
    hmac_config = HmacConfig(shared_secret_base64=raw_config["sharedSecret"])
elif hmac_mode == "resolver":
    port = raw_config["resolverPorts"]["python"]

    # Build lookup from config
    client_secrets: dict[str, str] = {}
    for client_name, client_data in raw_config["clients"].items():
        client_secrets[client_name] = client_data["sharedSecret"]

    hmac_config = HmacConfig(shared_secret_base64=raw_config["sharedSecret"])

    async def secret_resolver(request: Request) -> str | None:
        client_id = request.headers.get("x-harden-client-id")
        if client_id and client_id in client_secrets:
            return client_secrets[client_id]
        return None

elif hmac_mode == "global":
    port = raw_config["globalPorts"]["python"]
    use_global_middleware = True

    # Build Clients dictionary
    clients = {}
    for client_name, client_data in raw_config["clients"].items():
        clients[client_name] = HmacClientIdentity(shared_secret=client_data["sharedSecret"])

    hmac_config = HmacConfig(
        shared_secret_base64=raw_config["sharedSecret"],
        clients=clients,
    )
    secret_resolver = None
else:
    port = raw_config["ports"]["python"]

    # Build Clients dictionary
    clients = {}
    for client_name, client_data in raw_config["clients"].items():
        clients[client_name] = HmacClientIdentity(shared_secret=client_data["sharedSecret"])

    hmac_config = HmacConfig(
        shared_secret_base64=raw_config["sharedSecret"],
        clients=clients,
    )
    secret_resolver = None

app = FastAPI()

if use_global_middleware:
    # Global mode: ALL routes are protected by HMAC middleware
    app.add_middleware(HardenHmacMiddleware, config=hmac_config)

    @app.get("/api/hello")
    async def hello() -> dict:
        return {"message": "hello from python"}

    @app.post("/api/echo")
    async def echo(request: Request) -> JSONResponse:
        body_bytes = await request.body()
        body_text = body_bytes.decode("utf-8")
        try:
            parsed = json.loads(body_text)
        except (json.JSONDecodeError, ValueError):
            parsed = body_text
        return JSONResponse(content={"echo": parsed, "language": "python"})

    # In global mode, /health is also protected
    @app.get("/health")
    async def health() -> dict:
        return {"status": "healthy", "language": "python"}

else:
    # Per-route mode: only protected endpoints use HmacValidate dependency
    if hmac_mode == "resolver":
        hmac_validate = HmacValidate(hmac_config, secret_resolver=secret_resolver)
    else:
        hmac_validate = HmacValidate(hmac_config)

    install_hmac_exception_handler(app)

    @app.get("/api/hello")
    async def hello(_hmac: None = Depends(hmac_validate)) -> dict:
        return {"message": "hello from python"}

    @app.post("/api/echo")
    async def echo(request: Request, _hmac: None = Depends(hmac_validate)) -> JSONResponse:
        body_bytes = await request.body()
        body_text = body_bytes.decode("utf-8")
        try:
            parsed = json.loads(body_text)
        except (json.JSONDecodeError, ValueError):
            parsed = body_text
        return JSONResponse(content={"echo": parsed, "language": "python"})

    # Unprotected endpoint — no dependency, no HMAC required
    @app.get("/health")
    async def health() -> dict:
        return {"status": "healthy", "language": "python"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
