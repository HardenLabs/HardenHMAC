using System.Net;
using System.Text;
using FluentAssertions;
using HardenLabs.Hmac.AspNetCore;

namespace HardenLabs.Hmac.Tests;

public class ClientFactoryTests
{
    private const string OrdersSecret = "b3JkZXJzLXNlY3JldC1rZXktMzItYnl0ZXMhISEhIQ==";
    private const string PaymentsSecret = "cGF5bWVudHMtc2VjcmV0LWtleS0zMi1ieXRlcyEhISE=";

    private static HmacConfig CreateConfig()
    {
        return new HmacConfig
        {
            SignedHeaders = SignedHeadersConfig.None,
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
                    SignedHeaders = SignedHeadersConfig.None,
                },
            },
        };
    }

    [Fact]
    public void CreateClient_SetsBaseAddress()
    {
        var factory = new HardenHmacClientFactory(CreateConfig());

        var client = factory.CreateClient("order-service");

        client.BaseAddress.Should().NotBeNull();
        client.BaseAddress!.ToString().Should().Be("https://orders.example.com/");
    }

    [Fact]
    public void CreateClient_ThrowsForUnknownTarget()
    {
        var factory = new HardenHmacClientFactory(CreateConfig());

        var act = () => factory.CreateClient("nonexistent");

        act.Should().Throw<ArgumentException>()
            .WithMessage("*nonexistent*not configured*");
    }

    [Fact]
    public void CreateClient_SetsBaseAddressForTarget()
    {
        var config = new HmacConfig
        {
            SignedHeaders = SignedHeadersConfig.None,
            Targets = new Dictionary<string, HmacTargetConfig>
            {
                ["test-service"] = new HmacTargetConfig
                {
                    BaseUrl = "https://test.example.com",
                    SharedSecret = OrdersSecret,
                },
            },
        };

        var factory = new HardenHmacClientFactory(config);
        var client = factory.CreateClient("test-service");

        client.BaseAddress.Should().NotBeNull();
        client.BaseAddress!.Host.Should().Be("test.example.com");
    }

    [Fact]
    public async Task CreateClient_EndToEnd_SignAndVerify()
    {
        // Create a signing config for the client target
        var secret = OrdersSecret;
        var config = new HmacConfig
        {
            SignedHeaders = SignedHeadersConfig.None,
            Targets = new Dictionary<string, HmacTargetConfig>
            {
                ["test-service"] = new HmacTargetConfig
                {
                    BaseUrl = "https://test.example.com",
                    SharedSecret = secret,
                },
            },
        };

        // Use the ForTarget method to get a resolved config, then sign+verify manually
        var targetConfig = config.ForTarget("test-service");

        var signer = new HmacRequestSigner(targetConfig);
        var validator = new HmacValidator(targetConfig);

        var result = signer.Sign("GET", "/api/orders", "");

        var validation = validator.Validate(
            "GET", "/api/orders", "",
            result.Signature,
            result.Timestamp.ToString());

        validation.IsValid.Should().BeTrue();
    }

    [Fact]
    public void CreateClient_DifferentTargets_UseDifferentSecrets()
    {
        var config = CreateConfig();

        var ordersConfig = config.ForTarget("order-service");
        var paymentsConfig = config.ForTarget("payment-service");

        ordersConfig.SharedSecretBase64.Should().Be(OrdersSecret);
        paymentsConfig.SharedSecretBase64.Should().Be(PaymentsSecret);

        // Sign the same request with both — signatures should differ
        var ordersSigner = new HmacRequestSigner(ordersConfig);
        var paymentsSigner = new HmacRequestSigner(paymentsConfig);

        var ts = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var ordersResult = ordersSigner.Sign("GET", "/api/test", "", timestamp: ts);
        var paymentsResult = paymentsSigner.Sign("GET", "/api/test", "", timestamp: ts);

        ordersResult.Signature.Should().NotBe(paymentsResult.Signature);
    }

    [Fact]
    public void CreateClient_BaseUrlWithTrailingSlash_Handled()
    {
        var config = new HmacConfig
        {
            Targets = new Dictionary<string, HmacTargetConfig>
            {
                ["svc"] = new HmacTargetConfig
                {
                    BaseUrl = "https://svc.example.com/",
                    SharedSecret = OrdersSecret,
                },
            },
        };

        var factory = new HardenHmacClientFactory(config);
        var client = factory.CreateClient("svc");

        client.BaseAddress!.ToString().Should().Be("https://svc.example.com/");
    }
}
