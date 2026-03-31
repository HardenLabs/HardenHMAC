import type { HmacConfig } from "./config.js";
import { CLIENT_ID_HEADER, configForTarget } from "./config.js";
import { signRequestHeaders } from "./middleware/fetch.js";

/** Factory for creating pre-configured fetch wrappers per named target. */
export interface HmacClientFactory {
  /**
   * Create a fetch wrapper for the named target.
   * The wrapper prepends the target's base URL and signs all requests.
   *
   * @param targetName - The target name as defined in config.targets.
   * @returns A fetch-like function that auto-signs requests.
   * @throws {Error} If the target name is not found.
   */
  createClient(
    targetName: string
  ): (path: string, init?: RequestInit) => Promise<Response>;
}

/**
 * Create an HmacClientFactory from the given config.
 *
 * @param config - HMAC configuration with targets.
 * @param fetchFn - The fetch function to wrap. Defaults to globalThis.fetch.
 * @returns Factory that creates per-target signed fetch wrappers.
 */
export function createHmacClientFactory(
  config: HmacConfig,
  fetchFn?: typeof globalThis.fetch
): HmacClientFactory {
  const baseFetch = fetchFn ?? globalThis.fetch;

  return {
    createClient(
      targetName: string
    ): (path: string, init?: RequestInit) => Promise<Response> {
      const target = config.targets?.[targetName];
      if (!target) {
        const available = config.targets
          ? Object.keys(config.targets).join(", ")
          : "";
        throw new Error(
          `Target '${targetName}' is not configured. Available targets: [${available}].`
        );
      }

      const targetConfig = configForTarget(config, targetName);
      const baseUrl = target.baseUrl.replace(/\/+$/, "");

      return async (
        path: string,
        init?: RequestInit
      ): Promise<Response> => {
        const fullUrl = `${baseUrl}${path}`;
        const method = init?.method ?? "GET";

        // Only string bodies are supported for HMAC signing.
        let body = "";
        if (init?.body !== undefined && init?.body !== null) {
          if (typeof init.body === "string") {
            body = init.body;
          } else {
            throw new Error(
              "HardenHMAC: Only string request bodies are supported for HMAC signing. " +
              "Convert your body to a string before passing it to fetch."
            );
          }
        }

        // Collect existing headers, including the client ID
        const existingHeaders: Record<string, string> = {
          [CLIENT_ID_HEADER]: targetName,
        };
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
          targetConfig,
          method,
          path,
          body,
          existingHeaders
        );

        const mergedHeaders: Record<string, string> = {
          ...existingHeaders,
          ...sigHeaders,
        };

        return baseFetch(fullUrl, {
          ...init,
          headers: mergedHeaders,
        });
      };
    },
  };
}
