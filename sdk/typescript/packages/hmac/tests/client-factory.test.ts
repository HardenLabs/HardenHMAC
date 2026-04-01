import { describe, it, expect, vi } from "vitest";
import type {
  HmacConfig,
  HmacResponse,
  HttpAdapter,
} from "../src/index.js";
import {
  noneSignedHeadersConfig,
  SIGNATURE_HEADER,
  TIMESTAMP_HEADER,
  FetchAdapter,
  AxiosAdapter,
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

/** Create a mock fetch that captures URL and headers from each call. */
function createMockFetch(): {
  mockFetch: typeof globalThis.fetch;
  captured: { url: string; headers: Record<string, string>; method: string; body: string | undefined }[];
} {
  const captured: { url: string; headers: Record<string, string>; method: string; body: string | undefined }[] = [];
  const mockFetch = vi.fn(
    async (url: string | URL | Request, init?: RequestInit) => {
      const resolvedUrl = typeof url === "string" ? url : url.toString();
      const headers: Record<string, string> = {};
      if (init?.headers && typeof init.headers === "object" && !Array.isArray(init.headers) && !(init.headers instanceof Headers)) {
        Object.assign(headers, init.headers);
      }
      captured.push({
        url: resolvedUrl,
        headers,
        method: init?.method ?? "GET",
        body: typeof init?.body === "string" ? init.body : undefined,
      });
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    }
  );
  return { mockFetch: mockFetch as typeof globalThis.fetch, captured };
}

describe("createHmacClientFactory", () => {
  it("throws for unknown target", () => {
    const config = makeConfig();
    const factory = createHmacClientFactory(config);
    expect(() => factory.createClient("nonexistent")).toThrow(
      /nonexistent.*not configured/
    );
  });

  it("creates client with correct base URL and signing via get()", async () => {
    const config = makeConfig();
    const { mockFetch, captured } = createMockFetch();

    const factory = createHmacClientFactory(config, { fetchFn: mockFetch });
    const client = factory.createClient("order-service");

    const resp = await client.get("/api/orders");

    expect(resp.status).toBe(200);
    expect(captured).toHaveLength(1);
    expect(captured[0]!.url).toBe("https://orders.example.com/api/orders");
    expect(captured[0]!.headers[SIGNATURE_HEADER.toLowerCase()] ?? captured[0]!.headers[SIGNATURE_HEADER]).toBeDefined();
    expect(captured[0]!.headers[TIMESTAMP_HEADER.toLowerCase()] ?? captured[0]!.headers[TIMESTAMP_HEADER]).toBeDefined();
  });

  it("strips trailing slash from base URL", async () => {
    const config = makeConfig();
    const { mockFetch, captured } = createMockFetch();

    const factory = createHmacClientFactory(config, { fetchFn: mockFetch });
    const client = factory.createClient("payment-service");

    await client.get("/api/pay");

    expect(captured[0]!.url).toBe("https://payments.example.com/api/pay");
  });

  it("signs with target-specific secret (different signatures)", async () => {
    const config = makeConfig();
    const { mockFetch, captured } = createMockFetch();

    const factory = createHmacClientFactory(config, { fetchFn: mockFetch });
    const ordersClient = factory.createClient("order-service");
    const paymentsClient = factory.createClient("payment-service");

    await ordersClient.get("/api/test");
    await paymentsClient.get("/api/test");

    expect(captured).toHaveLength(2);
    const ordersSig = captured[0]!.headers[SIGNATURE_HEADER];
    const paymentsSig = captured[1]!.headers[SIGNATURE_HEADER];
    expect(ordersSig).toBeDefined();
    expect(paymentsSig).toBeDefined();
    expect(ordersSig).not.toBe(paymentsSig);
  });

  it("post() sends body and uses POST method", async () => {
    const config = makeConfig();
    const { mockFetch, captured } = createMockFetch();

    const factory = createHmacClientFactory(config, { fetchFn: mockFetch });
    const client = factory.createClient("order-service");

    const body = JSON.stringify({ item: "widget" });
    await client.post("/api/orders", body, {
      headers: { "Content-Type": "application/json" },
    });

    expect(captured).toHaveLength(1);
    expect(captured[0]!.method).toBe("POST");
    expect(captured[0]!.body).toBe(body);
    expect(captured[0]!.headers["content-type"]).toBe("application/json");
  });

  it("put() sends body and uses PUT method", async () => {
    const config = makeConfig();
    const { mockFetch, captured } = createMockFetch();

    const factory = createHmacClientFactory(config, { fetchFn: mockFetch });
    const client = factory.createClient("order-service");

    await client.put("/api/orders/1", '{"status":"shipped"}');

    expect(captured[0]!.method).toBe("PUT");
    expect(captured[0]!.body).toBe('{"status":"shipped"}');
  });

  it("patch() sends body and uses PATCH method", async () => {
    const config = makeConfig();
    const { mockFetch, captured } = createMockFetch();

    const factory = createHmacClientFactory(config, { fetchFn: mockFetch });
    const client = factory.createClient("order-service");

    await client.patch("/api/orders/1", '{"note":"updated"}');

    expect(captured[0]!.method).toBe("PATCH");
  });

  it("delete() uses DELETE method without body", async () => {
    const config = makeConfig();
    const { mockFetch, captured } = createMockFetch();

    const factory = createHmacClientFactory(config, { fetchFn: mockFetch });
    const client = factory.createClient("order-service");

    await client.delete("/api/orders/1");

    expect(captured[0]!.method).toBe("DELETE");
    expect(captured[0]!.body).toBeUndefined();
  });

  it("request() allows arbitrary HTTP methods", async () => {
    const config = makeConfig();
    const { mockFetch, captured } = createMockFetch();

    const factory = createHmacClientFactory(config, { fetchFn: mockFetch });
    const client = factory.createClient("order-service");

    await client.request("OPTIONS", "/api/orders");

    expect(captured[0]!.method).toBe("OPTIONS");
  });

  it("request() uppercases the method", async () => {
    const config = makeConfig();
    const { mockFetch, captured } = createMockFetch();

    const factory = createHmacClientFactory(config, { fetchFn: mockFetch });
    const client = factory.createClient("order-service");

    await client.request("patch", "/api/orders/1", '{"x":1}');

    expect(captured[0]!.method).toBe("PATCH");
  });

  it("HmacResponse json() and text() both work", async () => {
    const config = makeConfig();
    const mockFetch = vi.fn(async () => {
      return new Response(JSON.stringify({ message: "hello" }), { status: 200 });
    }) as typeof globalThis.fetch;

    const factory = createHmacClientFactory(config, { fetchFn: mockFetch });
    const client = factory.createClient("order-service");

    const resp = await client.get("/api/test");
    const json = await resp.json();
    expect(json).toEqual({ message: "hello" });

    // text() should also work after json() (cached body)
    const text = await resp.text();
    expect(text).toBe('{"message":"hello"}');
  });
});

describe("AxiosAdapter", () => {
  it("works with a mock axios instance", async () => {
    const config = makeConfig();

    const capturedRequests: { url: string; method: string; data?: string; headers?: Record<string, string> }[] = [];
    const mockAxios = {
      request: vi.fn(async (reqConfig: { url: string; method: string; data?: string; headers?: Record<string, string> }) => {
        capturedRequests.push(reqConfig);
        return {
          status: 200,
          headers: { "content-type": "application/json" } as Record<string, string>,
          data: { result: "ok" },
        };
      }),
    };

    const factory = createHmacClientFactory(config, { axios: mockAxios });
    const client = factory.createClient("order-service");

    const resp = await client.get("/api/orders");

    expect(resp.status).toBe(200);
    const json = await resp.json();
    expect(json).toEqual({ result: "ok" });
    expect(capturedRequests).toHaveLength(1);
    expect(capturedRequests[0]!.url).toBe("https://orders.example.com/api/orders");
    expect(capturedRequests[0]!.method).toBe("GET");
    expect(capturedRequests[0]!.headers?.[SIGNATURE_HEADER]).toBeDefined();
  });

  it("axios option takes precedence over fetchFn", async () => {
    const config = makeConfig();

    const mockFetch = vi.fn(async () => new Response("fetch", { status: 200 })) as typeof globalThis.fetch;
    const mockAxios = {
      request: vi.fn(async () => ({
        status: 201,
        headers: {} as Record<string, string>,
        data: "axios",
      })),
    };

    const factory = createHmacClientFactory(config, { fetchFn: mockFetch, axios: mockAxios });
    const client = factory.createClient("order-service");

    const resp = await client.get("/api/test");

    expect(resp.status).toBe(201);
    expect(mockFetch).not.toHaveBeenCalled();
    expect(mockAxios.request).toHaveBeenCalledOnce();
  });

  it("AxiosAdapter json() parses string data", async () => {
    const mockAxios = {
      request: vi.fn(async () => ({
        status: 200,
        headers: {} as Record<string, string>,
        data: '{"key":"value"}',
      })),
    };

    const adapter = new AxiosAdapter(mockAxios);
    const resp = await adapter.request("https://example.com", "GET", undefined, {});

    const json = await resp.json();
    expect(json).toEqual({ key: "value" });
  });

  it("AxiosAdapter text() serializes object data", async () => {
    const mockAxios = {
      request: vi.fn(async () => ({
        status: 200,
        headers: {} as Record<string, string>,
        data: { key: "value" },
      })),
    };

    const adapter = new AxiosAdapter(mockAxios);
    const resp = await adapter.request("https://example.com", "GET", undefined, {});

    const text = await resp.text();
    expect(text).toBe('{"key":"value"}');
  });
});

describe("FetchAdapter", () => {
  it("converts Response headers to plain object", async () => {
    const mockFetch = vi.fn(async () => {
      return new Response("ok", {
        status: 200,
        headers: { "X-Custom": "value", "Content-Type": "text/plain" },
      });
    }) as typeof globalThis.fetch;

    const adapter = new FetchAdapter(mockFetch);
    const resp = await adapter.request("https://example.com", "GET", undefined, {});

    expect(resp.status).toBe(200);
    expect(resp.headers["x-custom"]).toBe("value");
    expect(resp.headers["content-type"]).toBe("text/plain");
  });
});
