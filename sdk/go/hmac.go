package hardenhmac

import (
	"strconv"
	"strings"
	"time"
)

// SignRequestHeaders computes the HMAC signing headers for an outgoing request.
//
// Returns a map containing X-Harden-Signature, X-Harden-Timestamp,
// and optionally X-Harden-Signed-Headers.
//
// If timestamp is 0, the current time is used.
func SignRequestHeaders(config *HmacConfig, method, path, body string, requestHeaders map[string]string, timestamp int64) (map[string]string, error) {
	if timestamp == 0 {
		timestamp = time.Now().Unix()
	}

	_, headerNames := BuildSignedHeaders(config.SignedHeaders, requestHeaders)

	canonicalString, err := BuildCanonicalString(
		method,
		path,
		body,
		timestamp,
		&config.SignedHeaders,
		requestHeaders,
	)
	if err != nil {
		return nil, err
	}

	signature, err := Sign(config.SharedSecretBase64, canonicalString)
	if err != nil {
		return nil, err
	}

	result := map[string]string{
		SignatureHeader: signature,
		TimestampHeader: strconv.FormatInt(timestamp, 10),
	}

	if len(headerNames) > 0 {
		result[SignedHeadersHeader] = strings.Join(headerNames, ";")
	}

	return result, nil
}
