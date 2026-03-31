package hardenhmac

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"
)

func okHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Verify body is still readable after middleware consumed it
		body, _ := io.ReadAll(r.Body)
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(body)
	})
}

func signedRequest(t *testing.T, method, path, body string, config *HmacConfig) *http.Request {
	t.Helper()
	ts := time.Now().Unix()
	canonical := BuildCanonicalString(method, path, body, ts, &config.SignedHeaders, nil)
	sig, err := Sign(config.SharedSecretBase64, canonical)
	if err != nil {
		t.Fatalf("Sign failed: %v", err)
	}

	var bodyReader io.Reader
	if body != "" {
		bodyReader = strings.NewReader(body)
	}
	req := httptest.NewRequest(method, path, bodyReader)
	req.Header.Set(SignatureHeader, sig)
	req.Header.Set(TimestampHeader, strconv.FormatInt(ts, 10))
	return req
}

func TestMiddleware_ValidRequest(t *testing.T) {
	config := validConfig()
	middleware := NewHmacMiddleware(config, nil)
	handler := middleware(okHandler())

	req := signedRequest(t, "GET", "/test", "", config)
	rr := httptest.NewRecorder()
	handler.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected 200, got %d: %s", rr.Code, rr.Body.String())
	}
}

func TestMiddleware_ValidPostWithBody(t *testing.T) {
	config := validConfig()
	middleware := NewHmacMiddleware(config, nil)
	handler := middleware(okHandler())

	body := `{"key":"value"}`
	req := signedRequest(t, "POST", "/test", body, config)
	rr := httptest.NewRecorder()
	handler.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected 200, got %d: %s", rr.Code, rr.Body.String())
	}
	// Verify body was preserved for the handler
	if rr.Body.String() != body {
		t.Errorf("body not preserved: got %q, want %q", rr.Body.String(), body)
	}
}

func TestMiddleware_MissingSignature(t *testing.T) {
	config := validConfig()
	middleware := NewHmacMiddleware(config, nil)
	handler := middleware(okHandler())

	req := httptest.NewRequest("GET", "/test", nil)
	req.Header.Set(TimestampHeader, strconv.FormatInt(time.Now().Unix(), 10))

	rr := httptest.NewRecorder()
	handler.ServeHTTP(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rr.Code)
	}
	assertJSONError(t, rr.Body.Bytes(), "missing_signature")
}

func TestMiddleware_MissingTimestamp(t *testing.T) {
	config := validConfig()
	middleware := NewHmacMiddleware(config, nil)
	handler := middleware(okHandler())

	req := httptest.NewRequest("GET", "/test", nil)
	req.Header.Set(SignatureHeader, "abc123")

	rr := httptest.NewRecorder()
	handler.ServeHTTP(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rr.Code)
	}
	assertJSONError(t, rr.Body.Bytes(), "missing_timestamp")
}

func TestMiddleware_InvalidSignature(t *testing.T) {
	config := validConfig()
	middleware := NewHmacMiddleware(config, nil)
	handler := middleware(okHandler())

	req := httptest.NewRequest("GET", "/test", nil)
	req.Header.Set(SignatureHeader, "0000000000000000000000000000000000000000000000000000000000000000")
	req.Header.Set(TimestampHeader, strconv.FormatInt(time.Now().Unix(), 10))

	rr := httptest.NewRecorder()
	handler.ServeHTTP(rr, req)

	if rr.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rr.Code)
	}
	assertJSONError(t, rr.Body.Bytes(), "signature_invalid")
}

func TestMiddleware_NoSecret(t *testing.T) {
	config := &HmacConfig{
		SignedHeaders: NoneSignedHeadersConfig(),
	}
	middleware := NewHmacMiddleware(config, nil)
	handler := middleware(okHandler())

	req := httptest.NewRequest("GET", "/test", nil)
	req.Header.Set(SignatureHeader, "abc")
	req.Header.Set(TimestampHeader, strconv.FormatInt(time.Now().Unix(), 10))

	rr := httptest.NewRecorder()
	handler.ServeHTTP(rr, req)

	if rr.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rr.Code)
	}
	assertJSONError(t, rr.Body.Bytes(), "no_secret")
}

func TestMiddleware_ClientIdResolution(t *testing.T) {
	config := &HmacConfig{
		SignedHeaders: NoneSignedHeadersConfig(),
		Clients: map[string]HmacClientIdentity{
			"client-a": {SharedSecret: testSecret},
		},
	}
	middleware := NewHmacMiddleware(config, nil)
	handler := middleware(okHandler())

	ts := time.Now().Unix()
	// Sign with the client's secret
	sigConfig := NoneSignedHeadersConfig()
	canonical := BuildCanonicalString("GET", "/test", "", ts, &sigConfig, nil)
	sig, _ := Sign(testSecret, canonical)

	req := httptest.NewRequest("GET", "/test", nil)
	req.Header.Set(SignatureHeader, sig)
	req.Header.Set(TimestampHeader, strconv.FormatInt(ts, 10))
	req.Header.Set(ClientIdHeader, "client-a")

	rr := httptest.NewRecorder()
	handler.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected 200, got %d: %s", rr.Code, rr.Body.String())
	}
}

func TestMiddleware_UnknownClientId(t *testing.T) {
	config := &HmacConfig{
		SignedHeaders: NoneSignedHeadersConfig(),
		Clients: map[string]HmacClientIdentity{
			"client-a": {SharedSecret: testSecret},
		},
	}
	middleware := NewHmacMiddleware(config, nil)
	handler := middleware(okHandler())

	req := httptest.NewRequest("GET", "/test", nil)
	req.Header.Set(SignatureHeader, "abc")
	req.Header.Set(TimestampHeader, strconv.FormatInt(time.Now().Unix(), 10))
	req.Header.Set(ClientIdHeader, "unknown-client")

	rr := httptest.NewRecorder()
	handler.ServeHTTP(rr, req)

	if rr.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rr.Code)
	}
	assertJSONError(t, rr.Body.Bytes(), "unknown_client")
}

func TestMiddleware_SecretResolver(t *testing.T) {
	config := &HmacConfig{
		SignedHeaders: NoneSignedHeadersConfig(),
	}
	resolver := func(r *http.Request) (string, error) {
		return testSecret, nil
	}
	middleware := NewHmacMiddleware(config, resolver)
	handler := middleware(okHandler())

	ts := time.Now().Unix()
	sigConfig := NoneSignedHeadersConfig()
	canonical := BuildCanonicalString("GET", "/test", "", ts, &sigConfig, nil)
	sig, _ := Sign(testSecret, canonical)

	req := httptest.NewRequest("GET", "/test", nil)
	req.Header.Set(SignatureHeader, sig)
	req.Header.Set(TimestampHeader, strconv.FormatInt(ts, 10))

	rr := httptest.NewRecorder()
	handler.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected 200, got %d: %s", rr.Code, rr.Body.String())
	}
}

func TestMiddleware_SecretResolverError(t *testing.T) {
	config := &HmacConfig{
		SignedHeaders: NoneSignedHeadersConfig(),
	}
	resolver := func(r *http.Request) (string, error) {
		return "", fmt.Errorf("database unavailable")
	}
	middleware := NewHmacMiddleware(config, resolver)
	handler := middleware(okHandler())

	req := httptest.NewRequest("GET", "/test", nil)
	req.Header.Set(SignatureHeader, "abc")
	req.Header.Set(TimestampHeader, strconv.FormatInt(time.Now().Unix(), 10))

	rr := httptest.NewRecorder()
	handler.ServeHTTP(rr, req)

	if rr.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rr.Code)
	}
	assertJSONError(t, rr.Body.Bytes(), "secret_resolver_error")
}

func TestMiddleware_SecretResolverFallthrough(t *testing.T) {
	// Resolver returns empty string => falls through to config
	config := &HmacConfig{
		SharedSecretBase64: testSecret,
		SignedHeaders:      NoneSignedHeadersConfig(),
	}
	resolver := func(r *http.Request) (string, error) {
		return "", nil // empty = fall through
	}
	middleware := NewHmacMiddleware(config, resolver)
	handler := middleware(okHandler())

	req := signedRequest(t, "GET", "/test", "", config)
	rr := httptest.NewRecorder()
	handler.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected 200, got %d: %s", rr.Code, rr.Body.String())
	}
}

func TestMiddleware_QueryStringPreserved(t *testing.T) {
	config := validConfig()
	middleware := NewHmacMiddleware(config, nil)
	handler := middleware(okHandler())

	ts := time.Now().Unix()
	path := "/test?foo=bar&baz=qux"
	sigConfig := NoneSignedHeadersConfig()
	canonical := BuildCanonicalString("GET", path, "", ts, &sigConfig, nil)
	sig, _ := Sign(testSecret, canonical)

	req := httptest.NewRequest("GET", path, nil)
	req.Header.Set(SignatureHeader, sig)
	req.Header.Set(TimestampHeader, strconv.FormatInt(ts, 10))

	rr := httptest.NewRecorder()
	handler.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected 200, got %d: %s", rr.Code, rr.Body.String())
	}
}

func assertJSONError(t *testing.T, body []byte, expectedError string) {
	t.Helper()
	var resp map[string]string
	if err := json.Unmarshal(body, &resp); err != nil {
		t.Fatalf("failed to parse JSON response: %v\nbody: %s", err, string(body))
	}
	if resp["error"] != expectedError {
		t.Errorf("expected error %q, got %q", expectedError, resp["error"])
	}
}
