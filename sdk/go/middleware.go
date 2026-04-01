package hardenhmac

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"strings"
)

// SecretResolver is a function that resolves the shared secret for an incoming request.
// Return the Base64-encoded secret, or empty string to fall through to config-based resolution.
// Return an error to reject the request immediately.
type SecretResolver func(r *http.Request) (string, error)

// NewHmacMiddleware creates HTTP middleware that validates HMAC signatures on incoming requests.
//
// Resolution order for the shared secret:
//  1. secretResolver (if non-nil) -- use result if non-empty
//  2. X-Harden-Client-Id header + found in config.Clients -- use that client's secret
//  3. X-Harden-Client-Id header + NOT in config.Clients -- 401 unknown_client
//  4. No X-Harden-Client-Id -- fall back to config.SharedSecretBase64
//  5. Nothing available -- 401 no_secret
//
// Error responses are JSON: {"error": "...", "message": "..."}.
func NewHmacMiddleware(config *HmacConfig, secretResolver SecretResolver) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Read the body without consuming it
			bodyBytes, err := io.ReadAll(r.Body)
			if err != nil {
				writeJSONError(w, http.StatusBadRequest, "body_read_error", "Failed to read request body.")
				return
			}
			r.Body = io.NopCloser(bytes.NewReader(bodyBytes))

			// Build path with query string
			path := r.URL.Path
			if r.URL.RawQuery != "" {
				path = path + "?" + r.URL.RawQuery
			}

			// Resolve the shared secret
			secret, resolveErr := resolveSecret(config, secretResolver, r)
			if resolveErr != nil {
				writeJSONError(w, resolveErr.statusCode, resolveErr.errorType, resolveErr.message)
				return
			}

			// Build an effective config with the resolved secret
			effectiveConfig := &HmacConfig{
				SharedSecretBase64:        secret,
				SignedHeaders:             config.SignedHeaders,
				TimestampToleranceSeconds: config.effectiveTolerance(),
			}

			// Extract request headers as a flat map
			requestHeaders := flattenHeaders(r.Header)

			reqInfo := &RequestInfo{
				Method:          r.Method,
				Path:            path,
				Body:            string(bodyBytes),
				SignatureHeader: r.Header.Get(SignatureHeader),
				TimestampHeader: r.Header.Get(TimestampHeader),
				RequestHeaders:  requestHeaders,
			}

			if valErr := ValidateRequest(effectiveConfig, reqInfo); valErr != nil {
				if hmacErr, ok := valErr.(*HmacValidationError); ok {
					statusCode := http.StatusUnauthorized
					if hmacErr.IsMissing() || hmacErr.ErrorType == "invalid_timestamp" {
						statusCode = http.StatusBadRequest
					}
					config.effectiveLogger().Printf("HMAC validation failed: %s - %s", hmacErr.ErrorType, hmacErr.Message)
					writeJSONError(w, statusCode, hmacErr.ErrorType, hmacErr.Message)
					return
				}
				writeJSONError(w, http.StatusInternalServerError, "internal_error", "Unexpected validation error.")
				return
			}

			next.ServeHTTP(w, r)
		})
	}
}

type resolveError struct {
	statusCode int
	errorType  string
	message    string
}

func resolveSecret(config *HmacConfig, secretResolver SecretResolver, r *http.Request) (string, *resolveError) {
	// 1. Try the secret resolver
	if secretResolver != nil {
		resolved, err := secretResolver(r)
		if err != nil {
			config.effectiveLogger().Printf("secret resolver error: %v", err)
			return "", &resolveError{
				statusCode: http.StatusUnauthorized,
				errorType:  "server_error",
				message:    "Internal error resolving authentication.",
			}
		}
		if resolved != "" {
			return resolved, nil
		}
	}

	// 2-3. Check X-Harden-Client-Id header
	clientID := r.Header.Get(ClientIdHeader)
	if clientID != "" {
		if config.Clients != nil {
			if client, ok := config.Clients[clientID]; ok {
				return client.SharedSecret, nil
			}
		}
		return "", &resolveError{
			statusCode: http.StatusUnauthorized,
			errorType:  "unknown_client",
			message:    "Unknown or unconfigured client.",
		}
	}

	// 4. Fall back to global secret
	if config.SharedSecretBase64 != "" {
		return config.SharedSecretBase64, nil
	}

	// 5. Nothing
	return "", &resolveError{
		statusCode: http.StatusUnauthorized,
		errorType:  "no_secret",
		message:    "No shared secret configured for this request.",
	}
}

func flattenHeaders(headers http.Header) map[string]string {
	flat := make(map[string]string, len(headers))
	for name, values := range headers {
		if len(values) > 0 {
			flat[name] = strings.Join(values, ", ")
		}
	}
	return flat
}

func writeJSONError(w http.ResponseWriter, statusCode int, errorType, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	resp := map[string]string{
		"error":   errorType,
		"message": message,
	}
	_ = json.NewEncoder(w).Encode(resp)
}
