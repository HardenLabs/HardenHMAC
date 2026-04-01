# hardenlabs-hmac

Cross-language HMAC-SHA256 request signing with a defined canonical string format. Guaranteed identical signatures across C#, Python, TypeScript, and Go.

## Installation

```bash
pip install hardenlabs-hmac
pip install "hardenlabs-hmac[fastapi]"   # for FastAPI middleware
pip install "hardenlabs-hmac[requests]"  # for requests library support
```

## Quick Start — Server (FastAPI)

```python
from fastapi import FastAPI
from hardenlabs_hmac.config import HmacConfig, HmacClientIdentity, SignedHeadersConfig
from hardenlabs_hmac.middleware.fastapi import HardenHmacMiddleware

config = HmacConfig(
    signed_headers=SignedHeadersConfig.default(),
    timestamp_tolerance_seconds=30,
    clients={
        "order-service": HmacClientIdentity(shared_secret="orders-base64-secret"),
    },
)

app = FastAPI()
app.add_middleware(HardenHmacMiddleware, config=config)

@app.get("/api/hello")
async def hello():
    return {"message": "Authenticated!"}
```

## Quick Start — Client (httpx)

```python
from hardenlabs_hmac.client import HmacClientFactory
from hardenlabs_hmac.config import HmacConfig, HmacTargetConfig

config = HmacConfig(
    targets={
        "my-service": HmacTargetConfig(
            base_url="https://api.example.com",
            shared_secret="your-base64-encoded-secret",
        ),
    },
)

factory = HmacClientFactory(config)
with factory.create_sync_client("my-service") as client:
    response = client.get("/api/hello")  # automatically signed
```

## Quick Start — Client (requests)

```python
from hardenlabs_hmac.client import HmacClientFactory
from hardenlabs_hmac.config import HmacConfig, HmacTargetConfig

config = HmacConfig(
    targets={
        "my-service": HmacTargetConfig(
            base_url="https://api.example.com",
            shared_secret="your-base64-encoded-secret",
        ),
    },
)

factory = HmacClientFactory(config)
with factory.create_requests_session("my-service") as client:
    response = client.get("/api/hello")  # automatically signed
```

## Documentation

Full documentation, canonical string specification, and cross-language compatibility details: [github.com/HardenLabs/HardenHMAC](https://github.com/HardenLabs/HardenHMAC)

## License

[Apache License 2.0](https://github.com/HardenLabs/HardenHMAC/blob/main/LICENSE)
