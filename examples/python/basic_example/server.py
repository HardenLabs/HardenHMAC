"""Basic FastAPI server with HardenHMAC validation."""

import base64

from fastapi import FastAPI
from hardenlabs_hmac.config import HmacConfig, SignedHeadersConfig
from hardenlabs_hmac.middleware.fastapi import HardenHmacMiddleware

# Shared secret (in production, load from environment/secrets manager)
shared_secret = base64.b64encode(b"my-shared-secret-key-32-bytes!!").decode()

config = HmacConfig(
    shared_secret_base64=shared_secret,
    signed_headers=SignedHeadersConfig.default(),
    timestamp_tolerance_seconds=30,
)

app = FastAPI()
app.add_middleware(HardenHmacMiddleware, config=config)


@app.get("/api/hello")
async def hello():
    return {"message": "Hello from HardenHMAC!"}


@app.post("/api/echo")
async def echo(body: dict):
    return {"echo": body}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
