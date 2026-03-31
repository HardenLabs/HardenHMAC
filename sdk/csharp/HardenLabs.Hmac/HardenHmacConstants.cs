namespace HardenLabs.Hmac;

/// <summary>
/// Constants for HardenHMAC header names and defaults.
/// </summary>
public static class HardenHmacConstants
{
    /// <summary>Header containing the 64-char hex HMAC signature.</summary>
    public const string SignatureHeader = "X-Harden-Signature";

    /// <summary>Header containing the Unix timestamp in seconds.</summary>
    public const string TimestampHeader = "X-Harden-Timestamp";

    /// <summary>Header containing semicolon-separated signed header names.</summary>
    public const string SignedHeadersHeader = "X-Harden-Signed-Headers";

    /// <summary>Prefix for Harden-internal headers (always excluded from signing).</summary>
    public const string HardenHeaderPrefix = "X-Harden-";

    /// <summary>Prefix for custom X-* headers.</summary>
    public const string XHeaderPrefix = "X-";

    /// <summary>Default timestamp tolerance in seconds.</summary>
    public const int DefaultTimestampToleranceSeconds = 30;
}
