using System.Net;
using FluentAssertions;
using HardenLabs.Hmac.AspNetCore;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

namespace HardenLabs.Hmac.Tests;

public class SecretResolverMiddlewareTests : IAsyncLifetime
{
    private const string DefaultSecret = "ZGVmYXVsdC1zZWNyZXQta2V5LTMyLWJ5dGVzISEhISE=";
    private const string TenantASecret = "dGVuYW50LWEtc2VjcmV0LWtleS0zMi1ieXRlcyEhIQ==";
    private const string TenantBSecret = "dGVuYW50LWItc2VjcmV0LWtleS0zMi1ieXRlcyEhIQ==";

    private IHost? _host;
    private HttpClient? _testClient;

    public async Task InitializeAsync()
    {
        var config = new HmacConfig
        {
            SharedSecretBase64 = DefaultSecret,
            SignedHeaders = SignedHeadersConfig.None,
            TimestampToleranceSeconds = 30,
        };

        // Secret resolver: look up by X-Client-Id header
        Func<HttpContext, Task<string?>> secretResolver = ctx =>
        {
            var clientId = ctx.Request.Headers["X-Client-Id"].FirstOrDefault();
            return clientId switch
            {
                "tenant-a" => Task.FromResult<string?>(TenantASecret),
                "tenant-b" => Task.FromResult<string?>(TenantBSecret),
                _ => Task.FromResult<string?>(null), // fall back to config.SharedSecretBase64
            };
        };

        _host = await new HostBuilder()
            .ConfigureWebHost(webBuilder =>
            {
                webBuilder
                    .UseTestServer()
                    .ConfigureServices(services =>
                    {
                        services.AddHardenHmac(config, secretResolver);
                        services.AddLogging();
                    })
                    .Configure(app =>
                    {
                        app.UseHardenHmac();
                        app.Run(async context =>
                        {
                            context.Response.StatusCode = 200;
                            await context.Response.WriteAsync("OK");
                        });
                    });
            })
            .StartAsync();

        _testClient = _host.GetTestClient();
    }

    public async Task DisposeAsync()
    {
        _testClient?.Dispose();
        if (_host is not null)
        {
            await _host.StopAsync();
            _host.Dispose();
        }
    }

    [Fact]
    public async Task Resolver_TenantA_ValidSignature_Returns200()
    {
        var timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var canonical = CanonicalStringBuilder.Build("GET", "/api/test", "", timestamp, SignedHeadersConfig.None);
        var signature = HmacSigner.Sign(TenantASecret, canonical);

        var request = new HttpRequestMessage(HttpMethod.Get, "/api/test");
        request.Headers.Add("X-Client-Id", "tenant-a");
        request.Headers.Add(HardenHmacConstants.SignatureHeader, signature);
        request.Headers.Add(HardenHmacConstants.TimestampHeader, timestamp.ToString());

        var response = await _testClient!.SendAsync(request);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task Resolver_TenantB_ValidSignature_Returns200()
    {
        var timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var canonical = CanonicalStringBuilder.Build("GET", "/api/test", "", timestamp, SignedHeadersConfig.None);
        var signature = HmacSigner.Sign(TenantBSecret, canonical);

        var request = new HttpRequestMessage(HttpMethod.Get, "/api/test");
        request.Headers.Add("X-Client-Id", "tenant-b");
        request.Headers.Add(HardenHmacConstants.SignatureHeader, signature);
        request.Headers.Add(HardenHmacConstants.TimestampHeader, timestamp.ToString());

        var response = await _testClient!.SendAsync(request);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task Resolver_WrongSecret_Returns401()
    {
        var timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        // Sign with default secret but send as tenant-a (which should use tenant-a secret)
        var canonical = CanonicalStringBuilder.Build("GET", "/api/test", "", timestamp, SignedHeadersConfig.None);
        var signature = HmacSigner.Sign(DefaultSecret, canonical);

        var request = new HttpRequestMessage(HttpMethod.Get, "/api/test");
        request.Headers.Add("X-Client-Id", "tenant-a");
        request.Headers.Add(HardenHmacConstants.SignatureHeader, signature);
        request.Headers.Add(HardenHmacConstants.TimestampHeader, timestamp.ToString());

        var response = await _testClient!.SendAsync(request);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task Resolver_NullFallback_UsesDefaultSecret()
    {
        var timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        // No X-Client-Id header, resolver returns null, falls back to DefaultSecret
        var canonical = CanonicalStringBuilder.Build("GET", "/api/test", "", timestamp, SignedHeadersConfig.None);
        var signature = HmacSigner.Sign(DefaultSecret, canonical);

        var request = new HttpRequestMessage(HttpMethod.Get, "/api/test");
        request.Headers.Add(HardenHmacConstants.SignatureHeader, signature);
        request.Headers.Add(HardenHmacConstants.TimestampHeader, timestamp.ToString());

        var response = await _testClient!.SendAsync(request);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }
}
