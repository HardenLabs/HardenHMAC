using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace HardenLabs.Hmac.AspNetCore;

/// <summary>
/// Extension methods for registering HardenHMAC services.
/// </summary>
public static class ServiceCollectionExtensions
{
    /// <summary>
    /// Register HardenHMAC services for dependency injection with an explicit config object.
    /// </summary>
    /// <param name="services">The service collection.</param>
    /// <param name="config">HMAC configuration.</param>
    /// <param name="secretResolver">
    /// Optional callback to resolve the shared secret per-request (e.g., for multi-tenant).
    /// If the resolver returns null, falls back to <see cref="HmacConfig.SharedSecretBase64"/>.
    /// </param>
    /// <returns>The service collection for chaining.</returns>
    public static IServiceCollection AddHardenHmac(
        this IServiceCollection services,
        HmacConfig config,
        Func<HttpContext, Task<string?>>? secretResolver = null)
    {
        ArgumentNullException.ThrowIfNull(config);

        services.AddSingleton(config);
        services.AddSingleton<HmacValidator>();
        services.AddSingleton<HmacRequestSigner>();
        services.AddSingleton<IHardenHmacClientFactory>(new HardenHmacClientFactory(config));

        if (secretResolver is not null)
        {
            services.AddSingleton(secretResolver);
        }

        return services;
    }

    /// <summary>
    /// Register HardenHMAC services from an <see cref="IConfiguration"/> section (e.g., from appsettings.json).
    /// Binds to the "HardenHmac" section by default when using the full configuration root.
    /// </summary>
    /// <param name="services">The service collection.</param>
    /// <param name="configuration">
    /// Configuration section to bind. Pass <c>configuration.GetSection("HardenHmac")</c>
    /// or any <see cref="IConfiguration"/> that contains the HmacConfig properties.
    /// </param>
    /// <param name="secretResolver">
    /// Optional callback to resolve the shared secret per-request (e.g., for multi-tenant).
    /// </param>
    /// <returns>The service collection for chaining.</returns>
    public static IServiceCollection AddHardenHmac(
        this IServiceCollection services,
        IConfiguration configuration,
        Func<HttpContext, Task<string?>>? secretResolver = null)
    {
        ArgumentNullException.ThrowIfNull(configuration);

        var config = new HmacConfig();
        configuration.Bind(config);

        return services.AddHardenHmac(config, secretResolver);
    }

}
