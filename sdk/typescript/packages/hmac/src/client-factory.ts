import type { HmacConfig } from "./config.js";
import { CLIENT_ID_HEADER, configForTarget } from "./config.js";
import type {
  HmacClient,
  HmacResponse,
  HttpAdapter,
  RequestOptions,
  HmacClientFactoryOptions,
} from "./http-client.js";
import { FetchAdapter, AxiosAdapter } from "./http-client.js";
import { signRequestHeaders } from "./middleware/fetch.js";

/** Factory for creating pre-configured HMAC-signing HTTP clients per named target. */
export interface HmacClientFactory {
  /**
   * Create an HTTP client for the named target.
   * The client prepends the target's base URL and signs all requests.
   *
   * @param targetName - The target name as defined in config.targets.
   * @returns An HmacClient that auto-signs requests.
   * @throws {Error} If the target name is not found.
   */
  createClient(targetName: string): HmacClient;
}

/**
 * Create an HmacClientFactory from the given config.
 *
 * @param config - HMAC configuration with targets.
 * @param options - Optional adapter configuration (fetch function or axios instance).
 * @returns Factory that creates per-target signed HTTP clients.
 */
export function createHmacClientFactory(
  config: HmacConfig,
  options?: HmacClientFactoryOptions
): HmacClientFactory {
  const adapter: HttpAdapter = options?.axios
    ? new AxiosAdapter(options.axios)
    : new FetchAdapter(options?.fetchFn);

  return {
    createClient(targetName: string): HmacClient {
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

      function signedRequest(
        method: string,
        path: string,
        body?: string,
        opts?: RequestOptions
      ): Promise<HmacResponse> {
        const existingHeaders: Record<string, string> = {
          [CLIENT_ID_HEADER.toLowerCase()]: targetName,
          ...Object.fromEntries(
            Object.entries(opts?.headers ?? {}).map(([k, v]) => [
              k.toLowerCase(),
              v,
            ])
          ),
        };

        const sigHeaders = signRequestHeaders(
          targetConfig,
          method,
          path,
          body ?? "",
          existingHeaders
        );

        const mergedHeaders: Record<string, string> = {
          ...existingHeaders,
          ...sigHeaders,
        };

        const fullUrl = `${baseUrl}${path}`;
        return adapter.request(fullUrl, method, body, mergedHeaders);
      }

      return {
        get: (path, opts) => signedRequest("GET", path, undefined, opts),
        post: (path, body, opts) => signedRequest("POST", path, body, opts),
        put: (path, body, opts) => signedRequest("PUT", path, body, opts),
        patch: (path, body, opts) => signedRequest("PATCH", path, body, opts),
        delete: (path, opts) => signedRequest("DELETE", path, undefined, opts),
        request: (method, path, body, opts) =>
          signedRequest(method.toUpperCase(), path, body, opts),
      };
    },
  };
}
