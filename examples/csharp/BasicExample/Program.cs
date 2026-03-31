using HardenLabs.Hmac;
using HardenLabs.Hmac.AspNetCore;

// ── Option A: Single-secret mode (backwards-compatible) ──
var sharedSecret = Convert.ToBase64String("my-shared-secret-key-32-bytes!!"u8.ToArray());

var singleConfig = new HmacConfig
{
    SharedSecretBase64 = sharedSecret,
    SignedHeaders = SignedHeadersConfig.Default,
    TimestampToleranceSeconds = 30
};

// ── Option B: Multi-target mode ──
var ordersSecret = Convert.ToBase64String("orders-secret-key-32-bytes!!!!!"u8.ToArray());
var paymentsSecret = Convert.ToBase64String("payments-secret-key-32-bytes!!!"u8.ToArray());

var multiConfig = new HmacConfig
{
    SharedSecretBase64 = sharedSecret, // server-side default
    TimestampToleranceSeconds = 30,
    Targets = new Dictionary<string, HmacTargetConfig>
    {
        ["order-service"] = new HmacTargetConfig
        {
            BaseUrl = "http://localhost:5001",
            SharedSecret = ordersSecret,
        },
        ["payment-service"] = new HmacTargetConfig
        {
            BaseUrl = "http://localhost:5002",
            SharedSecret = paymentsSecret,
            TimestampToleranceSeconds = 60,
        },
    },
};

var builder = WebApplication.CreateBuilder(args);

// Register multi-target config (also works with single-secret singleConfig)
builder.Services.AddHardenHmac(multiConfig);

// Also register a legacy named HttpClient (still works)
builder.Services.AddHardenHmacClient("legacy-client", singleConfig)
    .ConfigureHttpClient(c => c.BaseAddress = new Uri("http://localhost:5000"));

var app = builder.Build();

// Server: validate incoming requests
app.UseHardenHmac();

app.MapGet("/api/hello", () => Results.Ok(new { message = "Hello from HardenHMAC!" }));

app.MapPost("/api/echo", async (HttpRequest request) =>
{
    using var reader = new StreamReader(request.Body);
    var body = await reader.ReadToEndAsync();
    return Results.Ok(new { echo = body });
});

// Client demo: use the factory to create per-target clients
app.MapGet("/api/demo-factory", (IHardenHmacClientFactory factory) =>
{
    // factory.CreateClient("order-service") returns HttpClient
    // with BaseAddress set to http://localhost:5001 and auto-signing
    var orderClient = factory.CreateClient("order-service");
    return Results.Ok(new
    {
        ordersBaseUrl = orderClient.BaseAddress?.ToString(),
        message = "Clients created via IHardenHmacClientFactory auto-sign requests",
    });
});

// Legacy named client demo
app.MapGet("/api/demo-legacy", async (IHttpClientFactory httpFactory) =>
{
    var client = httpFactory.CreateClient("legacy-client");
    var response = await client.GetAsync("/api/hello");
    var content = await response.Content.ReadAsStringAsync();
    return Results.Ok(new { status = (int)response.StatusCode, body = content });
});

app.Run();
