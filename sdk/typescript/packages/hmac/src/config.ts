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

/** Identity and credentials for a named client that connects to this server. */
export interface HmacClientIdentity {
  /** The shared secret as a Base64-encoded string for this client. */
  sharedSecret: string;
}

/** Per-target configuration for a named service target (client-side). */
export interface HmacTargetConfig {
  /** Base URL for the target service. */
  baseUrl: string;
  /** The shared secret as a Base64-encoded string for this target. */
  sharedSecret: string;
  /** Per-target signed headers override. If undefined, uses global config. */
  signedHeaders?: SignedHeadersConfig;
  /** Per-target timestamp tolerance override. If undefined, uses global config. */
  timestampToleranceSeconds?: number;
}

/** Configuration for HMAC signing and validation. */
export interface HmacConfig {
  /** The shared secret as a Base64-encoded string. */
  sharedSecretBase64: string;
  /** Named service targets with their own base URLs and secrets. */
  targets?: Record<string, HmacTargetConfig>;
  /** Named client identities for server-side multi-client secret resolution. */
  clients?: Record<string, HmacClientIdentity>;
  /** Configuration for which headers to include in the signature. */
  signedHeaders: SignedHeadersConfig;
  /** Timestamp tolerance in seconds for server-side validation. Default: 30. */
  timestampToleranceSeconds: number;
}

/** Header name constants. */
export const SIGNATURE_HEADER = "X-Harden-Signature";
export const TIMESTAMP_HEADER = "X-Harden-Timestamp";
export const SIGNED_HEADERS_HEADER = "X-Harden-Signed-Headers";
export const CLIENT_ID_HEADER = "X-Harden-Client-Id";
export const HARDEN_HEADER_PREFIX = "x-harden-";
export const CLIENT_ID_HEADER_LOWER = "x-harden-client-id";
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
    targets: overrides?.targets,
    clients: overrides?.clients,
    signedHeaders: overrides?.signedHeaders ?? defaultSignedHeadersConfig(),
    timestampToleranceSeconds:
      overrides?.timestampToleranceSeconds ??
      DEFAULT_TIMESTAMP_TOLERANCE_SECONDS,
  };
}

/**
 * Resolve the effective shared secret for a named target.
 * Returns the target's secret if set, otherwise the global secret.
 *
 * @throws {Error} If the target is not found.
 */
export function getEffectiveSecret(
  config: HmacConfig,
  targetName: string
): string {
  const target = config.targets?.[targetName];
  if (!target) {
    const available = config.targets
      ? Object.keys(config.targets).join(", ")
      : "";
    throw new Error(
      `Target '${targetName}' is not configured. Available targets: [${available}].`
    );
  }
  return target.sharedSecret || config.sharedSecretBase64;
}

/**
 * Resolve the effective signed headers config for a named target.
 */
export function getEffectiveSignedHeaders(
  config: HmacConfig,
  targetName: string
): SignedHeadersConfig {
  const target = config.targets?.[targetName];
  if (target?.signedHeaders) {
    return target.signedHeaders;
  }
  return config.signedHeaders;
}

/**
 * Resolve the effective timestamp tolerance for a named target.
 */
export function getEffectiveTimestampTolerance(
  config: HmacConfig,
  targetName: string
): number {
  const target = config.targets?.[targetName];
  if (target?.timestampToleranceSeconds !== undefined) {
    return target.timestampToleranceSeconds;
  }
  return config.timestampToleranceSeconds;
}

/**
 * Build an effective HmacConfig for a specific target with all overrides resolved.
 */
export function configForTarget(
  config: HmacConfig,
  targetName: string
): HmacConfig {
  return {
    sharedSecretBase64: getEffectiveSecret(config, targetName),
    signedHeaders: getEffectiveSignedHeaders(config, targetName),
    timestampToleranceSeconds: getEffectiveTimestampTolerance(
      config,
      targetName
    ),
  };
}
