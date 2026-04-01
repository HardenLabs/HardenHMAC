package hardenhmac

import (
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"
	"time"
)

// newTestMux sets up a mux with a protected route (/api/test) and an
// unprotected route (/health) for per-route validation tests.
func newTestMux(config *HmacConfig) *http.ServeMux {
	validate := NewHmacValidateHandler(config, nil)

	mux := http.NewServeMux()
	mux.Handle("/api/test", validate(okHandler()))
	mux.Handle("/health", okHandler())
	return mux
}

func TestHmacValidateHandler_ProtectedRoute_ValidSignature(t *testing.T) {
	config := validConfig()
	mux := newTestMux(config)

	req := signedRequest(t, "GET", "/api/test", "", config)
	rr := httptest.NewRecorder()
	mux.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected 200, got %d: %s", rr.Code, rr.Body.String())
	}
}

func TestHmacValidateHandler_ProtectedRoute_MissingSignature(t *testing.T) {
	config := validConfig()
	mux := newTestMux(config)

	req := httptest.NewRequest("GET", "/api/test", nil)
	req.Header.Set(TimestampHeader, strconv.FormatInt(time.Now().Unix(), 10))

	rr := httptest.NewRecorder()
	mux.ServeHTTP(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rr.Code)
	}
	assertJSONError(t, rr.Body.Bytes(), "missing_signature")
}

func TestHmacValidateHandler_ProtectedRoute_InvalidSignature(t *testing.T) {
	config := validConfig()
	mux := newTestMux(config)

	req := httptest.NewRequest("GET", "/api/test", nil)
	req.Header.Set(SignatureHeader, "0000000000000000000000000000000000000000000000000000000000000000")
	req.Header.Set(TimestampHeader, strconv.FormatInt(time.Now().Unix(), 10))

	rr := httptest.NewRecorder()
	mux.ServeHTTP(rr, req)

	if rr.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d", rr.Code)
	}
	assertJSONError(t, rr.Body.Bytes(), "signature_invalid")
}

func TestHmacValidateHandler_UnprotectedRoute_NoSignature(t *testing.T) {
	config := validConfig()
	mux := newTestMux(config)

	req := httptest.NewRequest("GET", "/health", nil)

	rr := httptest.NewRecorder()
	mux.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected 200, got %d: %s", rr.Code, rr.Body.String())
	}
}
