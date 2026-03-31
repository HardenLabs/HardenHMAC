package hardenhmac

import (
	"testing"
)

func TestBuildCanonicalString_BasicGet(t *testing.T) {
	result := BuildCanonicalString("GET", "/api/users", "", 1700000000, nil, nil)
	expected := "GET\n/api/users\n\n\n1700000000"
	if result != expected {
		t.Errorf("basic GET:\ngot:  %q\nwant: %q", result, expected)
	}
}

func TestBuildCanonicalString_PostWithBody(t *testing.T) {
	result := BuildCanonicalString("POST", "/api/users", `{"name":"Alice","email":"alice@example.com"}`, 1700000001, nil, nil)
	expected := "POST\n/api/users\n\n{\"name\":\"Alice\",\"email\":\"alice@example.com\"}\n1700000001"
	if result != expected {
		t.Errorf("POST with body:\ngot:  %q\nwant: %q", result, expected)
	}
}

func TestBuildCanonicalString_MethodUppercased(t *testing.T) {
	result := BuildCanonicalString("gEt", "/api/mixed-case", "", 1700000020, nil, nil)
	expected := "GET\n/api/mixed-case\n\n\n1700000020"
	if result != expected {
		t.Errorf("mixed case method:\ngot:  %q\nwant: %q", result, expected)
	}
}

func TestBuildCanonicalString_SignedHeaders_AuthAndX(t *testing.T) {
	config := &SignedHeadersConfig{
		IncludeAuthorization: true,
		IncludeXHeaders:      true,
	}
	headers := map[string]string{
		"Authorization":      "Bearer eyJhbGciOiJIUzI1NiJ9.test",
		"X-Request-Id":       "req-abc-123",
		"Content-Type":       "application/json",
		"X-Harden-Timestamp": "1700000004",
	}
	result := BuildCanonicalString("POST", "/api/orders", `{"item":"widget","qty":5}`, 1700000004, config, headers)
	expected := "POST\n/api/orders\nauthorization:Bearer eyJhbGciOiJIUzI1NiJ9.test\nx-request-id:req-abc-123\n{\"item\":\"widget\",\"qty\":5}\n1700000004"
	if result != expected {
		t.Errorf("signed headers auth+x:\ngot:  %q\nwant: %q", result, expected)
	}
}

func TestBuildCanonicalString_MultipleSortedHeaders(t *testing.T) {
	config := &SignedHeadersConfig{
		IncludeAuthorization: true,
		IncludeXHeaders:      true,
		AdditionalHeaders:    []string{"Content-Type"},
	}
	headers := map[string]string{
		"Authorization":       "Bearer token123",
		"Content-Type":        "application/json",
		"X-Custom-A":          "value-a",
		"X-Custom-B":          "value-b",
		"Accept":              "application/json",
		"X-Harden-Signature":  "will-be-excluded",
	}
	result := BuildCanonicalString("POST", "/api/data", `{"key":"value"}`, 1700000007, config, headers)
	expected := "POST\n/api/data\nauthorization:Bearer token123\ncontent-type:application/json\nx-custom-a:value-a\nx-custom-b:value-b\n{\"key\":\"value\"}\n1700000007"
	if result != expected {
		t.Errorf("multiple sorted headers:\ngot:  %q\nwant: %q", result, expected)
	}
}

func TestBuildCanonicalString_ExcludeHeaders(t *testing.T) {
	config := &SignedHeadersConfig{
		IncludeAuthorization: true,
		IncludeXHeaders:      true,
		ExcludeHeaders:       []string{"X-Custom-B"},
	}
	headers := map[string]string{
		"Authorization": "Bearer excluded-test",
		"X-Custom-A":    "keep-this",
		"X-Custom-B":    "exclude-this",
	}
	result := BuildCanonicalString("GET", "/api/filtered", "", 1700000009, config, headers)
	expected := "GET\n/api/filtered\nauthorization:Bearer excluded-test\nx-custom-a:keep-this\n\n1700000009"
	if result != expected {
		t.Errorf("exclude headers:\ngot:  %q\nwant: %q", result, expected)
	}
}

func TestBuildCanonicalString_HeaderValueTrimming(t *testing.T) {
	config := &SignedHeadersConfig{
		IncludeAuthorization: true,
		IncludeXHeaders:      true,
	}
	headers := map[string]string{
		"Authorization": "  Bearer spaced-token  ",
		"X-Padded":      "  trimmed-value  ",
	}
	result := BuildCanonicalString("GET", "/api/trim-test", "", 1700000010, config, headers)
	expected := "GET\n/api/trim-test\nauthorization:Bearer spaced-token\nx-padded:trimmed-value\n\n1700000010"
	if result != expected {
		t.Errorf("header trimming:\ngot:  %q\nwant: %q", result, expected)
	}
}

func TestBuildCanonicalString_EmptyHeaderValue(t *testing.T) {
	config := &SignedHeadersConfig{
		IncludeXHeaders: true,
	}
	headers := map[string]string{
		"X-Empty": "",
	}
	result := BuildCanonicalString("GET", "/api/empty-header", "", 1700000021, config, headers)
	expected := "GET\n/api/empty-header\nx-empty:\n\n1700000021"
	if result != expected {
		t.Errorf("empty header value:\ngot:  %q\nwant: %q", result, expected)
	}
}

func TestBuildCanonicalString_AuthExcludedWhenDisabled(t *testing.T) {
	config := &SignedHeadersConfig{
		IncludeAuthorization: false,
		IncludeXHeaders:      true,
	}
	headers := map[string]string{
		"Authorization": "Bearer should-not-be-signed",
		"X-Request-Id":  "req-999",
	}
	result := BuildCanonicalString("GET", "/api/auth-excluded", "", 1700000022, config, headers)
	expected := "GET\n/api/auth-excluded\nx-request-id:req-999\n\n1700000022"
	if result != expected {
		t.Errorf("auth excluded:\ngot:  %q\nwant: %q", result, expected)
	}
}

func TestBuildCanonicalString_RootPath(t *testing.T) {
	result := BuildCanonicalString("GET", "/", "", 1700000011, nil, nil)
	expected := "GET\n/\n\n\n1700000011"
	if result != expected {
		t.Errorf("root path:\ngot:  %q\nwant: %q", result, expected)
	}
}

func TestBuildCanonicalString_QueryParams(t *testing.T) {
	result := BuildCanonicalString("PUT", "/api/users/123?active=true&role=admin", `{"name":"Bob"}`, 1700000002, nil, nil)
	expected := "PUT\n/api/users/123?active=true&role=admin\n\n{\"name\":\"Bob\"}\n1700000002"
	if result != expected {
		t.Errorf("query params:\ngot:  %q\nwant: %q", result, expected)
	}
}

func TestBuildSignedHeaders_ReturnsNames(t *testing.T) {
	config := SignedHeadersConfig{
		IncludeAuthorization: true,
		IncludeXHeaders:      true,
	}
	headers := map[string]string{
		"Authorization": "Bearer token",
		"X-Request-Id":  "abc",
	}
	str, names := BuildSignedHeaders(config, headers)
	if str != "authorization:Bearer token\nx-request-id:abc" {
		t.Errorf("header string: got %q", str)
	}
	if len(names) != 2 || names[0] != "authorization" || names[1] != "x-request-id" {
		t.Errorf("header names: got %v", names)
	}
}

func TestBuildCanonicalString_NilConfig(t *testing.T) {
	// nil config should produce empty signed headers
	result := BuildCanonicalString("GET", "/test", "", 1000, nil, map[string]string{
		"Authorization": "Bearer tok",
		"X-Foo":         "bar",
	})
	expected := "GET\n/test\n\n\n1000"
	if result != expected {
		t.Errorf("nil config:\ngot:  %q\nwant: %q", result, expected)
	}
}
