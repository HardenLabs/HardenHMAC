namespace HardenLabs.Hmac.AspNetCore;

/// <summary>
/// Factory for creating pre-configured HttpClients that automatically sign requests
/// for named service targets.
/// </summary>
public interface IHardenHmacClientFactory
{
    /// <summary>
    /// Create an HttpClient for the named target.
    /// The client's BaseAddress is set from the target's BaseUrl,
    /// and all requests are automatically signed with the target's shared secret.
    /// </summary>
    /// <param name="targetName">The name of the target as defined in <see cref="HmacConfig.Targets"/>.</param>
    /// <returns>A configured HttpClient.</returns>
    /// <exception cref="ArgumentException">If the target name is not found in configuration.</exception>
    HttpClient CreateClient(string targetName);
}
