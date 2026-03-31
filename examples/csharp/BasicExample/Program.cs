using System.Text;
using HardenLabs.Hmac;
using HardenLabs.Hmac.AspNetCore;

// ── Shared configuration ──
var sharedSecret = Convert.ToBase64String("my-shared-secret-key-32-bytes!!"u8.ToArray());
var ordersSecret = Convert.ToBase64String("orders-secret-key-32-bytes!!!!!"u8.ToArray());

var config = new HmacConfig
{
    SharedSecretBase64 = sharedSecret,
    TimestampToleranceSeconds = 30,
    SignedHeaders = SignedHeadersConfig.Default,
    Targets = new Dictionary<string, HmacTargetConfig>
    {
        ["order-service"] = new HmacTargetConfig
        {
            BaseUrl = "http://localhost:5099",
            SharedSecret = ordersSecret,
        },
    },
};

// ── Server ──
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddHardenHmac(config);
builder.WebHost.UseUrls("http://localhost:5099");

var app = builder.Build();
app.UseHardenHmac();

app.MapGet("/api/hello", () => Results.Ok(new { message = "Hello from HardenHMAC!" }));

app.MapPost("/api/echo", async (HttpRequest request) =>
{
    using var reader = new StreamReader(request.Body);
    var body = await reader.ReadToEndAsync();
    return Results.Ok(new { echo = body });
});

// Start server in background
await app.StartAsync();
Console.WriteLine("Server started on http://localhost:5099");

// ── Client ──
Console.WriteLine("\n=== Client: signing requests with IHardenHmacClientFactory ===");

var factory = app.Services.GetRequiredService<IHardenHmacClientFactory>();
var client = factory.CreateClient("order-service");

// GET request
Console.WriteLine("\nGET /api/hello");
var getResponse = await client.GetAsync("/api/hello");
var getBody = await getResponse.Content.ReadAsStringAsync();
Console.WriteLine($"  Status: {(int)getResponse.StatusCode}");
Console.WriteLine($"  Body:   {getBody}");

// POST request with body
Console.WriteLine("\nPOST /api/echo");
var postContent = new StringContent("{\"item\":\"widget\",\"qty\":5}", Encoding.UTF8, "application/json");
var postResponse = await client.PostAsync("/api/echo", postContent);
var postBody = await postResponse.Content.ReadAsStringAsync();
Console.WriteLine($"  Status: {(int)postResponse.StatusCode}");
Console.WriteLine($"  Body:   {postBody}");

// ── Manual signing (without factory) ──
Console.WriteLine("\n=== Client: manual signing with HmacRequestSigner ===");

var manualConfig = new HmacConfig
{
    SharedSecretBase64 = sharedSecret,
    SignedHeaders = SignedHeadersConfig.Default,
};

var signer = new HmacRequestSigner(manualConfig);
var result = signer.Sign("GET", "/api/hello", "");

using var manualClient = new HttpClient { BaseAddress = new Uri("http://localhost:5099") };
manualClient.DefaultRequestHeaders.Add("X-Harden-Signature", result.Signature);
manualClient.DefaultRequestHeaders.Add("X-Harden-Timestamp", result.Timestamp.ToString());

Console.WriteLine("\nGET /api/hello (manually signed)");
var manualResponse = await manualClient.GetAsync("/api/hello");
var manualBody = await manualResponse.Content.ReadAsStringAsync();
Console.WriteLine($"  Status: {(int)manualResponse.StatusCode}");
Console.WriteLine($"  Body:   {manualBody}");

await app.StopAsync();
Console.WriteLine("\nServer stopped.");
