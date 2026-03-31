// Package main implements the Go HMAC integration test server.
//
// REQUIRES: Go installation and hardenlabs-hmac Go SDK.
// This file is a placeholder — it will not compile until the Go SDK
// is available and wired in go.mod.
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
)

type config struct {
	Clients map[string]struct {
		SharedSecret string `json:"sharedSecret"`
	} `json:"clients"`
	Ports map[string]int `json:"ports"`
}

func loadConfig() (*config, error) {
	// Walk up to find config.json
	dir, _ := os.Getwd()
	for dir != "/" {
		candidate := filepath.Join(dir, "config.json")
		if _, err := os.Stat(candidate); err == nil {
			data, err := os.ReadFile(candidate)
			if err != nil {
				return nil, err
			}
			var cfg config
			if err := json.Unmarshal(data, &cfg); err != nil {
				return nil, err
			}
			return &cfg, nil
		}
		dir = filepath.Dir(dir)
	}
	return nil, fmt.Errorf("config.json not found")
}

func main() {
	cfg, err := loadConfig()
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	port := cfg.Ports["go"]

	// TODO: Wire HardenHMAC Go middleware here
	// For now, endpoints are unprotected placeholders.

	http.HandleFunc("/api/hello", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"message": "hello from go"})
	})

	http.HandleFunc("/api/echo", func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		defer r.Body.Close()

		var parsed interface{}
		if err := json.Unmarshal(body, &parsed); err != nil {
			parsed = string(body)
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"echo":     parsed,
			"language": "go",
		})
	})

	addr := fmt.Sprintf("0.0.0.0:%d", port)
	log.Printf("Go server listening on port %d", port)
	log.Fatal(http.ListenAndServe(addr, nil))
}
