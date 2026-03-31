package hardenhmac

import (
	"os"
	"strconv"
	"strings"
)

// FromEnv loads HmacConfig from environment variables with the given prefix.
//
// If prefix is empty, "HARDEN_HMAC_" is used.
//
// Supported environment variables:
//
//	{PREFIX}SHARED_SECRET_BASE64           -- global shared secret
//	{PREFIX}TIMESTAMP_TOLERANCE_SECONDS    -- global tolerance (default: 30)
//	{PREFIX}SIGNED_HEADERS__INCLUDE_AUTHORIZATION -- true/false (default: true)
//	{PREFIX}SIGNED_HEADERS__INCLUDE_X_HEADERS     -- true/false (default: true)
//	{PREFIX}TARGETS__{NAME}__BASE_URL     -- per-target base URL
//	{PREFIX}TARGETS__{NAME}__SHARED_SECRET -- per-target secret
//	{PREFIX}TARGETS__{NAME}__TIMESTAMP_TOLERANCE_SECONDS -- per-target tolerance
//	{PREFIX}CLIENTS__{NAME}__SHARED_SECRET -- per-client secret (server-side)
func FromEnv(prefix string) (*HmacConfig, error) {
	return fromEnvMap(prefix, envToMap())
}

// fromEnvMap is the testable core that takes an explicit env map.
func fromEnvMap(prefix string, env map[string]string) (*HmacConfig, error) {
	if prefix == "" {
		prefix = "HARDEN_HMAC_"
	}
	upperPrefix := strings.ToUpper(prefix)

	// Extract all env vars with the prefix
	prefixed := make(map[string]string)
	for key, value := range env {
		if strings.HasPrefix(strings.ToUpper(key), upperPrefix) {
			suffix := key[len(upperPrefix):]
			prefixed[strings.ToUpper(suffix)] = value
		}
	}

	// Parse global settings
	sharedSecret := prefixed["SHARED_SECRET_BASE64"]
	tolerance := DefaultTimestampToleranceSeconds
	if s, ok := prefixed["TIMESTAMP_TOLERANCE_SECONDS"]; ok {
		if v, err := strconv.Atoi(s); err == nil {
			tolerance = v
		}
	}

	// Parse signed headers
	includeAuth := parseBool(prefixed["SIGNED_HEADERS__INCLUDE_AUTHORIZATION"], true)
	includeX := parseBool(prefixed["SIGNED_HEADERS__INCLUDE_X_HEADERS"], true)
	signedHeaders := SignedHeadersConfig{
		IncludeAuthorization: includeAuth,
		IncludeXHeaders:      includeX,
	}

	// Parse targets: keys matching TARGETS__{NAME}__{FIELD}
	type targetFields map[string]string
	targets := make(map[string]targetFields)
	for key, value := range prefixed {
		if !strings.HasPrefix(key, "TARGETS__") {
			continue
		}
		rest := key[len("TARGETS__"):]
		parts := strings.SplitN(rest, "__", 2)
		if len(parts) != 2 {
			continue
		}
		targetName := strings.ToLower(strings.ReplaceAll(parts[0], "_", "-"))
		fieldName := strings.ToUpper(parts[1])
		if targets[targetName] == nil {
			targets[targetName] = make(targetFields)
		}
		targets[targetName][fieldName] = value
	}

	targetConfigs := make(map[string]HmacTargetConfig, len(targets))
	for name, fields := range targets {
		tc := HmacTargetConfig{
			BaseURL:      fields["BASE_URL"],
			SharedSecret: fields["SHARED_SECRET"],
		}
		if s, ok := fields["TIMESTAMP_TOLERANCE_SECONDS"]; ok {
			if v, err := strconv.Atoi(s); err == nil {
				tc.TimestampToleranceSeconds = &v
			}
		}
		targetConfigs[name] = tc
	}

	// Parse clients: keys matching CLIENTS__{NAME}__{FIELD}
	type clientFields map[string]string
	clients := make(map[string]clientFields)
	for key, value := range prefixed {
		if !strings.HasPrefix(key, "CLIENTS__") {
			continue
		}
		rest := key[len("CLIENTS__"):]
		parts := strings.SplitN(rest, "__", 2)
		if len(parts) != 2 {
			continue
		}
		clientName := strings.ToLower(strings.ReplaceAll(parts[0], "_", "-"))
		fieldName := strings.ToUpper(parts[1])
		if clients[clientName] == nil {
			clients[clientName] = make(clientFields)
		}
		clients[clientName][fieldName] = value
	}

	clientConfigs := make(map[string]HmacClientIdentity, len(clients))
	for name, fields := range clients {
		clientConfigs[name] = HmacClientIdentity{
			SharedSecret: fields["SHARED_SECRET"],
		}
	}

	config := &HmacConfig{
		SharedSecretBase64:        sharedSecret,
		TimestampToleranceSeconds: tolerance,
		SignedHeaders:             signedHeaders,
		Targets:                   targetConfigs,
		Clients:                   clientConfigs,
	}

	return config, nil
}

func parseBool(value string, defaultVal bool) bool {
	if value == "" {
		return defaultVal
	}
	lower := strings.ToLower(value)
	return lower == "true" || lower == "1" || lower == "yes"
}

func envToMap() map[string]string {
	env := make(map[string]string)
	for _, entry := range os.Environ() {
		if idx := strings.IndexByte(entry, '='); idx >= 0 {
			env[entry[:idx]] = entry[idx+1:]
		}
	}
	return env
}
