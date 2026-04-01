using System.Security.Cryptography;
using System.Text;

namespace HardenLabs.Hmac;

/// <summary>
/// HMAC-SHA256 signing and verification with constant-time comparison.
/// </summary>
public static class HmacSigner
{
    /// <summary>
    /// Compute the HMAC-SHA256 signature of a canonical string.
    /// </summary>
    /// <param name="sharedSecretBase64">The shared secret as a Base64-encoded string.</param>
    /// <param name="canonicalString">The canonical string to sign.</param>
    /// <returns>Lowercase hexadecimal signature string (64 characters).</returns>
    public static string Sign(string sharedSecretBase64, string canonicalString)
    {
        ArgumentNullException.ThrowIfNull(sharedSecretBase64);
        ArgumentNullException.ThrowIfNull(canonicalString);

        var keyBytes = Convert.FromBase64String(sharedSecretBase64);
        try
        {
            var dataBytes = Encoding.UTF8.GetBytes(canonicalString);
            var hashBytes = HMACSHA256.HashData(keyBytes, dataBytes);
            return Convert.ToHexString(hashBytes).ToLowerInvariant();
        }
        finally
        {
            CryptographicOperations.ZeroMemory(keyBytes);
        }
    }

    /// <summary>
    /// Verify a signature against a canonical string using constant-time comparison.
    /// </summary>
    /// <param name="sharedSecretBase64">The shared secret as a Base64-encoded string.</param>
    /// <param name="canonicalString">The canonical string that was signed.</param>
    /// <param name="signature">The signature to verify (64-char lowercase hex).</param>
    /// <returns>True if the signature is valid.</returns>
    public static bool Verify(string sharedSecretBase64, string canonicalString, string signature)
    {
        ArgumentNullException.ThrowIfNull(sharedSecretBase64);
        ArgumentNullException.ThrowIfNull(canonicalString);
        ArgumentNullException.ThrowIfNull(signature);

        // Sign already zeroes key bytes internally, no additional zeroing needed here.
        var expected = Sign(sharedSecretBase64, canonicalString);
        var expectedBytes = Encoding.UTF8.GetBytes(expected);
        var signatureBytes = Encoding.UTF8.GetBytes(signature);

        if (expectedBytes.Length != signatureBytes.Length)
        {
            return false;
        }

        return CryptographicOperations.FixedTimeEquals(expectedBytes, signatureBytes);
    }
}
