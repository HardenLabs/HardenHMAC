using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;

namespace HardenLabs.Hmac.AspNetCore;

/// <summary>
/// ASP.NET Core middleware that validates incoming HMAC-signed requests.
/// Supports a static shared secret from config and/or a dynamic secret resolver callback
/// for multi-tenant scenarios.
/// </summary>
public sealed class HardenHmacMiddleware
{
    private readonly RequestDelegate _next;
    private readonly HmacConfig _config;
    private readonly ILogger<HardenHmacMiddleware> _logger;
    private readonly Func<HttpContext, Task<string?>>? _secretResolver;

    public HardenHmacMiddleware(
        RequestDelegate next,
        HmacConfig config,
        ILogger<HardenHmacMiddleware> logger)
        : this(next, config, logger, secretResolver: null)
    {
    }

    public HardenHmacMiddleware(
        RequestDelegate next,
        HmacConfig config,
        ILogger<HardenHmacMiddleware> logger,
        Func<HttpContext, Task<string?>>? secretResolver)
    {
        _next = next ?? throw new ArgumentNullException(nameof(next));
        _config = config ?? throw new ArgumentNullException(nameof(config));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _secretResolver = secretResolver;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        var request = context.Request;

        // Read body (enable buffering so downstream can read it too)
        request.EnableBuffering();
        string body;
        using (var reader = new StreamReader(request.Body, Encoding.UTF8, leaveOpen: true))
        {
            body = await reader.ReadToEndAsync();
            request.Body.Position = 0;
        }

        var path = request.Path.Value ?? "/";
        if (request.QueryString.HasValue)
        {
            path += request.QueryString.Value;
        }

        // Extract request headers as dictionary (first value per header)
        var requestHeaders = new Dictionary<string, string>();
        foreach (var header in request.Headers)
        {
            requestHeaders[header.Key] = header.Value.ToString();
        }

        var signatureHeader = request.Headers[HardenHmacConstants.SignatureHeader].FirstOrDefault();
        var timestampHeader = request.Headers[HardenHmacConstants.TimestampHeader].FirstOrDefault();

        // Resolve the shared secret: try resolver, then Clients dict, then config fallback
        var (effectiveSecret, resolveError) = await ResolveSecretAsync(context);

        if (resolveError is not null)
        {
            _logger.LogWarning("HMAC validation failed: {ErrorType} for {Method} {Path}",
                resolveError.Value.errorType, request.Method, path);

            context.Response.StatusCode = 401;
            context.Response.ContentType = "application/json";
            var errorBody = JsonSerializer.Serialize(new { error = resolveError.Value.errorType, message = resolveError.Value.message });
            await context.Response.WriteAsync(errorBody);
            return;
        }

        if (string.IsNullOrEmpty(effectiveSecret))
        {
            _logger.LogWarning("HMAC validation failed: no shared secret configured or resolved for {Method} {Path}",
                request.Method, path);

            context.Response.StatusCode = 401;
            context.Response.ContentType = "application/json";
            var noSecretBody = JsonSerializer.Serialize(new { error = "no_secret", message = "No shared secret configured for this request." });
            await context.Response.WriteAsync(noSecretBody);
            return;
        }

        var validationConfig = new HmacConfig
        {
            SharedSecretBase64 = effectiveSecret,
            SignedHeaders = _config.SignedHeaders,
            TimestampToleranceSeconds = _config.TimestampToleranceSeconds,
        };

        var validator = new HmacValidator(validationConfig);
        var result = validator.Validate(
            request.Method,
            path,
            body,
            signatureHeader,
            timestampHeader,
            requestHeaders);

        if (!result.IsValid)
        {
            _logger.LogWarning("HMAC validation failed: {ErrorType} - {ErrorMessage}",
                result.ErrorType, result.ErrorMessage);

            context.Response.StatusCode = result.ErrorType switch
            {
                "timestamp_expired" or "timestamp_out_of_range" => 401,
                "signature_invalid" => 401,
                "missing_signature" or "missing_timestamp" or "invalid_timestamp" => 400,
                _ => 401
            };

            context.Response.ContentType = "application/json";
            var responseBody = JsonSerializer.Serialize(new { error = result.ErrorType, message = result.ErrorMessage });
            await context.Response.WriteAsync(responseBody);
            return;
        }

        _logger.LogDebug("HMAC validation succeeded for {Method} {Path}", request.Method, path);
        await _next(context);
    }

    private async Task<(string? secret, (string errorType, string message)? error)> ResolveSecretAsync(HttpContext context)
    {
        // 1. secretResolver callback (if provided) takes highest priority
        if (_secretResolver is not null)
        {
            var resolved = await _secretResolver(context);
            if (!string.IsNullOrEmpty(resolved))
            {
                return (resolved, null);
            }
        }

        // 2. X-Harden-Client-Id header → look up in config.Clients
        var clientId = context.Request.Headers[HardenHmacConstants.ClientIdHeader].FirstOrDefault();
        if (!string.IsNullOrEmpty(clientId))
        {
            if (_config.Clients.TryGetValue(clientId, out var clientIdentity)
                && !string.IsNullOrEmpty(clientIdentity.SharedSecret))
            {
                return (clientIdentity.SharedSecret, null);
            }

            // Client ID was provided but not found in Clients dictionary
            return (null, ("unknown_client", "Unknown or unconfigured client."));
        }

        // 3. Fall back to config.SharedSecretBase64
        var fallback = !string.IsNullOrEmpty(_config.SharedSecretBase64)
            ? _config.SharedSecretBase64
            : null;
        return (fallback, null);
    }
}
