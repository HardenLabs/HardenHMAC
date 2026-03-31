import { describe, it, expect, beforeAll, afterAll } from "vitest";
import express from "express";
import type { Server } from "node:http";
import { buildCanonicalString } from "../src/canonical.js";
import type { HmacConfig, SignedHeadersConfig } from "../src/config.js";
import { sign } from "../src/signing.js";
import { hardenHmacMiddleware, type SecretResolver } from "../src/middleware/express.js";

const DEFAULT_SECRET = "ZGVmYXVsdC1zZWNyZXQta2V5LTMyLWJ5dGVzISEhISE=";
const TENANT_A_SECRET = "dGVuYW50LWEtc2VjcmV0LWtleS0zMi1ieXRlcyEhIQ==";
const TENANT_B_SECRET = "dGVuYW50LWItc2VjcmV0LWtleS0zMi1ieXRlcyEhIQ==";

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
};

const secretResolver: SecretResolver = (req) => {
  const clientId = req.headers["x-client-id"] as string | undefined;
  if (clientId === "tenant-a") return TENANT_A_SECRET;
  if (clientId === "tenant-b") return TENANT_B_SECRET;
  return null;
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
  app.use(hardenHmacMiddleware(config, secretResolver));

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

describe("Express middleware with secretResolver", () => {
  it("tenant-a valid signature passes", async () => {
    const { signature, timestamp } = signReq(TENANT_A_SECRET, "GET", "/api/test");
    const response = await fetch(`${baseUrl}/api/test`, {
      headers: {
        "X-Client-Id": "tenant-a",
        "X-Harden-Signature": signature,
        "X-Harden-Timestamp": timestamp,
      },
    });
    expect(response.status).toBe(200);
  });

  it("tenant-b valid signature passes", async () => {
    const { signature, timestamp } = signReq(TENANT_B_SECRET, "GET", "/api/test");
    const response = await fetch(`${baseUrl}/api/test`, {
      headers: {
        "X-Client-Id": "tenant-b",
        "X-Harden-Signature": signature,
        "X-Harden-Timestamp": timestamp,
      },
    });
    expect(response.status).toBe(200);
  });

  it("wrong secret for tenant returns 401", async () => {
    const { signature, timestamp } = signReq(DEFAULT_SECRET, "GET", "/api/test");
    const response = await fetch(`${baseUrl}/api/test`, {
      headers: {
        "X-Client-Id": "tenant-a",
        "X-Harden-Signature": signature,
        "X-Harden-Timestamp": timestamp,
      },
    });
    expect(response.status).toBe(401);
  });

  it("no client-id falls back to default secret", async () => {
    const { signature, timestamp } = signReq(DEFAULT_SECRET, "GET", "/api/test");
    const response = await fetch(`${baseUrl}/api/test`, {
      headers: {
        "X-Harden-Signature": signature,
        "X-Harden-Timestamp": timestamp,
      },
    });
    expect(response.status).toBe(200);
  });
});

describe("Express middleware no secret", () => {
  it("returns 401 when no secret configured and resolver returns null", async () => {
    const noSecretConfig: HmacConfig = {
      sharedSecretBase64: "",
      signedHeaders: noneConfig,
      timestampToleranceSeconds: 30,
    };
    const nullResolver: SecretResolver = () => null;

    const app = express();
    app.use(express.text({ type: "*/*" }));
    app.use(hardenHmacMiddleware(noSecretConfig, nullResolver));
    app.get("/api/test", (_req, res) => res.json({ message: "ok" }));

    const noSecretServer = await new Promise<Server>((resolve) => {
      const s = app.listen(0, () => resolve(s));
    });
    const addr = noSecretServer.address();
    const port = addr && typeof addr !== "string" ? addr.port : 0;

    try {
      const ts = Math.floor(Date.now() / 1000);
      const response = await fetch(`http://127.0.0.1:${port}/api/test`, {
        headers: {
          "X-Harden-Signature": "a".repeat(64),
          "X-Harden-Timestamp": String(ts),
        },
      });
      expect(response.status).toBe(401);
      const json = (await response.json()) as { error: string };
      expect(json.error).toBe("no_secret");
    } finally {
      await new Promise<void>((resolve, reject) => {
        noSecretServer.close((err) => (err ? reject(err) : resolve()));
      });
    }
  });
});
