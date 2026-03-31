import { describe, it, expect } from "vitest";
import { fromEnv } from "../src/env-loader.js";

const GLOBAL_SECRET = "Z2xvYmFsLXNlY3JldC1rZXktMzItYnl0ZXMhISEhIQ==";
const ORDERS_SECRET = "b3JkZXJzLXNlY3JldC1rZXktMzItYnl0ZXMhISEhIQ==";
const PAYMENTS_SECRET = "cGF5bWVudHMtc2VjcmV0LWtleS0zMi1ieXRlcyEhISE=";

describe("fromEnv", () => {
  it("parses single secret", () => {
    const env: Record<string, string> = {
      HARDEN_HMAC_SHARED_SECRET_BASE64: GLOBAL_SECRET,
      HARDEN_HMAC_TIMESTAMP_TOLERANCE_SECONDS: "60",
    };
    const config = fromEnv("HARDEN_HMAC_", env);
    expect(config.sharedSecretBase64).toBe(GLOBAL_SECRET);
    expect(config.timestampToleranceSeconds).toBe(60);
  });

  it("parses multi-target", () => {
    const env: Record<string, string> = {
      HARDEN_HMAC_SHARED_SECRET_BASE64: GLOBAL_SECRET,
      HARDEN_HMAC_TARGETS__ORDER_SERVICE__BASE_URL: "https://orders.example.com",
      HARDEN_HMAC_TARGETS__ORDER_SERVICE__SHARED_SECRET: ORDERS_SECRET,
      HARDEN_HMAC_TARGETS__PAYMENT_SERVICE__BASE_URL: "https://payments.example.com",
      HARDEN_HMAC_TARGETS__PAYMENT_SERVICE__SHARED_SECRET: PAYMENTS_SECRET,
      HARDEN_HMAC_TARGETS__PAYMENT_SERVICE__TIMESTAMP_TOLERANCE_SECONDS: "60",
    };
    const config = fromEnv("HARDEN_HMAC_", env);

    expect(config.targets).toBeDefined();
    expect(Object.keys(config.targets!)).toHaveLength(2);
    expect(config.targets!["order-service"]!.baseUrl).toBe("https://orders.example.com");
    expect(config.targets!["order-service"]!.sharedSecret).toBe(ORDERS_SECRET);
    expect(config.targets!["payment-service"]!.baseUrl).toBe("https://payments.example.com");
    expect(config.targets!["payment-service"]!.timestampToleranceSeconds).toBe(60);
  });

  it("parses signed headers", () => {
    const env: Record<string, string> = {
      HARDEN_HMAC_SHARED_SECRET_BASE64: GLOBAL_SECRET,
      HARDEN_HMAC_SIGNED_HEADERS__INCLUDE_AUTHORIZATION: "false",
      HARDEN_HMAC_SIGNED_HEADERS__INCLUDE_X_HEADERS: "true",
    };
    const config = fromEnv("HARDEN_HMAC_", env);
    expect(config.signedHeaders.includeAuthorization).toBe(false);
    expect(config.signedHeaders.includeXHeaders).toBe(true);
  });

  it("uses custom prefix", () => {
    const env: Record<string, string> = {
      MY_APP_SHARED_SECRET_BASE64: GLOBAL_SECRET,
    };
    const config = fromEnv("MY_APP_", env);
    expect(config.sharedSecretBase64).toBe(GLOBAL_SECRET);
  });

  it("returns defaults for empty env", () => {
    const config = fromEnv("HARDEN_HMAC_", {});
    expect(config.sharedSecretBase64).toBe("");
    expect(config.targets).toBeUndefined();
    expect(config.timestampToleranceSeconds).toBe(30);
  });

  it("is case-insensitive on prefix", () => {
    const env: Record<string, string> = {
      harden_hmac_SHARED_SECRET_BASE64: GLOBAL_SECRET,
    };
    const config = fromEnv("HARDEN_HMAC_", env);
    expect(config.sharedSecretBase64).toBe(GLOBAL_SECRET);
  });
});
