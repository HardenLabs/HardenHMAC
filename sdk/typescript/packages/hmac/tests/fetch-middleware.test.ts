import { describe, it, expect, vi } from "vitest";
import { createSignedFetch } from "../src/middleware/fetch.js";
import type { HmacConfig } from "../src/config.js";
import {
  noneSignedHeadersConfig,
  SIGNATURE_HEADER,
  TIMESTAMP_HEADER,
} from "../src/config.js";
import { verify } from "../src/signing.js";

const TEST_SECRET =
  "dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24=";

function makeConfig(): HmacConfig {
  return {
    sharedSecretBase64: TEST_SECRET,
    timestampToleranceSeconds: 30,
    signedHeaders: noneSignedHeadersConfig(),
  };
}

/** Create a mock fetch that captures the init passed to it. */
function createMockFetch(): {
  mockFetch: typeof globalThis.fetch;
  captured: { url: string | URL; headers: Record<string, string>; method: string; body: string | undefined }[];
} {
  const captured: { url: string | URL; headers: Record<string, string>; method: string; body: string | undefined }[] = [];
  const mockFetch = vi.fn(
    async (url: string | URL | Request, init?: RequestInit) => {
      const headers: Record<string, string> = {};
      if (init?.headers && typeof init.headers === "object" && !Array.isArray(init.headers) && !(init.headers instanceof Headers)) {
        Object.assign(headers, init.headers);
      }
      captured.push({
        url: typeof url === "string" ? url : url instanceof URL ? url : url.url,
        headers,
        method: init?.method ?? "GET",
        body: typeof init?.body === "string" ? init.body : undefined,
      });
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    }
  );
  return { mockFetch: mockFetch as typeof globalThis.fetch, captured };
}

describe("createSignedFetch", () => {
  it("adds signing headers to GET requests", async () => {
    const config = makeConfig();
    const { mockFetch, captured } = createMockFetch();
    const signedFetch = createSignedFetch(config, mockFetch);

    await signedFetch("/api/test");

    expect(captured).toHaveLength(1);
    expect(captured[0]!.headers[SIGNATURE_HEADER]).toBeDefined();
    expect(captured[0]!.headers[TIMESTAMP_HEADER]).toBeDefined();
    expect(captured[0]!.headers[SIGNATURE_HEADER]).toMatch(/^[0-9a-f]{64}$/);
  });

  it("adds signing headers to POST requests with string body", async () => {
    const config = makeConfig();
    const { mockFetch, captured } = createMockFetch();
    const signedFetch = createSignedFetch(config, mockFetch);

    const body = '{"name":"Alice"}';
    await signedFetch("/api/users", {
      method: "POST",
      body,
    });

    expect(captured).toHaveLength(1);
    expect(captured[0]!.headers[SIGNATURE_HEADER]).toBeDefined();
    expect(captured[0]!.headers[TIMESTAMP_HEADER]).toBeDefined();
    expect(captured[0]!.method).toBe("POST");
  });

  it("extracts path correctly from absolute URLs", async () => {
    const config = makeConfig();
    const { mockFetch, captured } = createMockFetch();
    const signedFetch = createSignedFetch(config, mockFetch);

    await signedFetch("https://api.example.com/api/orders");

    expect(captured).toHaveLength(1);
    // The URL passed to the underlying fetch should be the original absolute URL
    expect(captured[0]!.url).toBe("https://api.example.com/api/orders");
    // The signature should be valid — verify it was signed with the correct path
    const sig = captured[0]!.headers[SIGNATURE_HEADER]!;
    const ts = captured[0]!.headers[TIMESTAMP_HEADER]!;
    const canonical = `GET\n/api/orders\n\n\n${ts}`;
    expect(verify(TEST_SECRET, canonical, sig)).toBe(true);
  });

  it("works with URL object input", async () => {
    const config = makeConfig();
    const { mockFetch, captured } = createMockFetch();
    const signedFetch = createSignedFetch(config, mockFetch);

    const url = new URL("https://api.example.com/api/items");
    await signedFetch(url);

    expect(captured).toHaveLength(1);
    expect(captured[0]!.headers[SIGNATURE_HEADER]).toBeDefined();
    expect(captured[0]!.headers[TIMESTAMP_HEADER]).toBeDefined();
    // Verify signature uses pathname from URL object
    const sig = captured[0]!.headers[SIGNATURE_HEADER]!;
    const ts = captured[0]!.headers[TIMESTAMP_HEADER]!;
    const canonical = `GET\n/api/items\n\n\n${ts}`;
    expect(verify(TEST_SECRET, canonical, sig)).toBe(true);
  });

  it("handles headers as plain object", async () => {
    const config = makeConfig();
    const { mockFetch, captured } = createMockFetch();
    const signedFetch = createSignedFetch(config, mockFetch);

    await signedFetch("/api/test", {
      headers: { "Content-Type": "application/json", "X-Custom": "value" },
    });

    expect(captured).toHaveLength(1);
    expect(captured[0]!.headers[SIGNATURE_HEADER]).toBeDefined();
    // Existing headers should be preserved (lowercased by the implementation)
    expect(captured[0]!.headers["content-type"]).toBe("application/json");
    expect(captured[0]!.headers["x-custom"]).toBe("value");
  });

  it("handles headers as Headers instance", async () => {
    const config = makeConfig();
    const { mockFetch, captured } = createMockFetch();
    const signedFetch = createSignedFetch(config, mockFetch);

    const headers = new Headers();
    headers.set("Authorization", "Bearer token123");
    headers.set("Accept", "application/json");

    await signedFetch("/api/test", { headers });

    expect(captured).toHaveLength(1);
    expect(captured[0]!.headers[SIGNATURE_HEADER]).toBeDefined();
    expect(captured[0]!.headers["authorization"]).toBe("Bearer token123");
    expect(captured[0]!.headers["accept"]).toBe("application/json");
  });

  it("handles headers as array of tuples", async () => {
    const config = makeConfig();
    const { mockFetch, captured } = createMockFetch();
    const signedFetch = createSignedFetch(config, mockFetch);

    const headers: [string, string][] = [
      ["Content-Type", "text/plain"],
      ["X-Request-Id", "abc-123"],
    ];

    await signedFetch("/api/test", { headers });

    expect(captured).toHaveLength(1);
    expect(captured[0]!.headers[SIGNATURE_HEADER]).toBeDefined();
    expect(captured[0]!.headers["content-type"]).toBe("text/plain");
    expect(captured[0]!.headers["x-request-id"]).toBe("abc-123");
  });

  it("rejects non-string body with an error", async () => {
    const config = makeConfig();
    const { mockFetch } = createMockFetch();
    const signedFetch = createSignedFetch(config, mockFetch);

    const formData = new FormData();
    formData.append("file", "data");

    await expect(
      signedFetch("/api/upload", {
        method: "POST",
        body: formData,
      })
    ).rejects.toThrow("Only string request bodies are supported");
  });

  it("handles requests with query strings in the URL", async () => {
    const config = makeConfig();
    const { mockFetch, captured } = createMockFetch();
    const signedFetch = createSignedFetch(config, mockFetch);

    await signedFetch("https://api.example.com/api/search?q=hello&page=2");

    expect(captured).toHaveLength(1);
    const sig = captured[0]!.headers[SIGNATURE_HEADER]!;
    const ts = captured[0]!.headers[TIMESTAMP_HEADER]!;
    // The path should include the query string
    const canonical = `GET\n/api/search?q=hello&page=2\n\n\n${ts}`;
    expect(verify(TEST_SECRET, canonical, sig)).toBe(true);
  });

  it("defaults method to GET when init is undefined", async () => {
    const config = makeConfig();
    const { mockFetch, captured } = createMockFetch();
    const signedFetch = createSignedFetch(config, mockFetch);

    await signedFetch("/api/test");

    expect(captured).toHaveLength(1);
    // Verify the signature was computed with GET
    const sig = captured[0]!.headers[SIGNATURE_HEADER]!;
    const ts = captured[0]!.headers[TIMESTAMP_HEADER]!;
    const canonical = `GET\n/api/test\n\n\n${ts}`;
    expect(verify(TEST_SECRET, canonical, sig)).toBe(true);
  });

  it("passes through the original URL to the underlying fetch", async () => {
    const config = makeConfig();
    const { mockFetch, captured } = createMockFetch();
    const signedFetch = createSignedFetch(config, mockFetch);

    const originalUrl = "https://api.example.com/api/test";
    await signedFetch(originalUrl);

    // The URL passed to the mock should be the original, not the extracted path
    expect(captured[0]!.url).toBe(originalUrl);
  });
});
