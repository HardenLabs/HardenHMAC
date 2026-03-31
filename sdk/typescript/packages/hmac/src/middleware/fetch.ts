import { buildCanonicalString, buildSignedHeaders } from "../canonical.js";
import type { HmacConfig } from "../config.js";
import {
  SIGNATURE_HEADER,
  SIGNED_HEADERS_HEADER,
  TIMESTAMP_HEADER,
} from "../config.js";
import { sign } from "../signing.js";

/**
 * Sign headers for an outgoing request.
 *
 * Returns a Record of headers to add to the request.
 */
export function signRequestHeaders(
  config: HmacConfig,
  method: string,
  path: string,
  body: string = "",
  requestHeaders: Record<string, string> = {},
  timestamp?: number
): Record<string, string> {
  const ts = timestamp ?? Math.floor(Date.now() / 1000);

  const { headerNames } = buildSignedHeaders(
    config.signedHeaders,
    requestHeaders
  );

  const canonicalString = buildCanonicalString({
    method,
    path,
    body,
    timestamp: ts,
    signedHeadersConfig: config.signedHeaders,
    requestHeaders,
  });

  const signature = sign(config.sharedSecretBase64, canonicalString);

  const result: Record<string, string> = {
    [SIGNATURE_HEADER]: signature,
    [TIMESTAMP_HEADER]: String(ts),
  };

  if (headerNames.length > 0) {
    result[SIGNED_HEADERS_HEADER] = headerNames.join(";");
  }

  return result;
}

/**
 * Create a fetch wrapper that automatically signs outgoing requests.
 *
 * @param config - HMAC configuration with shared secret.
 * @param fetchFn - The fetch function to wrap (defaults to globalThis.fetch).
 * @returns A function that signs requests before passing them to the underlying fetch.
 */
export function createSignedFetch(
  config: HmacConfig,
  fetchFn?: typeof globalThis.fetch
): (url: string | URL, init?: RequestInit) => Promise<Response> {
  const baseFetch = fetchFn ?? globalThis.fetch;

  return async (
    url: string | URL,
    init?: RequestInit
  ): Promise<Response> => {
    const parsedUrl = typeof url === "string" ? new URL(url) : url;
    const path = parsedUrl.pathname + parsedUrl.search;
    const method = init?.method ?? "GET";
    const body = init?.body ? String(init.body) : "";

    // Collect existing headers
    const existingHeaders: Record<string, string> = {};
    if (init?.headers) {
      if (init.headers instanceof Headers) {
        init.headers.forEach((value, key) => {
          existingHeaders[key] = value;
        });
      } else if (Array.isArray(init.headers)) {
        for (const [key, value] of init.headers) {
          existingHeaders[key!] = String(value);
        }
      } else {
        for (const [key, value] of Object.entries(init.headers)) {
          existingHeaders[key] = String(value);
        }
      }
    }

    const sigHeaders = signRequestHeaders(
      config,
      method,
      path,
      body,
      existingHeaders
    );

    const mergedHeaders: Record<string, string> = {
      ...existingHeaders,
      ...sigHeaders,
    };

    return baseFetch(url, {
      ...init,
      headers: mergedHeaders,
    });
  };
}
