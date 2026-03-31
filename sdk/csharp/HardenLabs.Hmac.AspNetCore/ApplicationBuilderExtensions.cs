using Microsoft.AspNetCore.Builder;

namespace HardenLabs.Hmac.AspNetCore;

/// <summary>
/// Extension methods for adding HardenHMAC middleware to the ASP.NET Core pipeline.
/// </summary>
public static class ApplicationBuilderExtensions
{
    /// <summary>
    /// Add HardenHMAC validation middleware to the request pipeline.
    /// Requests without valid HMAC signatures will be rejected.
    /// </summary>
    /// <param name="app">The application builder.</param>
    /// <returns>The application builder for chaining.</returns>
    public static IApplicationBuilder UseHardenHmac(this IApplicationBuilder app)
    {
        return app.UseMiddleware<HardenHmacMiddleware>();
    }
}
