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
from fastapi import Depends, FastAPI, Request
from hardenlabs_hmac import HmacValidate, install_hmac_exception_handler
from hardenlabs_hmac.config import HmacConfig, HmacClientIdentity, SignedHeadersConfig

config = HmacConfig(
    signed_headers=SignedHeadersConfig.default(),
    timestamp_tolerance_seconds=30,
    clients={
        "order-service": HmacClientIdentity(shared_secret="orders-base64-secret"),
    },
)

hmac_validate = HmacValidate(config)

app = FastAPI()
install_hmac_exception_handler(app)

# Protected — requires valid HMAC signature
@app.get("/api/hello")
async def hello(request: Request, _hmac: None = Depends(hmac_validate)):
    return {"message": "Authenticated!"}

# Unprotected — no dependency, no HMAC required
@app.get("/health")
async def health():
    return {"status": "healthy"}
```

Routes without `Depends(hmac_validate)` are not validated. Use the global `HardenHmacMiddleware` instead if you want all routes validated.

### Public API — Server

| Symbol | Description |
|--------|-------------|
| `HmacValidate(config, secret_resolver=None)` | Per-route dependency for `Depends()` |
| `install_hmac_exception_handler(app)` | Register error handler (call once per app) |
| `HmacValidationHttpError` | Exception raised on validation failure |
| `HardenHmacMiddleware` | Global middleware (validates all routes) |

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
