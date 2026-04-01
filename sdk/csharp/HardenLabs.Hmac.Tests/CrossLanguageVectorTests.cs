using System.Text.Json;
using System.Text.Json.Serialization;
using FluentAssertions;

namespace HardenLabs.Hmac.Tests;

public class CrossLanguageVectorTests
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true
    };

    private static TestVectorFile LoadVectors()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "test-vectors.json");
        var json = File.ReadAllText(path);
        return JsonSerializer.Deserialize<TestVectorFile>(json, JsonOptions)
            ?? throw new InvalidOperationException("Failed to deserialize test vectors.");
    }

    [Fact]
    public void AllVectors_CanonicalStringMatchesExpected()
    {
        var file = LoadVectors();

        foreach (var vector in file.Vectors)
        {
            var config = MapConfig(vector.SignedHeadersConfig);
            var headers = vector.RequestHeaders.ToDictionary(
                kvp => kvp.Key,
                kvp => kvp.Value);

            var canonical = CanonicalStringBuilder.Build(
                vector.Method,
                vector.Path,
                vector.Body,
                vector.Timestamp,
                config,
                headers);

            canonical.Should().Be(vector.ExpectedCanonicalString,
                $"Vector '{vector.Id}' canonical string mismatch");
        }
    }

    [Fact]
    public void AllVectors_SignatureMatchesExpected()
    {
        var file = LoadVectors();

        foreach (var vector in file.Vectors)
        {
            var config = MapConfig(vector.SignedHeadersConfig);
            var headers = vector.RequestHeaders.ToDictionary(
                kvp => kvp.Key,
                kvp => kvp.Value);

            var canonical = CanonicalStringBuilder.Build(
                vector.Method,
                vector.Path,
                vector.Body,
                vector.Timestamp,
                config,
                headers);

            var signature = HmacSigner.Sign(vector.SharedSecretBase64, canonical);

            signature.Should().Be(vector.ExpectedSignature,
                $"Vector '{vector.Id}' signature mismatch");
        }
    }

    [Fact]
    public void AllVectors_VerifyReturnsTrue()
    {
        var file = LoadVectors();

        foreach (var vector in file.Vectors)
        {
            var verified = HmacSigner.Verify(
                vector.SharedSecretBase64,
                vector.ExpectedCanonicalString,
                vector.ExpectedSignature);

            verified.Should().BeTrue($"Vector '{vector.Id}' should verify successfully");
        }
    }

    private static SignedHeadersConfig MapConfig(TestSignedHeadersConfig config)
    {
        return new SignedHeadersConfig
        {
            IncludeAuthorization = config.IncludeAuthorization,
            IncludeXHeaders = config.IncludeXHeaders,
            AdditionalHeaders = config.AdditionalHeaders,
            ExcludeHeaders = config.ExcludeHeaders
        };
    }

    private sealed class TestVectorFile
    {
        public string Version { get; set; } = "";
        public string Description { get; set; } = "";
        public List<TestVector> Vectors { get; set; } = [];
    }

    private sealed class TestVector
    {
        public string Id { get; set; } = "";
        public string Description { get; set; } = "";
        public string Method { get; set; } = "";
        public string Path { get; set; } = "";
        public string Body { get; set; } = "";
        public long Timestamp { get; set; }
        public TestSignedHeadersConfig SignedHeadersConfig { get; set; } = new();
        public Dictionary<string, string> RequestHeaders { get; set; } = [];
        public string SharedSecretBase64 { get; set; } = "";
        public string ExpectedCanonicalString { get; set; } = "";
        public string ExpectedSignature { get; set; } = "";
    }

    private sealed class TestSignedHeadersConfig
    {
        public bool IncludeAuthorization { get; set; }
        public bool IncludeXHeaders { get; set; }
        public List<string> AdditionalHeaders { get; set; } = [];
        public List<string> ExcludeHeaders { get; set; } = [];
    }
}
