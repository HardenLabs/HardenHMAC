namespace HardenLabs.Hmac;

/// <summary>
/// Signs outgoing HTTP requests with HMAC-SHA256.
/// </summary>
public sealed class HmacRequestSigner
{
    private readonly HmacConfig _config;

    public HmacRequestSigner(HmacConfig config)
    {
        _config = config ?? throw new ArgumentNullException(nameof(config));
    }

    /// <summary>
    /// Sign a request and return the signing result with all header values.
    /// </summary>
    /// <param name="method">HTTP method.</param>
    /// <param name="path">Request path including query string.</param>
    /// <param name="body">Request body (empty string if none).</param>
    /// <param name="requestHeaders">Request headers for signed header selection.</param>
    /// <param name="timestamp">Unix timestamp (if null, uses DateTimeOffset.UtcNow).</param>
    /// <returns>Signing result with signature, timestamp, and signed header names.</returns>
    public HmacSigningResult Sign(
        string method,
        string path,
        string body,
        IReadOnlyDictionary<string, string>? requestHeaders = null,
        long? timestamp = null)
    {
        var ts = timestamp ?? DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var headers = requestHeaders ?? new Dictionary<string, string>();

        var (_, headerNames) = CanonicalStringBuilder.BuildSignedHeaders(
            _config.SignedHeaders, headers);

        var canonicalString = CanonicalStringBuilder.Build(
            method, path, body ?? string.Empty, ts,
            _config.SignedHeaders, headers);

        var signature = HmacSigner.Sign(_config.SharedSecretBase64, canonicalString);

        return new HmacSigningResult(signature, ts, headerNames, canonicalString);
    }
}
