namespace HardenLabs.Hmac;

/// <summary>
/// Identity and credentials for a named client that connects to this server.
/// Used in multi-client server configurations where different clients
/// authenticate with different shared secrets.
/// </summary>
public sealed class HmacClientIdentity
{
    /// <summary>
    /// The shared secret as a Base64-encoded string for this client.
    /// </summary>
    public string SharedSecret { get; set; } = "";
}
