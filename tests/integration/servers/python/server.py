"""Python HMAC integration test server."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

# Ensure the SDK is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "sdk" / "python" / "src"))

from hardenlabs_hmac.config import HmacClientIdentity, HmacConfig
from hardenlabs_hmac.middleware.depends import HmacValidate, install_hmac_exception_handler

# Load config.json
config_path = Path(__file__).resolve().parents[2] / "config.json"
with open(config_path) as f:
    raw_config = json.load(f)

port = raw_config["ports"]["python"]

# Build Clients dictionary
clients = {}
for client_name, client_data in raw_config["clients"].items():
    clients[client_name] = HmacClientIdentity(shared_secret=client_data["sharedSecret"])

hmac_config = HmacConfig(clients=clients)
hmac_validate = HmacValidate(hmac_config)

app = FastAPI()
install_hmac_exception_handler(app)


# Protected endpoints — require HmacValidate dependency
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
