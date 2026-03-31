package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"

	hardenhmac "github.com/HardenLabs/hardenhmac-go"
)

type configFile struct {
	Clients map[string]struct {
		SharedSecret string `json:"sharedSecret"`
	} `json:"clients"`
	Ports map[string]int `json:"ports"`
}

func loadConfig() (*configFile, error) {
	dir, _ := os.Getwd()
	for dir != "/" {
		candidate := filepath.Join(dir, "config.json")
		if _, err := os.Stat(candidate); err == nil {
			data, err := os.ReadFile(candidate)
			if err != nil {
				return nil, err
			}
			var cfg configFile
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

	// Build HmacConfig with Clients from config.json
	clients := make(map[string]hardenhmac.HmacClientIdentity)
	for name, c := range cfg.Clients {
		clients[name] = hardenhmac.HmacClientIdentity{SharedSecret: c.SharedSecret}
	}

	hmacConfig := &hardenhmac.HmacConfig{
		TimestampToleranceSeconds: 30,
		SignedHeaders:             hardenhmac.DefaultSignedHeadersConfig(),
		Clients:                   clients,
	}

	mux := http.NewServeMux()

	mux.HandleFunc("/api/hello", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"message": "hello from go"})
	})

	mux.HandleFunc("/api/echo", func(w http.ResponseWriter, r *http.Request) {
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

	// Wrap with HMAC validation middleware
	handler := hardenhmac.NewHmacMiddleware(hmacConfig, nil)(mux)

	addr := fmt.Sprintf("0.0.0.0:%d", port)
	log.Printf("Go server listening on port %d", port)
	log.Fatal(http.ListenAndServe(addr, handler))
}
