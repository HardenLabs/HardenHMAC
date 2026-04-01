package hardenhmac

import (
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

type testVectorFile struct {
	Version     string       `json:"version"`
	Description string       `json:"description"`
	Vectors     []testVector `json:"vectors"`
}

type testVector struct {
	ID                      string            `json:"id"`
	Description             string            `json:"description"`
	Method                  string            `json:"method"`
	Path                    string            `json:"path"`
	Body                    string            `json:"body"`
	Timestamp               int64             `json:"timestamp"`
	SignedHeadersConfig     shConfigJSON      `json:"signed_headers_config"`
	RequestHeaders          map[string]string `json:"request_headers"`
	SharedSecretBase64      string            `json:"shared_secret_base64"`
	ExpectedCanonicalString string            `json:"expected_canonical_string"`
	ExpectedSignature       string            `json:"expected_signature"`
}

type shConfigJSON struct {
	IncludeAuthorization bool     `json:"include_authorization"`
	IncludeXHeaders      bool     `json:"include_x_headers"`
	AdditionalHeaders    []string `json:"additional_headers"`
	ExcludeHeaders       []string `json:"exclude_headers"`
}

func loadTestVectors(t *testing.T) []testVector {
	t.Helper()

	// Find the test vectors file relative to this source file
	_, thisFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("could not determine test file path")
	}
	sdkDir := filepath.Dir(thisFile)
	vectorsPath := filepath.Join(sdkDir, "..", "..", "tests", "cross-language", "test-vectors.json")

	data, err := os.ReadFile(vectorsPath)
	if err != nil {
		t.Fatalf("failed to read test vectors: %v", err)
	}

	var file testVectorFile
	if err := json.Unmarshal(data, &file); err != nil {
		t.Fatalf("failed to parse test vectors: %v", err)
	}

	if len(file.Vectors) == 0 {
		t.Fatal("no test vectors found")
	}

	return file.Vectors
}

func TestCrossLanguage_CanonicalString(t *testing.T) {
	vectors := loadTestVectors(t)

	for _, v := range vectors {
		t.Run(v.ID, func(t *testing.T) {
			config := &SignedHeadersConfig{
				IncludeAuthorization: v.SignedHeadersConfig.IncludeAuthorization,
				IncludeXHeaders:      v.SignedHeadersConfig.IncludeXHeaders,
				AdditionalHeaders:    v.SignedHeadersConfig.AdditionalHeaders,
				ExcludeHeaders:       v.SignedHeadersConfig.ExcludeHeaders,
			}

			result, err := BuildCanonicalString(
				v.Method,
				v.Path,
				v.Body,
				v.Timestamp,
				config,
				v.RequestHeaders,
			)
			if err != nil {
				t.Fatalf("BuildCanonicalString failed for %s: %v", v.ID, err)
			}

			if result != v.ExpectedCanonicalString {
				t.Errorf("canonical string mismatch for %s:\ngot:  %q\nwant: %q", v.ID, result, v.ExpectedCanonicalString)
			}
		})
	}
}

func TestCrossLanguage_Signature(t *testing.T) {
	vectors := loadTestVectors(t)

	for _, v := range vectors {
		t.Run(v.ID, func(t *testing.T) {
			config := &SignedHeadersConfig{
				IncludeAuthorization: v.SignedHeadersConfig.IncludeAuthorization,
				IncludeXHeaders:      v.SignedHeadersConfig.IncludeXHeaders,
				AdditionalHeaders:    v.SignedHeadersConfig.AdditionalHeaders,
				ExcludeHeaders:       v.SignedHeadersConfig.ExcludeHeaders,
			}

			canonical, err := BuildCanonicalString(
				v.Method,
				v.Path,
				v.Body,
				v.Timestamp,
				config,
				v.RequestHeaders,
			)
			if err != nil {
				t.Fatalf("BuildCanonicalString failed for %s: %v", v.ID, err)
			}

			sig, err := Sign(v.SharedSecretBase64, canonical)
			if err != nil {
				t.Fatalf("Sign failed for %s: %v", v.ID, err)
			}

			if sig != v.ExpectedSignature {
				t.Errorf("signature mismatch for %s:\ngot:  %s\nwant: %s", v.ID, sig, v.ExpectedSignature)
			}
		})
	}
}

func TestCrossLanguage_Verify(t *testing.T) {
	vectors := loadTestVectors(t)

	for _, v := range vectors {
		t.Run(v.ID, func(t *testing.T) {
			config := &SignedHeadersConfig{
				IncludeAuthorization: v.SignedHeadersConfig.IncludeAuthorization,
				IncludeXHeaders:      v.SignedHeadersConfig.IncludeXHeaders,
				AdditionalHeaders:    v.SignedHeadersConfig.AdditionalHeaders,
				ExcludeHeaders:       v.SignedHeadersConfig.ExcludeHeaders,
			}

			canonical, err := BuildCanonicalString(
				v.Method,
				v.Path,
				v.Body,
				v.Timestamp,
				config,
				v.RequestHeaders,
			)
			if err != nil {
				t.Fatalf("BuildCanonicalString failed for %s: %v", v.ID, err)
			}

			ok, err := Verify(v.SharedSecretBase64, canonical, v.ExpectedSignature)
			if err != nil {
				t.Fatalf("Verify failed for %s: %v", v.ID, err)
			}
			if !ok {
				t.Errorf("Verify returned false for %s (expected true)", v.ID)
			}
		})
	}
}
