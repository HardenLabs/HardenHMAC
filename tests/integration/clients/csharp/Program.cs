using System.Text;
using System.Text.Json;
using HardenLabs.Hmac;
using HardenLabs.Hmac.AspNetCore;

const string ClientId = "csharp-client";

// Load config.json - walk up from current directory
string? configPath = null;
var searchDir = Directory.GetCurrentDirectory();
while (searchDir != null)
{
    var candidate = Path.Combine(searchDir, "config.json");
    if (File.Exists(candidate))
    {
        configPath = candidate;
        break;
    }
    candidate = Path.Combine(searchDir, "tests", "integration", "config.json");
    if (File.Exists(candidate))
    {
        configPath = candidate;
        break;
    }
    searchDir = Path.GetDirectoryName(searchDir);
}

if (configPath is null)
{
    Console.Error.WriteLine("ERROR: config.json not found");
    return 1;
}

var json = File.ReadAllText(configPath);
var configDoc = JsonDocument.Parse(json);

// Get this client's shared secret
var mySecret = configDoc.RootElement
    .GetProperty("clients")
    .GetProperty(ClientId)
    .GetProperty("sharedSecret")
    .GetString()!;

// Get server ports
var ports = new Dictionary<string, int>();
foreach (var port in configDoc.RootElement.GetProperty("ports").EnumerateObject())
{
    ports[port.Name] = port.Value.GetInt32();
}

var results = new List<string>();
var servers = new[] { "csharp", "python", "typescript" };

foreach (var server in servers)
{
    if (!ports.TryGetValue(server, out var port))
        continue;

    var serverName = $"{server}-server";
    var baseUrl = $"http://localhost:{port}";

    // Create a client with HMAC signing for each server
    var hmacConfig = new HmacConfig
    {
        SharedSecretBase64 = mySecret,
    };

    var handler = new HardenHmacDelegatingHandler(hmacConfig, new HttpClientHandler(), clientId: ClientId);
    using var client = new HttpClient(handler)
    {
        BaseAddress = new Uri(baseUrl),
    };

    // GET /api/hello
    try
    {
        var response = await client.GetAsync("/api/hello");
        var status = (int)response.StatusCode;
        if (status == 200)
        {
            results.Add($"PASS {ClientId} -> {serverName} GET /api/hello ({status})");
        }
        else
        {
            var body = await response.Content.ReadAsStringAsync();
            results.Add($"FAIL {ClientId} -> {serverName} GET /api/hello ({status}): {body}");
        }
    }
    catch (Exception ex)
    {
        results.Add($"FAIL {ClientId} -> {serverName} GET /api/hello (ERR): {ex.Message}");
    }

    // POST /api/echo
    try
    {
        var postBody = JsonSerializer.Serialize(new { from = ClientId, test = "integration" });
        var content = new StringContent(postBody, Encoding.UTF8, "application/json");
        var response = await client.PostAsync("/api/echo", content);
        var status = (int)response.StatusCode;
        if (status == 200)
        {
            results.Add($"PASS {ClientId} -> {serverName} POST /api/echo ({status})");
        }
        else
        {
            var body = await response.Content.ReadAsStringAsync();
            results.Add($"FAIL {ClientId} -> {serverName} POST /api/echo ({status}): {body}");
        }
    }
    catch (Exception ex)
    {
        results.Add($"FAIL {ClientId} -> {serverName} POST /api/echo (ERR): {ex.Message}");
    }
}

foreach (var result in results)
{
    Console.WriteLine(result);
}

return results.Any(r => r.StartsWith("FAIL")) ? 1 : 0;
