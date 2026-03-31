export {
  buildCanonicalString,
  buildSignedHeaders,
  type CanonicalStringParams,
  type SignedHeadersResult,
} from "./canonical.js";

export {
  type HmacClientIdentity,
  type HmacConfig,
  type HmacTargetConfig,
  type SignedHeadersConfig,
  SIGNATURE_HEADER,
  TIMESTAMP_HEADER,
  SIGNED_HEADERS_HEADER,
  CLIENT_ID_HEADER,
  DEFAULT_TIMESTAMP_TOLERANCE_SECONDS,
  defaultSignedHeadersConfig,
  noneSignedHeadersConfig,
  createHmacConfig,
  getEffectiveSecret,
  getEffectiveSignedHeaders,
  getEffectiveTimestampTolerance,
  configForTarget,
} from "./config.js";

export { HmacValidationError, type HmacErrorType } from "./errors.js";

export { sign, verify } from "./signing.js";

export { validateRequest, type ValidateRequestParams } from "./validation.js";

export { signRequestHeaders, createSignedFetch } from "./middleware/fetch.js";

export { hardenHmacMiddleware, type SecretResolver } from "./middleware/express.js";

export { fromEnv } from "./env-loader.js";

export {
  createHmacClientFactory,
  type HmacClientFactory,
} from "./client-factory.js";
