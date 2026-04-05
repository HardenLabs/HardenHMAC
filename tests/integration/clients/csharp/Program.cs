using System.Text;
using System.Text.Json;
using HardenLabs.Hmac;
using HardenLabs.Hmac.AspNetCore;

const string ClientId = "csharp-client";
const string ClientIdHeader = "X-Harden-Client-Id";

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

// Get resolver and global ports
var resolverPorts = new Dictionary<string, int>();
if (configDoc.RootElement.TryGetProperty("resolverPorts", out var rp))
{
    foreach (var port in rp.EnumerateObject())
    {
        resolverPorts[port.Name] = port.Value.GetInt32();
    }
}
var globalPorts = new Dictionary<string, int>();
if (configDoc.RootElement.TryGetProperty("globalPorts", out var gp))
{
    foreach (var port in gp.EnumerateObject())
    {
        globalPorts[port.Name] = port.Value.GetInt32();
    }
}

var sharedSecret = configDoc.RootElement.GetProperty("sharedSecret").GetString()!;

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

    // IT-3: Fallback secret (sign with sharedSecret, NO X-Harden-Client-Id)
    try
    {
        var fallbackConfig = new HmacConfig { SharedSecretBase64 = sharedSecret };
        var fallbackHandler = new HardenHmacDelegatingHandler(fallbackConfig, new HttpClientHandler(), clientId: null);
        using var fallbackClient = new HttpClient(fallbackHandler) { BaseAddress = new Uri(baseUrl) };
        var response = await fallbackClient.GetAsync("/api/hello");
        var status = (int)response.StatusCode;
        if (status == 200)
        {
            results.Add($"PASS {ClientId}/fallback -> {serverName} GET /api/hello ({status})");
        }
        else
        {
            var body = await response.Content.ReadAsStringAsync();
            results.Add($"FAIL {ClientId}/fallback -> {serverName} GET /api/hello ({status}): {body}");
        }
    }
    catch (HttpRequestException ex) when (ex.InnerException is System.Net.Sockets.SocketException)
    {
        results.Add($"SKIP {ClientId}/fallback -> {serverName} GET /api/hello (server not running)");
    }
    catch (Exception ex)
    {
        results.Add($"FAIL {ClientId}/fallback -> {serverName} GET /api/hello (ERR): {ex.Message}");
    }

    // IT-4: Unknown client rejection
    try
    {
        var bogusSecret = Convert.ToBase64String(Encoding.UTF8.GetBytes("wrong-secret-for-unknown-client!!!"));
        var bogusConfig = new HmacConfig { SharedSecretBase64 = bogusSecret };
        var bogusHandler = new HardenHmacDelegatingHandler(bogusConfig, new HttpClientHandler(), clientId: "nonexistent-client");
        using var bogusClient = new HttpClient(bogusHandler) { BaseAddress = new Uri(baseUrl) };
        var response = await bogusClient.GetAsync("/api/hello");
        var status = (int)response.StatusCode;
        if (status >= 400 && status < 500)
        {
            results.Add($"PASS {ClientId}/unknown-client -> {serverName} GET /api/hello ({status})");
        }
        else
        {
            var body = await response.Content.ReadAsStringAsync();
            results.Add($"FAIL {ClientId}/unknown-client -> {serverName} GET /api/hello (expected 4xx, got {status}): {body}");
        }
    }
    catch (HttpRequestException ex) when (ex.InnerException is System.Net.Sockets.SocketException)
    {
        results.Add($"SKIP {ClientId}/unknown-client -> {serverName} GET /api/hello (server not running)");
    }
    catch (Exception ex)
    {
        results.Add($"FAIL {ClientId}/unknown-client -> {serverName} GET /api/hello (ERR): {ex.Message}");
    }

    // IT-5: Stale timestamp (300s in the past)
    try
    {
        var staleTs = DateTimeOffset.UtcNow.ToUnixTimeSeconds() - 300;
        var staleSigner = new HmacRequestSigner(hmacConfig);
        var staleResult = staleSigner.Sign("GET", "/api/hello", "", new Dictionary<string, string>
        {
            { ClientIdHeader, ClientId }
        }, staleTs);
        using var staleClient = new HttpClient { BaseAddress = new Uri(baseUrl) };
        var staleRequest = new HttpRequestMessage(HttpMethod.Get, "/api/hello");
        staleRequest.Headers.TryAddWithoutValidation(ClientIdHeader, ClientId);
        staleRequest.Headers.TryAddWithoutValidation(HardenHmacConstants.SignatureHeader, staleResult.Signature);
        staleRequest.Headers.TryAddWithoutValidation(HardenHmacConstants.TimestampHeader, staleResult.Timestamp.ToString());
        if (staleResult.SignedHeaderNames.Count > 0)
        {
            staleRequest.Headers.TryAddWithoutValidation(HardenHmacConstants.SignedHeadersHeader, string.Join(";", staleResult.SignedHeaderNames));
        }
        var response = await staleClient.SendAsync(staleRequest);
        var status = (int)response.StatusCode;
        if (status >= 400 && status < 500)
        {
            results.Add($"PASS {ClientId}/stale-ts -> {serverName} GET /api/hello ({status})");
        }
        else
        {
            var body = await response.Content.ReadAsStringAsync();
            results.Add($"FAIL {ClientId}/stale-ts -> {serverName} GET /api/hello (expected 4xx, got {status}): {body}");
        }
    }
    catch (HttpRequestException ex) when (ex.InnerException is System.Net.Sockets.SocketException)
    {
        results.Add($"SKIP {ClientId}/stale-ts -> {serverName} GET /api/hello (server not running)");
    }
    catch (Exception ex)
    {
        results.Add($"FAIL {ClientId}/stale-ts -> {serverName} GET /api/hello (ERR): {ex.Message}");
    }

    // IT-8: Empty body POST
    try
    {
        var content = new StringContent("", Encoding.UTF8, "application/json");
        var response = await client.PostAsync("/api/echo", content);
        var status = (int)response.StatusCode;
        if (status == 200)
        {
            results.Add($"PASS {ClientId}/empty-body -> {serverName} POST /api/echo ({status})");
        }
        else
        {
            var body = await response.Content.ReadAsStringAsync();
            results.Add($"FAIL {ClientId}/empty-body -> {serverName} POST /api/echo ({status}): {body}");
        }
    }
    catch (HttpRequestException ex) when (ex.InnerException is System.Net.Sockets.SocketException)
    {
        results.Add($"SKIP {ClientId}/empty-body -> {serverName} POST /api/echo (server not running)");
    }
    catch (Exception ex)
    {
        results.Add($"FAIL {ClientId}/empty-body -> {serverName} POST /api/echo (ERR): {ex.Message}");
    }

    // IT-9: Wrong SignedHeaders (client uses None, server uses Default)
    // Include Authorization header so signed-headers difference actually matters
    try
    {
        var noneConfig = new HmacConfig
        {
            SharedSecretBase64 = mySecret,
            SignedHeaders = SignedHeadersConfig.None,
        };
        var noneHandler = new HardenHmacDelegatingHandler(noneConfig, new HttpClientHandler(), clientId: ClientId);
        using var noneClient = new HttpClient(noneHandler) { BaseAddress = new Uri(baseUrl) };
        noneClient.DefaultRequestHeaders.Add("Authorization", "Bearer test");
        var response = await noneClient.GetAsync("/api/hello");
        var status = (int)response.StatusCode;
        if (status >= 400 && status < 500)
        {
            results.Add($"PASS {ClientId}/wrong-headers -> {serverName} GET /api/hello ({status})");
        }
        else
        {
            var body = await response.Content.ReadAsStringAsync();
            results.Add($"FAIL {ClientId}/wrong-headers -> {serverName} GET /api/hello (expected 4xx, got {status}): {body}");
        }
    }
    catch (HttpRequestException ex) when (ex.InnerException is System.Net.Sockets.SocketException)
    {
        results.Add($"SKIP {ClientId}/wrong-headers -> {serverName} GET /api/hello (server not running)");
    }
    catch (Exception ex)
    {
        results.Add($"FAIL {ClientId}/wrong-headers -> {serverName} GET /api/hello (ERR): {ex.Message}");
    }

    // IT-10: Query string
    try
    {
        var response = await client.GetAsync("/api/hello?foo=bar&baz=1");
        var status = (int)response.StatusCode;
        if (status == 200)
        {
            results.Add($"PASS {ClientId}/query -> {serverName} GET /api/hello?foo=bar&baz=1 ({status})");
        }
        else
        {
            var body = await response.Content.ReadAsStringAsync();
            results.Add($"FAIL {ClientId}/query -> {serverName} GET /api/hello?foo=bar&baz=1 ({status}): {body}");
        }
    }
    catch (HttpRequestException ex) when (ex.InnerException is System.Net.Sockets.SocketException)
    {
        results.Add($"SKIP {ClientId}/query -> {serverName} GET /api/hello?foo=bar&baz=1 (server not running)");
    }
    catch (Exception ex)
    {
        results.Add($"FAIL {ClientId}/query -> {serverName} GET /api/hello?foo=bar&baz=1 (ERR): {ex.Message}");
    }
}

// ============================================================
// Shared-secret server tests
// ============================================================
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

// ============================================================
// Resolver server tests (IT-6)
// ============================================================
foreach (var server in servers)
{
    if (!resolverPorts.TryGetValue(server, out var resolverPort))
        continue;

    var serverName = $"{server}-resolver";
    var baseUrl = $"http://localhost:{resolverPort}";

    var resolverHmacConfig = new HmacConfig { SharedSecretBase64 = mySecret };
    var resolverHandler = new HardenHmacDelegatingHandler(resolverHmacConfig, new HttpClientHandler(), clientId: ClientId);
    using var resolverClient = new HttpClient(resolverHandler) { BaseAddress = new Uri(baseUrl) };

    // GET /api/hello
    try
    {
        var response = await resolverClient.GetAsync("/api/hello");
        var status = (int)response.StatusCode;
        if (status == 200)
            results.Add($"PASS {ClientId} -> {serverName} GET /api/hello ({status})");
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
        var postBody = JsonSerializer.Serialize(new { from = ClientId, test = "integration-resolver" });
        var content = new StringContent(postBody, Encoding.UTF8, "application/json");
        var response = await resolverClient.PostAsync("/api/echo", content);
        var status = (int)response.StatusCode;
        if (status == 200)
            results.Add($"PASS {ClientId} -> {serverName} POST /api/echo ({status})");
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
}

// ============================================================
// Global middleware server tests (IT-7)
// ============================================================
foreach (var server in servers)
{
    if (!globalPorts.TryGetValue(server, out var globalPort))
        continue;

    var serverName = $"{server}-global";
    var baseUrl = $"http://localhost:{globalPort}";

    var globalHmacConfig = new HmacConfig { SharedSecretBase64 = mySecret };
    var globalHandler = new HardenHmacDelegatingHandler(globalHmacConfig, new HttpClientHandler(), clientId: ClientId);
    using var globalClient = new HttpClient(globalHandler) { BaseAddress = new Uri(baseUrl) };

    // Signed GET /api/hello
    try
    {
        var response = await globalClient.GetAsync("/api/hello");
        var status = (int)response.StatusCode;
        if (status == 200)
            results.Add($"PASS {ClientId} -> {serverName} GET /api/hello ({status})");
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

    // Signed POST /api/echo
    try
    {
        var postBody = JsonSerializer.Serialize(new { from = ClientId, test = "integration-global" });
        var content = new StringContent(postBody, Encoding.UTF8, "application/json");
        var response = await globalClient.PostAsync("/api/echo", content);
        var status = (int)response.StatusCode;
        if (status == 200)
            results.Add($"PASS {ClientId} -> {serverName} POST /api/echo ({status})");
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

    // Signed GET /health (global mode protects ALL routes)
    try
    {
        var response = await globalClient.GetAsync("/health");
        var status = (int)response.StatusCode;
        if (status == 200)
            results.Add($"PASS {ClientId} -> {serverName} GET /health ({status})");
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

    // Unsigned GET /health (global mode should reject)
    try
    {
        using var plainClient = new HttpClient { BaseAddress = new Uri(baseUrl) };
        var response = await plainClient.GetAsync("/health");
        var status = (int)response.StatusCode;
        if (status >= 400 && status < 500)
            results.Add($"PASS {ClientId}/nohmac -> {serverName} GET /health ({status})");
        else
        {
            var body = await response.Content.ReadAsStringAsync();
            results.Add($"FAIL {ClientId}/nohmac -> {serverName} GET /health (expected 4xx, got {status}): {body}");
        }
    }
    catch (HttpRequestException ex) when (ex.InnerException is System.Net.Sockets.SocketException)
    {
        results.Add($"SKIP {ClientId}/nohmac -> {serverName} GET /health (server not running)");
    }
    catch (Exception ex)
    {
        results.Add($"FAIL {ClientId}/nohmac -> {serverName} GET /health (ERR): {ex.Message}");
    }
}

foreach (var result in results)
{
    Console.WriteLine(result);
}

return results.Any(r => r.StartsWith("FAIL")) ? 1 : 0;
