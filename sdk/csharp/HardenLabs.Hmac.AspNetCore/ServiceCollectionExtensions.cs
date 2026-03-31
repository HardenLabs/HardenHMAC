using Microsoft.Extensions.DependencyInjection;

namespace HardenLabs.Hmac.AspNetCore;

/// <summary>
/// Extension methods for registering HardenHMAC services.
/// </summary>
public static class ServiceCollectionExtensions
{
    /// <summary>
    /// Register HardenHMAC services for dependency injection.
    /// </summary>
    /// <param name="services">The service collection.</param>
    /// <param name="config">HMAC configuration.</param>
    /// <returns>The service collection for chaining.</returns>
    public static IServiceCollection AddHardenHmac(this IServiceCollection services, HmacConfig config)
    {
        ArgumentNullException.ThrowIfNull(config);

        services.AddSingleton(config);
        services.AddSingleton<HmacValidator>();
        services.AddSingleton<HmacRequestSigner>();

        return services;
    }

    /// <summary>
    /// Add a named HttpClient with HardenHMAC signing handler.
    /// </summary>
    /// <param name="services">The service collection.</param>
    /// <param name="name">HttpClient name.</param>
    /// <param name="config">HMAC configuration.</param>
    /// <returns>The IHttpClientBuilder for further configuration.</returns>
    public static IHttpClientBuilder AddHardenHmacClient(
        this IServiceCollection services,
        string name,
        HmacConfig config)
    {
        return services.AddHttpClient(name)
            .AddHttpMessageHandler(() => new HardenHmacDelegatingHandler(config));
    }
}
