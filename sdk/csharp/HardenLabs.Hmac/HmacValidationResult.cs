namespace HardenLabs.Hmac;

/// <summary>
/// Result of validating an HMAC-signed request.
/// </summary>
public sealed class HmacValidationResult
{
    /// <summary>Whether the request passed validation.</summary>
    public bool IsValid { get; }

    /// <summary>Error type identifier (null if valid). Values: "missing_signature", "missing_timestamp",
    /// "invalid_timestamp", "timestamp_expired", "timestamp_out_of_range", "signature_invalid".</summary>
    public string? ErrorType { get; }

    /// <summary>Human-readable error message (null if valid).</summary>
    public string? ErrorMessage { get; }

    private HmacValidationResult(bool isValid, string? errorType = null, string? errorMessage = null)
    {
        IsValid = isValid;
        ErrorType = errorType;
        ErrorMessage = errorMessage;
    }

    /// <summary>Create a successful validation result.</summary>
    public static HmacValidationResult Success() => new(true);

    /// <summary>Create a failed validation result.</summary>
    public static HmacValidationResult Failure(string errorType, string errorMessage) =>
        new(false, errorType, errorMessage);
}
