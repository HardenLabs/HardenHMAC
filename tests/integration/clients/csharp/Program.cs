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
var servers = new[] { "csharp", "python", "typescript", "go" };

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
    catch (HttpRequestException ex) when (ex.InnerException is System.Net.Sockets.SocketException)
    {
        results.Add($"SKIP {ClientId} -> {serverName} GET /api/hello (server not running)");
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
    catch (HttpRequestException ex) when (ex.InnerException is System.Net.Sockets.SocketException)
    {
        results.Add($"SKIP {ClientId} -> {serverName} POST /api/echo (server not running)");
    }
    catch (Exception ex)
    {
        results.Add($"FAIL {ClientId} -> {serverName} POST /api/echo (ERR): {ex.Message}");
    }

    // GET /health — unprotected, no HMAC required (use plain HttpClient)
    try
    {
        using var plainClient = new HttpClient { BaseAddress = new Uri(baseUrl) };
        var response = await plainClient.GetAsync("/health");
        var status = (int)response.StatusCode;
        if (status == 200)
        {
            results.Add($"PASS {ClientId} -> {serverName} GET /health ({status})");
        }
        else
        {
            var body = await response.Content.ReadAsStringAsync();
            results.Add($"FAIL {ClientId} -> {serverName} GET /health ({status}): {body}");
        }
    }
    catch (HttpRequestException ex) when (ex.InnerException is System.Net.Sockets.SocketException)
    {
        results.Add($"SKIP {ClientId} -> {serverName} GET /health (server not running)");
    }
    catch (Exception ex)
    {
        results.Add($"FAIL {ClientId} -> {serverName} GET /health (ERR): {ex.Message}");
    }

    // GET /api/hello — protected, WITHOUT HMAC headers (expect 4xx rejection)
    try
    {
        using var plainClient = new HttpClient { BaseAddress = new Uri(baseUrl) };
        var response = await plainClient.GetAsync("/api/hello");
        var status = (int)response.StatusCode;
        if (status >= 400 && status < 500)
        {
            results.Add($"PASS {ClientId}/nohmac -> {serverName} GET /api/hello ({status})");
        }
        else
        {
            var body = await response.Content.ReadAsStringAsync();
            results.Add($"FAIL {ClientId}/nohmac -> {serverName} GET /api/hello (expected 4xx, got {status}): {body}");
        }
    }
    catch (HttpRequestException ex) when (ex.InnerException is System.Net.Sockets.SocketException)
    {
        results.Add($"SKIP {ClientId}/nohmac -> {serverName} GET /api/hello (server not running)");
    }
    catch (Exception ex)
    {
        results.Add($"FAIL {ClientId}/nohmac -> {serverName} GET /api/hello (ERR): {ex.Message}");
    }
}

// ============================================================
// Shared-secret server tests
// ============================================================
var sharedSecret = configDoc.RootElement.GetProperty("sharedSecret").GetString()!;
var sharedPorts = new Dictionary<string, int>();
foreach (var port in configDoc.RootElement.GetProperty("sharedPorts").EnumerateObject())
{
    sharedPorts[port.Name] = port.Value.GetInt32();
}

foreach (var server in servers)
{
    if (!sharedPorts.TryGetValue(server, out var sharedPort))
        continue;

    var serverName = $"{server}-shared";
    var baseUrl = $"http://localhost:{sharedPort}";

    var sharedHmacConfig = new HmacConfig
    {
        SharedSecretBase64 = sharedSecret,
    };

    var sharedHandler = new HardenHmacDelegatingHandler(sharedHmacConfig, new HttpClientHandler(), clientId: ClientId);
    using var sharedClient = new HttpClient(sharedHandler)
    {
        BaseAddress = new Uri(baseUrl),
    };

    // GET /api/hello
    try
    {
        var response = await sharedClient.GetAsync("/api/hello");
        var status = (int)response.StatusCode;
        if (status == 200)
        {
            results.Add($"PASS {ClientId}/shared -> {serverName} GET /api/hello ({status})");
        }
        else
        {
            var body = await response.Content.ReadAsStringAsync();
            results.Add($"FAIL {ClientId}/shared -> {serverName} GET /api/hello ({status}): {body}");
        }
    }
    catch (HttpRequestException ex) when (ex.InnerException is System.Net.Sockets.SocketException)
    {
        results.Add($"SKIP {ClientId}/shared -> {serverName} GET /api/hello (server not running)");
    }
    catch (Exception ex)
    {
        results.Add($"FAIL {ClientId}/shared -> {serverName} GET /api/hello (ERR): {ex.Message}");
    }

    // POST /api/echo
    try
    {
        var postBody = JsonSerializer.Serialize(new { from = ClientId, test = "integration-shared" });
        var content = new StringContent(postBody, Encoding.UTF8, "application/json");
        var response = await sharedClient.PostAsync("/api/echo", content);
        var status = (int)response.StatusCode;
        if (status == 200)
        {
            results.Add($"PASS {ClientId}/shared -> {serverName} POST /api/echo ({status})");
        }
        else
        {
            var body = await response.Content.ReadAsStringAsync();
            results.Add($"FAIL {ClientId}/shared -> {serverName} POST /api/echo ({status}): {body}");
        }
    }
    catch (HttpRequestException ex) when (ex.InnerException is System.Net.Sockets.SocketException)
    {
        results.Add($"SKIP {ClientId}/shared -> {serverName} POST /api/echo (server not running)");
    }
    catch (Exception ex)
    {
        results.Add($"FAIL {ClientId}/shared -> {serverName} POST /api/echo (ERR): {ex.Message}");
    }
}

foreach (var result in results)
{
    Console.WriteLine(result);
}

return results.Any(r => r.StartsWith("FAIL")) ? 1 : 0;
