export {
  buildCanonicalString,
  buildSignedHeaders,
  type CanonicalStringParams,
  type SignedHeadersResult,
} from "./canonical.js";

export {
  type HmacConfig,
  type SignedHeadersConfig,
  SIGNATURE_HEADER,
  TIMESTAMP_HEADER,
  SIGNED_HEADERS_HEADER,
  DEFAULT_TIMESTAMP_TOLERANCE_SECONDS,
  defaultSignedHeadersConfig,
  noneSignedHeadersConfig,
  createHmacConfig,
} from "./config.js";

export { HmacValidationError, type HmacErrorType } from "./errors.js";

export { sign, verify } from "./signing.js";

export { validateRequest, type ValidateRequestParams } from "./validation.js";

export { signRequestHeaders, createSignedFetch } from "./middleware/fetch.js";

export { hardenHmacMiddleware } from "./middleware/express.js";
