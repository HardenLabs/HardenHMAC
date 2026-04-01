import { describe, it, expect } from "vitest";
import { buildCanonicalString, buildSignedHeaders } from "../src/canonical.js";
import type { SignedHeadersConfig } from "../src/config.js";

const noneConfig: SignedHeadersConfig = {
  includeAuthorization: false,
  includeXHeaders: false,
  additionalHeaders: [],
  excludeHeaders: [],
};

describe("buildCanonicalString", () => {
  it("builds basic GET canonical string", () => {
    const result = buildCanonicalString({
      method: "GET",
      path: "/api/users",
      body: "",
      timestamp: 1700000000,
      signedHeadersConfig: noneConfig,
    });
    expect(result).toBe("GET\n/api/users\n\n\n1700000000");
  });

  it("includes body in POST", () => {
    const body = '{"name":"Alice"}';
    const result = buildCanonicalString({
      method: "POST",
      path: "/api/users",
      body,
      timestamp: 1700000001,
      signedHeadersConfig: noneConfig,
    });
    expect(result).toBe(`POST\n/api/users\n\n${body}\n1700000001`);
  });

  it("uppercases method", () => {
    const result = buildCanonicalString({
      method: "get",
      path: "/api/users",
      body: "",
      timestamp: 1700000000,
      signedHeadersConfig: noneConfig,
    });
    expect(result).toMatch(/^GET\n/);
  });

  it("includes query string in path", () => {
    const result = buildCanonicalString({
      method: "GET",
      path: "/api/users?active=true",
      body: "",
      timestamp: 1700000000,
      signedHeadersConfig: noneConfig,
    });
    expect(result).toContain("/api/users?active=true");
  });

  it("handles root path", () => {
    const result = buildCanonicalString({
      method: "GET",
      path: "/",
      body: "",
      timestamp: 1700000000,
      signedHeadersConfig: noneConfig,
    });
    expect(result).toBe("GET\n/\n\n\n1700000000");
  });

  it("sorts signed headers alphabetically", () => {
    const config: SignedHeadersConfig = {
      includeAuthorization: true,
      includeXHeaders: true,
      additionalHeaders: [],
      excludeHeaders: [],
    };
    const result = buildCanonicalString({
      method: "GET",
      path: "/",
      body: "",
      timestamp: 1700000000,
      signedHeadersConfig: config,
      requestHeaders: {
        "X-Request-Id": "abc",
        Authorization: "Bearer tok",
      },
    });
    expect(result).toContain(
      "authorization:Bearer tok\nx-request-id:abc"
    );
  });

  it("excludes X-Harden-* headers", () => {
    const config: SignedHeadersConfig = {
      includeAuthorization: false,
      includeXHeaders: true,
      additionalHeaders: [],
      excludeHeaders: [],
    };
    const result = buildCanonicalString({
      method: "GET",
      path: "/",
      body: "",
      timestamp: 1700000000,
      signedHeadersConfig: config,
      requestHeaders: {
        "X-Request-Id": "abc",
        "X-Harden-Signature": "should-be-excluded",
      },
    });
    expect(result).toContain("x-request-id:abc");
    expect(result).not.toContain("x-harden-");
  });

  it("applies exclude override", () => {
    const config: SignedHeadersConfig = {
      includeAuthorization: false,
      includeXHeaders: true,
      additionalHeaders: [],
      excludeHeaders: ["X-Custom-B"],
    };
    const result = buildCanonicalString({
      method: "GET",
      path: "/",
      body: "",
      timestamp: 1700000000,
      signedHeadersConfig: config,
      requestHeaders: {
        "X-Custom-A": "keep",
        "X-Custom-B": "exclude",
      },
    });
    expect(result).toContain("x-custom-a:keep");
    expect(result).not.toContain("x-custom-b");
  });

  it("trims header values", () => {
    const config: SignedHeadersConfig = {
      includeAuthorization: true,
      includeXHeaders: false,
      additionalHeaders: [],
      excludeHeaders: [],
    };
    const result = buildCanonicalString({
      method: "GET",
      path: "/",
      body: "",
      timestamp: 1700000000,
      signedHeadersConfig: config,
      requestHeaders: {
        Authorization: "  Bearer tok  ",
      },
    });
    expect(result).toContain("authorization:Bearer tok");
  });

  // ATK-1: Newline injection validation
  it("throws on newline in method", () => {
    expect(() =>
      buildCanonicalString({
        method: "GET\nX-Injected:evil",
        path: "/api/test",
        body: "",
        timestamp: 1700000000,
        signedHeadersConfig: noneConfig,
      })
    ).toThrow("method must not contain newline characters");
  });

  it("throws on newline in path", () => {
    expect(() =>
      buildCanonicalString({
        method: "GET",
        path: "/api/test\nX-Injected:evil",
        body: "",
        timestamp: 1700000000,
        signedHeadersConfig: noneConfig,
      })
    ).toThrow("path must not contain newline characters");
  });

  // ATK-3: X-Harden-Client-Id always signed
  it("signs X-Harden-Client-Id even when includeXHeaders is false", () => {
    const config: SignedHeadersConfig = {
      includeAuthorization: false,
      includeXHeaders: false,
      additionalHeaders: [],
      excludeHeaders: [],
    };
    const result = buildCanonicalString({
      method: "GET",
      path: "/api/secure",
      body: "",
      timestamp: 1700000050,
      signedHeadersConfig: config,
      requestHeaders: {
        "X-Harden-Client-Id": "my-client",
        "X-Custom-Header": "should-not-be-signed",
      },
    });
    expect(result).toContain("x-harden-client-id:my-client");
    expect(result).not.toContain("x-custom-header");
  });

  it("includes additional headers", () => {
    const config: SignedHeadersConfig = {
      includeAuthorization: false,
      includeXHeaders: false,
      additionalHeaders: ["Content-Type"],
      excludeHeaders: [],
    };
    const result = buildCanonicalString({
      method: "GET",
      path: "/",
      body: "",
      timestamp: 1700000000,
      signedHeadersConfig: config,
      requestHeaders: {
        "Content-Type": "application/json",
        Accept: "text/html",
      },
    });
    expect(result).toContain("content-type:application/json");
    expect(result).not.toContain("accept");
  });
});

describe("buildSignedHeaders", () => {
  it("returns header names sorted", () => {
    const config: SignedHeadersConfig = {
      includeAuthorization: true,
      includeXHeaders: true,
      additionalHeaders: [],
      excludeHeaders: [],
    };
    const { headerString, headerNames } = buildSignedHeaders(config, {
      "X-Request-Id": "abc",
      Authorization: "Bearer tok",
    });
    expect(headerNames).toEqual(["authorization", "x-request-id"]);
    expect(headerString).toBe(
      "authorization:Bearer tok\nx-request-id:abc"
    );
  });
});
