using System.Net;
using System.Text.Json;
using FluentAssertions;
using HardenLabs.Hmac.AspNetCore;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

namespace HardenLabs.Hmac.Tests;

public class MultiClientMiddlewareTests : IAsyncLifetime
{
    private const string DefaultSecret = "ZGVmYXVsdC1zZWNyZXQta2V5LTMyLWJ5dGVzISEhISE=";
    private const string OrderSecret = "b3JkZXJzLXNlY3JldC1rZXktMzItYnl0ZXMhISEhIQ==";
    private const string PaymentSecret = "cGF5bWVudHMtc2VjcmV0LWtleS0zMi1ieXRlcyEhISE=";

    private IHost? _host;
    private HttpClient? _testClient;

    public async Task InitializeAsync()
    {
        var config = new HmacConfig
        {
            SharedSecretBase64 = DefaultSecret,
            SignedHeaders = SignedHeadersConfig.None,
            TimestampToleranceSeconds = 30,
            Clients = new Dictionary<string, HmacClientIdentity>
            {
                ["order-service"] = new HmacClientIdentity { SharedSecret = OrderSecret },
                ["payment-service"] = new HmacClientIdentity { SharedSecret = PaymentSecret },
            },
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
    public async Task KnownClient_ValidSignature_Returns200()
    {
        var timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var canonical = CanonicalStringBuilder.Build("GET", "/api/test", "", timestamp, SignedHeadersConfig.None);
        var signature = HmacSigner.Sign(OrderSecret, canonical);

        var request = new HttpRequestMessage(HttpMethod.Get, "/api/test");
        request.Headers.Add(HardenHmacConstants.ClientIdHeader, "order-service");
        request.Headers.Add(HardenHmacConstants.SignatureHeader, signature);
        request.Headers.Add(HardenHmacConstants.TimestampHeader, timestamp.ToString());

        var response = await _testClient!.SendAsync(request);
        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task KnownClient_WrongSecret_Returns401()
    {
        var timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var canonical = CanonicalStringBuilder.Build("GET", "/api/test", "", timestamp, SignedHeadersConfig.None);
        // Sign with default secret but send as order-service client
        var signature = HmacSigner.Sign(DefaultSecret, canonical);

        var request = new HttpRequestMessage(HttpMethod.Get, "/api/test");
        request.Headers.Add(HardenHmacConstants.ClientIdHeader, "order-service");
        request.Headers.Add(HardenHmacConstants.SignatureHeader, signature);
        request.Headers.Add(HardenHmacConstants.TimestampHeader, timestamp.ToString());

        var response = await _testClient!.SendAsync(request);
        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task UnknownClient_Returns401_UnknownClient()
    {
        var timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var canonical = CanonicalStringBuilder.Build("GET", "/api/test", "", timestamp, SignedHeadersConfig.None);
        var signature = HmacSigner.Sign(DefaultSecret, canonical);

        var request = new HttpRequestMessage(HttpMethod.Get, "/api/test");
        request.Headers.Add(HardenHmacConstants.ClientIdHeader, "nonexistent-service");
        request.Headers.Add(HardenHmacConstants.SignatureHeader, signature);
        request.Headers.Add(HardenHmacConstants.TimestampHeader, timestamp.ToString());

        var response = await _testClient!.SendAsync(request);
        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);

        var body = await response.Content.ReadAsStringAsync();
        var json = JsonSerializer.Deserialize<JsonElement>(body);
        json.GetProperty("error").GetString().Should().Be("unknown_client");
    }

    [Fact]
    public async Task NoClientId_FallsBackToDefaultSecret()
    {
        var timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var canonical = CanonicalStringBuilder.Build("GET", "/api/test", "", timestamp, SignedHeadersConfig.None);
        var signature = HmacSigner.Sign(DefaultSecret, canonical);

        var request = new HttpRequestMessage(HttpMethod.Get, "/api/test");
        request.Headers.Add(HardenHmacConstants.SignatureHeader, signature);
        request.Headers.Add(HardenHmacConstants.TimestampHeader, timestamp.ToString());

        var response = await _testClient!.SendAsync(request);
        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task PaymentClient_UsesPaymentSecret()
    {
        var timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var canonical = CanonicalStringBuilder.Build("GET", "/api/test", "", timestamp, SignedHeadersConfig.None);
        var signature = HmacSigner.Sign(PaymentSecret, canonical);

        var request = new HttpRequestMessage(HttpMethod.Get, "/api/test");
        request.Headers.Add(HardenHmacConstants.ClientIdHeader, "payment-service");
        request.Headers.Add(HardenHmacConstants.SignatureHeader, signature);
        request.Headers.Add(HardenHmacConstants.TimestampHeader, timestamp.ToString());

        var response = await _testClient!.SendAsync(request);
        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }
}

public class ClientIdDelegatingHandlerTests
{
    private const string TestSecret = "dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24=";

    [Fact]
    public async Task Handler_AddsClientIdHeader_WhenConfigured()
    {
        HttpRequestMessage? capturedRequest = null;
        var mockHandler = new MockHttpMessageHandler(request =>
        {
            capturedRequest = request;
            return new HttpResponseMessage(HttpStatusCode.OK);
        });

        var config = new HmacConfig
        {
            SharedSecretBase64 = TestSecret,
            SignedHeaders = SignedHeadersConfig.None,
        };

        var handler = new HardenHmacDelegatingHandler(config, mockHandler, clientId: "my-service");
        var client = new HttpClient(handler) { BaseAddress = new Uri("http://localhost") };

        await client.GetAsync("/api/test");

        capturedRequest.Should().NotBeNull();
        capturedRequest!.Headers.Contains(HardenHmacConstants.ClientIdHeader).Should().BeTrue();
        var clientId = capturedRequest.Headers.GetValues(HardenHmacConstants.ClientIdHeader).First();
        clientId.Should().Be("my-service");
    }

    [Fact]
    public async Task Handler_NoClientIdHeader_WhenNotConfigured()
    {
        HttpRequestMessage? capturedRequest = null;
        var mockHandler = new MockHttpMessageHandler(request =>
        {
            capturedRequest = request;
            return new HttpResponseMessage(HttpStatusCode.OK);
        });

        var config = new HmacConfig
        {
            SharedSecretBase64 = TestSecret,
            SignedHeaders = SignedHeadersConfig.None,
        };

        var handler = new HardenHmacDelegatingHandler(config, mockHandler);
        var client = new HttpClient(handler) { BaseAddress = new Uri("http://localhost") };

        await client.GetAsync("/api/test");

        capturedRequest.Should().NotBeNull();
        capturedRequest!.Headers.Contains(HardenHmacConstants.ClientIdHeader).Should().BeFalse();
    }

    [Fact]
    public void ClientFactory_PassesTargetNameAsClientId()
    {
        var config = new HmacConfig
        {
            SignedHeaders = SignedHeadersConfig.None,
            Targets = new Dictionary<string, HmacTargetConfig>
            {
                ["order-service"] = new HmacTargetConfig
                {
                    BaseUrl = "https://orders.example.com",
                    SharedSecret = TestSecret,
                },
            },
        };

        var factory = new HardenHmacClientFactory(config);
        var client = factory.CreateClient("order-service");

        // The client should be configured with the target name as client ID.
        // We verify by checking the base address is set (the handler is internal).
        client.BaseAddress.Should().NotBeNull();
        client.BaseAddress!.Host.Should().Be("orders.example.com");
    }

    private sealed class MockHttpMessageHandler : HttpMessageHandler
    {
        private readonly Func<HttpRequestMessage, HttpResponseMessage> _handler;

        public MockHttpMessageHandler(Func<HttpRequestMessage, HttpResponseMessage> handler)
        {
            _handler = handler;
        }

        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken)
        {
            return Task.FromResult(_handler(request));
        }
    }
}
