import {
  CLIENT_ID_HEADER_LOWER,
  HARDEN_HEADER_PREFIX,
  X_HEADER_PREFIX,
  type SignedHeadersConfig,
} from "./config.js";

/** Parameters for building a canonical string. */
export interface CanonicalStringParams {
  method: string;
  path: string;
  body: string;
  timestamp: number;
  signedHeadersConfig?: SignedHeadersConfig;
  requestHeaders?: Record<string, string>;
}

/**
 * Build a canonical string from request components per the v1.0 specification.
 *
 * Format: METHOD\nPATH\nSIGNED_HEADERS\nBODY\nTIMESTAMP
 */
export function buildCanonicalString(params: CanonicalStringParams): string {
  const {
    method,
    path,
    body,
    timestamp,
    signedHeadersConfig,
    requestHeaders,
  } = params;

  const config: SignedHeadersConfig = signedHeadersConfig ?? {
    includeAuthorization: false,
    includeXHeaders: false,
    additionalHeaders: [],
    excludeHeaders: [],
  };

  const headers = requestHeaders ?? {};
  const signedHeadersString = buildSignedHeadersString(config, headers);

  return [
    method.toUpperCase(),
    path,
    signedHeadersString,
    body ?? "",
    String(timestamp),
  ].join("\n");
}

/** Result of building signed headers. */
export interface SignedHeadersResult {
  headerString: string;
  headerNames: string[];
}

/**
 * Build the signed headers string and return header names.
 */
export function buildSignedHeaders(
  config: SignedHeadersConfig,
  requestHeaders: Record<string, string>
): SignedHeadersResult {
  const selected = selectHeaders(config, requestHeaders);
  const headerNames = selected.map((h) => h.name);
  const headerString = selected
    .map((h) => `${h.name}:${h.value}`)
    .join("\n");
  return { headerString, headerNames };
}

function buildSignedHeadersString(
  config: SignedHeadersConfig,
  requestHeaders: Record<string, string>
): string {
  const selected = selectHeaders(config, requestHeaders);
  return selected.map((h) => `${h.name}:${h.value}`).join("\n");
}

interface SelectedHeader {
  name: string;
  value: string;
}

function selectHeaders(
  config: SignedHeadersConfig,
  requestHeaders: Record<string, string>
): SelectedHeader[] {
  const excludeSet = new Set(
    config.excludeHeaders.map((h) => h.toLowerCase())
  );
  const additionalSet = new Set(
    config.additionalHeaders.map((h) => h.toLowerCase())
  );

  const selected: SelectedHeader[] = [];

  for (const [name, value] of Object.entries(requestHeaders)) {
    const lowerName = name.toLowerCase();
    const trimmedValue = value.trim();

    // Always exclude X-Harden-* headers, EXCEPT X-Harden-Client-Id
    // (client identity is an identity claim, not signing metadata)
    if (lowerName.startsWith(HARDEN_HEADER_PREFIX) && lowerName !== CLIENT_ID_HEADER_LOWER) {
      continue;
    }

    let include = false;

    if (config.includeAuthorization && lowerName === "authorization") {
      include = true;
    }

    if (
      config.includeXHeaders &&
      lowerName.startsWith(X_HEADER_PREFIX) &&
      (!lowerName.startsWith(HARDEN_HEADER_PREFIX) || lowerName === CLIENT_ID_HEADER_LOWER)
    ) {
      include = true;
    }

    if (additionalSet.has(lowerName)) {
      include = true;
    }

    // Apply exclude override
    if (excludeSet.has(lowerName)) {
      include = false;
    }

    if (include) {
      selected.push({ name: lowerName, value: trimmedValue });
    }
  }

  // Sort by Unicode code point order (ordinal), matching C# StringComparison.Ordinal
  // and Python default string comparison. Do NOT use localeCompare — it varies by runtime locale.
  selected.sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));

  return selected;
}
