namespace HardenLabs.Hmac.AspNetCore;

/// <summary>
/// Attribute to require HMAC validation for specific endpoints.
/// Apply to controller actions or entire controllers that should enforce signature validation.
///
/// Endpoints are NOT validated by default — you must explicitly opt-in with this attribute.
///
/// Use [SkipHmacValidate] to exempt specific methods when a controller is protected.
/// </summary>
/// <example>
/// <code>
/// // Protect a single action
/// [HttpPost("/api/orders")]
/// [HmacValidate]
/// public IActionResult CreateOrder([FromBody] OrderRequest order)
/// {
///     return Ok(new { status = "created" });
/// }
///
/// // Protect all actions in a controller
/// [ApiController]
/// [Route("api/orders")]
/// [HmacValidate]
/// public class OrdersController : ControllerBase
/// {
///     [HttpGet]
///     public IActionResult GetOrders() => Ok();
///
///     // Exempt specific method from validation
///     [HttpGet("health")]
///     [SkipHmacValidate]
///     public IActionResult Health() => Ok(new { status = "healthy" });
/// }
/// </code>
/// </example>
[AttributeUsage(AttributeTargets.Method | AttributeTargets.Class, AllowMultiple = false, Inherited = true)]
public class HmacValidateAttribute : Attribute
{
}
