import { describe, it, expect } from "vitest";
import { buildCanonicalString } from "../src/canonical.js";
import type { HmacConfig, SignedHeadersConfig } from "../src/config.js";
import { HmacValidationError } from "../src/errors.js";
import { sign } from "../src/signing.js";
import { validateRequest } from "../src/validation.js";

const TEST_SECRET = "dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24=";
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

describe("validateRequest", () => {
  it("succeeds for valid request", () => {
    const sig = signReq("GET", "/api/test", "", BASE_TIMESTAMP);
    expect(() =>
      validateRequest(config, {
        method: "GET",
        path: "/api/test",
        body: "",
        signatureHeader: sig,
        timestampHeader: String(BASE_TIMESTAMP),
        currentTimestamp: BASE_TIMESTAMP,
      })
    ).not.toThrow();
  });

  it("rejects missing signature", () => {
    try {
      validateRequest(config, {
        method: "GET",
        path: "/api/test",
        body: "",
        signatureHeader: undefined,
        timestampHeader: String(BASE_TIMESTAMP),
        currentTimestamp: BASE_TIMESTAMP,
      });
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(HmacValidationError);
      expect((e as HmacValidationError).errorType).toBe("missing_signature");
    }
  });

  it("rejects missing timestamp", () => {
    try {
      validateRequest(config, {
        method: "GET",
        path: "/api/test",
        body: "",
        signatureHeader: "some-sig",
        timestampHeader: undefined,
        currentTimestamp: BASE_TIMESTAMP,
      });
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(HmacValidationError);
      expect((e as HmacValidationError).errorType).toBe("missing_timestamp");
    }
  });

  it("rejects invalid timestamp", () => {
    try {
      validateRequest(config, {
        method: "GET",
        path: "/api/test",
        body: "",
        signatureHeader: "some-sig",
        timestampHeader: "not-a-number",
        currentTimestamp: BASE_TIMESTAMP,
      });
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(HmacValidationError);
      expect((e as HmacValidationError).errorType).toBe("invalid_timestamp");
    }
  });

  it("rejects expired timestamp", () => {
    const sig = signReq("GET", "/api/test", "", BASE_TIMESTAMP);
    try {
      validateRequest(config, {
        method: "GET",
        path: "/api/test",
        body: "",
        signatureHeader: sig,
        timestampHeader: String(BASE_TIMESTAMP),
        currentTimestamp: BASE_TIMESTAMP + 31,
      });
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(HmacValidationError);
      expect((e as HmacValidationError).errorType).toBe("timestamp_expired");
    }
  });

  it("accepts timestamp at exact tolerance", () => {
    const sig = signReq("GET", "/api/test", "", BASE_TIMESTAMP);
    expect(() =>
      validateRequest(config, {
        method: "GET",
        path: "/api/test",
        body: "",
        signatureHeader: sig,
        timestampHeader: String(BASE_TIMESTAMP),
        currentTimestamp: BASE_TIMESTAMP + 30,
      })
    ).not.toThrow();
  });

  it("rejects future timestamp", () => {
    const futureTs = BASE_TIMESTAMP + 100;
    const sig = signReq("GET", "/api/test", "", futureTs);
    try {
      validateRequest(config, {
        method: "GET",
        path: "/api/test",
        body: "",
        signatureHeader: sig,
        timestampHeader: String(futureTs),
        currentTimestamp: BASE_TIMESTAMP,
      });
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(HmacValidationError);
      expect((e as HmacValidationError).errorType).toBe(
        "timestamp_out_of_range"
      );
    }
  });

  it("rejects invalid signature", () => {
    try {
      validateRequest(config, {
        method: "GET",
        path: "/api/test",
        body: "",
        signatureHeader: "0".repeat(64),
        timestampHeader: String(BASE_TIMESTAMP),
        currentTimestamp: BASE_TIMESTAMP,
      });
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(HmacValidationError);
      expect((e as HmacValidationError).errorType).toBe("signature_invalid");
    }
  });

  it("rejects tampered body", () => {
    const sig = signReq("POST", "/api/test", '{"a":1}', BASE_TIMESTAMP);
    try {
      validateRequest(config, {
        method: "POST",
        path: "/api/test",
        body: '{"a":2}',
        signatureHeader: sig,
        timestampHeader: String(BASE_TIMESTAMP),
        currentTimestamp: BASE_TIMESTAMP,
      });
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(HmacValidationError);
      expect((e as HmacValidationError).errorType).toBe("signature_invalid");
    }
  });

  it("rejects tampered path", () => {
    const sig = signReq("GET", "/api/test", "", BASE_TIMESTAMP);
    try {
      validateRequest(config, {
        method: "GET",
        path: "/api/other",
        body: "",
        signatureHeader: sig,
        timestampHeader: String(BASE_TIMESTAMP),
        currentTimestamp: BASE_TIMESTAMP,
      });
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(HmacValidationError);
      expect((e as HmacValidationError).errorType).toBe("signature_invalid");
    }
  });

  it("honors custom tolerance", () => {
    const strictConfig: HmacConfig = {
      ...config,
      timestampToleranceSeconds: 5,
    };
    const sig = signReq("GET", "/api/test", "", BASE_TIMESTAMP);
    try {
      validateRequest(strictConfig, {
        method: "GET",
        path: "/api/test",
        body: "",
        signatureHeader: sig,
        timestampHeader: String(BASE_TIMESTAMP),
        currentTimestamp: BASE_TIMESTAMP + 6,
      });
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(HmacValidationError);
      expect((e as HmacValidationError).errorType).toBe("timestamp_expired");
    }
  });
});
