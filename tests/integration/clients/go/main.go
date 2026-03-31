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

const clientID = "go-client"

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
	}
}
