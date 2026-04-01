# HardenLabs.Hmac

Cross-language HMAC-SHA256 request signing with a defined canonical string format. Guaranteed identical signatures across C#, Python, TypeScript, and Go.

## Installation

```bash
dotnet add package HardenLabs.Hmac
dotnet add package HardenLabs.Hmac.AspNetCore  # for middleware
```

## Quick Start — Server (ASP.NET Core)

```csharp
using HardenLabs.Hmac;
using HardenLabs.Hmac.AspNetCore;

var config = new HmacConfig
{
    SignedHeaders = SignedHeadersConfig.Default,
    TimestampToleranceSeconds = 30,
    Clients = new Dictionary<string, HmacClientIdentity>
    {
        ["order-service"] = new HmacClientIdentity { SharedSecret = "orders-base64-secret" },
        ["payment-service"] = new HmacClientIdentity { SharedSecret = "payments-base64-secret" },
    },
};

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddHardenHmac(config);

var app = builder.Build();
app.UseHardenHmac();

app.MapGet("/api/hello", () => Results.Ok(new { message = "Authenticated!" }));
app.Run();
```

## Quick Start — Client (HttpClient)

```csharp
using HardenLabs.Hmac;
using HardenLabs.Hmac.AspNetCore;

var config = new HmacConfig
{
    SignedHeaders = SignedHeadersConfig.Default,
    Targets = new Dictionary<string, HmacTargetConfig>
    {
        ["order-service"] = new HmacTargetConfig
        {
            BaseUrl = "https://orders.example.com",
            SharedSecret = "orders-base64-secret",
        },
    },
};

var factory = new HardenHmacClientFactory(config);
var client = factory.CreateClient("order-service"); // BaseAddress + signing pre-configured
var response = await client.GetAsync("/api/hello");  // automatically signed
```

## Configuration from appsettings.json

```json
{
  "HardenHmac": {
    "TimestampToleranceSeconds": 30,
    "Clients": {
      "order-service": { "SharedSecret": "orders-base64-secret" }
    },
    "Targets": {
      "order-service": {
        "BaseUrl": "https://orders.example.com",
        "SharedSecret": "orders-base64-secret"
      }
    }
  }
}
```

```csharp
builder.Services.AddHardenHmac(builder.Configuration.GetSection("HardenHmac"));
```

## Documentation

Full documentation, canonical string specification, and cross-language compatibility details: [github.com/HardenLabs/HardenHMAC](https://github.com/HardenLabs/HardenHMAC)

## License

[Apache License 2.0](https://github.com/HardenLabs/HardenHMAC/blob/main/LICENSE)
