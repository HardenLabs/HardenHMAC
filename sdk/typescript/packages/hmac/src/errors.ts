/** Error types for HMAC validation failures. */
export type HmacErrorType =
  | "missing_signature"
  | "missing_timestamp"
  | "invalid_timestamp"
  | "timestamp_expired"
  | "timestamp_out_of_range"
  | "signature_invalid";

/** Error thrown when HMAC validation fails. */
export class HmacValidationError extends Error {
  readonly errorType: HmacErrorType;

  constructor(errorType: HmacErrorType, message: string) {
    super(`${errorType}: ${message}`);
    this.name = "HmacValidationError";
    this.errorType = errorType;
  }
}
