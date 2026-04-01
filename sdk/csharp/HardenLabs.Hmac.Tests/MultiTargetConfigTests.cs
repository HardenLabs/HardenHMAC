using FluentAssertions;

namespace HardenLabs.Hmac.Tests;

public class MultiTargetConfigTests
{
    private const string GlobalSecret = "Z2xvYmFsLXNlY3JldC1rZXktMzItYnl0ZXMhISEhIQ==";
    private const string OrdersSecret = "b3JkZXJzLXNlY3JldC1rZXktMzItYnl0ZXMhISEhIQ==";
    private const string PaymentsSecret = "cGF5bWVudHMtc2VjcmV0LWtleS0zMi1ieXRlcyEhISE=";

    private static HmacConfig CreateMultiTargetConfig()
    {
        return new HmacConfig
        {
            SharedSecretBase64 = GlobalSecret,
            TimestampToleranceSeconds = 30,
            SignedHeaders = SignedHeadersConfig.Default,
            Targets = new Dictionary<string, HmacTargetConfig>
            {
                ["order-service"] = new HmacTargetConfig
                {
                    BaseUrl = "https://orders.example.com",
                    SharedSecret = OrdersSecret,
                },
                ["payment-service"] = new HmacTargetConfig
                {
                    BaseUrl = "https://payments.example.com",
                    SharedSecret = PaymentsSecret,
                    TimestampToleranceSeconds = 60,
                    SignedHeaders = SignedHeadersConfig.None,
                },
                ["fallback-service"] = new HmacTargetConfig
                {
                    BaseUrl = "https://fallback.example.com",
                    // No SharedSecret — should fall back to global
                },
            },
        };
    }

    [Fact]
    public void GetEffectiveSecret_ReturnsTargetSecret_WhenSet()
    {
        var config = CreateMultiTargetConfig();

        config.GetEffectiveSecret("order-service").Should().Be(OrdersSecret);
        config.GetEffectiveSecret("payment-service").Should().Be(PaymentsSecret);
    }

    [Fact]
    public void GetEffectiveSecret_FallsBackToGlobal_WhenTargetSecretEmpty()
    {
        var config = CreateMultiTargetConfig();

        config.GetEffectiveSecret("fallback-service").Should().Be(GlobalSecret);
    }

    [Fact]
    public void GetEffectiveSecret_ThrowsForUnknownTarget()
    {
        var config = CreateMultiTargetConfig();

        var act = () => config.GetEffectiveSecret("nonexistent");

        act.Should().Throw<ArgumentException>()
            .WithMessage("*nonexistent*not configured*");
    }

    [Fact]
    public void GetEffectiveSignedHeaders_ReturnsTargetOverride_WhenSet()
    {
        var config = CreateMultiTargetConfig();

        var paymentHeaders = config.GetEffectiveSignedHeaders("payment-service");

        paymentHeaders.IncludeAuthorization.Should().BeFalse();
        paymentHeaders.IncludeXHeaders.Should().BeFalse();
    }

    [Fact]
    public void GetEffectiveSignedHeaders_ReturnsGlobal_WhenNotOverridden()
    {
        var config = CreateMultiTargetConfig();

        var orderHeaders = config.GetEffectiveSignedHeaders("order-service");

        orderHeaders.IncludeAuthorization.Should().BeTrue();
        orderHeaders.IncludeXHeaders.Should().BeTrue();
    }

    [Fact]
    public void GetEffectiveTimestampTolerance_ReturnsTargetOverride_WhenSet()
    {
        var config = CreateMultiTargetConfig();

        config.GetEffectiveTimestampTolerance("payment-service").Should().Be(60);
    }

    [Fact]
    public void GetEffectiveTimestampTolerance_ReturnsGlobal_WhenNotOverridden()
    {
        var config = CreateMultiTargetConfig();

        config.GetEffectiveTimestampTolerance("order-service").Should().Be(30);
    }

    [Fact]
    public void ForTarget_ReturnsResolvedConfig()
    {
        var config = CreateMultiTargetConfig();

        var paymentConfig = config.ForTarget("payment-service");

        paymentConfig.SharedSecretBase64.Should().Be(PaymentsSecret);
        paymentConfig.TimestampToleranceSeconds.Should().Be(60);
        paymentConfig.SignedHeaders.IncludeAuthorization.Should().BeFalse();
    }

    [Fact]
    public void ForTarget_FallbackTarget_UsesGlobalDefaults()
    {
        var config = CreateMultiTargetConfig();

        var fallbackConfig = config.ForTarget("fallback-service");

        fallbackConfig.SharedSecretBase64.Should().Be(GlobalSecret);
        fallbackConfig.TimestampToleranceSeconds.Should().Be(30);
        fallbackConfig.SignedHeaders.IncludeAuthorization.Should().BeTrue();
    }

    [Fact]
    public void BackwardsCompatibility_SingleSecretMode_Works()
    {
        var config = new HmacConfig
        {
            SharedSecretBase64 = GlobalSecret,
        };

        config.SharedSecretBase64.Should().Be(GlobalSecret);
        config.Targets.Should().BeEmpty();
        config.SignedHeaders.IncludeAuthorization.Should().BeTrue();
        config.TimestampToleranceSeconds.Should().Be(30);
    }

    [Fact]
    public void BackwardsCompatibility_SingleSecretMode_SignAndVerify()
    {
        var config = new HmacConfig
        {
            SharedSecretBase64 = GlobalSecret,
            SignedHeaders = SignedHeadersConfig.None,
        };

        var signer = new HmacRequestSigner(config);
        var validator = new HmacValidator(config);

        var result = signer.Sign("GET", "/api/test", "");

        var validation = validator.Validate(
            "GET", "/api/test", "",
            result.Signature,
            result.Timestamp.ToString());

        validation.IsValid.Should().BeTrue();
    }
}
