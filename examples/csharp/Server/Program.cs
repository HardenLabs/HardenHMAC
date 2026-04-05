using HardenLabs.Hmac;
using HardenLabs.Hmac.AspNetCore;

// In production, load from appsettings.json (see appsettings.example.json):
//   builder.Services.AddHardenHmac(builder.Configuration.GetSection("HardenHmac"));
//   or load from environment via .NET configuration binding (e.g. HardenHmac__SharedSecretBase64)
var ordersSecret = Convert.ToBase64String("orders-secret-key-32-bytes!!!!!"u8.ToArray());
var paymentsSecret = Convert.ToBase64String("payments-secret-key-32-bytes!!"u8.ToArray());
var defaultSecret = Convert.ToBase64String("my-shared-secret-key-32-bytes!!"u8.ToArray());

var config = new HmacConfig
{
    SharedSecretBase64 = defaultSecret, // fallback when no X-Harden-Client-Id header
    SignedHeaders = SignedHeadersConfig.Default,
    // For custom headers: new SignedHeadersConfig { IncludeAuthorization = true, IncludeXHeaders = true, AdditionalHeaders = ["X-Request-Id"], ExcludeHeaders = ["X-Debug"] }
    TimestampToleranceSeconds = 30,
    Clients = new Dictionary<string, HmacClientIdentity>
    {
        ["order-service"] = new HmacClientIdentity { SharedSecret = ordersSecret },
        ["payment-service"] = new HmacClientIdentity { SharedSecret = paymentsSecret },
    },
};

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddHardenHmac(config);

var app = builder.Build();

// Enable HMAC middleware (opt-in model: only endpoints with HmacValidateAttribute are validated)
app.UseRouting();
app.UseHardenHmac();

app.MapGet("/api/hello", () => Results.Ok(new { message = "Hello from HardenHMAC!" }))
    .WithMetadata(new HmacValidateAttribute());

app.MapPost("/api/echo", async (HttpRequest request) =>
{
    using var reader = new StreamReader(request.Body);
    var body = await reader.ReadToEndAsync();
    return Results.Ok(new { echo = body });
}).WithMetadata(new HmacValidateAttribute());

// Health endpoint — no HMAC validation required
app.MapGet("/health", () => Results.Ok(new { status = "ok" }));

// ── Option B: Multi-tenant server with secret resolver ──
// var tenantSecrets = new Dictionary<string, string>
// {
//     ["tenant-a"] = Convert.ToBase64String("tenant-a-secret-key-32-bytes!!"u8.ToArray()),
//     ["tenant-b"] = Convert.ToBase64String("tenant-b-secret-key-32-bytes!!"u8.ToArray()),
// };
// builder.Services.AddHardenHmac(config, async context =>
// {
//     var clientId = context.Request.Headers["X-Client-Id"].FirstOrDefault();
//     if (clientId != null && tenantSecrets.TryGetValue(clientId, out var secret))
//         return secret;
//     return null; // fall back to config.SharedSecretBase64
// });

app.Run();
