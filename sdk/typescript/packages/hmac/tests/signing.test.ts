import { describe, it, expect } from "vitest";
import { sign, verify } from "../src/signing.js";

const TEST_SECRET = "dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24=";

describe("sign", () => {
  it("produces 64-char lowercase hex", () => {
    const sig = sign(TEST_SECRET, "test data");
    expect(sig).toHaveLength(64);
    expect(sig).toMatch(/^[0-9a-f]{64}$/);
  });

  it("is deterministic", () => {
    const sig1 = sign(TEST_SECRET, "canonical string");
    const sig2 = sign(TEST_SECRET, "canonical string");
    expect(sig1).toBe(sig2);
  });

  it("different inputs produce different signatures", () => {
    const sig1 = sign(TEST_SECRET, "input 1");
    const sig2 = sign(TEST_SECRET, "input 2");
    expect(sig1).not.toBe(sig2);
  });

  it("different keys produce different signatures", () => {
    const otherSecret = "YW5vdGhlci10ZXN0LWtleS0yNTYtYml0cy1sb25nISE=";
    const sig1 = sign(TEST_SECRET, "same input");
    const sig2 = sign(otherSecret, "same input");
    expect(sig1).not.toBe(sig2);
  });
});

describe("verify", () => {
  it("returns true for valid signature", () => {
    const canonical = "GET\n/api/test\n\n\n1700000000";
    const sig = sign(TEST_SECRET, canonical);
    expect(verify(TEST_SECRET, canonical, sig)).toBe(true);
  });

  it("returns false for invalid signature", () => {
    expect(
      verify(TEST_SECRET, "GET\n/api/test\n\n\n1700000000", "0".repeat(64))
    ).toBe(false);
  });

  it("returns false for tampered canonical string", () => {
    const canonical = "GET\n/api/test\n\n\n1700000000";
    const sig = sign(TEST_SECRET, canonical);
    expect(
      verify(TEST_SECRET, "GET\n/api/test\n\n\n1700000001", sig)
    ).toBe(false);
  });
});
