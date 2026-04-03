using System.Net;
using System.Text;
using FluentAssertions;
using HardenLabs.Hmac.AspNetCore;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;

namespace HardenLabs.Hmac.Tests;

public class MiddlewareTests : IAsyncLifetime
{
    private const string TestSecret = "dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24=";
    private WebApplication? _app;
    private HttpClient? _testClient;

    public async Task InitializeAsync()
    {
        var config = new HmacConfig
        {
            SharedSecretBase64 = TestSecret,
            SignedHeaders = SignedHeadersConfig.None,
            TimestampToleranceSeconds = 30
        };

        var builder = WebApplication.CreateBuilder();
        builder.Services.AddHardenHmac(config);
        builder.Services.AddLogging();
        builder.WebHost.UseTestServer();

        _app = builder.Build();
        _app.UseRouting();
        _app.UseHardenHmac();

        // Protected endpoints
        _app.MapGet("/api/test", () => "OK").WithMetadata(new HmacValidateAttribute());
        _app.MapPost("/api/test", () => "OK").WithMetadata(new HmacValidateAttribute());

        // Unprotected endpoint
        _app.MapGet("/health", () => "OK");

        // Protected endpoint with skip override
        _app.MapGet("/api/skip", () => "OK")
            .WithMetadata(new HmacValidateAttribute())
            .WithMetadata(new SkipHmacValidateAttribute());

        await _app.StartAsync();
        _testClient = _app.GetTestClient();
    }

    public async Task DisposeAsync()
    {
        _testClient?.Dispose();
        if (_app is not null)
        {
            await _app.StopAsync();
            await _app.DisposeAsync();
        }
    }

    [Fact]
    public async Task ValidSignature_OnProtectedEndpoint_Returns200()
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
    public async Task MissingSignature_OnProtectedEndpoint_Returns400()
    {
        var request = new HttpRequestMessage(HttpMethod.Get, "/api/test");
        request.Headers.Add(HardenHmacConstants.TimestampHeader, "1700000000");

        var response = await _testClient!.SendAsync(request);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task InvalidSignature_OnProtectedEndpoint_Returns401()
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
    public async Task ExpiredTimestamp_OnProtectedEndpoint_Returns401()
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
    public async Task PostWithBody_OnProtectedEndpoint_ValidatesCorrectly()
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

    [Fact]
    public async Task NoSignature_OnUnprotectedEndpoint_Returns200()
    {
        var request = new HttpRequestMessage(HttpMethod.Get, "/health");

        var response = await _testClient!.SendAsync(request);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task SkipAttribute_OnProtectedEndpoint_SkipsValidation()
    {
        var request = new HttpRequestMessage(HttpMethod.Get, "/api/skip");

        var response = await _testClient!.SendAsync(request);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }
}
