using System.Text;
using HardenLabs.Hmac;
using HardenLabs.Hmac.AspNetCore;
using Microsoft.Extensions.DependencyInjection;

// Same secrets as the server — in production, load from config/env
var ordersSecret = Convert.ToBase64String("orders-secret-key-32-bytes!!!!!"u8.ToArray());
var paymentsSecret = Convert.ToBase64String("payments-secret-key-32-bytes!!"u8.ToArray());

var config = new HmacConfig
{
    SignedHeaders = SignedHeadersConfig.Default,
    Targets = new Dictionary<string, HmacTargetConfig>
    {
        ["order-service"] = new HmacTargetConfig
        {
            BaseUrl = "http://localhost:5000",
            SharedSecret = ordersSecret,
        },
        ["payment-service"] = new HmacTargetConfig
        {
            BaseUrl = "http://localhost:5001",
            SharedSecret = paymentsSecret,
        },
    },
};

var factory = new HardenHmacClientFactory(config);

// GET via order-service
using var ordersClient = factory.CreateClient("order-service");
var getResponse = await ordersClient.GetAsync("/api/hello");
var getBody = await getResponse.Content.ReadAsStringAsync();
Console.WriteLine($"GET order-service /api/hello: {(int)getResponse.StatusCode} {getBody}");

// POST via payment-service
using var paymentsClient = factory.CreateClient("payment-service");
var postContent = new StringContent("{\"amount\":100}", Encoding.UTF8, "application/json");
var postResponse = await paymentsClient.PostAsync("/api/echo", postContent);
var postBody = await postResponse.Content.ReadAsStringAsync();
Console.WriteLine($"POST payment-service /api/echo: {(int)postResponse.StatusCode} {postBody}");

