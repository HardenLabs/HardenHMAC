package main

import (
	"encoding/base64"
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

const clientID = "go-client"

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

		// IT-3: Fallback secret (sign with sharedSecret, NO X-Harden-Client-Id)
		fallbackConfig := &hardenhmac.HmacConfig{
			SharedSecretBase64: cfg.SharedSecret,
			SignedHeaders:      hardenhmac.DefaultSignedHeadersConfig(),
		}
		fallbackTransport := &hardenhmac.SigningTransport{
			Config:     fallbackConfig,
			TargetName: "", // no client ID
		}
		fallbackClient := &http.Client{Transport: fallbackTransport}
		resp, err = fallbackClient.Get(fmt.Sprintf("%s/api/hello", baseURL))
		if err != nil {
			var netErr *net.OpError
			if errors.As(err, &netErr) {
				fmt.Printf("SKIP %s/fallback -> %s GET /api/hello (server not running)\n", clientID, s.name)
			} else {
				fmt.Printf("FAIL %s/fallback -> %s GET /api/hello: %v\n", clientID, s.name, err)
			}
		} else {
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			if resp.StatusCode == 200 {
				fmt.Printf("PASS %s/fallback -> %s GET /api/hello (%d)\n", clientID, s.name, resp.StatusCode)
			} else {
				fmt.Printf("FAIL %s/fallback -> %s GET /api/hello (%d): %s\n", clientID, s.name, resp.StatusCode, string(body))
			}
		}

		// IT-4: Unknown client rejection
		bogusSecret := base64.StdEncoding.EncodeToString([]byte("wrong-secret-for-unknown-client!!!"))
		bogusConfig := &hardenhmac.HmacConfig{
			SharedSecretBase64: bogusSecret,
			SignedHeaders:      hardenhmac.DefaultSignedHeadersConfig(),
		}
		bogusTransport := &hardenhmac.SigningTransport{
			Config:     bogusConfig,
			TargetName: "nonexistent-client",
		}
		bogusClient := &http.Client{Transport: bogusTransport}
		resp, err = bogusClient.Get(fmt.Sprintf("%s/api/hello", baseURL))
		if err != nil {
			var netErr *net.OpError
			if errors.As(err, &netErr) {
				fmt.Printf("SKIP %s/unknown-client -> %s GET /api/hello (server not running)\n", clientID, s.name)
			} else {
				fmt.Printf("FAIL %s/unknown-client -> %s GET /api/hello: %v\n", clientID, s.name, err)
			}
		} else {
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			if resp.StatusCode >= 400 && resp.StatusCode < 500 {
				fmt.Printf("PASS %s/unknown-client -> %s GET /api/hello (%d)\n", clientID, s.name, resp.StatusCode)
			} else {
				fmt.Printf("FAIL %s/unknown-client -> %s GET /api/hello (expected 4xx, got %d): %s\n", clientID, s.name, resp.StatusCode, string(body))
			}
		}

		// IT-5: Stale timestamp (300s in the past)
		staleTs := time.Now().Unix() - 300
		staleHeaders := map[string]string{
			hardenhmac.ClientIdHeader: clientID,
		}
		staleSigHeaders, staleErr := hardenhmac.SignRequestHeaders(hmacConfig, "GET", "/api/hello", "", staleHeaders, staleTs)
		if staleErr != nil {
			fmt.Printf("FAIL %s/stale-ts -> %s GET /api/hello: sign error: %v\n", clientID, s.name, staleErr)
		} else {
			staleReq, _ := http.NewRequest("GET", fmt.Sprintf("%s/api/hello", baseURL), nil)
			staleReq.Header.Set(hardenhmac.ClientIdHeader, clientID)
			for k, v := range staleSigHeaders {
				staleReq.Header.Set(k, v)
			}
			resp, err = plainClient.Do(staleReq)
			if err != nil {
				var netErr *net.OpError
				if errors.As(err, &netErr) {
					fmt.Printf("SKIP %s/stale-ts -> %s GET /api/hello (server not running)\n", clientID, s.name)
				} else {
					fmt.Printf("FAIL %s/stale-ts -> %s GET /api/hello: %v\n", clientID, s.name, err)
				}
			} else {
				body, _ := io.ReadAll(resp.Body)
				resp.Body.Close()
				if resp.StatusCode >= 400 && resp.StatusCode < 500 {
					fmt.Printf("PASS %s/stale-ts -> %s GET /api/hello (%d)\n", clientID, s.name, resp.StatusCode)
				} else {
					fmt.Printf("FAIL %s/stale-ts -> %s GET /api/hello (expected 4xx, got %d): %s\n", clientID, s.name, resp.StatusCode, string(body))
				}
			}
		}

		// IT-8: Empty body POST
		emptyPostReq, _ := http.NewRequest("POST", fmt.Sprintf("%s/api/echo", baseURL), strings.NewReader(""))
		emptyPostReq.Header.Set("Content-Type", "application/json")
		emptyPostReq.Header.Set(hardenhmac.ClientIdHeader, clientID)
		emptyExistingHeaders := map[string]string{
			"content-type":            "application/json",
			hardenhmac.ClientIdHeader: clientID,
		}
		emptySigHeaders, emptyErr := hardenhmac.SignRequestHeaders(hmacConfig, "POST", "/api/echo", "", emptyExistingHeaders, 0)
		if emptyErr != nil {
			fmt.Printf("FAIL %s/empty-body -> %s POST /api/echo: sign error: %v\n", clientID, s.name, emptyErr)
		} else {
			for k, v := range emptySigHeaders {
				emptyPostReq.Header.Set(k, v)
			}
			resp, err = plainClient.Do(emptyPostReq)
			if err != nil {
				var netErr *net.OpError
				if errors.As(err, &netErr) {
					fmt.Printf("SKIP %s/empty-body -> %s POST /api/echo (server not running)\n", clientID, s.name)
				} else {
					fmt.Printf("FAIL %s/empty-body -> %s POST /api/echo: %v\n", clientID, s.name, err)
				}
			} else {
				body, _ := io.ReadAll(resp.Body)
				resp.Body.Close()
				if resp.StatusCode == 200 {
					fmt.Printf("PASS %s/empty-body -> %s POST /api/echo (%d)\n", clientID, s.name, resp.StatusCode)
				} else {
					fmt.Printf("FAIL %s/empty-body -> %s POST /api/echo (%d): %s\n", clientID, s.name, resp.StatusCode, string(body))
				}
			}
		}

		// IT-9: Wrong SignedHeaders (client uses NoneSignedHeadersConfig, server uses Default)
		// Include Authorization header so signed-headers difference actually matters
		noneConfig := &hardenhmac.HmacConfig{
			SharedSecretBase64: mySecret,
			SignedHeaders:      hardenhmac.NoneSignedHeadersConfig(),
		}
		noneTransport := &hardenhmac.SigningTransport{
			Config:     noneConfig,
			TargetName: clientID,
		}
		noneClient := &http.Client{Transport: noneTransport}
		noneReq, _ := http.NewRequest("GET", fmt.Sprintf("%s/api/hello", baseURL), nil)
		noneReq.Header.Set("Authorization", "Bearer test")
		resp, err = noneClient.Do(noneReq)
		if err != nil {
			var netErr *net.OpError
			if errors.As(err, &netErr) {
				fmt.Printf("SKIP %s/wrong-headers -> %s GET /api/hello (server not running)\n", clientID, s.name)
			} else {
				fmt.Printf("FAIL %s/wrong-headers -> %s GET /api/hello: %v\n", clientID, s.name, err)
			}
		} else {
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			if resp.StatusCode >= 400 && resp.StatusCode < 500 {
				fmt.Printf("PASS %s/wrong-headers -> %s GET /api/hello (%d)\n", clientID, s.name, resp.StatusCode)
			} else {
				fmt.Printf("FAIL %s/wrong-headers -> %s GET /api/hello (expected 4xx, got %d): %s\n", clientID, s.name, resp.StatusCode, string(body))
			}
		}

		// IT-10: Query string
		queryTransport := &hardenhmac.SigningTransport{
			Config:     hmacConfig,
			TargetName: clientID,
		}
		queryClient := &hardenhmac.Client{
			Client:  &http.Client{Transport: queryTransport},
			BaseURL: baseURL,
		}
		resp, err = queryClient.Get("/api/hello?foo=bar&baz=1")
		if err != nil {
			var netErr *net.OpError
			if errors.As(err, &netErr) {
				fmt.Printf("SKIP %s/query -> %s GET /api/hello?foo=bar&baz=1 (server not running)\n", clientID, s.name)
			} else {
				fmt.Printf("FAIL %s/query -> %s GET /api/hello?foo=bar&baz=1: %v\n", clientID, s.name, err)
			}
		} else {
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			if resp.StatusCode == 200 {
				fmt.Printf("PASS %s/query -> %s GET /api/hello?foo=bar&baz=1 (%d)\n", clientID, s.name, resp.StatusCode)
			} else {
				fmt.Printf("FAIL %s/query -> %s GET /api/hello?foo=bar&baz=1 (%d): %s\n", clientID, s.name, resp.StatusCode, string(body))
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

	// ============================================================
	// Resolver server tests (IT-6)
	// ============================================================
	resolverServers := []serverTarget{
		{"csharp-resolver", cfg.ResolverPorts["csharp"]},
		{"python-resolver", cfg.ResolverPorts["python"]},
		{"typescript-resolver", cfg.ResolverPorts["typescript"]},
		{"go-resolver", cfg.ResolverPorts["go"]},
	}

	for _, s := range resolverServers {
		if s.port == 0 {
			continue
		}
		baseURL := fmt.Sprintf("http://localhost:%d", s.port)

		transport := &hardenhmac.SigningTransport{
			Config:     hmacConfig,
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
		resolverPostBody := fmt.Sprintf(`{"from":"%s","test":"integration-resolver"}`, clientID)
		resp, err = client.Post("/api/echo", "application/json", resolverPostBody)
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
				fmt.Printf("PASS %s -> %s POST /api/echo (%d)\n", clientID, s.name, resp.StatusCode)
			} else {
				fmt.Printf("FAIL %s -> %s POST /api/echo (%d): %s\n", clientID, s.name, resp.StatusCode, string(body))
			}
		}
	}

	// ============================================================
	// Global middleware server tests (IT-7)
	// ============================================================
	globalServers := []serverTarget{
		{"csharp-global", cfg.GlobalPorts["csharp"]},
		{"python-global", cfg.GlobalPorts["python"]},
		{"typescript-global", cfg.GlobalPorts["typescript"]},
		{"go-global", cfg.GlobalPorts["go"]},
	}

	for _, s := range globalServers {
		if s.port == 0 {
			continue
		}
		baseURL := fmt.Sprintf("http://localhost:%d", s.port)

		transport := &hardenhmac.SigningTransport{
			Config:     hmacConfig,
			TargetName: clientID,
		}
		client := &hardenhmac.Client{
			Client:  &http.Client{Transport: transport},
			BaseURL: baseURL,
		}

		// Signed GET /api/hello
		resp, err := client.Get("/api/hello")
		if err != nil {
			var netErr *net.OpError
			if errors.As(err, &netErr) {
				fmt.Printf("SKIP %s -> %s GET /api/hello (server not running)\n", clientID, s.name)
				fmt.Printf("SKIP %s -> %s POST /api/echo (server not running)\n", clientID, s.name)
				fmt.Printf("SKIP %s -> %s GET /health (server not running)\n", clientID, s.name)
				fmt.Printf("SKIP %s/nohmac -> %s GET /health (server not running)\n", clientID, s.name)
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

		// Signed POST /api/echo
		globalPostBody := fmt.Sprintf(`{"from":"%s","test":"integration-global"}`, clientID)
		resp, err = client.Post("/api/echo", "application/json", globalPostBody)
		if err != nil {
			var netErr *net.OpError
			if errors.As(err, &netErr) {
				fmt.Printf("SKIP %s -> %s POST /api/echo (server not running)\n", clientID, s.name)
			} else {
				fmt.Printf("FAIL %s -> %s POST /api/echo: %v\n", clientID, s.name, err)
			}
		} else {
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			if resp.StatusCode == 200 {
				fmt.Printf("PASS %s -> %s POST /api/echo (%d)\n", clientID, s.name, resp.StatusCode)
			} else {
				fmt.Printf("FAIL %s -> %s POST /api/echo (%d): %s\n", clientID, s.name, resp.StatusCode, string(body))
			}
		}

		// Signed GET /health (global mode protects ALL routes)
		resp, err = client.Get("/health")
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

		// Unsigned GET /health (global mode should reject)
		plainClient := &http.Client{}
		healthURL := fmt.Sprintf("%s/health", baseURL)
		resp, err = plainClient.Get(healthURL)
		if err != nil {
			var netErr *net.OpError
			if errors.As(err, &netErr) {
				fmt.Printf("SKIP %s/nohmac -> %s GET /health (server not running)\n", clientID, s.name)
			} else {
				fmt.Printf("FAIL %s/nohmac -> %s GET /health: %v\n", clientID, s.name, err)
			}
		} else {
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			if resp.StatusCode >= 400 && resp.StatusCode < 500 {
				fmt.Printf("PASS %s/nohmac -> %s GET /health (%d)\n", clientID, s.name, resp.StatusCode)
			} else {
				fmt.Printf("FAIL %s/nohmac -> %s GET /health (expected 4xx, got %d): %s\n", clientID, s.name, resp.StatusCode, string(body))
			}
		}
	}
}
