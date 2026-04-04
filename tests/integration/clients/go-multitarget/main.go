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
	"strings"
	"time"

	hardenhmac "github.com/HardenLabs/hardenhmac-go"
)

type targetEntry struct {
	BaseURL      string `json:"baseUrl"`
	SharedSecret string `json:"sharedSecret"`
}

type multiTargetTests struct {
	Targets map[string]targetEntry `json:"targets"`
}

type configFile struct {
	MultiTargetTests multiTargetTests `json:"multiTargetTests"`
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

func isConnError(err error) bool {
	var netErr *net.OpError
	return errors.As(err, &netErr)
}

func main() {
	cfg, err := loadConfig()
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	hasFail := false

	// Build HmacConfig with Targets
	hmacTargets := make(map[string]hardenhmac.HmacTargetConfig)
	for name, t := range cfg.MultiTargetTests.Targets {
		hmacTargets[name] = hardenhmac.HmacTargetConfig{
			BaseURL:      t.BaseURL,
			SharedSecret: t.SharedSecret,
		}
	}

	hmacConfig := &hardenhmac.HmacConfig{
		Targets:       hmacTargets,
		SignedHeaders: hardenhmac.DefaultSignedHeadersConfig(),
	}

	factory := hardenhmac.NewClientFactory(hmacConfig)

	// 1. Multi-target: call each server with correct target-specific secret
	targetNames := []string{"csharp-client", "python-client", "typescript-client", "go-client"}
	for _, targetName := range targetNames {
		serverName := strings.Replace(targetName, "-client", "-server", 1)

		client, err := factory.CreateClient(targetName)
		if err != nil {
			fmt.Printf("FAIL go-multitarget -> %s: factory error: %v\n", serverName, err)
			hasFail = true
			continue
		}

		// GET /api/hello
		resp, err := client.Get("/api/hello")
		if err != nil {
			if isConnError(err) {
				fmt.Printf("SKIP go-multitarget -> %s GET /api/hello (server not running)\n", serverName)
				fmt.Printf("SKIP go-multitarget -> %s POST /api/echo (server not running)\n", serverName)
				continue
			}
			fmt.Printf("FAIL go-multitarget -> %s GET /api/hello: %v\n", serverName, err)
			hasFail = true
			continue
		}
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		if resp.StatusCode == 200 {
			fmt.Printf("PASS go-multitarget -> %s GET /api/hello (%d)\n", serverName, resp.StatusCode)
		} else {
			fmt.Printf("FAIL go-multitarget -> %s GET /api/hello (%d): %s\n", serverName, resp.StatusCode, string(body))
			hasFail = true
		}

		// POST /api/echo
		postBody := fmt.Sprintf(`{"from":"%s","test":"multitarget"}`, targetName)
		resp, err = client.Post("/api/echo", "application/json", postBody)
		if err != nil {
			if isConnError(err) {
				fmt.Printf("SKIP go-multitarget -> %s POST /api/echo (server not running)\n", serverName)
				continue
			}
			fmt.Printf("FAIL go-multitarget -> %s POST /api/echo: %v\n", serverName, err)
			hasFail = true
			continue
		}
		body, _ = io.ReadAll(resp.Body)
		resp.Body.Close()
		if resp.StatusCode == 200 {
			fmt.Printf("PASS go-multitarget -> %s POST /api/echo (%d)\n", serverName, resp.StatusCode)
		} else {
			fmt.Printf("FAIL go-multitarget -> %s POST /api/echo (%d): %s\n", serverName, resp.StatusCode, string(body))
			hasFail = true
		}
	}

	// 2. Cross-client test: send as two different clients to the SAME server (python-server, port 9101)
	crossBase := cfg.MultiTargetTests.Targets["python-client"].BaseURL
	crossServer := "python-server"

	for _, crossID := range []string{"csharp-client", "go-client"} {
		crossSecret := cfg.MultiTargetTests.Targets[crossID].SharedSecret
		crossConfig := &hardenhmac.HmacConfig{
			SharedSecretBase64: crossSecret,
			SignedHeaders:      hardenhmac.DefaultSignedHeadersConfig(),
		}

		transport := &hardenhmac.SigningTransport{
			Config:     crossConfig,
			TargetName: crossID,
		}
		crossClient := &http.Client{Transport: transport, Timeout: 10 * time.Second}

		resp, err := crossClient.Get(crossBase + "/api/hello")
		if err != nil {
			if isConnError(err) {
				fmt.Printf("SKIP go-multitarget/cross(%s) -> %s GET /api/hello (server not running)\n", crossID, crossServer)
				continue
			}
			fmt.Printf("FAIL go-multitarget/cross(%s) -> %s GET /api/hello: %v\n", crossID, crossServer, err)
			hasFail = true
			continue
		}
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		if resp.StatusCode == 200 {
			fmt.Printf("PASS go-multitarget/cross(%s) -> %s GET /api/hello (%d)\n", crossID, crossServer, resp.StatusCode)
		} else {
			fmt.Printf("FAIL go-multitarget/cross(%s) -> %s GET /api/hello (%d): %s\n", crossID, crossServer, resp.StatusCode, string(body))
			hasFail = true
		}
	}

	// 3. Negative test: wrong secret for client ID -> expect 4xx
	wrongSecret := cfg.MultiTargetTests.Targets["go-client"].SharedSecret
	wrongConfig := &hardenhmac.HmacConfig{
		SharedSecretBase64: wrongSecret, // go-client secret
		SignedHeaders:      hardenhmac.DefaultSignedHeadersConfig(),
	}
	wrongTransport := &hardenhmac.SigningTransport{
		Config:     wrongConfig,
		TargetName: "csharp-client", // claim to be csharp-client
	}
	wrongClient := &http.Client{Transport: wrongTransport, Timeout: 10 * time.Second}

	resp, err := wrongClient.Get(crossBase + "/api/hello")
	if err != nil {
		if isConnError(err) {
			fmt.Printf("SKIP go-multitarget/wrong-secret -> %s GET /api/hello (server not running)\n", crossServer)
		} else {
			fmt.Printf("FAIL go-multitarget/wrong-secret -> %s GET /api/hello: %v\n", crossServer, err)
			hasFail = true
		}
	} else {
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		if resp.StatusCode >= 400 && resp.StatusCode < 500 {
			fmt.Printf("PASS go-multitarget/wrong-secret -> %s GET /api/hello (%d)\n", crossServer, resp.StatusCode)
		} else {
			fmt.Printf("FAIL go-multitarget/wrong-secret -> %s GET /api/hello (expected 4xx, got %d): %s\n", crossServer, resp.StatusCode, string(body))
			hasFail = true
		}
	}

	if hasFail {
		os.Exit(1)
	}
}
