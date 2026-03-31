package hardenhmac

import (
	"fmt"
	"strconv"
	"strings"
	"time"
)

// RequestInfo holds the components of an HTTP request needed for HMAC validation.
type RequestInfo struct {
	// Method is the HTTP method (e.g., "GET", "POST").
	Method string
	// Path is the request path including query string.
	Path string
	// Body is the request body as a string (empty string if no body).
	Body string
	// SignatureHeader is the value of the X-Harden-Signature header.
	SignatureHeader string
	// TimestampHeader is the value of the X-Harden-Timestamp header.
	TimestampHeader string
	// RequestHeaders maps header names (original case) to values.
	RequestHeaders map[string]string
}

// ValidateRequest validates an incoming request's signature and timestamp.
//
// It checks that the required headers are present, the timestamp is within tolerance,
// and the HMAC signature matches. Returns nil on success, or an *HmacValidationError.
//
// Uses time.Now() for the current timestamp. Use ValidateRequestAt for testing with
// a fixed timestamp.
func ValidateRequest(config *HmacConfig, req *RequestInfo) error {
	return ValidateRequestAt(config, req, time.Now().Unix())
}

// ValidateRequestAt validates a request using the given current timestamp.
// This is useful for testing with deterministic timestamps.
func ValidateRequestAt(config *HmacConfig, req *RequestInfo, currentTimestamp int64) error {
	if req.SignatureHeader == "" {
		return &HmacValidationError{
			ErrorType: "missing_signature",
			Message:   "X-Harden-Signature header is required.",
		}
	}

	if req.TimestampHeader == "" {
		return &HmacValidationError{
			ErrorType: "missing_timestamp",
			Message:   "X-Harden-Timestamp header is required.",
		}
	}

	trimmed := strings.TrimSpace(req.TimestampHeader)
	requestTimestamp, err := strconv.ParseInt(trimmed, 10, 64)
	if err != nil {
		return &HmacValidationError{
			ErrorType: "invalid_timestamp",
			Message:   "X-Harden-Timestamp header is not a valid integer.",
		}
	}

	tolerance := int64(config.effectiveTolerance())
	delta := currentTimestamp - requestTimestamp

	if delta > tolerance {
		return &HmacValidationError{
			ErrorType: "timestamp_expired",
			Message:   fmt.Sprintf("Request timestamp is %d seconds in the past (tolerance: %ds).", delta, tolerance),
		}
	}

	if delta < -tolerance {
		return &HmacValidationError{
			ErrorType: "timestamp_out_of_range",
			Message:   fmt.Sprintf("Request timestamp is %d seconds in the future (tolerance: %ds).", -delta, tolerance),
		}
	}

	canonicalString := BuildCanonicalString(
		req.Method,
		req.Path,
		req.Body,
		requestTimestamp,
		&config.SignedHeaders,
		req.RequestHeaders,
	)

	valid, signErr := Verify(config.SharedSecretBase64, canonicalString, req.SignatureHeader)
	if signErr != nil {
		return &HmacValidationError{
			ErrorType: "signature_invalid",
			Message:   "Failed to verify signature: " + signErr.Error(),
		}
	}

	if !valid {
		return &HmacValidationError{
			ErrorType: "signature_invalid",
			Message:   "HMAC signature does not match the expected value.",
		}
	}

	return nil
}
