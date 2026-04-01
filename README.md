# HardenHMAC

Cross-language HMAC-SHA256 request signing with a defined canonical string format. Guaranteed identical signatures across C#, Python, TypeScript, and Go through a shared test vector suite.

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

**Go**
```bash
go get github.com/HardenLabs/hardenhmac-go
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
    SignedHeaders = SignedHeadersConfig.Default,
    Targets = new Dictionary<string, HmacTargetConfig>
    {
        ["my-service"] = new HmacTargetConfig
        {
            BaseUrl = "https://api.example.com",
            SharedSecret = "your-base64-encoded-secret",
        }
    }
};

builder.Services.AddHardenHmac(config);

// Use IHardenHmacClientFactory to create per-target clients
var client = factory.CreateClient("my-service"); // BaseAddress + signing pre-configured
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

### Go — Server (net/http)

```go
package main

import (
	"net/http"
	hardenhmac "github.com/HardenLabs/hardenhmac-go"
)

func main() {
	config := &hardenhmac.HmacConfig{
		SharedSecretBase64: "your-base64-encoded-secret",
		SignedHeaders:      hardenhmac.DefaultSignedHeadersConfig(),
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/api/hello", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"message":"Authenticated!"}`))
	})

	handler := hardenhmac.NewHmacMiddleware(config, nil)(mux)
	http.ListenAndServe(":8080", handler)
}
```

### Go — Client (http.Client)

```go
package main

import (
	"fmt"
	"net/http"
	hardenhmac "github.com/HardenLabs/hardenhmac-go"
)

func main() {
	config := &hardenhmac.HmacConfig{
		SharedSecretBase64: "your-base64-encoded-secret",
		SignedHeaders:      hardenhmac.DefaultSignedHeadersConfig(),
		Targets: map[string]hardenhmac.HmacTargetConfig{
			"my-service": {
				BaseURL:      "https://api.example.com",
				SharedSecret: "your-base64-encoded-secret",
			},
		},
	}

	factory := hardenhmac.NewClientFactory(config)
	client, _ := factory.CreateClient("my-service") // BaseURL + signing pre-configured
	resp, _ := client.Get("/api/hello") // automatically signed
	fmt.Println(resp.Status)
}
```

## Multi-Target Configuration

For services that call multiple backends, configure named targets with per-target base URLs and secrets.

### C# — Multi-Target Client

```csharp
var config = new HmacConfig
{
    SharedSecretBase64 = "default-secret",  // server-side fallback
    Targets = new Dictionary<string, HmacTargetConfig>
    {
        ["order-service"] = new HmacTargetConfig
        {
            BaseUrl = "https://orders.example.com",
            SharedSecret = "orders-base64-secret",
        },
        ["payment-service"] = new HmacTargetConfig
        {
            BaseUrl = "https://payments.example.com",
            SharedSecret = "payments-base64-secret",
            TimestampToleranceSeconds = 60,  // per-target override
        },
    },
};

builder.Services.AddHardenHmac(config);

// Inject IHardenHmacClientFactory to create per-target clients
var client = factory.CreateClient("order-service");
var response = await client.GetAsync("/api/orders"); // auto-signed, correct base URL
```

### Python — Multi-Target Client

```python
from hardenlabs_hmac.client import HmacClientFactory
from hardenlabs_hmac.config import HmacConfig, HmacTargetConfig

config = HmacConfig(
    targets={
        "order-service": HmacTargetConfig(
            base_url="https://orders.example.com",
            shared_secret="orders-base64-secret",
        ),
        "payment-service": HmacTargetConfig(
            base_url="https://payments.example.com",
            shared_secret="payments-base64-secret",
        ),
    },
)

factory = HmacClientFactory(config)
async with factory.create_client("order-service") as client:
    response = await client.get("/api/orders")  # auto-signed
```

### TypeScript — Multi-Target Client

```typescript
import { createHmacConfig, createHmacClientFactory } from "@hardenlabs/hmac";

const config = createHmacConfig("default-secret", {
  targets: {
    "order-service": {
      baseUrl: "https://orders.example.com",
      sharedSecret: "orders-base64-secret",
    },
    "payment-service": {
      baseUrl: "https://payments.example.com",
      sharedSecret: "payments-base64-secret",
    },
  },
});

const factory = createHmacClientFactory(config);
const ordersClient = factory.createClient("order-service");
const response = await ordersClient("/api/orders"); // auto-signed, correct base URL
```

## Multi-Client Server Configuration

For servers that accept requests from multiple known clients, each with their own secret, use the `Clients` dictionary. Clients identify themselves via the `X-Harden-Client-Id` header.

### C# -- Multi-Client Server

```csharp
var config = new HmacConfig
{
    SharedSecretBase64 = "fallback-secret",  // used when no client ID header
    SignedHeaders = SignedHeadersConfig.Default,
    TimestampToleranceSeconds = 30,
    Clients = new Dictionary<string, HmacClientIdentity>
    {
        ["order-service"] = new HmacClientIdentity { SharedSecret = "orders-base64-secret" },
        ["payment-service"] = new HmacClientIdentity { SharedSecret = "payments-base64-secret" },
    },
};

builder.Services.AddHardenHmac(config);
app.UseHardenHmac();
// Requests with X-Harden-Client-Id: order-service -> validated with orders secret
// Requests with X-Harden-Client-Id: unknown -> rejected with 401 unknown_client
// Requests without X-Harden-Client-Id -> validated with fallback secret
```

### Python -- Multi-Client Server

```python
from hardenlabs_hmac.config import HmacClientIdentity, HmacConfig, SignedHeadersConfig

config = HmacConfig(
    shared_secret_base64="fallback-secret",
    signed_headers=SignedHeadersConfig.default(),
    clients={
        "order-service": HmacClientIdentity(shared_secret="orders-base64-secret"),
        "payment-service": HmacClientIdentity(shared_secret="payments-base64-secret"),
    },
)
app.add_middleware(HardenHmacMiddleware, config=config)
```

### TypeScript -- Multi-Client Server

```typescript
const config = createHmacConfig("fallback-secret", {
  clients: {
    "order-service": { sharedSecret: "orders-base64-secret" },
    "payment-service": { sharedSecret: "payments-base64-secret" },
  },
});
app.use(hardenHmacMiddleware(config));
```

### Go -- Multi-Client Server

```go
config := &hardenhmac.HmacConfig{
	SharedSecretBase64: "fallback-secret",
	SignedHeaders:      hardenhmac.DefaultSignedHeadersConfig(),
	Clients: map[string]hardenhmac.HmacClientIdentity{
		"order-service":   {SharedSecret: "orders-base64-secret"},
		"payment-service": {SharedSecret: "payments-base64-secret"},
	},
}

handler := hardenhmac.NewHmacMiddleware(config, nil)(mux)
```

The client factory automatically adds the `X-Harden-Client-Id` header when creating clients via `CreateClient`/`createClient`.

## Environment Variable Configuration

All SDKs support loading configuration from environment variables with the `HARDEN_HMAC_` prefix.

**Single secret:**
```bash
HARDEN_HMAC_SHARED_SECRET_BASE64=your-base64-secret
HARDEN_HMAC_TIMESTAMP_TOLERANCE_SECONDS=30
```

**Multi-target:**
```bash
HARDEN_HMAC_TARGETS__ORDER_SERVICE__BASE_URL=https://orders.example.com
HARDEN_HMAC_TARGETS__ORDER_SERVICE__SHARED_SECRET=orders-base64-secret
HARDEN_HMAC_TARGETS__PAYMENT_SERVICE__BASE_URL=https://payments.example.com
HARDEN_HMAC_TARGETS__PAYMENT_SERVICE__SHARED_SECRET=payments-base64-secret
```

**C#**: Native `IConfiguration` handles `__` separators automatically via `AddHardenHmac(configuration)`.

**Python**: `config = HmacConfig.from_env()` — optionally loads `.env` via python-dotenv if installed.

**TypeScript**: `config = fromEnv()` — optionally loads `.env` via dotenv if installed as peer dependency.

**Go**: Environment variable configuration is handled programmatically. Load `HARDEN_HMAC_SHARED_SECRET_BASE64` via `os.Getenv()` and construct `HmacConfig` directly.

## Multi-Tenant Server (Secret Resolver)

For servers that validate requests from multiple clients with different secrets:

```csharp
// C# — resolve secret per-request
services.AddHardenHmac(config, secretResolver: async (httpContext) => {
    var clientId = httpContext.Request.Headers["X-Client-Id"].FirstOrDefault();
    return await LookupSecret(clientId);
});
```

```python
# Python — resolve secret per-request
async def resolve_secret(request):
    client_id = request.headers.get("x-client-id")
    return await lookup_secret(client_id)

app.add_middleware(HardenHmacMiddleware, config=config, secret_resolver=resolve_secret)
```

```typescript
// TypeScript — resolve secret per-request
app.use(hardenHmacMiddleware(config, (req) => {
  const clientId = req.headers["x-client-id"] as string;
  return lookupSecret(clientId);
}));
```

```go
// Go — resolve secret per-request
resolver := func(r *http.Request) (string, error) {
	clientID := r.Header.Get("X-Client-Id")
	return lookupSecret(clientID)
}
handler := hardenhmac.NewHmacMiddleware(config, resolver)(mux)
```

If the resolver returns `null` (or empty string in Go), the middleware falls back to `config.SharedSecretBase64`.

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

`X-Harden-*` headers (which carry the signature itself) are always excluded, **except** `X-Harden-Client-Id` which is an identity claim and is included in the signature when present.

Headers are sorted alphabetically by lowercase name, values are trimmed, and the format is `name:value` joined by `\n`.

## HTTP Headers

| Header | Purpose | Signed? |
|--------|---------|---------|
| `X-Harden-Signature` | 64-char lowercase hex HMAC-SHA256 signature | No |
| `X-Harden-Timestamp` | Unix timestamp in seconds | No |
| `X-Harden-Signed-Headers` | Semicolon-separated signed header names (only if headers are signed) | No |
| `X-Harden-Client-Id` | Client identity for multi-client server resolution | **Yes** |

## Framework Middleware

### ASP.NET Core

```csharp
// Server-side validation
app.UseHardenHmac();

// Client-side signing via multi-target factory
builder.Services.AddHardenHmac(config);
var client = factory.CreateClient("order-service"); // from IHardenHmacClientFactory

// From IConfiguration (appsettings.json / env vars)
builder.Services.AddHardenHmac(configuration.GetSection("HardenHmac"));
```

### FastAPI / Starlette

```python
# Simple
app.add_middleware(HardenHmacMiddleware, config=config)

# Multi-tenant
app.add_middleware(HardenHmacMiddleware, config=config, secret_resolver=my_resolver)
```

### Express

```typescript
// Simple
app.use(hardenHmacMiddleware(config));

// Multi-tenant
app.use(hardenHmacMiddleware(config, secretResolver));
```

### net/http (Go)

```go
// Simple
handler := hardenhmac.NewHmacMiddleware(config, nil)(mux)

// Multi-tenant
handler := hardenhmac.NewHmacMiddleware(config, secretResolver)(mux)
```

## Cross-Language Compatibility Guarantee

All four implementations (C#, Python, TypeScript, Go) produce identical canonical strings and signatures for the same inputs. This is verified by a shared test vector suite at `tests/cross-language/test-vectors.json`.

The test vectors are authoritative. If an implementation produces a different result than the vectors specify, the implementation is wrong.

## Timestamp Validation

Server-side middleware rejects requests outside the tolerance window (default: 30 seconds):

- Requests older than tolerance: `timestamp_expired` (401)
- Requests from the future beyond tolerance: `timestamp_out_of_range` (401)
- Missing/invalid timestamp header: `missing_timestamp` / `invalid_timestamp` (400)

## Contributing

Contributions are welcome. Please ensure:

1. All four language implementations pass the cross-language test vectors
2. New features must include test vectors if they affect the canonical string or signature
3. Run all tests before submitting a PR:
   ```bash
   # C#
   cd sdk/csharp && dotnet test

   # Python
   cd sdk/python && pytest tests/ -v

   # TypeScript
   cd sdk/typescript/packages/hmac && npm test

   # Go
   cd sdk/go && go test ./... -v
   ```

## License

[Apache License 2.0](LICENSE)

Copyright 2026 HardenLabs
