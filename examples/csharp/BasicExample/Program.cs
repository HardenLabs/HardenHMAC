using HardenLabs.Hmac;
using HardenLabs.Hmac.AspNetCore;

// Shared secret (in production, load from environment/secrets manager)
var sharedSecret = Convert.ToBase64String("my-shared-secret-key-32-bytes!!"u8.ToArray());

var config = new HmacConfig
{
    SharedSecretBase64 = sharedSecret,
    SignedHeaders = SignedHeadersConfig.Default,
    TimestampToleranceSeconds = 30
};

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddHardenHmac(config);

// Register a named HttpClient that auto-signs requests
builder.Services.AddHardenHmacClient("signed-client", config)
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

// Client demo endpoint: signs and sends a request to itself
app.MapGet("/api/demo-client", async (IHttpClientFactory factory) =>
{
    var client = factory.CreateClient("signed-client");
    var response = await client.GetAsync("/api/hello");
    var content = await response.Content.ReadAsStringAsync();
    return Results.Ok(new { status = (int)response.StatusCode, body = content });
});

app.Run();
