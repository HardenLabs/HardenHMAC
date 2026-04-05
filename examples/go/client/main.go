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
	apiSecret := "dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24="
	dataSecret := "ZGF0YS1zZXJ2ZXItc2VjcmV0LWtleS0zMi1ieXRlcyE="

	config := &hardenhmac.HmacConfig{
		SignedHeaders: hardenhmac.DefaultSignedHeadersConfig(),
		Targets: map[string]hardenhmac.HmacTargetConfig{
			"api-server": {
				BaseURL:      "http://localhost:8080",
				SharedSecret: apiSecret,
			},
			"data-server": {
				BaseURL:      "http://localhost:8081",
				SharedSecret: dataSecret,
			},
		},
	}

	factory := hardenhmac.NewClientFactory(config)

	// api-server: GET request
	apiClient, err := factory.CreateClient("api-server")
	if err != nil {
		log.Fatalf("Failed to create api-server client: %v", err)
	}

	fmt.Println("--- GET api-server /api/health ---")
	resp, err := apiClient.Get("/api/health")
	if err != nil {
		log.Fatalf("GET failed: %v", err)
	}
	body, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	fmt.Printf("Status: %d\nBody: %s\n", resp.StatusCode, string(body))

	// data-server: POST request
	dataClient, err := factory.CreateClient("data-server")
	if err != nil {
		log.Fatalf("Failed to create data-server client: %v", err)
	}

	fmt.Println("\n--- POST data-server /api/data ---")
	resp, err = dataClient.Post("/api/data", "application/json", `{"key":"value"}`)
	if err != nil {
		log.Fatalf("POST failed: %v", err)
	}
	body, _ = io.ReadAll(resp.Body)
	resp.Body.Close()
	fmt.Printf("Status: %d\nBody: %s\n", resp.StatusCode, string(body))
}
