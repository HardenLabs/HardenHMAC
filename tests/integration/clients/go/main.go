package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"

	hardenhmac "github.com/HardenLabs/hardenhmac-go"
)

const clientID = "go-client"

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

type serverTarget struct {
	name string
	port int
}

func main() {
	cfg, err := loadConfig()
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	mySecret := cfg.Clients[clientID].SharedSecret

	servers := []serverTarget{
		{"csharp-server", cfg.Ports["csharp"]},
		{"python-server", cfg.Ports["python"]},
		{"typescript-server", cfg.Ports["typescript"]},
		{"go-server", cfg.Ports["go"]},
	}

	// Build config with our secret — we'll create clients manually per server
	// because the factory sends target name as client ID, but we need "go-client"
	hmacConfig := &hardenhmac.HmacConfig{
		SharedSecretBase64: mySecret,
		SignedHeaders:      hardenhmac.DefaultSignedHeadersConfig(),
	}

	for _, s := range servers {
		baseURL := fmt.Sprintf("http://localhost:%d", s.port)

		// Create a signing transport with our client ID (not the target name)
		transport := &hardenhmac.SigningTransport{
			Config:     hmacConfig,
			TargetName: clientID, // "go-client", not "csharp-server"
		}
		client := &hardenhmac.Client{
			Client:  &http.Client{Transport: transport},
			BaseURL: baseURL,
		}

		// GET /api/hello
		resp, err := client.Get("/api/hello")
		if err != nil {
			var netErr *net.OpError
			if errors.As(err, &netErr) {
				fmt.Printf("SKIP %s -> %s GET /api/hello (server not running)\n", clientID, s.name)
				fmt.Printf("SKIP %s -> %s POST /api/echo (server not running)\n", clientID, s.name)
				continue
			}
			fmt.Printf("FAIL %s -> %s GET /api/hello: %v\n", clientID, s.name, err)
		} else {
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			if resp.StatusCode == 200 {
				fmt.Printf("PASS %s -> %s GET /api/hello (%d)\n", clientID, s.name, resp.StatusCode)
			} else {
				fmt.Printf("FAIL %s -> %s GET /api/hello (%d): %s\n", clientID, s.name, resp.StatusCode, string(body))
			}
		}

		// POST /api/echo
		postBody := fmt.Sprintf(`{"from":"%s","test":"integration"}`, clientID)
		resp, err = client.Post("/api/echo", "application/json", postBody)
		if err != nil {
			var netErr *net.OpError
			if errors.As(err, &netErr) {
				fmt.Printf("SKIP %s -> %s POST /api/echo (server not running)\n", clientID, s.name)
				continue
			}
			fmt.Printf("FAIL %s -> %s POST /api/echo: %v\n", clientID, s.name, err)
		} else {
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			if resp.StatusCode == 200 {
				var parsed map[string]interface{}
				json.Unmarshal(body, &parsed)
				fmt.Printf("PASS %s -> %s POST /api/echo (%d)\n", clientID, s.name, resp.StatusCode)
			} else {
				fmt.Printf("FAIL %s -> %s POST /api/echo (%d): %s\n", clientID, s.name, resp.StatusCode, string(body))
			}
		}

		// GET /health — unprotected, no HMAC required (plain HTTP client)
		plainClient := &http.Client{}
		healthURL := fmt.Sprintf("%s/health", baseURL)
		resp, err = plainClient.Get(healthURL)
		if err != nil {
			var netErr *net.OpError
			if errors.As(err, &netErr) {
				fmt.Printf("SKIP %s -> %s GET /health (server not running)\n", clientID, s.name)
			} else {
				fmt.Printf("FAIL %s -> %s GET /health: %v\n", clientID, s.name, err)
			}
		} else {
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			if resp.StatusCode == 200 {
				fmt.Printf("PASS %s -> %s GET /health (%d)\n", clientID, s.name, resp.StatusCode)
			} else {
				fmt.Printf("FAIL %s -> %s GET /health (%d): %s\n", clientID, s.name, resp.StatusCode, string(body))
			}
		}

		// GET /api/hello — protected, WITHOUT HMAC headers (expect 4xx rejection)
		helloURL := fmt.Sprintf("%s/api/hello", baseURL)
		resp, err = plainClient.Get(helloURL)
		if err != nil {
			var netErr *net.OpError
			if errors.As(err, &netErr) {
				fmt.Printf("SKIP %s/nohmac -> %s GET /api/hello (server not running)\n", clientID, s.name)
			} else {
				fmt.Printf("FAIL %s/nohmac -> %s GET /api/hello: %v\n", clientID, s.name, err)
			}
		} else {
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			if resp.StatusCode >= 400 && resp.StatusCode < 500 {
				fmt.Printf("PASS %s/nohmac -> %s GET /api/hello (%d)\n", clientID, s.name, resp.StatusCode)
			} else {
				fmt.Printf("FAIL %s/nohmac -> %s GET /api/hello (expected 4xx, got %d): %s\n", clientID, s.name, resp.StatusCode, string(body))
			}
		}
	}

	// ============================================================
	// Shared-secret server tests
	// ============================================================
	sharedServers := []serverTarget{
		{"csharp-shared", cfg.SharedPorts["csharp"]},
		{"python-shared", cfg.SharedPorts["python"]},
		{"typescript-shared", cfg.SharedPorts["typescript"]},
		{"go-shared", cfg.SharedPorts["go"]},
	}

	sharedHmacConfig := &hardenhmac.HmacConfig{
		SharedSecretBase64: cfg.SharedSecret,
		SignedHeaders:      hardenhmac.DefaultSignedHeadersConfig(),
	}

	for _, s := range sharedServers {
		baseURL := fmt.Sprintf("http://localhost:%d", s.port)

		transport := &hardenhmac.SigningTransport{
			Config:     sharedHmacConfig,
			TargetName: clientID,
		}
		client := &hardenhmac.Client{
			Client:  &http.Client{Transport: transport},
			BaseURL: baseURL,
		}

		// GET /api/hello
		resp, err := client.Get("/api/hello")
		if err != nil {
			var netErr *net.OpError
			if errors.As(err, &netErr) {
				fmt.Printf("SKIP %s/shared -> %s GET /api/hello (server not running)\n", clientID, s.name)
				fmt.Printf("SKIP %s/shared -> %s POST /api/echo (server not running)\n", clientID, s.name)
				continue
			}
			fmt.Printf("FAIL %s/shared -> %s GET /api/hello: %v\n", clientID, s.name, err)
		} else {
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			if resp.StatusCode == 200 {
				fmt.Printf("PASS %s/shared -> %s GET /api/hello (%d)\n", clientID, s.name, resp.StatusCode)
			} else {
				fmt.Printf("FAIL %s/shared -> %s GET /api/hello (%d): %s\n", clientID, s.name, resp.StatusCode, string(body))
			}
		}

		// POST /api/echo
		postBody := fmt.Sprintf(`{"from":"%s","test":"integration-shared"}`, clientID)
		resp, err = client.Post("/api/echo", "application/json", postBody)
		if err != nil {
			var netErr *net.OpError
			if errors.As(err, &netErr) {
				fmt.Printf("SKIP %s/shared -> %s POST /api/echo (server not running)\n", clientID, s.name)
				continue
			}
			fmt.Printf("FAIL %s/shared -> %s POST /api/echo: %v\n", clientID, s.name, err)
		} else {
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			if resp.StatusCode == 200 {
				fmt.Printf("PASS %s/shared -> %s POST /api/echo (%d)\n", clientID, s.name, resp.StatusCode)
			} else {
				fmt.Printf("FAIL %s/shared -> %s POST /api/echo (%d): %s\n", clientID, s.name, resp.StatusCode, string(body))
			}
		}
	}
}
