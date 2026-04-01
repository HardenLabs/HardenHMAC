package hardenhmac

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"strings"
)

// Sign computes HMAC-SHA256 and returns the lowercase hex signature (64 characters).
//
// sharedSecretBase64 must be a valid Base64-encoded string.
// canonicalString is the canonical string to sign, encoded as UTF-8.
func Sign(sharedSecretBase64 string, canonicalString string) (string, error) {
	keyBytes, err := decodeSharedSecret(sharedSecretBase64)
	if err != nil {
		return "", err
	}
	defer func() {
		for i := range keyBytes {
			keyBytes[i] = 0
		}
	}()

	mac := hmac.New(sha256.New, keyBytes)
	mac.Write([]byte(canonicalString))
	digest := mac.Sum(nil)

	return hex.EncodeToString(digest), nil
}

// Verify checks a signature against a canonical string using constant-time comparison.
//
// Returns true if the signature is valid. Returns an error only for invalid base64 input.
func Verify(sharedSecretBase64 string, canonicalString string, signature string) (bool, error) {
	expected, err := Sign(sharedSecretBase64, canonicalString)
	if err != nil {
		return false, err
	}

	// Constant-time comparison to prevent timing attacks.
	// hmac.Equal compares two MACs in constant time. Here we compare hex strings
	// as byte slices, which is safe because both are exactly 64 bytes.
	if len(expected) != len(signature) {
		return false, nil
	}

	return hmac.Equal([]byte(expected), []byte(signature)), nil
}

// decodeSharedSecret decodes and validates a Base64-encoded shared secret.
func decodeSharedSecret(sharedSecretBase64 string) ([]byte, error) {
	// Strip whitespace to match C#/TypeScript/Python behavior
	stripped := strings.Join(strings.Fields(sharedSecretBase64), "")
	if stripped == "" {
		return nil, errors.New("shared secret is empty")
	}

	decoded, err := base64.StdEncoding.DecodeString(stripped)
	if err != nil {
		return nil, errors.New("shared secret is not valid Base64: " + err.Error())
	}

	if len(decoded) == 0 {
		return nil, errors.New("shared secret decodes to empty bytes")
	}

	return decoded, nil
}
