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
        var handler = new HardenHmacDelegatingHandler(effectiveConfig, clientId: targetName);
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
