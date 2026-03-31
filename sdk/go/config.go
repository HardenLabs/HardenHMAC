// Package hardenhmac provides HMAC-SHA256 request signing and validation
// for the HardenHMAC cross-language signing protocol.
package hardenhmac

const (
	// SignatureHeader is the HTTP header name for the HMAC signature.
	SignatureHeader = "X-Harden-Signature"
	// TimestampHeader is the HTTP header name for the request timestamp.
	TimestampHeader = "X-Harden-Timestamp"
	// SignedHeadersHeader is the HTTP header name listing which headers were signed.
	SignedHeadersHeader = "X-Harden-Signed-Headers"
	// ClientIdHeader is the HTTP header name for the client identity.
	ClientIdHeader = "X-Harden-Client-Id"
	// clientIdHeaderLower is the lowercase version for comparison.
	clientIdHeaderLower = "x-harden-client-id"
	// HardenHeaderPrefix is the lowercase prefix for all Harden protocol headers.
	HardenHeaderPrefix = "x-harden-"
	// XHeaderPrefix is the lowercase prefix for X-* headers.
	XHeaderPrefix = "x-"
	// DefaultTimestampToleranceSeconds is the default timestamp tolerance for validation.
	DefaultTimestampToleranceSeconds = 30
)

// SignedHeadersConfig controls which request headers are included in the HMAC signature.
type SignedHeadersConfig struct {
	// IncludeAuthorization includes the Authorization header in the signature.
	IncludeAuthorization bool
	// IncludeXHeaders includes all X-* headers (except X-Harden-*) in the signature.
	IncludeXHeaders bool
	// AdditionalHeaders lists extra header names to include (case-insensitive).
	AdditionalHeaders []string
	// ExcludeHeaders lists header names to exclude (case-insensitive, overrides inclusion).
	ExcludeHeaders []string
}

// DefaultSignedHeadersConfig returns the default configuration: include Authorization and X-* headers.
func DefaultSignedHeadersConfig() SignedHeadersConfig {
	return SignedHeadersConfig{
		IncludeAuthorization: true,
		IncludeXHeaders:      true,
		AdditionalHeaders:    nil,
		ExcludeHeaders:       nil,
	}
}

// NoneSignedHeadersConfig returns a configuration that signs no headers.
func NoneSignedHeadersConfig() SignedHeadersConfig {
	return SignedHeadersConfig{
		IncludeAuthorization: false,
		IncludeXHeaders:      false,
		AdditionalHeaders:    nil,
		ExcludeHeaders:       nil,
	}
}

// HmacTargetConfig is per-target configuration for a named service target (client-side).
type HmacTargetConfig struct {
	// BaseURL is the base URL for the target service.
	BaseURL string
	// SharedSecret is the Base64-encoded shared secret for this target.
	// If empty, the global SharedSecretBase64 from HmacConfig is used.
	SharedSecret string
	// SignedHeaders overrides the global signed headers config for this target.
	// If nil, the global config is used.
	SignedHeaders *SignedHeadersConfig
	// TimestampToleranceSeconds overrides the global timestamp tolerance.
	// If nil, the global tolerance is used.
	TimestampToleranceSeconds *int
}

// HmacClientIdentity holds the shared secret for a known client (server-side multi-client).
type HmacClientIdentity struct {
	// SharedSecret is the Base64-encoded shared secret for this client.
	SharedSecret string
}

// HmacConfig is the top-level configuration for HMAC signing and validation.
type HmacConfig struct {
	// SharedSecretBase64 is the global shared secret as a Base64-encoded string.
	SharedSecretBase64 string
	// TimestampToleranceSeconds is the global timestamp tolerance for validation.
	// Zero value defaults to DefaultTimestampToleranceSeconds.
	TimestampToleranceSeconds int
	// SignedHeaders is the global signed headers configuration.
	SignedHeaders SignedHeadersConfig
	// Targets maps target names to their configurations (client-side).
	Targets map[string]HmacTargetConfig
	// Clients maps client IDs to their identities (server-side multi-client).
	Clients map[string]HmacClientIdentity
}

// effectiveTolerance returns the effective timestamp tolerance, defaulting if zero.
func (c *HmacConfig) effectiveTolerance() int {
	if c.TimestampToleranceSeconds > 0 {
		return c.TimestampToleranceSeconds
	}
	return DefaultTimestampToleranceSeconds
}

// GetEffectiveSecret resolves the shared secret for a named target.
// Returns the target's secret if set, otherwise the global secret.
// Returns an error if the target is not configured.
func (c *HmacConfig) GetEffectiveSecret(targetName string) (string, error) {
	target, ok := c.Targets[targetName]
	if !ok {
		available := make([]string, 0, len(c.Targets))
		for k := range c.Targets {
			available = append(available, k)
		}
		return "", &ConfigError{
			Message: "Target '" + targetName + "' is not configured. Available targets: " + formatList(available) + ".",
		}
	}
	if target.SharedSecret != "" {
		return target.SharedSecret, nil
	}
	return c.SharedSecretBase64, nil
}

// GetEffectiveSignedHeaders resolves the signed headers config for a named target.
func (c *HmacConfig) GetEffectiveSignedHeaders(targetName string) SignedHeadersConfig {
	if target, ok := c.Targets[targetName]; ok && target.SignedHeaders != nil {
		return *target.SignedHeaders
	}
	return c.SignedHeaders
}

// GetEffectiveTimestampTolerance resolves the timestamp tolerance for a named target.
func (c *HmacConfig) GetEffectiveTimestampTolerance(targetName string) int {
	if target, ok := c.Targets[targetName]; ok && target.TimestampToleranceSeconds != nil {
		return *target.TimestampToleranceSeconds
	}
	return c.effectiveTolerance()
}

// ForTarget builds an effective HmacConfig for a specific target with all overrides resolved.
func (c *HmacConfig) ForTarget(targetName string) (*HmacConfig, error) {
	secret, err := c.GetEffectiveSecret(targetName)
	if err != nil {
		return nil, err
	}
	sh := c.GetEffectiveSignedHeaders(targetName)
	tol := c.GetEffectiveTimestampTolerance(targetName)
	return &HmacConfig{
		SharedSecretBase64:        secret,
		SignedHeaders:             sh,
		TimestampToleranceSeconds: tol,
	}, nil
}

// ConfigError is returned when configuration is invalid or a target/client is not found.
type ConfigError struct {
	Message string
}

func (e *ConfigError) Error() string { return e.Message }

func formatList(items []string) string {
	if len(items) == 0 {
		return "[]"
	}
	s := "["
	for i, item := range items {
		if i > 0 {
			s += ", "
		}
		s += item
	}
	s += "]"
	return s
}
