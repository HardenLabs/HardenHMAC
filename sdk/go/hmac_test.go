package hardenhmac

import (
	"strings"
	"testing"
)

func TestSignRequestHeaders_InvalidBase64Secret(t *testing.T) {
	config := &HmacConfig{
		SharedSecretBase64: "not-valid-base64!!!",
		SignedHeaders:      NoneSignedHeadersConfig(),
	}

	_, err := SignRequestHeaders(config, "GET", "/test", "", nil, 1700000000)
	if err == nil {
		t.Fatal("expected error for invalid base64 secret, got nil")
	}
}

func TestSignRequestHeaders_EmptyMethod(t *testing.T) {
	config := &HmacConfig{
		SharedSecretBase64: testSecret,
		SignedHeaders:      NoneSignedHeadersConfig(),
	}

	headers, err := SignRequestHeaders(config, "", "/test", "", nil, 1700000000)
	if err != nil {
		t.Fatalf("unexpected error with empty method: %v", err)
	}

	sig := headers[SignatureHeader]
	if sig == "" {
		t.Error("expected signature header even with empty method")
	}
	if len(sig) != 64 {
		t.Errorf("expected 64-char signature, got %d chars", len(sig))
	}
}

func TestSignRequestHeaders_EmptyPath(t *testing.T) {
	config := &HmacConfig{
		SharedSecretBase64: testSecret,
		SignedHeaders:      NoneSignedHeadersConfig(),
	}

	headers, err := SignRequestHeaders(config, "GET", "", "", nil, 1700000000)
	if err != nil {
		t.Fatalf("unexpected error with empty path: %v", err)
	}

	if headers[SignatureHeader] == "" {
		t.Error("expected signature header even with empty path")
	}
	if headers[TimestampHeader] == "" {
		t.Error("expected timestamp header even with empty path")
	}
}

func TestSignRequestHeaders_AllExpectedHeaders(t *testing.T) {
	config := &HmacConfig{
		SharedSecretBase64: testSecret,
		SignedHeaders:      NoneSignedHeadersConfig(),
	}

	headers, err := SignRequestHeaders(config, "POST", "/api/data", `{"x":1}`, nil, 1700000000)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Must have signature
	if _, ok := headers[SignatureHeader]; !ok {
		t.Error("missing X-Harden-Signature in output")
	}
	// Must have timestamp
	ts, ok := headers[TimestampHeader]
	if !ok {
		t.Error("missing X-Harden-Timestamp in output")
	}
	if ts != "1700000000" {
		t.Errorf("expected timestamp '1700000000', got %q", ts)
	}
}

func TestSignRequestHeaders_WithSignedHeaders(t *testing.T) {
	config := &HmacConfig{
		SharedSecretBase64: testSecret,
		SignedHeaders: SignedHeadersConfig{
			AdditionalHeaders: []string{"Content-Type"},
		},
	}

	reqHeaders := map[string]string{
		"Content-Type": "application/json",
	}

	headers, err := SignRequestHeaders(config, "POST", "/api/data", `{"x":1}`, reqHeaders, 1700000000)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Must include X-Harden-Signed-Headers
	sh, ok := headers[SignedHeadersHeader]
	if !ok {
		t.Error("missing X-Harden-Signed-Headers when signed headers are configured")
	}
	if !strings.Contains(sh, "content-type") {
		t.Errorf("expected 'content-type' in signed headers, got %q", sh)
	}
}

func TestSignRequestHeaders_ZeroTimestamp_UsesCurrentTime(t *testing.T) {
	config := &HmacConfig{
		SharedSecretBase64: testSecret,
		SignedHeaders:      NoneSignedHeadersConfig(),
	}

	headers, err := SignRequestHeaders(config, "GET", "/test", "", nil, 0)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	ts := headers[TimestampHeader]
	if ts == "" {
		t.Error("expected timestamp header")
	}
	if ts == "0" {
		t.Error("timestamp should not be 0 when auto-generated")
	}
}
