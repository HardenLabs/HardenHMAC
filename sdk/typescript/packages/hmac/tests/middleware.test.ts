import { describe, it, expect, beforeAll, afterAll } from "vitest";
import express from "express";
import type { Server } from "node:http";
import { buildCanonicalString } from "../src/canonical.js";
import type { HmacConfig, SignedHeadersConfig } from "../src/config.js";
import { sign } from "../src/signing.js";
import { hardenHmacMiddleware } from "../src/middleware/express.js";

const TEST_SECRET =
  "dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24=";
const BASE_TIMESTAMP = 1700000000;

const noneConfig: SignedHeadersConfig = {
  includeAuthorization: false,
  includeXHeaders: false,
  additionalHeaders: [],
  excludeHeaders: [],
};

const config: HmacConfig = {
  sharedSecretBase64: TEST_SECRET,
  signedHeaders: noneConfig,
  timestampToleranceSeconds: 30,
};

function signReq(
  method: string,
  path: string,
  body: string,
  timestamp: number
): string {
  const canonical = buildCanonicalString({
    method,
    path,
    body,
    timestamp,
    signedHeadersConfig: noneConfig,
  });
  return sign(TEST_SECRET, canonical);
}

let server: Server;
let baseUrl: string;

beforeAll(async () => {
  const app = express();
  // Use express.text() for raw body, as required by the middleware
  app.use(express.text({ type: "*/*" }));
  app.use(hardenHmacMiddleware(config));

  app.get("/api/test", (_req, res) => {
    res.json({ message: "ok" });
  });
  app.post("/api/test", (_req, res) => {
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

describe("Express hardenHmacMiddleware", () => {
  it("passes a valid GET request", async () => {
    const ts = Math.floor(Date.now() / 1000);
    const sig = signReq("GET", "/api/test", "", ts);

    const response = await fetch(`${baseUrl}/api/test`, {
      headers: {
        "X-Harden-Signature": sig,
        "X-Harden-Timestamp": String(ts),
      },
    });

    expect(response.status).toBe(200);
    const json = (await response.json()) as { message: string };
    expect(json.message).toBe("ok");
  });

  it("rejects missing signature with 400", async () => {
    const response = await fetch(`${baseUrl}/api/test`, {
      headers: {
        "X-Harden-Timestamp": String(BASE_TIMESTAMP),
      },
    });

    expect(response.status).toBe(400);
    const json = (await response.json()) as { error: string };
    expect(json.error).toBe("missing_signature");
  });

  it("rejects invalid signature with 401", async () => {
    const ts = Math.floor(Date.now() / 1000);
    const response = await fetch(`${baseUrl}/api/test`, {
      headers: {
        "X-Harden-Signature": "0".repeat(64),
        "X-Harden-Timestamp": String(ts),
      },
    });

    expect(response.status).toBe(401);
    const json = (await response.json()) as { error: string };
    expect(json.error).toBe("signature_invalid");
  });

  it("rejects expired timestamp with 401", async () => {
    // Timestamp from the far past (2023)
    const oldTs = BASE_TIMESTAMP;
    const sig = signReq("GET", "/api/test", "", oldTs);

    const response = await fetch(`${baseUrl}/api/test`, {
      headers: {
        "X-Harden-Signature": sig,
        "X-Harden-Timestamp": String(oldTs),
      },
    });

    expect(response.status).toBe(401);
    const json = (await response.json()) as { error: string };
    expect(json.error).toBe("timestamp_expired");
  });

  it("passes a valid POST with body", async () => {
    const body = '{"name":"Alice"}';
    const ts = Math.floor(Date.now() / 1000);
    const sig = signReq("POST", "/api/test", body, ts);

    const response = await fetch(`${baseUrl}/api/test`, {
      method: "POST",
      headers: {
        "Content-Type": "text/plain",
        "X-Harden-Signature": sig,
        "X-Harden-Timestamp": String(ts),
      },
      body,
    });

    expect(response.status).toBe(200);
    const json = (await response.json()) as { message: string };
    expect(json.message).toBe("ok");
  });

  it("rejects parsed object body with 400", async () => {
    // Create a separate Express app that uses express.json() before our middleware
    const jsonApp = express();
    jsonApp.use(express.json());
    jsonApp.use(hardenHmacMiddleware(config));
    jsonApp.post("/api/test", (_req, res) => {
      res.json({ message: "ok" });
    });

    const jsonServer = await new Promise<Server>((resolve) => {
      const s = jsonApp.listen(0, () => resolve(s));
    });
    const addr = jsonServer.address();
    const port = addr && typeof addr !== "string" ? addr.port : 0;

    try {
      const ts = Math.floor(Date.now() / 1000);
      const body = '{"name":"test"}';
      const sig = signReq("POST", "/api/test", body, ts);

      const response = await fetch(`http://127.0.0.1:${port}/api/test`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Harden-Signature": sig,
          "X-Harden-Timestamp": String(ts),
        },
        body,
      });

      expect(response.status).toBe(400);
      const json = (await response.json()) as { error: string };
      expect(json.error).toBe("body_not_raw");
    } finally {
      await new Promise<void>((resolve, reject) => {
        jsonServer.close((err) => (err ? reject(err) : resolve()));
      });
    }
  });
});
