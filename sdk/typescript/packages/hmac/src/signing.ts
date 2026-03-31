import { createHmac, timingSafeEqual } from "node:crypto";

const BASE64_REGEX = /^[A-Za-z0-9+/]*={0,2}$/;

/**
 * Validate that a string is valid standard Base64.
 * Throws a descriptive error if the input contains invalid characters.
 */
function validateBase64(input: string, label: string): void {
  const stripped = input.replace(/\s/g, "");
  if (stripped.length === 0) {
    throw new Error(`${label} is empty after stripping whitespace.`);
  }
  if (stripped.length % 4 !== 0) {
    throw new Error(
      `${label} is not valid Base64. Length must be a multiple of 4 (got ${stripped.length}).`
    );
  }
  if (!BASE64_REGEX.test(stripped)) {
    throw new Error(
      `${label} is not valid Base64. Contains characters outside the Base64 alphabet.`
    );
  }
  // Round-trip validation: decode then re-encode to catch padding mismatches
  const decoded = Buffer.from(stripped, "base64");
  if (decoded.toString("base64") !== stripped) {
    throw new Error(
      `${label} is not valid Base64. Decoded/re-encoded value does not match input.`
    );
  }
}

/**
 * Compute the HMAC-SHA256 signature of a canonical string.
 *
 * @param sharedSecretBase64 - The shared secret as a Base64-encoded string.
 * @param canonicalString - The canonical string to sign.
 * @returns Lowercase hexadecimal signature string (64 characters).
 */
export function sign(
  sharedSecretBase64: string,
  canonicalString: string
): string {
  const stripped = sharedSecretBase64.replace(/\s/g, "");
  validateBase64(stripped, "sharedSecretBase64");
  const keyBytes = Buffer.from(stripped, "base64");
  const hmac = createHmac("sha256", keyBytes);
  hmac.update(canonicalString, "utf8");
  return hmac.digest("hex");
}

/**
 * Verify a signature against a canonical string using constant-time comparison.
 *
 * @param sharedSecretBase64 - The shared secret as a Base64-encoded string.
 * @param canonicalString - The canonical string that was signed.
 * @param signature - The signature to verify (64-char lowercase hex).
 * @returns True if the signature is valid.
 */
export function verify(
  sharedSecretBase64: string,
  canonicalString: string,
  signature: string
): boolean {
  // sign() handles stripping and validation
  const expected = sign(sharedSecretBase64, canonicalString);
  const expectedBuf = Buffer.from(expected, "utf8");
  const signatureBuf = Buffer.from(signature, "utf8");

  if (expectedBuf.length !== signatureBuf.length) {
    return false;
  }

  return timingSafeEqual(expectedBuf, signatureBuf);
}
