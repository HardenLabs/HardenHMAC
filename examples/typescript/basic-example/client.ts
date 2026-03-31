/**
 * Client that signs requests with HardenHMAC — single-secret and multi-target modes.
 *
 * Run: npx tsx client.ts
 */

import {
  createHmacConfig,
  createHmacClientFactory,
  noneSignedHeadersConfig,
  signRequestHeaders,
  fromEnv,
} from "@hardenlabs/hmac";

// ── Option A: Single-secret mode (backwards-compatible) ──
const sharedSecret = Buffer.from("my-shared-secret-key-32-bytes!!").toString(
  "base64"
);

const singleConfig = createHmacConfig(sharedSecret, {
  signedHeaders: noneSignedHeadersConfig(),
});

const BASE_URL = "http://localhost:3000";

async function demoSingleSecret(): Promise<void> {
  console.log("=== Single-secret mode ===");
  const headers = signRequestHeaders(singleConfig, "GET", "/api/hello");
  const resp = await fetch(`${BASE_URL}/api/hello`, { headers });
  console.log(`GET /api/hello: ${resp.status} ${JSON.stringify(await resp.json())}`);
}

// ── Option B: Multi-target mode (factory) ──
const ordersSecret = Buffer.from("orders-secret-key-32-bytes!!!!!").toString("base64");
const paymentsSecret = Buffer.from("payments-secret-key-32-bytes!!!").toString("base64");

const multiConfig = createHmacConfig(sharedSecret, {
  signedHeaders: noneSignedHeadersConfig(),
  targets: {
    "order-service": {
      baseUrl: "http://localhost:3001",
      sharedSecret: ordersSecret,
    },
    "payment-service": {
      baseUrl: "http://localhost:3002",
      sharedSecret: paymentsSecret,
      timestampToleranceSeconds: 60,
    },
  },
});

async function demoMultiTarget(): Promise<void> {
  console.log("\n=== Multi-target mode (factory) ===");
  const factory = createHmacClientFactory(multiConfig);

  // Each fetch wrapper has the correct base URL and auto-signs with the target's secret
  const ordersFetch = factory.createFetch("order-service");
  const paymentsFetch = factory.createFetch("payment-service");

  // These calls go to http://localhost:3001/api/orders and http://localhost:3002/api/charge
  console.log("  ordersFetch and paymentsFetch created with auto-signing");
  console.log("  ordersFetch('/api/orders') => GET http://localhost:3001/api/orders");
  console.log("  paymentsFetch('/api/charge', {method:'POST',...}) => POST http://localhost:3002/api/charge");
}

function demoEnvLoading(): void {
  console.log("\n=== Environment variable loading ===");
  // In production, set env vars:
  //   HARDEN_HMAC_TARGETS__ORDER_SERVICE__BASE_URL=https://orders.example.com
  //   HARDEN_HMAC_TARGETS__ORDER_SERVICE__SHARED_SECRET=base64-key
  // Then:
  //   const config = fromEnv();
  //   const factory = createHmacClientFactory(config);
  console.log("  Set HARDEN_HMAC_* env vars, then call fromEnv()");
}

async function main(): Promise<void> {
  await demoSingleSecret();
  await demoMultiTarget();
  demoEnvLoading();
}

main().catch(console.error);
