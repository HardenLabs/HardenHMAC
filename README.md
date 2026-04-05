# HardenHMAC

[![CI](https://github.com/HardenLabs/HardenHMAC/actions/workflows/pr-validate.yml/badge.svg)](https://github.com/HardenLabs/HardenHMAC/actions/workflows/pr-validate.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://github.com/HardenLabs/HardenHMAC/blob/main/LICENSE)
[![NuGet](https://img.shields.io/nuget/v/HardenLabs.Hmac)](https://www.nuget.org/packages/HardenLabs.Hmac)
[![PyPI](https://img.shields.io/pypi/v/hardenlabs-hmac)](https://pypi.org/project/hardenlabs-hmac)
[![npm](https://img.shields.io/npm/v/@hardenlabs/hmac)](https://www.npmjs.com/package/@hardenlabs/hmac)

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
pip install "hardenlabs-hmac[fastapi]"   # for FastAPI middleware
pip install "hardenlabs-hmac[httpx]"     # for httpx client (used by create_sync_client)
pip install "hardenlabs-hmac[requests]"  # for requests client (used by create_requests_session)
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

Single shared secret. For multiple named clients, see [Multi-Client Server](#multi-client-server).

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
app.UseRouting();
app.UseHardenHmac();

// Protected — requires valid HMAC signature
app.MapGet("/api/hello", () => Results.Ok(new { message = "Authenticated!" }))
    .WithMetadata(new HmacValidateAttribute());

// Unprotected — no HMAC required
app.MapGet("/health", () => Results.Ok(new { status = "healthy" }));

app.Run();
```

Use `[HmacValidate]` on controllers or actions to opt in to HMAC validation. Use `[SkipHmacValidate]` on individual actions to exempt them when the controller is protected:

```csharp
[ApiController]
[Route("api/orders")]
[HmacValidate]              // All actions in this controller require HMAC
public class OrdersController : ControllerBase
{
    [HttpGet]
    public IActionResult GetOrders() => Ok();

    [HttpGet("health")]
    [SkipHmacValidate]      // Exempt from validation
    public IActionResult Health() => Ok(new { status = "healthy" });
}
```

### C# — Client (HttpClient)

Single target. For multiple targets with different secrets, see [Multi-Target Client](#multi-target-client).

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

var factory = new HardenHmacClientFactory(config);
var client = factory.CreateClient("my-service"); // BaseAddress + signing pre-configured
var response = await client.GetAsync("/api/hello"); // automatically signed
```

### Python — Server (FastAPI)

Single shared secret. For multiple named clients, see [Multi-Client Server](#multi-client-server).

```python
from fastapi import Depends, FastAPI, Request
from hardenlabs_hmac import HmacValidate, install_hmac_exception_handler
from hardenlabs_hmac.config import HmacConfig, SignedHeadersConfig

config = HmacConfig(
    shared_secret_base64="your-base64-encoded-secret",
    signed_headers=SignedHeadersConfig.default(),
    timestamp_tolerance_seconds=30,
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

### Python — Client

Single target. For multiple targets with different secrets, see [Multi-Target Client](#multi-target-client).

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
with factory.create_sync_client("my-service") as client:  # requires [httpx]; or create_requests_session() with [requests]
    response = client.get("/api/hello")  # automatically signed
```

### TypeScript — Server (Express)

Single shared secret. For multiple named clients, see [Multi-Client Server](#multi-client-server).

```typescript
import express from "express";
import { createHmacConfig, createHmacValidateMiddleware } from "@hardenlabs/hmac";

const config = createHmacConfig("your-base64-encoded-secret", {
  timestampToleranceSeconds: 30,
});

const app = express();
// IMPORTANT: Use express.text(), NOT express.json() — the middleware needs the raw body
app.use(express.text({ type: "*/*" }));

const hmacValidate = createHmacValidateMiddleware(config);

// Protected — requires valid HMAC signature
app.get("/api/hello", hmacValidate, (_req, res) => {
  res.json({ message: "Authenticated!" });
});

// Unprotected — no middleware, no HMAC required
app.get("/health", (_req, res) => {
  res.json({ status: "healthy" });
});

app.listen(3000);
```

### TypeScript — Client

Single target. For multiple targets with different secrets, see [Multi-Target Client](#multi-target-client).

```typescript
import { createHmacConfig, createHmacClientFactory } from "@hardenlabs/hmac";

const config = createHmacConfig("your-base64-encoded-secret", {
  targets: {
    "my-service": {
      baseUrl: "https://api.example.com",
      sharedSecret: "your-base64-encoded-secret",
    },
  },
});

// Uses fetch by default; to use axios, install/import axios and pass it as the
// second argument: createHmacClientFactory(config, { axios: axios.create() })
const factory = createHmacClientFactory(config);
const client = factory.createClient("my-service");
const response = await client.get("/api/hello"); // automatically signed
const data = await response.json();

// POST with body/headers works the same way regardless of adapter
const postResponse = await client.post("/api/data", JSON.stringify({ key: "value" }), {
  headers: { "Content-Type": "application/json" },
});
```

### Go — Server (net/http)

Single shared secret. For multiple named clients, see [Multi-Client Server](#multi-client-server).

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

	validate := hardenhmac.NewHmacValidateHandler(config, nil)

	mux := http.NewServeMux()

	// Protected — requires valid HMAC signature
	mux.Handle("/api/hello", validate(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"message":"Authenticated!"}`))
	})))

	// Unprotected — no wrapper, no HMAC required
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"status":"healthy"}`))
	})

	http.ListenAndServe(":8080", mux)
}
```

### Go — Client (http.Client)

Single target. For multiple targets with different secrets, see [Multi-Target Client](#multi-target-client).

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

## Server Configuration Scenarios

### Single Shared Secret

The simplest setup — one secret shared between client and server:

```python
# Python
config = HmacConfig(shared_secret_base64="your-base64-encoded-secret")
```

```csharp
// C#
var config = new HmacConfig { SharedSecretBase64 = "your-base64-encoded-secret" };
```

```typescript
// TypeScript
const config = createHmacConfig("your-base64-encoded-secret");
```

```go
// Go
config := &hardenhmac.HmacConfig{SharedSecretBase64: "your-base64-encoded-secret"}
```

If a client sends `X-Harden-Client-Id` but the server has no `Clients` configured, the server ignores the client ID and validates using `SharedSecretBase64`.

### Multi-Client Server

For servers that accept requests from multiple known clients, each with their own secret. Clients identify themselves via the `X-Harden-Client-Id` header.

```csharp
// C#
var config = new HmacConfig
{
    SharedSecretBase64 = "fallback-secret",  // used when no X-Harden-Client-Id header
    Clients = new Dictionary<string, HmacClientIdentity>
    {
        ["order-service"] = new HmacClientIdentity { SharedSecret = "orders-base64-secret" },
        ["payment-service"] = new HmacClientIdentity { SharedSecret = "payments-base64-secret" },
    },
};
```

```python
# Python
config = HmacConfig(
    shared_secret_base64="fallback-secret",
    clients={
        "order-service": HmacClientIdentity(shared_secret="orders-base64-secret"),
        "payment-service": HmacClientIdentity(shared_secret="payments-base64-secret"),
    },
)
```

```typescript
// TypeScript
const config = createHmacConfig("fallback-secret", {
  clients: {
    "order-service": { sharedSecret: "orders-base64-secret" },
    "payment-service": { sharedSecret: "payments-base64-secret" },
  },
});
```

```go
// Go
config := &hardenhmac.HmacConfig{
	SharedSecretBase64: "fallback-secret",
	Clients: map[string]hardenhmac.HmacClientIdentity{
		"order-service":   {SharedSecret: "orders-base64-secret"},
		"payment-service": {SharedSecret: "payments-base64-secret"},
	},
}
```

### Secret Resolver (Dynamic)

For servers that look up secrets dynamically per-request (e.g., from a database). The resolver runs before the `Clients` dictionary, so it can override or extend the built-in resolution:

```csharp
// C#
services.AddHardenHmac(config, secretResolver: async (httpContext) => {
    var clientId = httpContext.Request.Headers["X-Harden-Client-Id"].FirstOrDefault();
    return await LookupSecretFromDatabase(clientId);
});
```

```python
# Python
async def resolve_secret(request):
    client_id = request.headers.get("x-harden-client-id")
    return await lookup_secret_from_database(client_id)

hmac_validate = HmacValidate(config, secret_resolver=resolve_secret)
```

```typescript
// TypeScript
const hmacValidate = createHmacValidateMiddleware(config, (req) => {
  const clientId = req.headers["x-harden-client-id"] as string;
  return lookupSecretFromDatabase(clientId);
});
```

```go
// Go
resolver := func(r *http.Request) (string, error) {
	clientID := r.Header.Get("X-Harden-Client-Id")
	return lookupSecretFromDatabase(clientID)
}
validate := hardenhmac.NewHmacValidateHandler(config, resolver)
```

If the resolver returns `null` (or empty string in Go), the middleware falls back to the `Clients` dictionary, then to `SharedSecretBase64`.

### Server Secret Resolution Order

The server resolves the shared secret for each request in this order:

1. **Secret resolver callback** (if configured) — use result if non-empty
2. **`X-Harden-Client-Id` header + `Clients` is non-empty + client found** — use that client's secret
3. **`X-Harden-Client-Id` header + `Clients` is non-empty + client NOT found** — reject with `401 unknown_client`
4. **No `X-Harden-Client-Id`, or `Clients` is empty/not configured** — fall back to `SharedSecretBase64`
5. **Nothing available** — reject with `401 no_secret`

## Client Configuration Scenarios

### Single Target

The Quick Start examples above show single-target usage. The client factory configures base URL, secret, and automatic signing in one call.

The factory also sets `X-Harden-Client-Id` to the target name. This identifies the client to multi-client servers. Single-secret servers ignore it.

### Multi-Target Client

For services that call multiple backends, configure named targets with per-target base URLs and secrets:

```csharp
// C#
var config = new HmacConfig
{
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

var factory = new HardenHmacClientFactory(config);
var ordersClient = factory.CreateClient("order-service");
var paymentsClient = factory.CreateClient("payment-service");
```

```python
# Python
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
    response = await client.get("/api/orders")  # auto-signed with orders secret
```

```typescript
// TypeScript
const config = createHmacConfig("", {
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
```

```go
// Go
config := &hardenhmac.HmacConfig{
	Targets: map[string]hardenhmac.HmacTargetConfig{
		"order-service": {
			BaseURL:      "https://orders.example.com",
			SharedSecret: "orders-base64-secret",
		},
		"payment-service": {
			BaseURL:      "https://payments.example.com",
			SharedSecret: "payments-base64-secret",
		},
	},
}

factory := hardenhmac.NewClientFactory(config)
ordersClient, _ := factory.CreateClient("order-service")
```

Each target can override `SignedHeaders` and `TimestampToleranceSeconds`. If not set, the global config values are used.

The client factory automatically adds `X-Harden-Client-Id` set to the target name when creating clients via `CreateClient`/`createClient`.

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

**Go**: `config, err := hardenhmac.FromEnv("HARDEN_HMAC_")` — parses targets, clients, and global settings from environment variables.

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

## Network Requirements

HardenHMAC relies on custom HTTP headers (`X-Harden-*`) to transmit signatures, timestamps, and client identity. **These headers must be allowed through all network intermediaries** between the client and server.

Components that commonly strip or block custom headers:
- **WAFs** (AWS WAF, Cloudflare, Azure Front Door) — may strip unknown `X-*` headers
- **CDNs** (CloudFront, Fastly, Akamai) — may not forward custom request headers by default
- **Reverse proxies** (nginx, HAProxy, Envoy) — may require explicit `proxy_pass_header` or `proxy_set_header` configuration
- **API gateways** (AWS API Gateway, Kong, Apigee) — may filter headers not in an allowlist
- **Load balancers** (ALB, NLB) — generally pass headers through, but verify

**Required headers to allowlist:**

| Header | Direction | Required |
|--------|-----------|----------|
| `X-Harden-Signature` | Client → Server | Always |
| `X-Harden-Timestamp` | Client → Server | Always |
| `X-Harden-Client-Id` | Client → Server | When using multi-client server config |
| `X-Harden-Signed-Headers` | Client → Server | When signing headers beyond defaults |

If HMAC validation fails with `missing_signature` or `missing_timestamp` errors despite the client sending correct headers, check whether a network intermediary is stripping them.

## Framework Middleware

### ASP.NET Core

```csharp
// Per-endpoint validation (opt-in via attributes)
app.UseRouting();
app.UseHardenHmac();
app.MapGet("/api/data", () => "OK").WithMetadata(new HmacValidateAttribute());

// Controller attributes
[HmacValidate]                    // protect all actions
[SkipHmacValidate]                // exempt specific actions

// Client-side signing via multi-target factory
builder.Services.AddHardenHmac(config);
var client = factory.CreateClient("order-service"); // from IHardenHmacClientFactory

// From IConfiguration (appsettings.json / env vars)
builder.Services.AddHardenHmac(configuration.GetSection("HardenHmac"));
```

### FastAPI / Starlette

```python
# Per-endpoint validation (opt-in via dependency injection)
hmac_validate = HmacValidate(config)
install_hmac_exception_handler(app)

@app.get("/api/data")
async def get_data(request: Request, _hmac: None = Depends(hmac_validate)):
    return {"data": "protected"}

# Multi-tenant (with secret resolver)
hmac_validate = HmacValidate(config, secret_resolver=my_resolver)

# Global middleware (validates all routes)
app.add_middleware(HardenHmacMiddleware, config=config)
```

### Express

```typescript
// Per-route validation (opt-in via route middleware)
const hmacValidate = createHmacValidateMiddleware(config);
app.get("/api/data", hmacValidate, handler);

// Multi-tenant
const hmacValidate = createHmacValidateMiddleware(config, secretResolver);

// Global middleware (validates all routes)
app.use(hardenHmacMiddleware(config));
```

### net/http (Go)

```go
// Per-route validation (opt-in via handler wrapper)
validate := hardenhmac.NewHmacValidateHandler(config, nil)
mux.Handle("/api/data", validate(dataHandler))

// Multi-tenant
validate := hardenhmac.NewHmacValidateHandler(config, secretResolver)

// Global middleware (validates all routes)
handler := hardenhmac.NewHmacMiddleware(config, nil)(mux)
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

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to report issues, set up your development environment, and submit pull requests.

## License

[Apache License 2.0](LICENSE)

Copyright 2026 HardenLabs
