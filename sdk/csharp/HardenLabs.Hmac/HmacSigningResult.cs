namespace HardenLabs.Hmac;

/// <summary>
/// Result of signing a request, containing the signature and metadata.
/// </summary>
/// <param name="Signature">The 64-character lowercase hex HMAC-SHA256 signature.</param>
/// <param name="Timestamp">The Unix timestamp used in the signature.</param>
/// <param name="SignedHeaderNames">Sorted list of signed header names (empty if no headers signed).</param>
/// <param name="CanonicalString">The canonical string that was signed (useful for debugging).</param>
public sealed record HmacSigningResult(
    string Signature,
    long Timestamp,
    IReadOnlyList<string> SignedHeaderNames,
    string CanonicalString);
