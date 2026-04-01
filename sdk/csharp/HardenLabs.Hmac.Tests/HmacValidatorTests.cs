using FluentAssertions;

namespace HardenLabs.Hmac.Tests;

public class HmacValidatorTests
{
    private const string TestSecret = "dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24=";
    private const long BaseTimestamp = 1700000000;

    private readonly HmacValidator _validator = new(new HmacConfig
    {
        SharedSecretBase64 = TestSecret,
        SignedHeaders = SignedHeadersConfig.None,
        TimestampToleranceSeconds = 30
    });

    private string SignRequest(string method, string path, string body, long timestamp)
    {
        var canonical = CanonicalStringBuilder.Build(method, path, body, timestamp, SignedHeadersConfig.None);
        return HmacSigner.Sign(TestSecret, canonical);
    }

    [Fact]
    public void Validate_ValidRequest_ReturnsSuccess()
    {
        var sig = SignRequest("GET", "/api/test", "", BaseTimestamp);

        var result = _validator.Validate(
            "GET", "/api/test", "",
            sig, BaseTimestamp.ToString(),
            currentTimestamp: BaseTimestamp);

        result.IsValid.Should().BeTrue();
        result.ErrorType.Should().BeNull();
    }

    [Fact]
    public void Validate_MissingSignature_ReturnsFailure()
    {
        var result = _validator.Validate(
            "GET", "/api/test", "",
            null, BaseTimestamp.ToString(),
            currentTimestamp: BaseTimestamp);

        result.IsValid.Should().BeFalse();
        result.ErrorType.Should().Be("missing_signature");
    }

    [Fact]
    public void Validate_EmptySignature_ReturnsFailure()
    {
        var result = _validator.Validate(
            "GET", "/api/test", "",
            "", BaseTimestamp.ToString(),
            currentTimestamp: BaseTimestamp);

        result.IsValid.Should().BeFalse();
        result.ErrorType.Should().Be("missing_signature");
    }

    [Fact]
    public void Validate_MissingTimestamp_ReturnsFailure()
    {
        var result = _validator.Validate(
            "GET", "/api/test", "",
            "some-sig", null,
            currentTimestamp: BaseTimestamp);

        result.IsValid.Should().BeFalse();
        result.ErrorType.Should().Be("missing_timestamp");
    }

    [Fact]
    public void Validate_InvalidTimestamp_ReturnsFailure()
    {
        var result = _validator.Validate(
            "GET", "/api/test", "",
            "some-sig", "not-a-number",
            currentTimestamp: BaseTimestamp);

        result.IsValid.Should().BeFalse();
        result.ErrorType.Should().Be("invalid_timestamp");
    }

    [Fact]
    public void Validate_TimestampExpired_ReturnsFailure()
    {
        var sig = SignRequest("GET", "/api/test", "", BaseTimestamp);

        var result = _validator.Validate(
            "GET", "/api/test", "",
            sig, BaseTimestamp.ToString(),
            currentTimestamp: BaseTimestamp + 31); // 31 seconds past tolerance

        result.IsValid.Should().BeFalse();
        result.ErrorType.Should().Be("timestamp_expired");
    }

    [Fact]
    public void Validate_TimestampExactlyAtTolerance_Succeeds()
    {
        var sig = SignRequest("GET", "/api/test", "", BaseTimestamp);

        var result = _validator.Validate(
            "GET", "/api/test", "",
            sig, BaseTimestamp.ToString(),
            currentTimestamp: BaseTimestamp + 30); // Exactly at tolerance

        result.IsValid.Should().BeTrue();
    }

    [Fact]
    public void Validate_FutureTimestamp_ReturnsFailure()
    {
        var futureTs = BaseTimestamp + 100;
        var sig = SignRequest("GET", "/api/test", "", futureTs);

        var result = _validator.Validate(
            "GET", "/api/test", "",
            sig, futureTs.ToString(),
            currentTimestamp: BaseTimestamp); // 100 seconds in the future

        result.IsValid.Should().BeFalse();
        result.ErrorType.Should().Be("timestamp_out_of_range");
    }

    [Fact]
    public void Validate_InvalidSignature_ReturnsFailure()
    {
        var result = _validator.Validate(
            "GET", "/api/test", "",
            "0000000000000000000000000000000000000000000000000000000000000000",
            BaseTimestamp.ToString(),
            currentTimestamp: BaseTimestamp);

        result.IsValid.Should().BeFalse();
        result.ErrorType.Should().Be("signature_invalid");
    }

    [Fact]
    public void Validate_TamperedBody_ReturnsFailure()
    {
        var sig = SignRequest("POST", "/api/test", "{\"a\":1}", BaseTimestamp);

        var result = _validator.Validate(
            "POST", "/api/test", "{\"a\":2}",
            sig, BaseTimestamp.ToString(),
            currentTimestamp: BaseTimestamp);

        result.IsValid.Should().BeFalse();
        result.ErrorType.Should().Be("signature_invalid");
    }

    [Fact]
    public void Validate_TamperedPath_ReturnsFailure()
    {
        var sig = SignRequest("GET", "/api/test", "", BaseTimestamp);

        var result = _validator.Validate(
            "GET", "/api/other", "",
            sig, BaseTimestamp.ToString(),
            currentTimestamp: BaseTimestamp);

        result.IsValid.Should().BeFalse();
        result.ErrorType.Should().Be("signature_invalid");
    }

    [Fact]
    public void Validate_TamperedMethod_ReturnsFailure()
    {
        var sig = SignRequest("GET", "/api/test", "", BaseTimestamp);

        var result = _validator.Validate(
            "POST", "/api/test", "",
            sig, BaseTimestamp.ToString(),
            currentTimestamp: BaseTimestamp);

        result.IsValid.Should().BeFalse();
        result.ErrorType.Should().Be("signature_invalid");
    }

    [Fact]
    public void Validate_CustomTolerance_Honored()
    {
        var validator = new HmacValidator(new HmacConfig
        {
            SharedSecretBase64 = TestSecret,
            SignedHeaders = SignedHeadersConfig.None,
            TimestampToleranceSeconds = 5
        });

        var sig = SignRequest("GET", "/api/test", "", BaseTimestamp);

        // 6 seconds past a 5-second tolerance
        var result = validator.Validate(
            "GET", "/api/test", "",
            sig, BaseTimestamp.ToString(),
            currentTimestamp: BaseTimestamp + 6);

        result.IsValid.Should().BeFalse();
        result.ErrorType.Should().Be("timestamp_expired");
    }
}
