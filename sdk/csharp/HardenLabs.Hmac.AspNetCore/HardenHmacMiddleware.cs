using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;

namespace HardenLabs.Hmac.AspNetCore;

/// <summary>
/// ASP.NET Core middleware that validates incoming HMAC-signed requests.
/// </summary>
public sealed class HardenHmacMiddleware
{
    private readonly RequestDelegate _next;
    private readonly HmacValidator _validator;
    private readonly HmacConfig _config;
    private readonly ILogger<HardenHmacMiddleware> _logger;

    public HardenHmacMiddleware(
        RequestDelegate next,
        HmacConfig config,
        ILogger<HardenHmacMiddleware> logger)
    {
        _next = next ?? throw new ArgumentNullException(nameof(next));
        _config = config ?? throw new ArgumentNullException(nameof(config));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _validator = new HmacValidator(config);
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

        var result = _validator.Validate(
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
}
