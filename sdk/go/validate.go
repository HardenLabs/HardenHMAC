package hardenhmac

import "net/http"

// NewHmacValidateHandler creates per-route HMAC validation middleware.
// Wrap individual handlers that require HMAC authentication, leaving
// other routes unprotected.
//
// This uses the same validation logic as [NewHmacMiddleware] but is intended
// for per-route use rather than wrapping an entire mux.
//
// Usage:
//
//	validate := hardenhmac.NewHmacValidateHandler(config, nil)
//
//	// Protected route
//	mux.Handle("/api/orders", validate(ordersHandler))
//
//	// Unprotected route
//	mux.Handle("/health", healthHandler)
func NewHmacValidateHandler(config *HmacConfig, secretResolver SecretResolver) func(http.Handler) http.Handler {
	return NewHmacMiddleware(config, secretResolver)
}
