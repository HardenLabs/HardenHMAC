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

  it("throws for empty base64 string", () => {
    expect(() => sign("", "test data")).toThrow("empty");
  });

  it("throws for whitespace-only base64 string", () => {
    expect(() => sign("   \t\n  ", "test data")).toThrow("empty");
  });

  it("throws for invalid base64 (bad characters)", () => {
    expect(() => sign("not!valid@base64#", "test data")).toThrow(
      "not valid Base64"
    );
  });

  it("throws for base64 with wrong length (not multiple of 4)", () => {
    expect(() => sign("abc", "test data")).toThrow("multiple of 4");
  });

  it("throws for base64 with incorrect padding", () => {
    // "YQ=a" is 4 chars but padding is misplaced
    expect(() => sign("YQ=a", "test data")).toThrow("not valid Base64");
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

  it("returns false for wrong signature (constant-time comparison path)", () => {
    const canonical = "POST\n/api/data\n{\"key\":\"val\"}\n\n1700000000";
    const correctSig = sign(TEST_SECRET, canonical);
    // Flip one character in the signature to ensure constant-time compare catches it
    const wrongSig =
      correctSig[0] === "a"
        ? "b" + correctSig.slice(1)
        : "a" + correctSig.slice(1);
    expect(verify(TEST_SECRET, canonical, wrongSig)).toBe(false);
  });

  it("returns false for signature with wrong length", () => {
    const canonical = "GET\n/api/test\n\n\n1700000000";
    // Too short — triggers the length-mismatch early return
    expect(verify(TEST_SECRET, canonical, "abcd")).toBe(false);
  });

  it("returns false for tampered body in canonical string", () => {
    const canonical = "POST\n/api/submit\n{\"amount\":100}\n\n1700000000";
    const sig = sign(TEST_SECRET, canonical);
    const tampered = "POST\n/api/submit\n{\"amount\":999}\n\n1700000000";
    expect(verify(TEST_SECRET, tampered, sig)).toBe(false);
  });

  it("returns false for tampered method in canonical string", () => {
    const canonical = "GET\n/api/test\n\n\n1700000000";
    const sig = sign(TEST_SECRET, canonical);
    const tampered = "POST\n/api/test\n\n\n1700000000";
    expect(verify(TEST_SECRET, tampered, sig)).toBe(false);
  });
});
