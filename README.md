# HardenHMAC

Cross-language HMAC-SHA256 request signing with a defined canonical string format. Guaranteed identical signatures across C#, Python, and TypeScript through a shared test vector suite.

## Installation

**C# / .NET**
```bash
dotnet add package HardenLabs.Hmac
dotnet add package HardenLabs.Hmac.AspNetCore  # for middleware
```

**Python**
```bash
pip install hardenlabs-hmac
pip install "hardenlabs-hmac[fastapi]"  # for FastAPI middleware
```

**TypeScript / Node.js**
```bash
npm install @hardenlabs/hmac
```

## Quick Start

### C# — Server (ASP.NET Core)

```csharp
using HardenLabs.Hmac;
using HardenLabs.Hmac.AspNetCore;

var config = new HmacConfig
{
    SharedSecretBase64 = "your-base64-encoded-secret",
    SignedHeaders = SignedHeadersConfig.Default,
    TimestampToleranceSeconds = 30
};

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddHardenHmac(config);

var app = builder.Build();
app.UseHardenHmac();

app.MapGet("/api/hello", () => Results.Ok(new { message = "Authenticated!" }));
app.Run();
```

### C# — Client (HttpClient)

```csharp
using HardenLabs.Hmac;
using HardenLabs.Hmac.AspNetCore;

var config = new HmacConfig
{
    SharedSecretBase64 = "your-base64-encoded-secret",
    SignedHeaders = SignedHeadersConfig.Default
};

// Register a named HttpClient that auto-signs requests
builder.Services.AddHardenHmacClient("my-service", config)
    .ConfigureHttpClient(c => c.BaseAddress = new Uri("https://api.example.com"));

// Use it via IHttpClientFactory
var client = factory.CreateClient("my-service");
var response = await client.GetAsync("/api/hello"); // automatically signed
```

### Python — Server (FastAPI)

```python
import base64
from fastapi import FastAPI
from hardenlabs_hmac.config import HmacConfig, SignedHeadersConfig
from hardenlabs_hmac.middleware.fastapi import HardenHmacMiddleware

config = HmacConfig(
    shared_secret_base64="your-base64-encoded-secret",
    signed_headers=SignedHeadersConfig.default(),
    timestamp_tolerance_seconds=30,
)

app = FastAPI()
app.add_middleware(HardenHmacMiddleware, config=config)

@app.get("/api/hello")
async def hello():
    return {"message": "Authenticated!"}
```

### Python — Client

```python
import httpx
from hardenlabs_hmac.client import sign_request_headers
from hardenlabs_hmac.config import HmacConfig, SignedHeadersConfig

config = HmacConfig(
    shared_secret_base64="your-base64-encoded-secret",
    signed_headers=SignedHeadersConfig.default(),
)

headers = sign_request_headers(config, "GET", "/api/hello")
response = httpx.get("https://api.example.com/api/hello", headers=headers)
```

### TypeScript — Server (Express)

```typescript
import express from "express";
import { createHmacConfig, hardenHmacMiddleware } from "@hardenlabs/hmac";

const config = createHmacConfig("your-base64-encoded-secret", {
  timestampToleranceSeconds: 30,
});

const app = express();
app.use(express.text({ type: "*/*" }));
app.use(hardenHmacMiddleware(config));

app.get("/api/hello", (_req, res) => {
  res.json({ message: "Authenticated!" });
});

app.listen(3000);
```

### TypeScript — Client

```typescript
import { createHmacConfig, signRequestHeaders } from "@hardenlabs/hmac";

const config = createHmacConfig("your-base64-encoded-secret");

const headers = signRequestHeaders(config, "GET", "/api/hello");
const response = await fetch("https://api.example.com/api/hello", { headers });
```

## What HardenHMAC Does NOT Do

HardenHMAC is a focused signing library. It deliberately does not include:

- **Key management** -- You generate, distribute, store, and rotate shared secrets yourself.
- **Key rotation** -- There is no built-in mechanism for rotating keys across services.
- **Replay protection** -- A valid request can be replayed within the timestamp tolerance window. Add nonce tracking if you need it.
- **Body encryption** -- The request body is signed but not encrypted.
- **Rate limiting, authorization, or access control** -- This library handles authentication only.

You are responsible for key exchange and rotation. For automatic ephemeral key rotation with zero management overhead, see [HardenAPI](https://hardenapi.com).

## Canonical String Format

All implementations produce signatures from the same canonical string:

```
METHOD\nPATH\nSIGNED_HEADERS\nBODY\nTIMESTAMP
```

| Field | Content | Empty value |
|-------|---------|-------------|
| METHOD | HTTP method, uppercase | Never empty |
| PATH | Request path + query string, as-is | Never empty (min `/`) |
| SIGNED_HEADERS | Sorted `name:value` pairs joined by `\n` | Empty string |
| BODY | Request body as string | Empty string |
| TIMESTAMP | Unix timestamp in seconds | Never empty |

The signature is `HMAC-SHA256(base64_decode(secret), utf8_encode(canonical_string))` output as lowercase hex (64 characters).

See [docs/CANONICAL-STRING-SPEC.md](docs/CANONICAL-STRING-SPEC.md) for the formal specification.

## Signed Headers Configuration

Control which headers are included in the signature:

| Option | Default | Description |
|--------|---------|-------------|
| `IncludeAuthorization` | `true` | Include the `Authorization` header |
| `IncludeXHeaders` | `true` | Include all `X-*` headers (except `X-Harden-*`) |
| `AdditionalHeaders` | `[]` | Explicit list of extra headers to include |
| `ExcludeHeaders` | `[]` | Override: exclude specific headers |

`X-Harden-*` headers (which carry the signature itself) are always excluded.

Headers are sorted alphabetically by lowercase name, values are trimmed, and the format is `name:value` joined by `\n`.

## HTTP Headers

| Header | Purpose |
|--------|---------|
| `X-Harden-Signature` | 64-char lowercase hex HMAC-SHA256 signature |
| `X-Harden-Timestamp` | Unix timestamp in seconds |
| `X-Harden-Signed-Headers` | Semicolon-separated signed header names (only if headers are signed) |

## Framework Middleware

### ASP.NET Core

```csharp
// Server-side validation
app.UseHardenHmac();

// Client-side signing via HttpClient
builder.Services.AddHardenHmacClient("service-name", config);
```

### FastAPI / Starlette

```python
app.add_middleware(HardenHmacMiddleware, config=config)
```

### Express

```typescript
app.use(hardenHmacMiddleware(config));
```

## Cross-Language Compatibility Guarantee

All three implementations (C#, Python, TypeScript) produce identical canonical strings and signatures for the same inputs. This is verified by a shared test vector suite at `tests/cross-language/test-vectors.json`.

The test vectors are authoritative. If an implementation produces a different result than the vectors specify, the implementation is wrong.

## Timestamp Validation

Server-side middleware rejects requests outside the tolerance window (default: 30 seconds):

- Requests older than tolerance: `timestamp_expired` (401)
- Requests from the future beyond tolerance: `timestamp_out_of_range` (401)
- Missing/invalid timestamp header: `missing_timestamp` / `invalid_timestamp` (400)

## Contributing

Contributions are welcome. Please ensure:

1. All three language implementations pass the cross-language test vectors
2. New features must include test vectors if they affect the canonical string or signature
3. Run all tests before submitting a PR:
   ```bash
   # C#
   cd sdk/csharp && dotnet test

   # Python
   cd sdk/python && pytest tests/ -v

   # TypeScript
   cd sdk/typescript/packages/hmac && npm test
   ```

## License

[Apache License 2.0](LICENSE)

Copyright 2026 HardenLabs
