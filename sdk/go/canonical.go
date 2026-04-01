package hardenhmac

import (
	"errors"
	"fmt"
	"sort"
	"strings"
)

// BuildCanonicalString builds the canonical string for HMAC signing per the v1.0 specification.
//
// Format: METHOD\nPATH\nSIGNED_HEADERS\nBODY\nTIMESTAMP
//
// The config parameter controls which headers are included. If nil, no headers are signed.
// requestHeaders maps header names (original case) to values.
func BuildCanonicalString(method, path, body string, timestamp int64, config *SignedHeadersConfig, requestHeaders map[string]string) (string, error) {
	if strings.Contains(method, "\n") {
		return "", errors.New("method must not contain newline characters")
	}
	if strings.Contains(path, "\n") {
		return "", errors.New("path must not contain newline characters")
	}

	var cfg SignedHeadersConfig
	if config != nil {
		cfg = *config
	}

	signedHeadersStr := buildSignedHeadersString(cfg, requestHeaders)

	return strings.Join([]string{
		strings.ToUpper(method),
		path,
		signedHeadersStr,
		body,
		fmt.Sprintf("%d", timestamp),
	}, "\n"), nil
}

// BuildSignedHeaders builds the signed headers string and returns the sorted header names.
func BuildSignedHeaders(config SignedHeadersConfig, requestHeaders map[string]string) (headerString string, headerNames []string) {
	selected := selectHeaders(config, requestHeaders)
	names := make([]string, len(selected))
	parts := make([]string, len(selected))
	for i, h := range selected {
		names[i] = h.name
		parts[i] = h.name + ":" + h.value
	}
	return strings.Join(parts, "\n"), names
}

func buildSignedHeadersString(config SignedHeadersConfig, requestHeaders map[string]string) string {
	selected := selectHeaders(config, requestHeaders)
	parts := make([]string, len(selected))
	for i, h := range selected {
		parts[i] = h.name + ":" + h.value
	}
	return strings.Join(parts, "\n")
}

type selectedHeader struct {
	name  string
	value string
}

func selectHeaders(config SignedHeadersConfig, requestHeaders map[string]string) []selectedHeader {
	excludeSet := make(map[string]bool, len(config.ExcludeHeaders))
	for _, h := range config.ExcludeHeaders {
		excludeSet[strings.ToLower(h)] = true
	}

	additionalSet := make(map[string]bool, len(config.AdditionalHeaders))
	for _, h := range config.AdditionalHeaders {
		additionalSet[strings.ToLower(h)] = true
	}

	var selected []selectedHeader

	for name, value := range requestHeaders {
		lowerName := strings.ToLower(name)
		trimmedValue := strings.TrimSpace(value)

		// Always exclude X-Harden-* headers, EXCEPT X-Harden-Client-Id
		// (client identity is an identity claim, not signing metadata)
		if strings.HasPrefix(lowerName, HardenHeaderPrefix) && lowerName != clientIdHeaderLower {
			continue
		}

		include := false

		if config.IncludeAuthorization && lowerName == "authorization" {
			include = true
		}

		if config.IncludeXHeaders && strings.HasPrefix(lowerName, XHeaderPrefix) &&
			(!strings.HasPrefix(lowerName, HardenHeaderPrefix) || lowerName == clientIdHeaderLower) {
			include = true
		}

		// X-Harden-Client-Id is always signed when present (identity claim must not be spoofable)
		if lowerName == clientIdHeaderLower {
			include = true
		}

		if additionalSet[lowerName] {
			include = true
		}

		// Apply exclude override
		if excludeSet[lowerName] {
			include = false
		}

		if include {
			selected = append(selected, selectedHeader{name: lowerName, value: trimmedValue})
		}
	}

	// Sort by name (byte-wise lexicographic, matching Go's default string comparison)
	sort.Slice(selected, func(i, j int) bool {
		return selected[i].name < selected[j].name
	})

	return selected
}
