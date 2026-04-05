namespace HardenLabs.Hmac.AspNetCore;

/// <summary>
/// Creates named HttpClients with the correct base URL and HMAC signing handler
/// based on the target configuration in <see cref="HmacConfig.Targets"/>.
/// </summary>
public sealed class HardenHmacClientFactory : IHardenHmacClientFactory
{
    private readonly HmacConfig _config;

    public HardenHmacClientFactory(HmacConfig config)
    {
        _config = config ?? throw new ArgumentNullException(nameof(config));
    }

    /// <inheritdoc />
    /// <remarks>
    /// Each call allocates a new <see cref="HttpClient"/> and its underlying
    /// <see cref="HttpMessageHandler"/>. To avoid socket exhaustion, callers
    /// should store the returned client as a singleton per target and reuse it
    /// for the lifetime of the application rather than creating a new client
    /// per request.
    /// </remarks>
    public HttpClient CreateClient(string targetName)
    {
        ArgumentNullException.ThrowIfNull(targetName);

        if (!_config.Targets.TryGetValue(targetName, out var target))
        {
            throw new ArgumentException(
                $"Target '{targetName}' is not configured. Available targets: [{string.Join(", ", _config.Targets.Keys)}].",
                nameof(targetName));
        }

        var effectiveConfig = _config.ForTarget(targetName);
        var handler = new HardenHmacDelegatingHandler(effectiveConfig, new HttpClientHandler(), clientId: targetName);
        var client = new HttpClient(handler);

        if (!string.IsNullOrEmpty(target.BaseUrl))
        {
            var baseUrl = target.BaseUrl;
            if (!baseUrl.EndsWith('/'))
            {
                baseUrl += '/';
            }
            client.BaseAddress = new Uri(baseUrl);
        }

        return client;
    }
}
