using System.Text.Json;
using HardenLabs.Hmac;
using HardenLabs.Hmac.AspNetCore;

// Load config.json
var configPath = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "config.json");
if (!File.Exists(configPath))
{
    // Try relative to working directory
    configPath = Path.Combine(Directory.GetCurrentDirectory(), "..", "..", "config.json");
}
if (!File.Exists(configPath))
{
    configPath = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "tests", "integration", "config.json"));
}

// Walk up from current dir to find config.json
var searchDir = Directory.GetCurrentDirectory();
while (searchDir != null)
{
    var candidate = Path.Combine(searchDir, "config.json");
    if (File.Exists(candidate))
    {
        configPath = candidate;
        break;
    }
    // Also check tests/integration/config.json from repo root
    candidate = Path.Combine(searchDir, "tests", "integration", "config.json");
    if (File.Exists(candidate))
    {
        configPath = candidate;
        break;
    }
    searchDir = Path.GetDirectoryName(searchDir);
}

var json = File.ReadAllText(configPath);
var configDoc = JsonDocument.Parse(json);

var port = configDoc.RootElement.GetProperty("ports").GetProperty("csharp").GetInt32();

// Build Clients dictionary from config
var clientsDict = new Dictionary<string, HmacClientIdentity>();
foreach (var client in configDoc.RootElement.GetProperty("clients").EnumerateObject())
{
    var secret = client.Value.GetProperty("sharedSecret").GetString()!;
    clientsDict[client.Name] = new HmacClientIdentity { SharedSecret = secret };
}

var hmacConfig = new HmacConfig
{
    Clients = clientsDict,
};

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddHardenHmac(hmacConfig);

var app = builder.Build();
app.UseHardenHmac();

app.MapGet("/api/hello", () => Results.Json(new { message = "hello from csharp" }));

app.MapPost("/api/echo", async (HttpRequest request) =>
{
    using var reader = new StreamReader(request.Body);
    var body = await reader.ReadToEndAsync();

    object? parsed;
    try
    {
        parsed = JsonSerializer.Deserialize<object>(body);
    }
    catch
    {
        parsed = body;
    }

    return Results.Json(new { echo = parsed, language = "csharp" });
});

app.Run($"http://0.0.0.0:{port}");
