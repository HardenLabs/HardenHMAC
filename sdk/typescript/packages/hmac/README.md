# @hardenlabs/hmac

Cross-language HMAC-SHA256 request signing with a defined canonical string format. Guaranteed identical signatures across C#, Python, TypeScript, and Go.

## Installation

```bash
npm install @hardenlabs/hmac
```

## Quick Start — Server (Express)

```typescript
import express from "express";
import { createHmacConfig, createHmacValidateMiddleware } from "@hardenlabs/hmac";

const config = createHmacConfig("your-base64-encoded-secret", {
  timestampToleranceSeconds: 30,
  clients: {
    "order-service": { sharedSecret: "orders-base64-secret" },
  },
});

const app = express();
// IMPORTANT: Use express.text(), NOT express.json()
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

Routes without `hmacValidate` in their middleware chain are not validated. Use `hardenHmacMiddleware(config)` with `app.use()` instead if you want all routes validated.

### Public API — Server

| Symbol | Description |
|--------|-------------|
| `createHmacValidateMiddleware(config, secretResolver?)` | Per-route middleware |
| `hardenHmacMiddleware(config, secretResolver?)` | Global middleware (validates all routes) |

## Quick Start — Client

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
```

## Documentation

Full documentation, canonical string specification, and cross-language compatibility details: [github.com/HardenLabs/HardenHMAC](https://github.com/HardenLabs/HardenHMAC)

## License

[Apache License 2.0](https://github.com/HardenLabs/HardenHMAC/blob/main/LICENSE)
