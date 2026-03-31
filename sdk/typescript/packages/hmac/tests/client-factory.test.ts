import { describe, it, expect, vi } from "vitest";
import {
  type HmacConfig,
  noneSignedHeadersConfig,
  defaultSignedHeadersConfig,
  SIGNATURE_HEADER,
  TIMESTAMP_HEADER,
} from "../src/index.js";
import { createHmacClientFactory } from "../src/client-factory.js";

const ORDERS_SECRET = "b3JkZXJzLXNlY3JldC1rZXktMzItYnl0ZXMhISEhIQ==";
const PAYMENTS_SECRET = "cGF5bWVudHMtc2VjcmV0LWtleS0zMi1ieXRlcyEhISE=";

function makeConfig(): HmacConfig {
  return {
    sharedSecretBase64: "",
    timestampToleranceSeconds: 30,
    signedHeaders: noneSignedHeadersConfig(),
    targets: {
      "order-service": {
        baseUrl: "https://orders.example.com",
        sharedSecret: ORDERS_SECRET,
      },
      "payment-service": {
        baseUrl: "https://payments.example.com/",
        sharedSecret: PAYMENTS_SECRET,
        signedHeaders: noneSignedHeadersConfig(),
      },
    },
  };
}

describe("createHmacClientFactory", () => {
  it("throws for unknown target", () => {
    const config = makeConfig();
    const factory = createHmacClientFactory(config);
    expect(() => factory.createClient("nonexistent")).toThrow(
      /nonexistent.*not configured/
    );
  });

  it("creates fetch with correct base URL and signing", async () => {
    const config = makeConfig();
    let capturedUrl = "";
    let capturedHeaders: Record<string, string> = {};

    const mockFetch = vi.fn(
      async (url: string | URL | Request, init?: RequestInit) => {
        capturedUrl = typeof url === "string" ? url : url.toString();
        if (init?.headers && typeof init.headers === "object" && !Array.isArray(init.headers) && !(init.headers instanceof Headers)) {
          capturedHeaders = init.headers as Record<string, string>;
        }
        return new Response("ok", { status: 200 });
      }
    );

    const factory = createHmacClientFactory(config, mockFetch as typeof globalThis.fetch);
    const ordersFetch = factory.createClient("order-service");

    await ordersFetch("/api/orders");

    expect(capturedUrl).toBe("https://orders.example.com/api/orders");
    expect(capturedHeaders[SIGNATURE_HEADER.toLowerCase()] ?? capturedHeaders[SIGNATURE_HEADER]).toBeDefined();
    expect(capturedHeaders[TIMESTAMP_HEADER.toLowerCase()] ?? capturedHeaders[TIMESTAMP_HEADER]).toBeDefined();
  });

  it("strips trailing slash from base URL", async () => {
    const config = makeConfig();
    let capturedUrl = "";

    const mockFetch = vi.fn(async (url: string | URL | Request) => {
      capturedUrl = typeof url === "string" ? url : url.toString();
      return new Response("ok", { status: 200 });
    });

    const factory = createHmacClientFactory(config, mockFetch as typeof globalThis.fetch);
    const paymentsFetch = factory.createClient("payment-service");

    await paymentsFetch("/api/pay");

    expect(capturedUrl).toBe("https://payments.example.com/api/pay");
  });

  it("signs with target-specific secret", async () => {
    const config = makeConfig();
    const capturedHeaders: Record<string, string>[] = [];

    const mockFetch = vi.fn(async (_url: string | URL | Request, init?: RequestInit) => {
      if (init?.headers && typeof init.headers === "object" && !Array.isArray(init.headers) && !(init.headers instanceof Headers)) {
        capturedHeaders.push({ ...(init.headers as Record<string, string>) });
      }
      return new Response("ok", { status: 200 });
    });

    const factory = createHmacClientFactory(config, mockFetch as typeof globalThis.fetch);
    const ordersFetch = factory.createClient("order-service");
    const paymentsFetch = factory.createClient("payment-service");

    await ordersFetch("/api/test");
    await paymentsFetch("/api/test");

    expect(capturedHeaders).toHaveLength(2);
    // Different secrets should produce different signatures
    const ordersSig = capturedHeaders[0]![SIGNATURE_HEADER];
    const paymentsSig = capturedHeaders[1]![SIGNATURE_HEADER];
    expect(ordersSig).toBeDefined();
    expect(paymentsSig).toBeDefined();
    expect(ordersSig).not.toBe(paymentsSig);
  });
});
