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
	SharedSecret string `json:"sharedSecret"`
	Clients      map[string]struct {
		SharedSecret string `json:"sharedSecret"`
	} `json:"clients"`
	Ports       map[string]int `json:"ports"`
	SharedPorts map[string]int `json:"sharedPorts"`
}

func loadConfig() (*configFile, error) {
	dir, err := os.Getwd()
	if err != nil {
		return nil, fmt.Errorf("cannot get working directory: %w", err)
	}
	for {
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
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	return nil, fmt.Errorf("config.json not found")
}

func main() {
	cfg, err := loadConfig()
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	hmacMode := os.Getenv("HMAC_MODE")

	var port int
	var hmacConfig *hardenhmac.HmacConfig

	if hmacMode == "shared" {
		port = cfg.SharedPorts["go"]
		hmacConfig = &hardenhmac.HmacConfig{
			SharedSecretBase64:        cfg.SharedSecret,
			TimestampToleranceSeconds: 30,
			SignedHeaders:             hardenhmac.DefaultSignedHeadersConfig(),
		}
	} else {
		port = cfg.Ports["go"]

		// Build HmacConfig with Clients from config.json
		clients := make(map[string]hardenhmac.HmacClientIdentity)
		for name, c := range cfg.Clients {
			clients[name] = hardenhmac.HmacClientIdentity{SharedSecret: c.SharedSecret}
		}

		hmacConfig = &hardenhmac.HmacConfig{
			TimestampToleranceSeconds: 30,
			SignedHeaders:             hardenhmac.DefaultSignedHeadersConfig(),
			Clients:                   clients,
		}
	}

	// Per-route HMAC validation wrapper
	validate := hardenhmac.NewHmacValidateHandler(hmacConfig, nil)

	mux := http.NewServeMux()

	// Protected endpoints — wrapped with validate
	mux.Handle("/api/hello", validate(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"message": "hello from go"})
	})))

	mux.Handle("/api/echo", validate(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
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
	})))

	// Unprotected endpoint — no wrapper, no HMAC required
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "healthy", "language": "go"})
	})

	handler := mux

	addr := fmt.Sprintf("0.0.0.0:%d", port)
	log.Printf("Go server listening on port %d", port)
	log.Fatal(http.ListenAndServe(addr, handler))
}
