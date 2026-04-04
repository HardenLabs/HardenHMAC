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
	Ports         map[string]int `json:"ports"`
	SharedPorts   map[string]int `json:"sharedPorts"`
	ResolverPorts map[string]int `json:"resolverPorts"`
	GlobalPorts   map[string]int `json:"globalPorts"`
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
	var secretResolver hardenhmac.SecretResolver
	useGlobalMiddleware := false

	if hmacMode == "shared" {
		port = cfg.SharedPorts["go"]
		hmacConfig = &hardenhmac.HmacConfig{
			SharedSecretBase64:        cfg.SharedSecret,
			TimestampToleranceSeconds: 30,
			SignedHeaders:             hardenhmac.DefaultSignedHeadersConfig(),
		}
	} else if hmacMode == "resolver" {
		port = cfg.ResolverPorts["go"]

		// Build lookup from config
		clientSecrets := make(map[string]string)
		for name, c := range cfg.Clients {
			clientSecrets[name] = c.SharedSecret
		}

		hmacConfig = &hardenhmac.HmacConfig{
			SharedSecretBase64:        cfg.SharedSecret,
			TimestampToleranceSeconds: 30,
			SignedHeaders:             hardenhmac.DefaultSignedHeadersConfig(),
		}

		secretResolver = func(r *http.Request) (string, error) {
			clientID := r.Header.Get("X-Harden-Client-Id")
			if clientID != "" {
				if secret, ok := clientSecrets[clientID]; ok {
					return secret, nil
				}
			}
			return "", nil
		}
	} else if hmacMode == "global" {
		port = cfg.GlobalPorts["go"]
		useGlobalMiddleware = true

		// Build HmacConfig with Clients from config.json
		clients := make(map[string]hardenhmac.HmacClientIdentity)
		for name, c := range cfg.Clients {
			clients[name] = hardenhmac.HmacClientIdentity{SharedSecret: c.SharedSecret}
		}

		hmacConfig = &hardenhmac.HmacConfig{
			SharedSecretBase64:        cfg.SharedSecret,
			TimestampToleranceSeconds: 30,
			SignedHeaders:             hardenhmac.DefaultSignedHeadersConfig(),
			Clients:                   clients,
		}
	} else {
		port = cfg.Ports["go"]

		// Build HmacConfig with Clients from config.json
		clients := make(map[string]hardenhmac.HmacClientIdentity)
		for name, c := range cfg.Clients {
			clients[name] = hardenhmac.HmacClientIdentity{SharedSecret: c.SharedSecret}
		}

		hmacConfig = &hardenhmac.HmacConfig{
			SharedSecretBase64:        cfg.SharedSecret,
			TimestampToleranceSeconds: 30,
			SignedHeaders:             hardenhmac.DefaultSignedHeadersConfig(),
			Clients:                   clients,
		}
	}

	mux := http.NewServeMux()

	if useGlobalMiddleware {
		// Global mode: all routes defined without per-route validation
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

		// In global mode, /health is also protected (wrapped by global middleware)
		mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]string{"status": "healthy", "language": "go"})
		})
	} else {
		// Per-route HMAC validation wrapper
		validate := hardenhmac.NewHmacValidateHandler(hmacConfig, secretResolver)

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
	}

	var handler http.Handler
	if useGlobalMiddleware {
		// Wrap entire mux with global HMAC middleware
		handler = hardenhmac.NewHmacMiddleware(hmacConfig, nil)(mux)
	} else {
		handler = mux
	}

	addr := fmt.Sprintf("0.0.0.0:%d", port)
	log.Printf("Go server listening on port %d", port)
	log.Fatal(http.ListenAndServe(addr, handler))
}
