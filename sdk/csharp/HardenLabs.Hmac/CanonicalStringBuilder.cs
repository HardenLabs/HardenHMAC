using System.Text;

namespace HardenLabs.Hmac;

/// <summary>
/// Builds the canonical string from HTTP request components per the v1.0 specification.
/// </summary>
public static class CanonicalStringBuilder
{
    // Pre-computed lowercase constants to avoid repeated ToLowerInvariant() in the hot loop
    private static readonly string HardenHeaderPrefixLower = HardenHmacConstants.HardenHeaderPrefix.ToLowerInvariant();
    private static readonly string ClientIdHeaderLower = HardenHmacConstants.ClientIdHeader.ToLowerInvariant();
    private static readonly string XHeaderPrefixLower = HardenHmacConstants.XHeaderPrefix.ToLowerInvariant();

    /// <summary>
    /// Build a canonical string from request components.
    /// </summary>
    /// <param name="method">HTTP method (will be uppercased).</param>
    /// <param name="path">Request path including query string.</param>
    /// <param name="body">Request body, or empty string if none.</param>
    /// <param name="timestamp">Unix timestamp in seconds.</param>
    /// <param name="signedHeadersConfig">Configuration for which headers to sign.</param>
    /// <param name="requestHeaders">All request headers (name -> value).</param>
    /// <returns>The canonical string.</returns>
    public static string Build(
        string method,
        string path,
        string body,
        long timestamp,
        SignedHeadersConfig? signedHeadersConfig = null,
        IReadOnlyDictionary<string, string>? requestHeaders = null)
    {
        ArgumentNullException.ThrowIfNull(method);
        ArgumentNullException.ThrowIfNull(path);

        var config = signedHeadersConfig ?? SignedHeadersConfig.None;
        var headers = requestHeaders ?? new Dictionary<string, string>();
        var signedHeadersString = BuildSignedHeadersString(config, headers);

        var sb = new StringBuilder();
        sb.Append(method.ToUpperInvariant());
        sb.Append('\n');
        sb.Append(path);
        sb.Append('\n');
        sb.Append(signedHeadersString);
        sb.Append('\n');
        sb.Append(body ?? string.Empty);
        sb.Append('\n');
        sb.Append(timestamp.ToString());

        return sb.ToString();
    }

    /// <summary>
    /// Build the signed headers portion of the canonical string.
    /// Returns the list of header names that were included (sorted, lowercase).
    /// </summary>
    public static (string headerString, IReadOnlyList<string> headerNames) BuildSignedHeaders(
        SignedHeadersConfig config,
        IReadOnlyDictionary<string, string> requestHeaders)
    {
        var selected = SelectHeaders(config, requestHeaders);
        var headerNames = selected.Select(h => h.name).ToList();
        var headerString = string.Join("\n", selected.Select(h => $"{h.name}:{h.value}"));
        return (headerString, headerNames);
    }

    private static string BuildSignedHeadersString(
        SignedHeadersConfig config,
        IReadOnlyDictionary<string, string> requestHeaders)
    {
        var selected = SelectHeaders(config, requestHeaders);
        return string.Join("\n", selected.Select(h => $"{h.name}:{h.value}"));
    }

    private static List<(string name, string value)> SelectHeaders(
        SignedHeadersConfig config,
        IReadOnlyDictionary<string, string> requestHeaders)
    {
        var excludeSet = new HashSet<string>(
            config.ExcludeHeaders.Select(h => h.ToLowerInvariant()),
            StringComparer.Ordinal);

        var additionalSet = new HashSet<string>(
            config.AdditionalHeaders.Select(h => h.ToLowerInvariant()),
            StringComparer.Ordinal);

        var selected = new List<(string name, string value)>();

        foreach (var kvp in requestHeaders)
        {
            var lowerName = kvp.Key.ToLowerInvariant();
            var trimmedValue = kvp.Value.Trim();

            // Always exclude X-Harden-* headers, EXCEPT X-Harden-Client-Id
            // (client identity is an identity claim, not signing metadata)
            if (lowerName.StartsWith(HardenHeaderPrefixLower)
                && !string.Equals(lowerName, ClientIdHeaderLower, StringComparison.Ordinal))
                continue;

            // Check if this header should be included
            bool include = false;

            if (config.IncludeAuthorization &&
                string.Equals(lowerName, "authorization", StringComparison.Ordinal))
            {
                include = true;
            }

            if (config.IncludeXHeaders &&
                lowerName.StartsWith(XHeaderPrefixLower) &&
                (!lowerName.StartsWith(HardenHeaderPrefixLower) ||
                 string.Equals(lowerName, ClientIdHeaderLower, StringComparison.Ordinal)))
            {
                include = true;
            }

            if (additionalSet.Contains(lowerName))
            {
                include = true;
            }

            // Apply exclude override
            if (excludeSet.Contains(lowerName))
            {
                include = false;
            }

            if (include)
            {
                selected.Add((lowerName, trimmedValue));
            }
        }

        // Sort alphabetically by lowercase name
        selected.Sort((a, b) => string.Compare(a.name, b.name, StringComparison.Ordinal));

        return selected;
    }
}
