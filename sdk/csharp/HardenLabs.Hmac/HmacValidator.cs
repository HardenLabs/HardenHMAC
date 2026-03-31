namespace HardenLabs.Hmac;

/// <summary>
/// Validates incoming HMAC-signed requests. Checks timestamp freshness and signature correctness.
/// </summary>
public sealed class HmacValidator
{
    private readonly HmacConfig _config;

    public HmacValidator(HmacConfig config)
    {
        _config = config ?? throw new ArgumentNullException(nameof(config));
    }

    /// <summary>
    /// Validate a request's HMAC signature and timestamp.
    /// </summary>
    /// <param name="method">HTTP method.</param>
    /// <param name="path">Request path including query string.</param>
    /// <param name="body">Request body (empty string if none).</param>
    /// <param name="signatureHeader">Value of X-Harden-Signature header.</param>
    /// <param name="timestampHeader">Value of X-Harden-Timestamp header.</param>
    /// <param name="requestHeaders">All request headers for signed header reconstruction.</param>
    /// <param name="currentTimestamp">Current Unix timestamp (if null, uses DateTimeOffset.UtcNow).</param>
    /// <returns>Validation result indicating success or failure with error details.</returns>
    public HmacValidationResult Validate(
        string method,
        string path,
        string body,
        string? signatureHeader,
        string? timestampHeader,
        IReadOnlyDictionary<string, string>? requestHeaders = null,
        long? currentTimestamp = null)
    {
        // Check required headers
        if (string.IsNullOrEmpty(signatureHeader))
        {
            return HmacValidationResult.Failure("missing_signature",
                "X-Harden-Signature header is required.");
        }

        if (string.IsNullOrEmpty(timestampHeader))
        {
            return HmacValidationResult.Failure("missing_timestamp",
                "X-Harden-Timestamp header is required.");
        }

        // Parse timestamp
        if (!long.TryParse(timestampHeader, out var requestTimestamp))
        {
            return HmacValidationResult.Failure("invalid_timestamp",
                "X-Harden-Timestamp header is not a valid integer.");
        }

        // Validate timestamp freshness
        var now = currentTimestamp ?? DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var delta = now - requestTimestamp;

        if (delta > _config.TimestampToleranceSeconds)
        {
            return HmacValidationResult.Failure("timestamp_expired",
                $"Request timestamp is {delta} seconds in the past (tolerance: {_config.TimestampToleranceSeconds}s).");
        }

        if (delta < -_config.TimestampToleranceSeconds)
        {
            return HmacValidationResult.Failure("timestamp_out_of_range",
                $"Request timestamp is {-delta} seconds in the future (tolerance: {_config.TimestampToleranceSeconds}s).");
        }

        // Build canonical string and verify signature
        var canonicalString = CanonicalStringBuilder.Build(
            method, path, body ?? string.Empty, requestTimestamp,
            _config.SignedHeaders, requestHeaders);

        if (!HmacSigner.Verify(_config.SharedSecretBase64, canonicalString, signatureHeader))
        {
            return HmacValidationResult.Failure("signature_invalid",
                "HMAC signature does not match the expected value.");
        }

        return HmacValidationResult.Success();
    }
}
