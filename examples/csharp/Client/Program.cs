using System.Text;
using HardenLabs.Hmac;
using HardenLabs.Hmac.AspNetCore;
using Microsoft.Extensions.DependencyInjection;

// Same shared secret as the server — in production, load from config/env
var sharedSecret = Convert.ToBase64String("my-shared-secret-key-32-bytes!!"u8.ToArray());

// ── Option A: Multi-target factory (recommended) ──
Console.WriteLine("=== Multi-target factory ===");

var config = new HmacConfig
{
    SharedSecretBase64 = sharedSecret,
    SignedHeaders = SignedHeadersConfig.Default,
    Targets = new Dictionary<string, HmacTargetConfig>
    {
        ["server"] = new HmacTargetConfig
        {
            BaseUrl = "http://localhost:5000",
            SharedSecret = sharedSecret,
        },
    },
};

var factory = new HardenHmacClientFactory(config);
using var client = factory.CreateClient("server");

// GET
var getResponse = await client.GetAsync("/api/hello");
var getBody = await getResponse.Content.ReadAsStringAsync();
Console.WriteLine($"GET /api/hello: {(int)getResponse.StatusCode} {getBody}");

// POST
var postContent = new StringContent("{\"item\":\"widget\",\"qty\":5}", Encoding.UTF8, "application/json");
var postResponse = await client.PostAsync("/api/echo", postContent);
var postBody = await postResponse.Content.ReadAsStringAsync();
Console.WriteLine($"POST /api/echo: {(int)postResponse.StatusCode} {postBody}");

// ── Option B: Manual signing ──
Console.WriteLine("\n=== Manual signing ===");

var signer = new HmacRequestSigner(config);
var result = signer.Sign("GET", "/api/hello", "");

using var manualClient = new HttpClient { BaseAddress = new Uri("http://localhost:5000") };
manualClient.DefaultRequestHeaders.Add("X-Harden-Signature", result.Signature);
manualClient.DefaultRequestHeaders.Add("X-Harden-Timestamp", result.Timestamp.ToString());

var manualResponse = await manualClient.GetAsync("/api/hello");
var manualBody = await manualResponse.Content.ReadAsStringAsync();
Console.WriteLine($"GET /api/hello: {(int)manualResponse.StatusCode} {manualBody}");
