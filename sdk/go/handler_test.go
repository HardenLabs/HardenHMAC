package hardenhmac

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestSigningTransport_BodyPreserved(t *testing.T) {
	// Verify that the request body is still readable after signing
	var receivedBody string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		receivedBody = string(body)
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	config := &HmacConfig{
		SharedSecretBase64: testSecret,
		SignedHeaders:      NoneSignedHeadersConfig(),
	}

	transport := &SigningTransport{
		Config: config,
	}

	reqBody := `{"key":"value","nested":{"a":1}}`
	req, _ := http.NewRequest("POST", server.URL+"/test", strings.NewReader(reqBody))
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Transport: transport}
	resp, err := client.Do(req)
	if err != nil {
		t.Fatalf("request failed: %v", err)
	}
	resp.Body.Close()

	if receivedBody != reqBody {
		t.Errorf("body not preserved after signing: got %q, want %q", receivedBody, reqBody)
	}
}

func TestSigningTransport_EmptyBody(t *testing.T) {
	var capturedHeaders http.Header
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedHeaders = r.Header.Clone()
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	config := &HmacConfig{
		SharedSecretBase64: testSecret,
		SignedHeaders:      NoneSignedHeadersConfig(),
	}

	transport := &SigningTransport{
		Config: config,
	}

	// GET with no body (req.Body is nil)
	client := &http.Client{Transport: transport}
	resp, err := client.Get(server.URL + "/empty")
	if err != nil {
		t.Fatalf("request failed: %v", err)
	}
	resp.Body.Close()

	sig := capturedHeaders.Get(SignatureHeader)
	if sig == "" {
		t.Error("missing signature header on request with empty body")
	}
	if len(sig) != 64 {
		t.Errorf("expected 64-char signature, got %d chars", len(sig))
	}
}

func TestSigningTransport_InvalidSecret(t *testing.T) {
	config := &HmacConfig{
		SharedSecretBase64: "not-valid-base64!!!",
		SignedHeaders:      NoneSignedHeadersConfig(),
	}

	transport := &SigningTransport{
		Config: config,
	}

	req, _ := http.NewRequest("GET", "http://localhost/test", nil)
	client := &http.Client{Transport: transport}
	_, err := client.Do(req)
	if err == nil {
		t.Fatal("expected error for invalid base64 secret, got nil")
	}
}

func TestSigningTransport_NilBase(t *testing.T) {
	// Verify that nil Base falls back to http.DefaultTransport (not panic)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	config := &HmacConfig{
		SharedSecretBase64: testSecret,
		SignedHeaders:      NoneSignedHeadersConfig(),
	}

	transport := &SigningTransport{
		Config: config,
		Base:   nil, // explicitly nil
	}

	req, _ := http.NewRequest("GET", server.URL+"/test", nil)
	resp, err := (&http.Client{Transport: transport}).Do(req)
	if err != nil {
		t.Fatalf("request with nil Base failed: %v", err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Errorf("expected 200, got %d", resp.StatusCode)
	}
}

func TestSigningTransport_QueryString(t *testing.T) {
	var capturedHeaders http.Header
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedHeaders = r.Header.Clone()
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	config := &HmacConfig{
		SharedSecretBase64: testSecret,
		SignedHeaders:      NoneSignedHeadersConfig(),
	}

	transport := &SigningTransport{
		Config: config,
	}

	client := &http.Client{Transport: transport}
	resp, err := client.Get(server.URL + "/search?q=hello&page=2")
	if err != nil {
		t.Fatalf("request failed: %v", err)
	}
	resp.Body.Close()

	sig := capturedHeaders.Get(SignatureHeader)
	if sig == "" {
		t.Error("missing signature header on request with query string")
	}
}
