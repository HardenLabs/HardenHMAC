using System.Text;
using System.Text.Json;
using HardenLabs.Hmac;
using HardenLabs.Hmac.AspNetCore;

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

var results = new List<string>();

// Build HmacConfig with Targets from multiTargetTests
var hmacConfig = new HmacConfig();
foreach (var target in configDoc.RootElement.GetProperty("multiTargetTests").GetProperty("targets").EnumerateObject())
{
    hmacConfig.Targets[target.Name] = new HmacTargetConfig
    {
        BaseUrl = target.Value.GetProperty("baseUrl").GetString()!,
        SharedSecret = target.Value.GetProperty("sharedSecret").GetString()!,
    };
}

var factory = new HardenHmacClientFactory(hmacConfig);

// 1. Multi-target: call each server with correct target-specific secret
var targetNames = new[] { "csharp-client", "python-client", "typescript-client", "go-client" };

foreach (var targetName in targetNames)
{
    var serverName = targetName.Replace("-client", "-server");
    using var client = factory.CreateClient(targetName);

    // GET /api/hello
    try
    {
        var response = await client.GetAsync("/api/hello");
        var status = (int)response.StatusCode;
        if (status == 200)
        {
            results.Add($"PASS csharp-multitarget -> {serverName} GET /api/hello ({status})");
        }
        else
        {
            var body = await response.Content.ReadAsStringAsync();
            results.Add($"FAIL csharp-multitarget -> {serverName} GET /api/hello ({status}): {body}");
        }
    }
    catch (HttpRequestException ex) when (ex.InnerException is System.Net.Sockets.SocketException)
    {
        results.Add($"SKIP csharp-multitarget -> {serverName} GET /api/hello (server not running)");
        results.Add($"SKIP csharp-multitarget -> {serverName} POST /api/echo (server not running)");
        continue;
    }
    catch (Exception ex)
    {
        results.Add($"FAIL csharp-multitarget -> {serverName} GET /api/hello (ERR): {ex.Message}");
        continue;
    }

    // POST /api/echo
    try
    {
        var postBody = JsonSerializer.Serialize(new { from = targetName, test = "multitarget" });
        var content = new StringContent(postBody, Encoding.UTF8, "application/json");
        var response = await client.PostAsync("/api/echo", content);
        var status = (int)response.StatusCode;
        if (status == 200)
        {
            results.Add($"PASS csharp-multitarget -> {serverName} POST /api/echo ({status})");
        }
        else
        {
            var body = await response.Content.ReadAsStringAsync();
            results.Add($"FAIL csharp-multitarget -> {serverName} POST /api/echo ({status}): {body}");
        }
    }
    catch (HttpRequestException ex) when (ex.InnerException is System.Net.Sockets.SocketException)
    {
        results.Add($"SKIP csharp-multitarget -> {serverName} POST /api/echo (server not running)");
    }
    catch (Exception ex)
    {
        results.Add($"FAIL csharp-multitarget -> {serverName} POST /api/echo (ERR): {ex.Message}");
    }
}

// 2. Cross-client test: send as two different clients to the SAME server (python-server, port 9101)
var crossBase = configDoc.RootElement
    .GetProperty("multiTargetTests")
    .GetProperty("targets")
    .GetProperty("python-client")
    .GetProperty("baseUrl")
    .GetString()!;

foreach (var crossId in new[] { "csharp-client", "go-client" })
{
    var crossSecret = configDoc.RootElement
        .GetProperty("multiTargetTests")
        .GetProperty("targets")
        .GetProperty(crossId)
        .GetProperty("sharedSecret")
        .GetString()!;

    var crossConfig = new HmacConfig { SharedSecretBase64 = crossSecret };
    var crossHandler = new HardenHmacDelegatingHandler(crossConfig, new HttpClientHandler(), clientId: crossId);
    using var crossClient = new HttpClient(crossHandler) { BaseAddress = new Uri(crossBase) };

    try
    {
        var response = await crossClient.GetAsync("/api/hello");
        var status = (int)response.StatusCode;
        if (status == 200)
        {
            results.Add($"PASS csharp-multitarget/cross({crossId}) -> python-server GET /api/hello ({status})");
        }
        else
        {
            var body = await response.Content.ReadAsStringAsync();
            results.Add($"FAIL csharp-multitarget/cross({crossId}) -> python-server GET /api/hello ({status}): {body}");
        }
    }
    catch (HttpRequestException ex) when (ex.InnerException is System.Net.Sockets.SocketException)
    {
        results.Add($"SKIP csharp-multitarget/cross({crossId}) -> python-server GET /api/hello (server not running)");
    }
    catch (Exception ex)
    {
        results.Add($"FAIL csharp-multitarget/cross({crossId}) -> python-server GET /api/hello (ERR): {ex.Message}");
    }
}

// 3. Negative test: wrong secret for client ID -> expect 4xx
{
    var wrongSecret = configDoc.RootElement
        .GetProperty("multiTargetTests")
        .GetProperty("targets")
        .GetProperty("go-client")
        .GetProperty("sharedSecret")
        .GetString()!;

    var wrongConfig = new HmacConfig { SharedSecretBase64 = wrongSecret };
    var wrongHandler = new HardenHmacDelegatingHandler(wrongConfig, new HttpClientHandler(), clientId: "csharp-client");
    using var wrongClient = new HttpClient(wrongHandler) { BaseAddress = new Uri(crossBase) };

    try
    {
        var response = await wrongClient.GetAsync("/api/hello");
        var status = (int)response.StatusCode;
        if (status >= 400 && status < 500)
        {
            results.Add($"PASS csharp-multitarget/wrong-secret -> python-server GET /api/hello ({status})");
        }
        else
        {
            var body = await response.Content.ReadAsStringAsync();
            results.Add($"FAIL csharp-multitarget/wrong-secret -> python-server GET /api/hello (expected 4xx, got {status}): {body}");
        }
    }
    catch (HttpRequestException ex) when (ex.InnerException is System.Net.Sockets.SocketException)
    {
        results.Add($"SKIP csharp-multitarget/wrong-secret -> python-server GET /api/hello (server not running)");
    }
    catch (Exception ex)
    {
        results.Add($"FAIL csharp-multitarget/wrong-secret -> python-server GET /api/hello (ERR): {ex.Message}");
    }
}

foreach (var result in results)
{
    Console.WriteLine(result);
}

return results.Any(r => r.StartsWith("FAIL")) ? 1 : 0;
