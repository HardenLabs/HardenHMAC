// Example server with multi-client HMAC validation using HardenHMAC.
//
// Usage:
//
//	export HARDEN_HMAC_SHARED_SECRET_BASE64="dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24="
//	go run main.go
//
// Then send signed requests with the client example.
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"

	hardenhmac "github.com/HardenLabs/hardenhmac-go"
)

func main() {
	secret := os.Getenv("HARDEN_HMAC_SHARED_SECRET_BASE64")
	if secret == "" {
		secret = "dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24="
	}
	// config, err := hardenhmac.FromEnv("HARDEN_HMAC_")

	config := &hardenhmac.HmacConfig{
		SharedSecretBase64:        secret,
		TimestampToleranceSeconds: 30,
		SignedHeaders:             hardenhmac.DefaultSignedHeadersConfig(),
		// For custom headers: hardenhmac.SignedHeadersConfig{IncludeAuthorization: true, IncludeXHeaders: true, AdditionalHeaders: []string{"X-Request-Id"}, ExcludeHeaders: []string{"X-Debug"}}
		Clients: map[string]hardenhmac.HmacClientIdentity{
			"frontend-app": {SharedSecret: secret},
			"mobile-app":   {SharedSecret: secret},
		},
	}

	mux := http.NewServeMux()

	// Per-route HMAC validation — only protected endpoints are wrapped
	validate := hardenhmac.NewHmacValidateHandler(config, nil)

	// Unprotected route
	mux.HandleFunc("/api/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	})

	// Protected route
	mux.Handle("/api/data", validate(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		clientID := r.Header.Get(hardenhmac.ClientIdHeader)
		_ = json.NewEncoder(w).Encode(map[string]string{
			"message":   "authenticated",
			"client_id": clientID,
		})
	})))

	// ── Option B: Multi-tenant server with secret resolver ──
	// tenantSecrets := map[string]string{
	//     "tenant-a": base64Encode("tenant-a-secret-key-32-bytes!!"),
	//     "tenant-b": base64Encode("tenant-b-secret-key-32-bytes!!"),
	// }
	// secretResolver := func(r *http.Request) (string, error) {
	//     clientID := r.Header.Get("X-Client-Id")
	//     if secret, ok := tenantSecrets[clientID]; ok {
	//         return secret, nil
	//     }
	//     return "", nil // fall back to config.SharedSecretBase64
	// }
	// handler := hardenhmac.NewHmacMiddleware(config, secretResolver)(mux)
	// log.Fatal(http.ListenAndServe(addr, handler))  // use handler instead of mux

	addr := ":8080"
	fmt.Printf("Server listening on %s\n", addr)
	log.Fatal(http.ListenAndServe(addr, mux))
}
