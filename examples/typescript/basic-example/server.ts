/**
 * Express server with HardenHMAC validation — single-secret and multi-tenant modes.
 *
 * Run: npx tsx server.ts
 */

import express from "express";
import type { Request } from "express";
import {
  createHmacConfig,
  hardenHmacMiddleware,
  noneSignedHeadersConfig,
  type SecretResolver,
} from "@hardenlabs/hmac";

// Secrets (in production, load from environment/secrets manager)
const defaultSecret = Buffer.from("my-shared-secret-key-32-bytes!!").toString(
  "base64"
);
const ordersSecret = Buffer.from("orders-secret-key-32-bytes!!!!!").toString(
  "base64"
);
const paymentsSecret = Buffer.from("payments-secret-key-32-bytes!!").toString(
  "base64"
);

const config = createHmacConfig(defaultSecret, {
  signedHeaders: noneSignedHeadersConfig(),
  timestampToleranceSeconds: 30,
});

// ── Option A: Multi-client server with named clients ──
// Each client identifies itself via X-Harden-Client-Id header.
// The middleware looks up the secret from the clients dictionary.
const multiClientConfig = {
  ...config,
  clients: {
    "order-service": { sharedSecret: ordersSecret },
    "payment-service": { sharedSecret: paymentsSecret },
  },
};

const simpleApp = express();
simpleApp.use(express.text({ type: "*/*" }));
simpleApp.use(hardenHmacMiddleware(multiClientConfig));

simpleApp.get("/api/hello", (_req, res) => {
  res.json({ message: "Hello from HardenHMAC!" });
});

simpleApp.post("/api/echo", (req, res) => {
  res.json({ echo: req.body });
});

// ── Option B: Multi-tenant server with secret resolver ──
const TENANT_SECRETS: Record<string, string> = {
  "tenant-a": Buffer.from("tenant-a-secret-key-32-bytes!!").toString("base64"),
  "tenant-b": Buffer.from("tenant-b-secret-key-32-bytes!!").toString("base64"),
};

const secretResolver: SecretResolver = (req: Request) => {
  const clientId = req.headers["x-client-id"] as string | undefined;
  if (clientId && TENANT_SECRETS[clientId]) {
    return TENANT_SECRETS[clientId]!;
  }
  return null; // fall back to config.sharedSecretBase64
};

const multiTenantApp = express();
multiTenantApp.use(express.text({ type: "*/*" }));
multiTenantApp.use(hardenHmacMiddleware(config, secretResolver));

multiTenantApp.get("/api/hello", (_req, res) => {
  res.json({ message: "Hello from multi-tenant HardenHMAC!" });
});

// Start simple server by default
simpleApp.listen(3000, () => {
  console.log("Simple server listening on http://localhost:3000");
});

// Uncomment for multi-tenant:
// multiTenantApp.listen(3001, () => {
//   console.log("Multi-tenant server listening on http://localhost:3001");
// });
