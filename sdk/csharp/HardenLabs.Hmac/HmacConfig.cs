namespace HardenLabs.Hmac;

/// <summary>
/// Configuration for HMAC signing and validation.
///
/// Supports two modes:
/// 1. Single-secret mode: set <see cref="SharedSecretBase64"/> for simple client or server use.
/// 2. Multi-target mode: populate <see cref="Targets"/> with named service configurations.
///
/// Global <see cref="SignedHeaders"/> and <see cref="TimestampToleranceSeconds"/> serve as defaults
/// that individual targets can override.
/// </summary>
public sealed class HmacConfig
{
    /// <summary>
    /// The shared secret as a Base64-encoded string.
    /// Used directly in single-secret mode, or as a server-side default when no target applies.
    /// </summary>
    public string SharedSecretBase64 { get; set; } = "";

    /// <summary>
    /// Named service targets, each with their own base URL and shared secret.
    /// Used for client-side multi-target configurations.
    /// </summary>
    public Dictionary<string, HmacTargetConfig> Targets { get; set; } = new();

    /// <summary>
    /// Named client identities for server-side multi-client secret resolution.
    /// When a request includes <c>X-Harden-Client-Id</c>, the middleware looks up
    /// the client name in this dictionary to find the appropriate shared secret.
    /// </summary>
    public Dictionary<string, HmacClientIdentity> Clients { get; set; } = new();

    /// <summary>
    /// Configuration for which headers to include in the signature.
    /// Individual targets can override this.
    /// </summary>
    public SignedHeadersConfig SignedHeaders { get; set; } = new();

    /// <summary>
    /// Timestamp tolerance in seconds for server-side validation. Default: 30.
    /// Individual targets can override this.
    /// </summary>
    public int TimestampToleranceSeconds { get; set; } = HardenHmacConstants.DefaultTimestampToleranceSeconds;

    /// <summary>
    /// Resolve the effective shared secret for a named target.
    /// Returns the target's secret if set, otherwise falls back to the global secret.
    /// </summary>
    /// <param name="targetName">The target name.</param>
    /// <returns>The effective Base64-encoded shared secret.</returns>
    /// <exception cref="ArgumentException">If the target is not found.</exception>
    public string GetEffectiveSecret(string targetName)
    {
        if (!Targets.TryGetValue(targetName, out var target))
        {
            throw new ArgumentException($"Target '{targetName}' is not configured.", nameof(targetName));
        }

        return !string.IsNullOrEmpty(target.SharedSecret) ? target.SharedSecret : SharedSecretBase64;
    }

    /// <summary>
    /// Resolve the effective signed headers config for a named target.
    /// Returns the target's override if set, otherwise the global config.
    /// </summary>
    public SignedHeadersConfig GetEffectiveSignedHeaders(string targetName)
    {
        if (Targets.TryGetValue(targetName, out var target) && target.SignedHeaders is not null)
        {
            return target.SignedHeaders;
        }

        return SignedHeaders;
    }

    /// <summary>
    /// Resolve the effective timestamp tolerance for a named target.
    /// Returns the target's override if set, otherwise the global config.
    /// </summary>
    public int GetEffectiveTimestampTolerance(string targetName)
    {
        if (Targets.TryGetValue(targetName, out var target) && target.TimestampToleranceSeconds.HasValue)
        {
            return target.TimestampToleranceSeconds.Value;
        }

        return TimestampToleranceSeconds;
    }

    /// <summary>
    /// Build an effective <see cref="HmacConfig"/> for a specific target,
    /// with all overrides resolved. Useful for creating per-target signers and validators.
    /// </summary>
    public HmacConfig ForTarget(string targetName)
    {
        return new HmacConfig
        {
            SharedSecretBase64 = GetEffectiveSecret(targetName),
            SignedHeaders = GetEffectiveSignedHeaders(targetName),
            TimestampToleranceSeconds = GetEffectiveTimestampTolerance(targetName),
        };
    }
}
