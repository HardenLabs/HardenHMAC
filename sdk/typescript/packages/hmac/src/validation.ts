import { buildCanonicalString } from "./canonical.js";
import type { HmacConfig } from "./config.js";
import { HmacValidationError } from "./errors.js";
import { verify } from "./signing.js";

/** Parameters for request validation. */
export interface ValidateRequestParams {
  method: string;
  path: string;
  body: string;
  signatureHeader: string | undefined | null;
  timestampHeader: string | undefined | null;
  requestHeaders?: Record<string, string>;
  /** Override current timestamp for testing. */
  currentTimestamp?: number;
}

/**
 * Validate an HMAC-signed request.
 *
 * Checks timestamp freshness and signature correctness.
 *
 * @throws {HmacValidationError} If validation fails.
 */
export function validateRequest(
  config: HmacConfig,
  params: ValidateRequestParams
): void {
  const {
    method,
    path,
    body,
    signatureHeader,
    timestampHeader,
    requestHeaders,
    currentTimestamp,
  } = params;

  if (!signatureHeader) {
    throw new HmacValidationError(
      "missing_signature",
      "X-Harden-Signature header is required."
    );
  }

  if (!timestampHeader) {
    throw new HmacValidationError(
      "missing_timestamp",
      "X-Harden-Timestamp header is required."
    );
  }

  const trimmedTimestamp = timestampHeader.trim();
  if (!/^-?\d+$/.test(trimmedTimestamp)) {
    throw new HmacValidationError(
      "invalid_timestamp",
      "X-Harden-Timestamp header is not a valid integer."
    );
  }
  const requestTimestamp = parseInt(trimmedTimestamp, 10);
  if (isNaN(requestTimestamp)) {
    throw new HmacValidationError(
      "invalid_timestamp",
      "X-Harden-Timestamp header is not a valid integer."
    );
  }

  const now =
    currentTimestamp ?? Math.floor(Date.now() / 1000);
  const delta = now - requestTimestamp;

  if (delta > config.timestampToleranceSeconds) {
    throw new HmacValidationError(
      "timestamp_expired",
      `Request timestamp is ${delta} seconds in the past (tolerance: ${config.timestampToleranceSeconds}s).`
    );
  }

  if (delta < -config.timestampToleranceSeconds) {
    throw new HmacValidationError(
      "timestamp_out_of_range",
      `Request timestamp is ${-delta} seconds in the future (tolerance: ${config.timestampToleranceSeconds}s).`
    );
  }

  const canonicalString = buildCanonicalString({
    method,
    path,
    body: body ?? "",
    timestamp: requestTimestamp,
    signedHeadersConfig: config.signedHeaders,
    requestHeaders,
  });

  if (!verify(config.sharedSecretBase64, canonicalString, signatureHeader)) {
    throw new HmacValidationError(
      "signature_invalid",
      "HMAC signature does not match the expected value."
    );
  }
}
