namespace HardenLabs.Hmac.AspNetCore;

/// <summary>
/// Attribute to skip HMAC validation for specific endpoints.
/// Use this to exempt individual actions when the controller is marked with [HmacValidate].
///
/// This follows the same pattern as ASP.NET's [AllowAnonymous] with [Authorize].
/// </summary>
/// <example>
/// <code>
/// [ApiController]
/// [Route("api/orders")]
/// [HmacValidate]
/// public class OrdersController : ControllerBase
/// {
///     [HttpGet]
///     public IActionResult GetOrders() => Ok();
///
///     [HttpGet("health")]
///     [SkipHmacValidate]
///     public IActionResult Health() => Ok(new { status = "healthy" });
/// }
/// </code>
/// </example>
[AttributeUsage(AttributeTargets.Method, AllowMultiple = false, Inherited = true)]
public class SkipHmacValidateAttribute : Attribute
{
}
