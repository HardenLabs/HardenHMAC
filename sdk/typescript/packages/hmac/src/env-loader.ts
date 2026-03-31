import type {
  HmacClientIdentity,
  HmacConfig,
  HmacTargetConfig,
  SignedHeadersConfig,
} from "./config.js";
import {
  DEFAULT_TIMESTAMP_TOLERANCE_SECONDS,
  defaultSignedHeadersConfig,
} from "./config.js";

/**
 * Try to load dotenv if it's available as a peer dependency.
 * This is a best-effort load — if dotenv is not installed, we skip silently.
 * Uses dynamic import() for ESM compatibility.
 */
async function tryLoadDotenv(): Promise<void> {
  try {
    const dotenv = await import("dotenv");
    dotenv.config();
  } catch {
    // dotenv is an optional peer dependency — skip if not available
  }
}

function parseBool(value: string | undefined, defaultValue: boolean): boolean {
  if (value === undefined) return defaultValue;
  return ["true", "1", "yes"].includes(value.toLowerCase());
}

/**
 * Load HmacConfig from environment variables.
 *
 * Supports the following variables (prefix default: "HARDEN_HMAC_"):
 *   {prefix}SHARED_SECRET_BASE64 — global shared secret
 *   {prefix}TIMESTAMP_TOLERANCE_SECONDS — global tolerance
 *   {prefix}SIGNED_HEADERS__INCLUDE_AUTHORIZATION — true/false
 *   {prefix}SIGNED_HEADERS__INCLUDE_X_HEADERS — true/false
 *   {prefix}TARGETS__{NAME}__BASE_URL — per-target base URL
 *   {prefix}TARGETS__{NAME}__SHARED_SECRET — per-target secret
 *   {prefix}TARGETS__{NAME}__TIMESTAMP_TOLERANCE_SECONDS — per-target tolerance
 *
 * If dotenv is installed as a peer dependency, .env file variables are loaded first.
 *
 * @param prefix - Environment variable prefix. Default: "HARDEN_HMAC_".
 * @param env - Optional env object for testing. Defaults to process.env.
 * @returns Parsed HmacConfig.
 */
/**
 * Parse an integer from a string, returning the default if the value is
 * undefined, empty, or not a valid integer.
 */
function safeParseInt(value: string | undefined, defaultValue: number): number {
  if (value === undefined || value === "") return defaultValue;
  const parsed = parseInt(value, 10);
  if (isNaN(parsed)) return defaultValue;
  return parsed;
}

export async function fromEnv(
  prefix: string = "HARDEN_HMAC_",
  env?: Record<string, string | undefined>
): Promise<HmacConfig> {
  if (!env) {
    await tryLoadDotenv();
    env = process.env;
  }

  const upperPrefix = prefix.toUpperCase();

  // Extract all prefixed vars
  const prefixed: Record<string, string> = {};
  for (const [key, value] of Object.entries(env)) {
    if (key && value !== undefined && key.toUpperCase().startsWith(upperPrefix)) {
      const suffix = key.substring(upperPrefix.length).toUpperCase();
      prefixed[suffix] = value;
    }
  }

  // Parse global settings
  const sharedSecretBase64 = prefixed["SHARED_SECRET_BASE64"] ?? "";
  const timestampToleranceSeconds = safeParseInt(
    prefixed["TIMESTAMP_TOLERANCE_SECONDS"],
    DEFAULT_TIMESTAMP_TOLERANCE_SECONDS
  );

  // Parse signed headers
  const signedHeaders: SignedHeadersConfig = {
    ...defaultSignedHeadersConfig(),
    includeAuthorization: parseBool(
      prefixed["SIGNED_HEADERS__INCLUDE_AUTHORIZATION"],
      true
    ),
    includeXHeaders: parseBool(
      prefixed["SIGNED_HEADERS__INCLUDE_X_HEADERS"],
      true
    ),
  };

  // Parse targets: keys matching TARGETS__{NAME}__{FIELD}
  const targetFields: Record<string, Record<string, string>> = {};
  const targetPrefix = "TARGETS__";
  for (const [key, value] of Object.entries(prefixed)) {
    if (!key.startsWith(targetPrefix)) continue;
    const rest = key.substring(targetPrefix.length);
    const separatorIndex = rest.indexOf("__");
    if (separatorIndex === -1) continue;
    const targetName = rest.substring(0, separatorIndex).toLowerCase().replace(/_/g, "-");
    const fieldName = rest.substring(separatorIndex + 2).toUpperCase();
    if (!targetFields[targetName]) {
      targetFields[targetName] = {};
    }
    targetFields[targetName][fieldName] = value;
  }

  const targets: Record<string, HmacTargetConfig> = {};
  for (const [name, fields] of Object.entries(targetFields)) {
    let targetSignedHeaders: SignedHeadersConfig | undefined;
    if (
      fields["SIGNED_HEADERS__INCLUDE_AUTHORIZATION"] !== undefined ||
      fields["SIGNED_HEADERS__INCLUDE_X_HEADERS"] !== undefined
    ) {
      targetSignedHeaders = {
        ...defaultSignedHeadersConfig(),
        includeAuthorization: parseBool(
          fields["SIGNED_HEADERS__INCLUDE_AUTHORIZATION"],
          true
        ),
        includeXHeaders: parseBool(
          fields["SIGNED_HEADERS__INCLUDE_X_HEADERS"],
          true
        ),
      };
    }

    let targetTimestampTolerance: number | undefined;
    if (fields["TIMESTAMP_TOLERANCE_SECONDS"] !== undefined) {
      const parsed = parseInt(fields["TIMESTAMP_TOLERANCE_SECONDS"], 10);
      targetTimestampTolerance = isNaN(parsed) ? undefined : parsed;
    }

    targets[name] = {
      baseUrl: fields["BASE_URL"] ?? "",
      sharedSecret: fields["SHARED_SECRET"] ?? "",
      signedHeaders: targetSignedHeaders,
      timestampToleranceSeconds: targetTimestampTolerance,
    };
  }

  // Parse clients: keys matching CLIENTS__{NAME}__{FIELD}
  const clientFields: Record<string, Record<string, string>> = {};
  const clientPrefix = "CLIENTS__";
  for (const [key, value] of Object.entries(prefixed)) {
    if (!key.startsWith(clientPrefix)) continue;
    const rest = key.substring(clientPrefix.length);
    const separatorIndex = rest.indexOf("__");
    if (separatorIndex === -1) continue;
    const clientName = rest.substring(0, separatorIndex).toLowerCase().replace(/_/g, "-");
    const fieldName = rest.substring(separatorIndex + 2).toUpperCase();
    if (!clientFields[clientName]) {
      clientFields[clientName] = {};
    }
    clientFields[clientName][fieldName] = value;
  }

  const clients: Record<string, HmacClientIdentity> = {};
  for (const [name, fields] of Object.entries(clientFields)) {
    clients[name] = {
      sharedSecret: fields["SHARED_SECRET"] ?? "",
    };
  }

  return {
    sharedSecretBase64,
    targets: Object.keys(targets).length > 0 ? targets : undefined,
    clients: Object.keys(clients).length > 0 ? clients : undefined,
    signedHeaders,
    timestampToleranceSeconds,
  };
}
