import { describe, it, expect } from "vitest";
import {
  type HmacConfig,
  createHmacConfig,
  noneSignedHeadersConfig,
  defaultSignedHeadersConfig,
  getEffectiveSecret,
  getEffectiveSignedHeaders,
  getEffectiveTimestampTolerance,
  configForTarget,
  sign,
  verify,
  buildCanonicalString,
} from "../src/index.js";

const GLOBAL_SECRET = "Z2xvYmFsLXNlY3JldC1rZXktMzItYnl0ZXMhISEhIQ==";
const ORDERS_SECRET = "b3JkZXJzLXNlY3JldC1rZXktMzItYnl0ZXMhISEhIQ==";
const PAYMENTS_SECRET = "cGF5bWVudHMtc2VjcmV0LWtleS0zMi1ieXRlcyEhISE=";

function makeMultiConfig(): HmacConfig {
  return {
    sharedSecretBase64: GLOBAL_SECRET,
    timestampToleranceSeconds: 30,
    signedHeaders: defaultSignedHeadersConfig(),
    targets: {
      "order-service": {
        baseUrl: "https://orders.example.com",
        sharedSecret: ORDERS_SECRET,
      },
      "payment-service": {
        baseUrl: "https://payments.example.com",
        sharedSecret: PAYMENTS_SECRET,
        timestampToleranceSeconds: 60,
        signedHeaders: noneSignedHeadersConfig(),
      },
      "fallback-service": {
        baseUrl: "https://fallback.example.com",
        sharedSecret: "", // should fall back to global
      },
    },
  };
}

describe("multi-target config", () => {
  describe("getEffectiveSecret", () => {
    it("returns target secret when set", () => {
      const config = makeMultiConfig();
      expect(getEffectiveSecret(config, "order-service")).toBe(ORDERS_SECRET);
      expect(getEffectiveSecret(config, "payment-service")).toBe(PAYMENTS_SECRET);
    });

    it("falls back to global when target secret is empty", () => {
      const config = makeMultiConfig();
      expect(getEffectiveSecret(config, "fallback-service")).toBe(GLOBAL_SECRET);
    });

    it("throws for unknown target", () => {
      const config = makeMultiConfig();
      expect(() => getEffectiveSecret(config, "nonexistent")).toThrow(
        /nonexistent.*not configured/
      );
    });
  });

  describe("getEffectiveSignedHeaders", () => {
    it("returns target override when set", () => {
      const config = makeMultiConfig();
      const headers = getEffectiveSignedHeaders(config, "payment-service");
      expect(headers.includeAuthorization).toBe(false);
      expect(headers.includeXHeaders).toBe(false);
    });

    it("returns global when not overridden", () => {
      const config = makeMultiConfig();
      const headers = getEffectiveSignedHeaders(config, "order-service");
      expect(headers.includeAuthorization).toBe(true);
    });
  });

  describe("getEffectiveTimestampTolerance", () => {
    it("returns target override when set", () => {
      const config = makeMultiConfig();
      expect(getEffectiveTimestampTolerance(config, "payment-service")).toBe(60);
    });

    it("returns global when not overridden", () => {
      const config = makeMultiConfig();
      expect(getEffectiveTimestampTolerance(config, "order-service")).toBe(30);
    });
  });

  describe("configForTarget", () => {
    it("returns resolved config", () => {
      const config = makeMultiConfig();
      const payment = configForTarget(config, "payment-service");
      expect(payment.sharedSecretBase64).toBe(PAYMENTS_SECRET);
      expect(payment.timestampToleranceSeconds).toBe(60);
      expect(payment.signedHeaders.includeAuthorization).toBe(false);
    });

    it("fallback target uses global defaults", () => {
      const config = makeMultiConfig();
      const fallback = configForTarget(config, "fallback-service");
      expect(fallback.sharedSecretBase64).toBe(GLOBAL_SECRET);
      expect(fallback.timestampToleranceSeconds).toBe(30);
      expect(fallback.signedHeaders.includeAuthorization).toBe(true);
    });
  });

  describe("backwards compatibility", () => {
    it("single-secret mode still works", () => {
      const config = createHmacConfig(GLOBAL_SECRET);
      expect(config.sharedSecretBase64).toBe(GLOBAL_SECRET);
      expect(config.targets).toBeUndefined();
    });

    it("sign and verify with single secret", () => {
      const config = createHmacConfig(GLOBAL_SECRET, {
        signedHeaders: noneSignedHeadersConfig(),
      });
      const ts = Math.floor(Date.now() / 1000);
      const canonical = buildCanonicalString({
        method: "GET",
        path: "/api/test",
        body: "",
        timestamp: ts,
        signedHeadersConfig: config.signedHeaders,
      });
      const sig = sign(config.sharedSecretBase64, canonical);
      expect(verify(config.sharedSecretBase64, canonical, sig)).toBe(true);
    });
  });

  describe("cross-target signing", () => {
    it("different targets produce different signatures", () => {
      const config = makeMultiConfig();
      const ts = Math.floor(Date.now() / 1000);

      const ordersConfig = configForTarget(config, "order-service");
      const paymentsConfig = configForTarget(config, "payment-service");

      const ordersCanonical = buildCanonicalString({
        method: "GET",
        path: "/api/test",
        body: "",
        timestamp: ts,
        signedHeadersConfig: ordersConfig.signedHeaders,
      });
      const paymentsCanonical = buildCanonicalString({
        method: "GET",
        path: "/api/test",
        body: "",
        timestamp: ts,
        signedHeadersConfig: paymentsConfig.signedHeaders,
      });

      const ordersSig = sign(ordersConfig.sharedSecretBase64, ordersCanonical);
      const paymentsSig = sign(paymentsConfig.sharedSecretBase64, paymentsCanonical);

      expect(ordersSig).not.toBe(paymentsSig);
    });
  });
});
