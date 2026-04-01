# @hardenlabs/hmac

Cross-language HMAC-SHA256 request signing with a defined canonical string format. Guaranteed identical signatures across C#, Python, TypeScript, and Go.

## Installation

```bash
npm install @hardenlabs/hmac
```

## Quick Start — Server (Express)

```typescript
import express from "express";
import { createHmacConfig, hardenHmacMiddleware } from "@hardenlabs/hmac";

const config = createHmacConfig("your-base64-encoded-secret", {
  timestampToleranceSeconds: 30,
  clients: {
    "order-service": { sharedSecret: "orders-base64-secret" },
  },
});

const app = express();
// IMPORTANT: Use express.text(), NOT express.json()
app.use(express.text({ type: "*/*" }));
app.use(hardenHmacMiddleware(config));

app.get("/api/hello", (_req, res) => {
  res.json({ message: "Authenticated!" });
});

app.listen(3000);
```

## Quick Start — Client (fetch)

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

const factory = createHmacClientFactory(config);
const client = factory.createClient("my-service");
const response = await client.get("/api/hello"); // automatically signed
const data = await response.json();
```

## Quick Start — Client (axios)

```typescript
import axios from "axios";
import { createHmacConfig, createHmacClientFactory } from "@hardenlabs/hmac";

const config = createHmacConfig("your-base64-encoded-secret", {
  targets: {
    "my-service": {
      baseUrl: "https://api.example.com",
      sharedSecret: "your-base64-encoded-secret",
    },
  },
});

const factory = createHmacClientFactory(config, { axios: axios.create() });
const client = factory.createClient("my-service");
const response = await client.get("/api/hello"); // automatically signed
```

## Documentation

Full documentation, canonical string specification, and cross-language compatibility details: [github.com/HardenLabs/HardenHMAC](https://github.com/HardenLabs/HardenHMAC)

## License

[Apache License 2.0](https://github.com/HardenLabs/HardenHMAC/blob/main/LICENSE)
