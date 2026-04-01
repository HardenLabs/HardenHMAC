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

	config := &hardenhmac.HmacConfig{
		SharedSecretBase64:        secret,
		TimestampToleranceSeconds: 30,
		SignedHeaders:             hardenhmac.DefaultSignedHeadersConfig(),
		Clients: map[string]hardenhmac.HmacClientIdentity{
			"frontend-app": {SharedSecret: secret},
			"mobile-app":   {SharedSecret: secret},
		},
	}

	mux := http.NewServeMux()

	mux.HandleFunc("/api/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	})

	mux.HandleFunc("/api/data", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		clientID := r.Header.Get(hardenhmac.ClientIdHeader)
		_ = json.NewEncoder(w).Encode(map[string]string{
			"message":   "authenticated",
			"client_id": clientID,
		})
	})

	// Wrap with HMAC middleware
	handler := hardenhmac.NewHmacMiddleware(config, nil)(mux)

	addr := ":8080"
	fmt.Printf("Server listening on %s\n", addr)
	log.Fatal(http.ListenAndServe(addr, handler))
}
