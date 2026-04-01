namespace HardenLabs.Hmac;

/// <summary>
/// Per-target configuration for a named service target (client-side).
/// Each target has its own base URL, shared secret, and optionally overrides
/// global signed headers and timestamp tolerance settings.
/// </summary>
public sealed class HmacTargetConfig
{
    /// <summary>
    /// Base URL for the target service (e.g., "https://orders.example.com").
    /// </summary>
    public string BaseUrl { get; set; } = "";

    /// <summary>
    /// The shared secret as a Base64-encoded string for this target.
    /// </summary>
    public string SharedSecret { get; set; } = "";

    /// <summary>
    /// Per-target signed headers override. If null, uses global config.
    /// </summary>
    public SignedHeadersConfig? SignedHeaders { get; set; }

    /// <summary>
    /// Per-target timestamp tolerance override in seconds. If null, uses global config.
    /// </summary>
    public int? TimestampToleranceSeconds { get; set; }
}
