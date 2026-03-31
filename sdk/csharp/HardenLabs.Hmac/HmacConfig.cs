namespace HardenLabs.Hmac;

/// <summary>
/// Configuration for HMAC signing and validation.
/// </summary>
public sealed class HmacConfig
{
    /// <summary>
    /// The shared secret as a Base64-encoded string. Required.
    /// </summary>
    public required string SharedSecretBase64 { get; init; }

    /// <summary>
    /// Configuration for which headers to include in the signature.
    /// </summary>
    public SignedHeadersConfig SignedHeaders { get; init; } = SignedHeadersConfig.Default;

    /// <summary>
    /// Timestamp tolerance in seconds for server-side validation. Default: 30.
    /// </summary>
    public int TimestampToleranceSeconds { get; init; } = HardenHmacConstants.DefaultTimestampToleranceSeconds;
}
