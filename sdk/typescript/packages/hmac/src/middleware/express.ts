import type { Request, Response, NextFunction } from "express";
import type { HmacConfig } from "../config.js";
import { CLIENT_ID_HEADER, SIGNATURE_HEADER, TIMESTAMP_HEADER } from "../config.js";
import { HmacValidationError } from "../errors.js";
import { validateRequest } from "../validation.js";

/**
 * Optional callback to resolve the shared secret per-request.
 * Return the Base64-encoded secret, or null/undefined to fall back to config.sharedSecretBase64.
 */
export type SecretResolver = (
  req: Request
) => string | null | undefined | Promise<string | null | undefined>;

/**
 * Create an Express middleware that validates incoming HMAC-signed requests.
 *
 * IMPORTANT: This middleware requires the raw request body as a string or Buffer.
 * Use `express.text({ type: "*\/*" })` or `express.raw()` upstream — NOT `express.json()`.
 *
 * If `express.json()` runs first, `req.body` will be a parsed object and
 * `JSON.stringify(req.body)` may produce different output than the original raw body,
 * causing signature verification to fail. In that case this middleware returns 400
 * with a descriptive error rather than silently producing incorrect results.
 *
 * @param config - HMAC configuration with shared secret and tolerance.
 * @param secretResolver - Optional callback to resolve the secret per-request (e.g., for multi-tenant).
 * @returns Express middleware function.
 */
export function hardenHmacMiddleware(
  config: HmacConfig,
  secretResolver?: SecretResolver
): (req: Request, res: Response, next: NextFunction) => void {
  return (req: Request, res: Response, next: NextFunction): void => {
    // Collect body as string.
    // Reject parsed objects — they cannot be reliably re-serialized to the original wire format.
    let body = "";
    if (typeof req.body === "string") {
      body = req.body;
    } else if (Buffer.isBuffer(req.body)) {
      body = req.body.toString("utf8");
    } else if (req.body !== undefined && req.body !== null) {
      // If it's a plain object with no keys, treat as empty body.
      // Express can set req.body = {} when no body parser matches.
      if (
        typeof req.body === "object" &&
        Object.keys(req.body as Record<string, unknown>).length === 0
      ) {
        body = "";
      } else {
        // req.body is a parsed object (e.g. from express.json()). This is not safe for HMAC
        // because JSON.stringify may differ from the original wire bytes.
        res.status(400).json({
          error: "body_not_raw",
          message:
            "HardenHMAC middleware requires the raw request body. " +
            "Use express.text() or express.raw() instead of express.json() " +
            "before this middleware.",
        });
        return;
      }
    }

    const path = req.originalUrl ?? req.url;

    // Extract headers as record
    const requestHeaders: Record<string, string> = {};
    for (const [name, value] of Object.entries(req.headers)) {
      if (typeof value === "string") {
        requestHeaders[name] = value;
      } else if (Array.isArray(value)) {
        requestHeaders[name] = value.join(", ");
      }
    }

    const rawSig = req.headers[SIGNATURE_HEADER.toLowerCase()];
    const signatureHeader = Array.isArray(rawSig) ? rawSig[0] : rawSig;
    const rawTs = req.headers[TIMESTAMP_HEADER.toLowerCase()];
    const timestampHeader = Array.isArray(rawTs) ? rawTs[0] : rawTs;

    // Validate with the resolved secret
    const validateWithSecret = (secret: string): void => {
      const effectiveConfig: HmacConfig = {
        ...config,
        sharedSecretBase64: secret,
      };

      try {
        validateRequest(effectiveConfig, {
          method: req.method,
          path,
          body,
          signatureHeader,
          timestampHeader,
          requestHeaders,
        });
      } catch (error) {
        if (error instanceof HmacValidationError) {
          const statusCode =
            error.errorType === "missing_signature" ||
            error.errorType === "missing_timestamp" ||
            error.errorType === "invalid_timestamp"
              ? 400
              : 401;
          res.status(statusCode).json({
            error: error.errorType,
            message: error.message,
          });
          return;
        }
        throw error;
      }

      next();
    };

    // Resolution chain: resolver -> Clients dict -> config fallback
    const resolveAndValidate = (resolverResult: string | null | undefined): void => {
      // 1. secretResolver callback result
      if (resolverResult) {
        validateWithSecret(resolverResult);
        return;
      }

      // 2. X-Harden-Client-Id header -> look up in config.clients
      const clientId = requestHeaders[CLIENT_ID_HEADER.toLowerCase()];
      if (clientId) {
        const clientIdentity = config.clients?.[clientId];
        if (clientIdentity?.sharedSecret) {
          validateWithSecret(clientIdentity.sharedSecret);
          return;
        }
        // Client ID was provided but not found
        res.status(401).json({
          error: "unknown_client",
          message: "Unknown or unconfigured client.",
        });
        return;
      }

      // 3. Fall back to config.sharedSecretBase64
      if (config.sharedSecretBase64) {
        validateWithSecret(config.sharedSecretBase64);
        return;
      }

      // 4. No secret available
      res.status(401).json({
        error: "no_secret",
        message: "No shared secret configured for this request.",
      });
    };

    if (secretResolver) {
      const result = secretResolver(req);
      if (result instanceof Promise) {
        result.then(resolveAndValidate).catch((err: unknown) => {
          next(err);
        });
        return;
      }
      resolveAndValidate(result);
    } else {
      resolveAndValidate(null);
    }
  };
}
