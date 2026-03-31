// Package main implements the Go HMAC integration test client.
//
// REQUIRES: Go installation and hardenlabs-hmac Go SDK.
// This file is a placeholder -- it will not compile until the Go SDK
// is available and wired in go.mod.
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
)

const clientID = "go-client"

type config struct {
	Clients map[string]struct {
		SharedSecret string `json:"sharedSecret"`
	} `json:"clients"`
	Ports map[string]int `json:"ports"`
}

func loadConfig() (*config, error) {
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
	_, err := loadConfig()
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	// TODO: Implement HMAC-signed requests using Go SDK
	// For now, this is a placeholder that exits with an error
	// indicating Go SDK is not yet available.
	fmt.Println("SKIP go-client: Go SDK not yet available")
	os.Exit(0)
}
