using System.Net.Http.Headers;

namespace HardenLabs.Hmac.AspNetCore;

/// <summary>
/// HttpClient DelegatingHandler that automatically signs outgoing requests with HMAC-SHA256.
/// Optionally adds an <c>X-Harden-Client-Id</c> header to identify the client to the server.
/// </summary>
public sealed class HardenHmacDelegatingHandler : DelegatingHandler
{
    private readonly HmacRequestSigner _signer;
    private readonly HmacConfig _config;
    private readonly string? _clientId;

    public HardenHmacDelegatingHandler(HmacConfig config, string? clientId = null)
    {
        _config = config ?? throw new ArgumentNullException(nameof(config));
        _signer = new HmacRequestSigner(config);
        _clientId = clientId;
    }

    public HardenHmacDelegatingHandler(HmacConfig config, HttpMessageHandler innerHandler, string? clientId = null)
        : base(innerHandler)
    {
        _config = config ?? throw new ArgumentNullException(nameof(config));
        _signer = new HmacRequestSigner(config);
        _clientId = clientId;
    }

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        // Add X-Harden-Client-Id if configured
        if (!string.IsNullOrEmpty(_clientId))
        {
            request.Headers.TryAddWithoutValidation(
                HardenHmacConstants.ClientIdHeader, _clientId);
        }

        var method = request.Method.Method;
        var path = request.RequestUri?.PathAndQuery ?? "/";

        string body = string.Empty;
        if (request.Content is not null)
        {
            body = await request.Content.ReadAsStringAsync(cancellationToken);
        }

        // Collect existing request headers for signed header computation
        var requestHeaders = new Dictionary<string, string>();
        foreach (var header in request.Headers)
        {
            requestHeaders[header.Key] = string.Join(", ", header.Value);
        }
        if (request.Content?.Headers is not null)
        {
            foreach (var header in request.Content.Headers)
            {
                requestHeaders[header.Key] = string.Join(", ", header.Value);
            }
        }

        var result = _signer.Sign(method, path, body, requestHeaders);

        request.Headers.TryAddWithoutValidation(
            HardenHmacConstants.SignatureHeader, result.Signature);
        request.Headers.TryAddWithoutValidation(
            HardenHmacConstants.TimestampHeader, result.Timestamp.ToString());

        if (result.SignedHeaderNames.Count > 0)
        {
            request.Headers.TryAddWithoutValidation(
                HardenHmacConstants.SignedHeadersHeader,
                string.Join(";", result.SignedHeaderNames));
        }

        return await base.SendAsync(request, cancellationToken);
    }
}
