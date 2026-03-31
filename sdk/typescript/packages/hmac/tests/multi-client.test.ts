import { describe, it, expect, beforeAll, afterAll } from "vitest";
import express from "express";
import type { Server } from "node:http";
import { buildCanonicalString } from "../src/canonical.js";
import type { HmacConfig, SignedHeadersConfig } from "../src/config.js";
import { CLIENT_ID_HEADER } from "../src/config.js";
import { sign } from "../src/signing.js";
import { hardenHmacMiddleware } from "../src/middleware/express.js";
import { createHmacClientFactory } from "../src/client-factory.js";
import { fromEnv } from "../src/env-loader.js";

const DEFAULT_SECRET = "ZGVmYXVsdC1zZWNyZXQta2V5LTMyLWJ5dGVzISEhISE=";
const ORDER_SECRET = "b3JkZXJzLXNlY3JldC1rZXktMzItYnl0ZXMhISEhIQ==";
const PAYMENT_SECRET = "cGF5bWVudHMtc2VjcmV0LWtleS0zMi1ieXRlcyEhISE=";

const noneConfig: SignedHeadersConfig = {
  includeAuthorization: false,
  includeXHeaders: false,
  additionalHeaders: [],
  excludeHeaders: [],
};

const config: HmacConfig = {
  sharedSecretBase64: DEFAULT_SECRET,
  signedHeaders: noneConfig,
  timestampToleranceSeconds: 30,
  clients: {
    "order-service": { sharedSecret: ORDER_SECRET },
    "payment-service": { sharedSecret: PAYMENT_SECRET },
  },
};

function signReq(
  secret: string,
  method: string,
  path: string,
  body: string = ""
): { signature: string; timestamp: string } {
  const ts = Math.floor(Date.now() / 1000);
  const canonical = buildCanonicalString({
    method,
    path,
    body,
    timestamp: ts,
    signedHeadersConfig: noneConfig,
  });
  return { signature: sign(secret, canonical), timestamp: String(ts) };
}

let server: Server;
let baseUrl: string;

beforeAll(async () => {
  const app = express();
  app.use(express.text({ type: "*/*" }));
  app.use(hardenHmacMiddleware(config));

  app.get("/api/test", (_req, res) => {
    res.json({ message: "ok" });
  });

  await new Promise<void>((resolve) => {
    server = app.listen(0, () => {
      const addr = server.address();
      if (addr && typeof addr !== "string") {
        baseUrl = `http://127.0.0.1:${addr.port}`;
      }
      resolve();
    });
  });
});

afterAll(async () => {
  await new Promise<void>((resolve, reject) => {
    server.close((err) => (err ? reject(err) : resolve()));
  });
});

describe("Express middleware with config.clients", () => {
  it("known client with valid signature passes", async () => {
    const { signature, timestamp } = signReq(
      ORDER_SECRET,
      "GET",
      "/api/test"
    );
    const response = await fetch(`${baseUrl}/api/test`, {
      headers: {
        [CLIENT_ID_HEADER]: "order-service",
        "X-Harden-Signature": signature,
        "X-Harden-Timestamp": timestamp,
      },
    });
    expect(response.status).toBe(200);
  });

  it("known client with wrong secret returns 401", async () => {
    const { signature, timestamp } = signReq(
      DEFAULT_SECRET,
      "GET",
      "/api/test"
    );
    const response = await fetch(`${baseUrl}/api/test`, {
      headers: {
        [CLIENT_ID_HEADER]: "order-service",
        "X-Harden-Signature": signature,
        "X-Harden-Timestamp": timestamp,
      },
    });
    expect(response.status).toBe(401);
  });

  it("unknown client returns 401 with unknown_client error", async () => {
    const { signature, timestamp } = signReq(
      DEFAULT_SECRET,
      "GET",
      "/api/test"
    );
    const response = await fetch(`${baseUrl}/api/test`, {
      headers: {
        [CLIENT_ID_HEADER]: "nonexistent-service",
        "X-Harden-Signature": signature,
        "X-Harden-Timestamp": timestamp,
      },
    });
    expect(response.status).toBe(401);
    const json = (await response.json()) as { error: string };
    expect(json.error).toBe("unknown_client");
  });

  it("no client ID falls back to default secret", async () => {
    const { signature, timestamp } = signReq(
      DEFAULT_SECRET,
      "GET",
      "/api/test"
    );
    const response = await fetch(`${baseUrl}/api/test`, {
      headers: {
        "X-Harden-Signature": signature,
        "X-Harden-Timestamp": timestamp,
      },
    });
    expect(response.status).toBe(200);
  });

  it("payment client uses payment secret", async () => {
    const { signature, timestamp } = signReq(
      PAYMENT_SECRET,
      "GET",
      "/api/test"
    );
    const response = await fetch(`${baseUrl}/api/test`, {
      headers: {
        [CLIENT_ID_HEADER]: "payment-service",
        "X-Harden-Signature": signature,
        "X-Harden-Timestamp": timestamp,
      },
    });
    expect(response.status).toBe(200);
  });
});

describe("Client factory adds X-Harden-Client-Id", () => {
  it("createClient includes client ID header in requests", async () => {
    let capturedHeaders: Record<string, string> = {};

    // Create a mock fetch that captures headers
    const mockFetch = async (
      url: string | URL | Request,
      init?: RequestInit
    ): Promise<Response> => {
      if (init?.headers) {
        const headers = init.headers as Record<string, string>;
        capturedHeaders = { ...headers };
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    };

    const clientConfig: HmacConfig = {
      sharedSecretBase64: ORDER_SECRET,
      signedHeaders: noneConfig,
      timestampToleranceSeconds: 30,
      targets: {
        "order-service": {
          baseUrl: "https://orders.example.com",
          sharedSecret: ORDER_SECRET,
        },
      },
    };

    const factory = createHmacClientFactory(clientConfig, mockFetch);
    const ordersFetch = factory.createClient("order-service");
    await ordersFetch("/api/orders");

    expect(capturedHeaders[CLIENT_ID_HEADER]).toBe("order-service");
  });
});

describe("Env loader parses clients", () => {
  it("loads clients from environment variables", async () => {
    const env: Record<string, string> = {
      HARDEN_HMAC_SHARED_SECRET_BASE64: DEFAULT_SECRET,
      HARDEN_HMAC_CLIENTS__ORDER_SERVICE__SHARED_SECRET: ORDER_SECRET,
      HARDEN_HMAC_CLIENTS__PAYMENT_SERVICE__SHARED_SECRET: PAYMENT_SECRET,
    };
    const loaded = await fromEnv("HARDEN_HMAC_", env);
    expect(loaded.clients?.["order-service"]?.sharedSecret).toBe(ORDER_SECRET);
    expect(loaded.clients?.["payment-service"]?.sharedSecret).toBe(
      PAYMENT_SECRET
    );
  });
});
