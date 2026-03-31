using System.Net;
using System.Net.Http.Headers;
using System.Text;
using FluentAssertions;
using HardenLabs.Hmac.AspNetCore;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

namespace HardenLabs.Hmac.Tests;

public class MiddlewareTests : IAsyncLifetime
{
    private const string TestSecret = "dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24=";
    private IHost? _host;
    private HttpClient? _testClient;

    public async Task InitializeAsync()
    {
        var config = new HmacConfig
        {
            SharedSecretBase64 = TestSecret,
            SignedHeaders = SignedHeadersConfig.None,
            TimestampToleranceSeconds = 30
        };

        _host = await new HostBuilder()
            .ConfigureWebHost(webBuilder =>
            {
                webBuilder
                    .UseTestServer()
                    .ConfigureServices(services =>
                    {
                        services.AddHardenHmac(config);
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
    public async Task Middleware_ValidSignature_Returns200()
    {
        var timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var canonical = CanonicalStringBuilder.Build("GET", "/api/test", "", timestamp, SignedHeadersConfig.None);
        var signature = HmacSigner.Sign(TestSecret, canonical);

        var request = new HttpRequestMessage(HttpMethod.Get, "/api/test");
        request.Headers.Add(HardenHmacConstants.SignatureHeader, signature);
        request.Headers.Add(HardenHmacConstants.TimestampHeader, timestamp.ToString());

        var response = await _testClient!.SendAsync(request);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task Middleware_MissingSignature_Returns400()
    {
        var request = new HttpRequestMessage(HttpMethod.Get, "/api/test");
        request.Headers.Add(HardenHmacConstants.TimestampHeader, "1700000000");

        var response = await _testClient!.SendAsync(request);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task Middleware_InvalidSignature_Returns401()
    {
        var timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var request = new HttpRequestMessage(HttpMethod.Get, "/api/test");
        request.Headers.Add(HardenHmacConstants.SignatureHeader,
            "0000000000000000000000000000000000000000000000000000000000000000");
        request.Headers.Add(HardenHmacConstants.TimestampHeader, timestamp.ToString());

        var response = await _testClient!.SendAsync(request);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task Middleware_ExpiredTimestamp_Returns401()
    {
        var oldTimestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds() - 60;
        var canonical = CanonicalStringBuilder.Build("GET", "/api/test", "", oldTimestamp, SignedHeadersConfig.None);
        var signature = HmacSigner.Sign(TestSecret, canonical);

        var request = new HttpRequestMessage(HttpMethod.Get, "/api/test");
        request.Headers.Add(HardenHmacConstants.SignatureHeader, signature);
        request.Headers.Add(HardenHmacConstants.TimestampHeader, oldTimestamp.ToString());

        var response = await _testClient!.SendAsync(request);

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task Middleware_PostWithBody_ValidatesCorrectly()
    {
        var timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var body = "{\"name\":\"test\"}";
        var canonical = CanonicalStringBuilder.Build("POST", "/api/test", body, timestamp, SignedHeadersConfig.None);
        var signature = HmacSigner.Sign(TestSecret, canonical);

        var request = new HttpRequestMessage(HttpMethod.Post, "/api/test")
        {
            Content = new StringContent(body, Encoding.UTF8, "application/json")
        };
        request.Headers.Add(HardenHmacConstants.SignatureHeader, signature);
        request.Headers.Add(HardenHmacConstants.TimestampHeader, timestamp.ToString());

        var response = await _testClient!.SendAsync(request);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }
}
