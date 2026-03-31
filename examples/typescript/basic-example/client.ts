/**
 * Client that signs requests with HardenHMAC using the multi-target factory.
 *
 * Run: npx tsx client.ts
 */

import { createHmacClientFactory } from "@hardenlabs/hmac";
import type { HmacConfig } from "@hardenlabs/hmac";

// Same secrets as the server — in production, load from environment/secrets manager
const ordersSecret = Buffer.from("orders-secret-key-32-bytes!!!!!").toString("base64");
const paymentsSecret = Buffer.from("payments-secret-key-32-bytes!!!").toString("base64");

const config: HmacConfig = {
  targets: {
    "order-service": {
      baseUrl: "http://localhost:3000",
      sharedSecret: ordersSecret,
    },
    "payment-service": {
      baseUrl: "http://localhost:3000",
      sharedSecret: paymentsSecret,
      timestampToleranceSeconds: 60,
    },
  },
};

const factory = createHmacClientFactory(config);

async function main(): Promise<void> {
  // Each fetch wrapper has base URL and signing pre-configured from the target
  const ordersFetch = factory.createClient("order-service");
  const paymentsFetch = factory.createClient("payment-service");

  // GET — base URL is prepended automatically
  const getResp = await ordersFetch("/api/hello");
  console.log(`GET order-service /api/hello: ${getResp.status} ${JSON.stringify(await getResp.json())}`);

  // POST with body
  const postResp = await paymentsFetch("/api/echo", {
    method: "POST",
    body: JSON.stringify({ amount: 100 }),
    headers: { "Content-Type": "application/json" },
  });
  console.log(`POST payment-service /api/echo: ${postResp.status} ${JSON.stringify(await postResp.json())}`);
}

main().catch(console.error);
