# hardenhmac-go

Cross-language HMAC-SHA256 request signing with a defined canonical string format. Guaranteed identical signatures across C#, Python, TypeScript, and Go.

## Installation

```bash
go get github.com/HardenLabs/hardenhmac-go
```

## Quick Start — Server (net/http)

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
		Clients: map[string]hardenhmac.HmacClientIdentity{
			"order-service": {SharedSecret: "orders-base64-secret"},
		},
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

Routes not wrapped with `validate()` are not validated. Use `NewHmacMiddleware` to wrap an entire mux if you want all routes validated.

### Public API — Server

| Symbol | Description |
|--------|-------------|
| `NewHmacValidateHandler(config, secretResolver)` | Per-route handler wrapper |
| `NewHmacMiddleware(config, secretResolver)` | Global middleware (validates all routes) |

## Quick Start — Client (http.Client)

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
	resp, _ := client.Get("/api/hello")              // automatically signed
	fmt.Println(resp.Status)
}
```

### Public API — Client

| Symbol | Description |
|--------|-------------|
| `NewClientFactory(config)` | Create clients with automatic HMAC signing |
| `SigningTransport` | `http.RoundTripper` that signs outgoing requests |
| `SignRequestHeaders(config, method, path, body, headers)` | Manual header signing |

### Public API — Core

| Symbol | Description |
|--------|-------------|
| `HmacConfig` | Configuration: secret, signed headers, tolerance, clients, targets |
| `SignedHeadersConfig` | Controls which headers are included in the signature |
| `DefaultSignedHeadersConfig()` | Default signed headers (Authorization + X-* headers) |
| `NoneSignedHeadersConfig()` | No headers signed |
| `FromEnv(prefix)` | Load config from environment variables |
| `BuildCanonicalString(...)` | Build the canonical string for signing |
| `Sign(secret, canonical)` | Compute HMAC-SHA256 signature |
| `Verify(secret, canonical, signature)` | Verify a signature |
| `ValidateRequest(config, ...)` | Full request validation (timestamp + signature) |

## Documentation

Full documentation, canonical string specification, and cross-language compatibility details: [github.com/HardenLabs/HardenHMAC](https://github.com/HardenLabs/HardenHMAC)

## License

[Apache License 2.0](https://github.com/HardenLabs/HardenHMAC/blob/main/LICENSE)
