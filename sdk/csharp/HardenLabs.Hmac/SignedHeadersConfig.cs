namespace HardenLabs.Hmac;

/// <summary>
/// Configuration for which request headers are included in the HMAC signature.
/// </summary>
public sealed class SignedHeadersConfig
{
    /// <summary>
    /// Include the Authorization header in the signature. Default: true.
    /// </summary>
    public bool IncludeAuthorization { get; init; } = true;

    /// <summary>
    /// Include all X-* headers (except X-Harden-*) in the signature. Default: true.
    /// </summary>
    public bool IncludeXHeaders { get; init; } = true;

    /// <summary>
    /// Additional header names to include in the signature (case-insensitive).
    /// </summary>
    public IReadOnlyList<string> AdditionalHeaders { get; init; } = [];

    /// <summary>
    /// Header names to exclude from the signature (case-insensitive, overrides inclusion).
    /// </summary>
    public IReadOnlyList<string> ExcludeHeaders { get; init; } = [];

    /// <summary>
    /// Default configuration: include Authorization and X-* headers.
    /// </summary>
    public static SignedHeadersConfig Default => new();

    /// <summary>
    /// Configuration that signs no headers.
    /// </summary>
    public static SignedHeadersConfig None => new()
    {
        IncludeAuthorization = false,
        IncludeXHeaders = false
    };
}
