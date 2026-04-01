using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.DependencyInjection;

namespace HardenLabs.Hmac.AspNetCore;

/// <summary>
/// Extension methods for adding HardenHMAC middleware to the ASP.NET Core pipeline.
/// </summary>
public static class ApplicationBuilderExtensions
{
    /// <summary>
    /// Add HardenHMAC validation middleware to the request pipeline.
    /// Requests without valid HMAC signatures will be rejected.
    /// If a secret resolver was registered via <see cref="ServiceCollectionExtensions.AddHardenHmac(Microsoft.Extensions.DependencyInjection.IServiceCollection, HmacConfig, Func{HttpContext, Task{string?}}?)"/>,
    /// it will be used to resolve secrets per-request.
    /// </summary>
    /// <param name="app">The application builder.</param>
    /// <returns>The application builder for chaining.</returns>
    public static IApplicationBuilder UseHardenHmac(this IApplicationBuilder app)
    {
        // Check if a secret resolver was registered
        var secretResolver = app.ApplicationServices.GetService<Func<HttpContext, Task<string?>>>();

        if (secretResolver is not null)
        {
            return app.UseMiddleware<HardenHmacMiddleware>(secretResolver);
        }

        return app.UseMiddleware<HardenHmacMiddleware>();
    }
}
