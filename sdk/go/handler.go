package hardenhmac

import (
	"bytes"
	"io"
	"net/http"
)

// SigningTransport is an http.RoundTripper that signs outgoing requests with HMAC.
//
// It adds X-Harden-Signature, X-Harden-Timestamp, and optionally
// X-Harden-Signed-Headers and X-Harden-Client-Id headers.
type SigningTransport struct {
	// Config is the HMAC configuration with the shared secret and signed headers settings.
	Config *HmacConfig
	// TargetName is the client identity sent as X-Harden-Client-Id.
	// If empty, no client ID header is added.
	TargetName string
	// Base is the underlying transport. If nil, http.DefaultTransport is used.
	Base http.RoundTripper
}

// RoundTrip signs the request and delegates to the base transport.
func (t *SigningTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	base := t.Base
	if base == nil {
		base = http.DefaultTransport
	}

	// Read the body to sign it, then replace it
	var bodyStr string
	if req.Body != nil {
		bodyBytes, err := io.ReadAll(req.Body)
		if err != nil {
			return nil, err
		}
		bodyStr = string(bodyBytes)
		req.Body = io.NopCloser(bytes.NewReader(bodyBytes))
	}

	// Build path with query string
	path := req.URL.Path
	if req.URL.RawQuery != "" {
		path = path + "?" + req.URL.RawQuery
	}

	// Set client ID before signing so it's included in the canonical string
	if t.TargetName != "" {
		req.Header.Set(ClientIdHeader, t.TargetName)
	}

	// Collect existing headers (now including client ID) for signed header selection
	existingHeaders := flattenHeaders(req.Header)

	sigHeaders, err := SignRequestHeaders(t.Config, req.Method, path, bodyStr, existingHeaders, 0)
	if err != nil {
		return nil, err
	}

	for name, value := range sigHeaders {
		req.Header.Set(name, value)
	}

	return base.RoundTrip(req)
}
