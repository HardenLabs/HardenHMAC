package hardenhmac

import (
	"testing"
)

func TestFromEnv_BasicConfig(t *testing.T) {
	env := map[string]string{
		"HARDEN_HMAC_SHARED_SECRET_BASE64":        testSecret,
		"HARDEN_HMAC_TIMESTAMP_TOLERANCE_SECONDS": "60",
	}

	config, err := fromEnvMap("", env)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if config.SharedSecretBase64 != testSecret {
		t.Errorf("shared secret: got %q, want %q", config.SharedSecretBase64, testSecret)
	}
	if config.TimestampToleranceSeconds != 60 {
		t.Errorf("tolerance: got %d, want 60", config.TimestampToleranceSeconds)
	}
}

func TestFromEnv_DefaultTolerance(t *testing.T) {
	env := map[string]string{
		"HARDEN_HMAC_SHARED_SECRET_BASE64": testSecret,
	}

	config, err := fromEnvMap("", env)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if config.TimestampToleranceSeconds != 30 {
		t.Errorf("default tolerance: got %d, want 30", config.TimestampToleranceSeconds)
	}
}

func TestFromEnv_SignedHeaders(t *testing.T) {
	env := map[string]string{
		"HARDEN_HMAC_SHARED_SECRET_BASE64":                  testSecret,
		"HARDEN_HMAC_SIGNED_HEADERS__INCLUDE_AUTHORIZATION": "false",
		"HARDEN_HMAC_SIGNED_HEADERS__INCLUDE_X_HEADERS":     "false",
	}

	config, err := fromEnvMap("", env)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if config.SignedHeaders.IncludeAuthorization {
		t.Error("expected IncludeAuthorization false")
	}
	if config.SignedHeaders.IncludeXHeaders {
		t.Error("expected IncludeXHeaders false")
	}
}

func TestFromEnv_SignedHeadersDefaults(t *testing.T) {
	env := map[string]string{
		"HARDEN_HMAC_SHARED_SECRET_BASE64": testSecret,
	}

	config, err := fromEnvMap("", env)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if !config.SignedHeaders.IncludeAuthorization {
		t.Error("expected IncludeAuthorization true by default")
	}
	if !config.SignedHeaders.IncludeXHeaders {
		t.Error("expected IncludeXHeaders true by default")
	}
}

func TestFromEnv_Targets(t *testing.T) {
	env := map[string]string{
		"HARDEN_HMAC_SHARED_SECRET_BASE64":                       testSecret,
		"HARDEN_HMAC_TARGETS__ORDERS_API__BASE_URL":              "https://orders.example.com",
		"HARDEN_HMAC_TARGETS__ORDERS_API__SHARED_SECRET":         "c2VjcmV0LWZvci1vcmRlcnM=",
		"HARDEN_HMAC_TARGETS__ORDERS_API__TIMESTAMP_TOLERANCE_SECONDS": "60",
		"HARDEN_HMAC_TARGETS__USERS_API__BASE_URL":               "https://users.example.com",
	}

	config, err := fromEnvMap("", env)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if len(config.Targets) != 2 {
		t.Fatalf("expected 2 targets, got %d", len(config.Targets))
	}

	orders, ok := config.Targets["orders-api"]
	if !ok {
		t.Fatal("orders-api target not found")
	}
	if orders.BaseURL != "https://orders.example.com" {
		t.Errorf("orders base URL: got %q", orders.BaseURL)
	}
	if orders.SharedSecret != "c2VjcmV0LWZvci1vcmRlcnM=" {
		t.Errorf("orders secret: got %q", orders.SharedSecret)
	}
	if orders.TimestampToleranceSeconds == nil || *orders.TimestampToleranceSeconds != 60 {
		t.Errorf("orders tolerance: got %v", orders.TimestampToleranceSeconds)
	}

	users, ok := config.Targets["users-api"]
	if !ok {
		t.Fatal("users-api target not found")
	}
	if users.BaseURL != "https://users.example.com" {
		t.Errorf("users base URL: got %q", users.BaseURL)
	}
	if users.SharedSecret != "" {
		t.Errorf("users secret should be empty, got %q", users.SharedSecret)
	}
	if users.TimestampToleranceSeconds != nil {
		t.Errorf("users tolerance should be nil, got %v", users.TimestampToleranceSeconds)
	}
}

func TestFromEnv_Clients(t *testing.T) {
	env := map[string]string{
		"HARDEN_HMAC_SHARED_SECRET_BASE64":              testSecret,
		"HARDEN_HMAC_CLIENTS__FRONTEND__SHARED_SECRET":  "ZnJvbnRlbmQtc2VjcmV0",
		"HARDEN_HMAC_CLIENTS__MOBILE_APP__SHARED_SECRET": "bW9iaWxlLXNlY3JldA==",
	}

	config, err := fromEnvMap("", env)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if len(config.Clients) != 2 {
		t.Fatalf("expected 2 clients, got %d", len(config.Clients))
	}

	frontend, ok := config.Clients["frontend"]
	if !ok {
		t.Fatal("frontend client not found")
	}
	if frontend.SharedSecret != "ZnJvbnRlbmQtc2VjcmV0" {
		t.Errorf("frontend secret: got %q", frontend.SharedSecret)
	}

	mobile, ok := config.Clients["mobile-app"]
	if !ok {
		t.Fatal("mobile-app client not found")
	}
	if mobile.SharedSecret != "bW9iaWxlLXNlY3JldA==" {
		t.Errorf("mobile secret: got %q", mobile.SharedSecret)
	}
}

func TestFromEnv_CustomPrefix(t *testing.T) {
	env := map[string]string{
		"MY_APP_SHARED_SECRET_BASE64": testSecret,
	}

	config, err := fromEnvMap("MY_APP_", env)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if config.SharedSecretBase64 != testSecret {
		t.Errorf("shared secret: got %q", config.SharedSecretBase64)
	}
}

func TestFromEnv_EmptyEnv(t *testing.T) {
	config, err := fromEnvMap("", map[string]string{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if config.SharedSecretBase64 != "" {
		t.Error("expected empty secret")
	}
	if config.TimestampToleranceSeconds != 30 {
		t.Errorf("expected default tolerance 30, got %d", config.TimestampToleranceSeconds)
	}
	if len(config.Targets) != 0 {
		t.Error("expected no targets")
	}
	if len(config.Clients) != 0 {
		t.Error("expected no clients")
	}
}

func TestFromEnv_CaseInsensitive(t *testing.T) {
	// Env var keys should match case-insensitively against the prefix
	env := map[string]string{
		"harden_hmac_SHARED_SECRET_BASE64": testSecret,
	}

	config, err := fromEnvMap("HARDEN_HMAC_", env)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if config.SharedSecretBase64 != testSecret {
		t.Errorf("case insensitive match failed: got %q", config.SharedSecretBase64)
	}
}
