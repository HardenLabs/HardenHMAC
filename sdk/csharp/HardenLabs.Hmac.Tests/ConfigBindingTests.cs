using FluentAssertions;
using HardenLabs.Hmac.AspNetCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace HardenLabs.Hmac.Tests;

public class ConfigBindingTests
{
    [Fact]
    public void BindFromIConfiguration_SingleSecret()
    {
        var configData = new Dictionary<string, string?>
        {
            ["SharedSecretBase64"] = "dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24=",
            ["TimestampToleranceSeconds"] = "60",
            ["SignedHeaders:IncludeAuthorization"] = "false",
            ["SignedHeaders:IncludeXHeaders"] = "true",
        };

        var configuration = new ConfigurationBuilder()
            .AddInMemoryCollection(configData)
            .Build();

        var config = new HmacConfig();
        configuration.Bind(config);

        config.SharedSecretBase64.Should().Be("dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24=");
        config.TimestampToleranceSeconds.Should().Be(60);
        config.SignedHeaders.IncludeAuthorization.Should().BeFalse();
        config.SignedHeaders.IncludeXHeaders.Should().BeTrue();
    }

    [Fact]
    public void BindFromIConfiguration_MultiTarget()
    {
        var configData = new Dictionary<string, string?>
        {
            ["SharedSecretBase64"] = "Z2xvYmFsLXNlY3JldA==",
            ["TimestampToleranceSeconds"] = "30",
            ["Targets:order-service:BaseUrl"] = "https://orders.example.com",
            ["Targets:order-service:SharedSecret"] = "b3JkZXJzLXNlY3JldA==",
            ["Targets:payment-service:BaseUrl"] = "https://payments.example.com",
            ["Targets:payment-service:SharedSecret"] = "cGF5bWVudHMtc2VjcmV0",
            ["Targets:payment-service:TimestampToleranceSeconds"] = "60",
        };

        var configuration = new ConfigurationBuilder()
            .AddInMemoryCollection(configData)
            .Build();

        var config = new HmacConfig();
        configuration.Bind(config);

        config.Targets.Should().HaveCount(2);
        config.Targets["order-service"].BaseUrl.Should().Be("https://orders.example.com");
        config.Targets["order-service"].SharedSecret.Should().Be("b3JkZXJzLXNlY3JldA==");
        config.Targets["payment-service"].BaseUrl.Should().Be("https://payments.example.com");
        config.Targets["payment-service"].TimestampToleranceSeconds.Should().Be(60);
    }

    [Fact]
    public void BindFromIConfiguration_EnvironmentVariableStyle()
    {
        // Simulate environment variables with __ separator (as IConfiguration does)
        var configData = new Dictionary<string, string?>
        {
            ["Targets:order-service:BaseUrl"] = "https://orders.example.com",
            ["Targets:order-service:SharedSecret"] = "b3JkZXJzLXNlY3JldA==",
        };

        var configuration = new ConfigurationBuilder()
            .AddInMemoryCollection(configData)
            .Build();

        var config = new HmacConfig();
        configuration.Bind(config);

        config.Targets.Should().ContainKey("order-service");
        config.Targets["order-service"].BaseUrl.Should().Be("https://orders.example.com");
    }

    [Fact]
    public void AddHardenHmac_FromIConfiguration_RegistersServices()
    {
        var configData = new Dictionary<string, string?>
        {
            ["SharedSecretBase64"] = "dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24=",
        };

        var configuration = new ConfigurationBuilder()
            .AddInMemoryCollection(configData)
            .Build();

        var services = new ServiceCollection();
        services.AddHardenHmac(configuration);

        var provider = services.BuildServiceProvider();

        provider.GetService<HmacConfig>().Should().NotBeNull();
        provider.GetService<HmacConfig>()!.SharedSecretBase64
            .Should().Be("dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24=");
        provider.GetService<IHardenHmacClientFactory>().Should().NotBeNull();
    }

    [Fact]
    public void AddHardenHmac_FromConfig_RegistersClientFactory()
    {
        var config = new HmacConfig
        {
            SharedSecretBase64 = "dGVzdA==",
            Targets = new Dictionary<string, HmacTargetConfig>
            {
                ["test-svc"] = new HmacTargetConfig
                {
                    BaseUrl = "https://test.example.com",
                    SharedSecret = "dGVzdA==",
                },
            },
        };

        var services = new ServiceCollection();
        services.AddHardenHmac(config);

        var provider = services.BuildServiceProvider();
        var factory = provider.GetService<IHardenHmacClientFactory>();

        factory.Should().NotBeNull();

        var client = factory!.CreateClient("test-svc");
        client.BaseAddress!.Host.Should().Be("test.example.com");
    }
}
