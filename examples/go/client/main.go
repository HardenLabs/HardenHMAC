// Example client using HardenHMAC client factory with named targets.
//
// Usage:
//
//	# Start the server example first, then:
//	go run main.go
package main

import (
	"fmt"
	"io"
	"log"

	hardenhmac "github.com/HardenLabs/hardenhmac-go"
)

func main() {
	secret := "dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24="

	config := &hardenhmac.HmacConfig{
		SharedSecretBase64: secret,
		SignedHeaders:      hardenhmac.DefaultSignedHeadersConfig(),
		Targets: map[string]hardenhmac.HmacTargetConfig{
			"backend": {
				BaseURL:      "http://localhost:8080",
				SharedSecret: secret,
			},
		},
	}

	factory := hardenhmac.NewClientFactory(config)
	client, err := factory.CreateClient("backend")
	if err != nil {
		log.Fatalf("Failed to create client: %v", err)
	}

	// GET request
	fmt.Println("--- GET /api/health ---")
	resp, err := client.Get("/api/health")
	if err != nil {
		log.Fatalf("GET failed: %v", err)
	}
	body, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	fmt.Printf("Status: %d\nBody: %s\n", resp.StatusCode, string(body))

	// POST request
	fmt.Println("\n--- POST /api/data ---")
	resp, err = client.Post("/api/data", "application/json", `{"key":"value"}`)
	if err != nil {
		log.Fatalf("POST failed: %v", err)
	}
	body, _ = io.ReadAll(resp.Body)
	resp.Body.Close()
	fmt.Printf("Status: %d\nBody: %s\n", resp.StatusCode, string(body))
}
