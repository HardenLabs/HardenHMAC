using System.Net;
using System.Text;
using FluentAssertions;
using HardenLabs.Hmac.AspNetCore;

namespace HardenLabs.Hmac.Tests;

public class DelegatingHandlerTests
{
    private const string TestSecret = "dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24=";

    [Fact]
    public async Task Handler_AddsSignatureHeaders()
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
            SignedHeaders = SignedHeadersConfig.None
        };

        var handler = new HardenHmacDelegatingHandler(config, mockHandler);
        var client = new HttpClient(handler) { BaseAddress = new Uri("http://localhost") };

        await client.GetAsync("/api/test");

        capturedRequest.Should().NotBeNull();
        capturedRequest!.Headers.Contains(HardenHmacConstants.SignatureHeader).Should().BeTrue();
        capturedRequest.Headers.Contains(HardenHmacConstants.TimestampHeader).Should().BeTrue();

        var sig = capturedRequest.Headers.GetValues(HardenHmacConstants.SignatureHeader).First();
        sig.Should().HaveLength(64);
        sig.Should().MatchRegex("^[0-9a-f]{64}$");
    }

    [Fact]
    public async Task Handler_SignatureIsVerifiable()
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
            SignedHeaders = SignedHeadersConfig.None
        };

        var handler = new HardenHmacDelegatingHandler(config, mockHandler);
        var client = new HttpClient(handler) { BaseAddress = new Uri("http://localhost") };

        var body = "{\"test\":true}";
        await client.PostAsync("/api/data", new StringContent(body, Encoding.UTF8, "application/json"));

        capturedRequest.Should().NotBeNull();
        var sig = capturedRequest!.Headers.GetValues(HardenHmacConstants.SignatureHeader).First();
        var ts = capturedRequest.Headers.GetValues(HardenHmacConstants.TimestampHeader).First();

        var canonical = CanonicalStringBuilder.Build(
            "POST", "/api/data", body, long.Parse(ts), SignedHeadersConfig.None);
        HmacSigner.Verify(TestSecret, canonical, sig).Should().BeTrue();
    }

    [Fact]
    public async Task Handler_IncludesSignedHeadersHeader_WhenHeadersSigned()
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
            SignedHeaders = new SignedHeadersConfig
            {
                IncludeAuthorization = true,
                IncludeXHeaders = false
            }
        };

        var handler = new HardenHmacDelegatingHandler(config, mockHandler);
        var client = new HttpClient(handler) { BaseAddress = new Uri("http://localhost") };

        var request = new HttpRequestMessage(HttpMethod.Get, "/api/test");
        request.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", "token123");
        await client.SendAsync(request);

        capturedRequest.Should().NotBeNull();
        capturedRequest!.Headers.Contains(HardenHmacConstants.SignedHeadersHeader).Should().BeTrue();
        var signedHeaders = capturedRequest.Headers.GetValues(HardenHmacConstants.SignedHeadersHeader).First();
        signedHeaders.Should().Contain("authorization");
    }

    [Fact]
    public async Task Handler_NoSignedHeadersHeader_WhenNoHeadersSigned()
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
            SignedHeaders = SignedHeadersConfig.None
        };

        var handler = new HardenHmacDelegatingHandler(config, mockHandler);
        var client = new HttpClient(handler) { BaseAddress = new Uri("http://localhost") };

        await client.GetAsync("/api/test");

        capturedRequest.Should().NotBeNull();
        capturedRequest!.Headers.Contains(HardenHmacConstants.SignedHeadersHeader).Should().BeFalse();
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
