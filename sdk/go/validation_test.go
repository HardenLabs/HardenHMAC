package hardenhmac

import (
	"testing"
)

func validConfig() *HmacConfig {
	return &HmacConfig{
		SharedSecretBase64:        testSecret,
		TimestampToleranceSeconds: 30,
		SignedHeaders:             NoneSignedHeadersConfig(),
	}
}

func signForValidation(t *testing.T, method, path, body string, timestamp int64) string {
	t.Helper()
	cfg := NoneSignedHeadersConfig()
	canonical := BuildCanonicalString(method, path, body, timestamp, &cfg, nil)
	sig, err := Sign(testSecret, canonical)
	if err != nil {
		t.Fatalf("Sign failed: %v", err)
	}
	return sig
}

func TestValidateRequest_Success(t *testing.T) {
	var ts int64 = 1700000000
	sig := signForValidation(t, "GET", "/api/users", "", ts)

	config := validConfig()
	err := ValidateRequestAt(config, &RequestInfo{
		Method:          "GET",
		Path:            "/api/users",
		Body:            "",
		SignatureHeader: sig,
		TimestampHeader: "1700000000",
	}, ts)
	if err != nil {
		t.Errorf("expected success, got: %v", err)
	}
}

func TestValidateRequest_MissingSignature(t *testing.T) {
	err := ValidateRequestAt(validConfig(), &RequestInfo{
		TimestampHeader: "1700000000",
	}, 1700000000)

	hmacErr, ok := err.(*HmacValidationError)
	if !ok {
		t.Fatalf("expected HmacValidationError, got %T", err)
	}
	if hmacErr.ErrorType != "missing_signature" {
		t.Errorf("expected missing_signature, got %s", hmacErr.ErrorType)
	}
}

func TestValidateRequest_MissingTimestamp(t *testing.T) {
	err := ValidateRequestAt(validConfig(), &RequestInfo{
		SignatureHeader: "abc123",
	}, 1700000000)

	hmacErr, ok := err.(*HmacValidationError)
	if !ok {
		t.Fatalf("expected HmacValidationError, got %T", err)
	}
	if hmacErr.ErrorType != "missing_timestamp" {
		t.Errorf("expected missing_timestamp, got %s", hmacErr.ErrorType)
	}
}

func TestValidateRequest_InvalidTimestamp(t *testing.T) {
	err := ValidateRequestAt(validConfig(), &RequestInfo{
		SignatureHeader: "abc123",
		TimestampHeader: "not-a-number",
	}, 1700000000)

	hmacErr, ok := err.(*HmacValidationError)
	if !ok {
		t.Fatalf("expected HmacValidationError, got %T", err)
	}
	if hmacErr.ErrorType != "invalid_timestamp" {
		t.Errorf("expected invalid_timestamp, got %s", hmacErr.ErrorType)
	}
}

func TestValidateRequest_TimestampExpired(t *testing.T) {
	var ts int64 = 1700000000
	sig := signForValidation(t, "GET", "/test", "", ts)

	err := ValidateRequestAt(validConfig(), &RequestInfo{
		Method:          "GET",
		Path:            "/test",
		SignatureHeader: sig,
		TimestampHeader: "1700000000",
	}, ts+31) // 31 seconds later, tolerance is 30

	hmacErr, ok := err.(*HmacValidationError)
	if !ok {
		t.Fatalf("expected HmacValidationError, got %T", err)
	}
	if hmacErr.ErrorType != "timestamp_expired" {
		t.Errorf("expected timestamp_expired, got %s", hmacErr.ErrorType)
	}
}

func TestValidateRequest_TimestampOutOfRange(t *testing.T) {
	var ts int64 = 1700000100
	sig := signForValidation(t, "GET", "/test", "", ts)

	err := ValidateRequestAt(validConfig(), &RequestInfo{
		Method:          "GET",
		Path:            "/test",
		SignatureHeader: sig,
		TimestampHeader: "1700000100",
	}, ts-31) // 31 seconds in the past, tolerance is 30

	hmacErr, ok := err.(*HmacValidationError)
	if !ok {
		t.Fatalf("expected HmacValidationError, got %T", err)
	}
	if hmacErr.ErrorType != "timestamp_out_of_range" {
		t.Errorf("expected timestamp_out_of_range, got %s", hmacErr.ErrorType)
	}
}

func TestValidateRequest_SignatureInvalid(t *testing.T) {
	var ts int64 = 1700000000
	err := ValidateRequestAt(validConfig(), &RequestInfo{
		Method:          "GET",
		Path:            "/api/users",
		SignatureHeader: "0000000000000000000000000000000000000000000000000000000000000000",
		TimestampHeader: "1700000000",
	}, ts)

	hmacErr, ok := err.(*HmacValidationError)
	if !ok {
		t.Fatalf("expected HmacValidationError, got %T", err)
	}
	if hmacErr.ErrorType != "signature_invalid" {
		t.Errorf("expected signature_invalid, got %s", hmacErr.ErrorType)
	}
}

func TestValidateRequest_BoundaryTimestampPast(t *testing.T) {
	// Exactly at tolerance boundary (delta == 30, tolerance == 30) should pass
	var ts int64 = 1700000000
	sig := signForValidation(t, "GET", "/test", "", ts)

	err := ValidateRequestAt(validConfig(), &RequestInfo{
		Method:          "GET",
		Path:            "/test",
		SignatureHeader: sig,
		TimestampHeader: "1700000000",
	}, ts+30)
	if err != nil {
		t.Errorf("expected pass at exact boundary, got: %v", err)
	}
}

func TestValidateRequest_BoundaryTimestampFuture(t *testing.T) {
	// Future boundary: delta == -30, tolerance == 30 should pass
	var ts int64 = 1700000050
	sig := signForValidation(t, "GET", "/api/future-boundary", "", ts)

	err := ValidateRequestAt(validConfig(), &RequestInfo{
		Method:          "GET",
		Path:            "/api/future-boundary",
		SignatureHeader: sig,
		TimestampHeader: "1700000050",
	}, 1700000020) // delta = 1700000020 - 1700000050 = -30
	if err != nil {
		t.Errorf("expected pass at future boundary, got: %v", err)
	}
}

func TestValidateRequest_DefaultTolerance(t *testing.T) {
	// Zero-value config should use DefaultTimestampToleranceSeconds
	config := &HmacConfig{
		SharedSecretBase64: testSecret,
		SignedHeaders:      NoneSignedHeadersConfig(),
		// TimestampToleranceSeconds: 0 (zero value)
	}

	var ts int64 = 1700000000
	sig := signForValidation(t, "GET", "/test", "", ts)

	err := ValidateRequestAt(config, &RequestInfo{
		Method:          "GET",
		Path:            "/test",
		SignatureHeader: sig,
		TimestampHeader: "1700000000",
	}, ts+30) // exactly at default tolerance
	if err != nil {
		t.Errorf("expected pass with default tolerance, got: %v", err)
	}

	err = ValidateRequestAt(config, &RequestInfo{
		Method:          "GET",
		Path:            "/test",
		SignatureHeader: sig,
		TimestampHeader: "1700000000",
	}, ts+31) // one past default tolerance
	if err == nil {
		t.Error("expected failure one past default tolerance")
	}
}

func TestHmacValidationError_IsMissing(t *testing.T) {
	e := &HmacValidationError{ErrorType: "missing_signature"}
	if !e.IsMissing() {
		t.Error("expected IsMissing() true")
	}
	e2 := &HmacValidationError{ErrorType: "signature_invalid"}
	if e2.IsMissing() {
		t.Error("expected IsMissing() false")
	}
}

func TestHmacValidationError_IsTimestamp(t *testing.T) {
	for _, et := range []string{"invalid_timestamp", "timestamp_expired", "timestamp_out_of_range"} {
		e := &HmacValidationError{ErrorType: et}
		if !e.IsTimestamp() {
			t.Errorf("expected IsTimestamp() true for %s", et)
		}
	}
	e := &HmacValidationError{ErrorType: "signature_invalid"}
	if e.IsTimestamp() {
		t.Error("expected IsTimestamp() false for signature_invalid")
	}
}
