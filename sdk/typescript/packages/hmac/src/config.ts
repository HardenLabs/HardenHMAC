/** Configuration for which request headers are included in the HMAC signature. */
export interface SignedHeadersConfig {
  /** Include the Authorization header in the signature. Default: true. */
  includeAuthorization: boolean;
  /** Include all X-* headers (except X-Harden-*) in the signature. Default: true. */
  includeXHeaders: boolean;
  /** Additional header names to include (case-insensitive). */
  additionalHeaders: string[];
  /** Header names to exclude (case-insensitive, overrides inclusion). */
  excludeHeaders: string[];
}

/** Configuration for HMAC signing and validation. */
export interface HmacConfig {
  /** The shared secret as a Base64-encoded string. */
  sharedSecretBase64: string;
  /** Configuration for which headers to include in the signature. */
  signedHeaders: SignedHeadersConfig;
  /** Timestamp tolerance in seconds for server-side validation. Default: 30. */
  timestampToleranceSeconds: number;
}

/** Header name constants. */
export const SIGNATURE_HEADER = "X-Harden-Signature";
export const TIMESTAMP_HEADER = "X-Harden-Timestamp";
export const SIGNED_HEADERS_HEADER = "X-Harden-Signed-Headers";
export const HARDEN_HEADER_PREFIX = "x-harden-";
export const X_HEADER_PREFIX = "x-";
export const DEFAULT_TIMESTAMP_TOLERANCE_SECONDS = 30;

/** Default signed headers configuration: include Authorization and X-* headers. */
export function defaultSignedHeadersConfig(): SignedHeadersConfig {
  return {
    includeAuthorization: true,
    includeXHeaders: true,
    additionalHeaders: [],
    excludeHeaders: [],
  };
}

/** Signed headers configuration that signs no headers. */
export function noneSignedHeadersConfig(): SignedHeadersConfig {
  return {
    includeAuthorization: false,
    includeXHeaders: false,
    additionalHeaders: [],
    excludeHeaders: [],
  };
}

/** Create an HmacConfig with sensible defaults. */
export function createHmacConfig(
  sharedSecretBase64: string,
  overrides?: Partial<Omit<HmacConfig, "sharedSecretBase64">>
): HmacConfig {
  return {
    sharedSecretBase64,
    signedHeaders: overrides?.signedHeaders ?? defaultSignedHeadersConfig(),
    timestampToleranceSeconds:
      overrides?.timestampToleranceSeconds ??
      DEFAULT_TIMESTAMP_TOLERANCE_SECONDS,
  };
}
