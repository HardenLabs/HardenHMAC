package hardenhmac

// HmacValidationError is returned when HMAC validation fails.
// ErrorType indicates the category of failure.
type HmacValidationError struct {
	// ErrorType is a machine-readable error category:
	// "missing_signature", "missing_timestamp", "invalid_timestamp",
	// "timestamp_expired", "timestamp_out_of_range", "signature_invalid".
	ErrorType string
	// Message is a human-readable description of the error.
	Message string
}

func (e *HmacValidationError) Error() string { return e.Message }

// IsMissing returns true if the error is about a missing required header.
func (e *HmacValidationError) IsMissing() bool {
	return e.ErrorType == "missing_signature" || e.ErrorType == "missing_timestamp"
}

// IsTimestamp returns true if the error is a timestamp validation failure.
func (e *HmacValidationError) IsTimestamp() bool {
	return e.ErrorType == "invalid_timestamp" ||
		e.ErrorType == "timestamp_expired" ||
		e.ErrorType == "timestamp_out_of_range"
}
