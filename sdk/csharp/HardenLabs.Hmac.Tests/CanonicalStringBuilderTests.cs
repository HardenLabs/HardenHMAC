using FluentAssertions;

namespace HardenLabs.Hmac.Tests;

public class CanonicalStringBuilderTests
{
    [Fact]
    public void Build_BasicGet_ProducesCorrectCanonicalString()
    {
        var result = CanonicalStringBuilder.Build("GET", "/api/users", "", 1700000000);
        result.Should().Be("GET\n/api/users\n\n\n1700000000");
    }

    [Fact]
    public void Build_PostWithBody_IncludesBody()
    {
        var body = "{\"name\":\"Alice\"}";
        var result = CanonicalStringBuilder.Build("POST", "/api/users", body, 1700000001);
        result.Should().Be($"POST\n/api/users\n\n{body}\n1700000001");
    }

    [Fact]
    public void Build_MethodIsUppercased()
    {
        var result = CanonicalStringBuilder.Build("get", "/api/users", "", 1700000000);
        result.Should().StartWith("GET\n");
    }

    [Fact]
    public void Build_PathIncludesQueryString()
    {
        var result = CanonicalStringBuilder.Build("GET", "/api/users?active=true", "", 1700000000);
        result.Should().Contain("/api/users?active=true");
    }

    [Fact]
    public void Build_RootPath_Works()
    {
        var result = CanonicalStringBuilder.Build("GET", "/", "", 1700000000);
        result.Should().Be("GET\n/\n\n\n1700000000");
    }

    [Fact]
    public void Build_NullBody_TreatedAsEmpty()
    {
        var result = CanonicalStringBuilder.Build("GET", "/", null!, 1700000000);
        result.Should().Be("GET\n/\n\n\n1700000000");
    }

    [Fact]
    public void Build_WithSignedHeaders_SortsAlphabetically()
    {
        var config = new SignedHeadersConfig
        {
            IncludeAuthorization = true,
            IncludeXHeaders = true
        };
        var headers = new Dictionary<string, string>
        {
            ["X-Request-Id"] = "abc",
            ["Authorization"] = "Bearer tok"
        };

        var result = CanonicalStringBuilder.Build("GET", "/", "", 1700000000, config, headers);

        // authorization comes before x-request-id alphabetically
        result.Should().Contain("authorization:Bearer tok\nx-request-id:abc");
    }

    [Fact]
    public void Build_ExcludesXHardenHeaders()
    {
        var config = new SignedHeadersConfig
        {
            IncludeXHeaders = true
        };
        var headers = new Dictionary<string, string>
        {
            ["X-Request-Id"] = "abc",
            ["X-Harden-Signature"] = "should-be-excluded",
            ["X-Harden-Timestamp"] = "12345"
        };

        var result = CanonicalStringBuilder.Build("GET", "/", "", 1700000000, config, headers);

        result.Should().Contain("x-request-id:abc");
        result.Should().NotContain("x-harden-");
    }

    [Fact]
    public void Build_ExcludeHeadersOverridesInclusion()
    {
        var config = new SignedHeadersConfig
        {
            IncludeXHeaders = true,
            ExcludeHeaders = ["X-Custom-B"]
        };
        var headers = new Dictionary<string, string>
        {
            ["X-Custom-A"] = "keep",
            ["X-Custom-B"] = "exclude"
        };

        var result = CanonicalStringBuilder.Build("GET", "/", "", 1700000000, config, headers);

        result.Should().Contain("x-custom-a:keep");
        result.Should().NotContain("x-custom-b");
    }

    [Fact]
    public void Build_HeaderValuesAreTrimmed()
    {
        var config = new SignedHeadersConfig
        {
            IncludeAuthorization = true
        };
        var headers = new Dictionary<string, string>
        {
            ["Authorization"] = "  Bearer tok  "
        };

        var result = CanonicalStringBuilder.Build("GET", "/", "", 1700000000, config, headers);

        result.Should().Contain("authorization:Bearer tok");
        result.Should().NotContain("  Bearer");
    }

    [Fact]
    public void Build_AdditionalHeaders_IncludesNonStandard()
    {
        var config = new SignedHeadersConfig
        {
            IncludeAuthorization = false,
            IncludeXHeaders = false,
            AdditionalHeaders = ["Content-Type"]
        };
        var headers = new Dictionary<string, string>
        {
            ["Content-Type"] = "application/json",
            ["Accept"] = "text/html"
        };

        var result = CanonicalStringBuilder.Build("GET", "/", "", 1700000000, config, headers);

        result.Should().Contain("content-type:application/json");
        result.Should().NotContain("accept");
    }

    [Fact]
    public void Build_NoMatchingHeaders_EmptySignedHeaders()
    {
        var config = SignedHeadersConfig.None;
        var headers = new Dictionary<string, string>
        {
            ["Authorization"] = "Bearer tok",
            ["X-Custom"] = "value"
        };

        var result = CanonicalStringBuilder.Build("GET", "/api", "", 1700000000, config, headers);

        // Should have two consecutive newlines for empty signed headers then empty body
        result.Should().Be("GET\n/api\n\n\n1700000000");
    }

    [Fact]
    public void BuildSignedHeaders_ReturnsHeaderNames()
    {
        var config = new SignedHeadersConfig
        {
            IncludeAuthorization = true,
            IncludeXHeaders = true
        };
        var headers = new Dictionary<string, string>
        {
            ["X-Request-Id"] = "abc",
            ["Authorization"] = "Bearer tok"
        };

        var (headerString, headerNames) = CanonicalStringBuilder.BuildSignedHeaders(config, headers);

        headerNames.Should().BeEquivalentTo(["authorization", "x-request-id"]);
        headerString.Should().Be("authorization:Bearer tok\nx-request-id:abc");
    }
}
