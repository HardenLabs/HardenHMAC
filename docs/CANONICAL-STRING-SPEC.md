# Canonical String Specification v1.0

## Format

```
METHOD\nPATH\nSIGNED_HEADERS\nBODY\nTIMESTAMP
```

The canonical string consists of exactly 5 fields separated by the newline character (`\n`, U+000A). The separator is always present even when a field is empty.

## Field Definitions

### 1. METHOD

The HTTP request method, converted to uppercase ASCII.

**Rules:**
- Must be uppercase: `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `HEAD`, `OPTIONS`
- No leading or trailing whitespace
- Never empty

**Examples:**
- `GET`
- `POST`

### 2. PATH

The request path including the query string, used as-is with no normalization.

**Rules:**
- Includes the leading `/`
- Includes the query string with the `?` prefix, if present
- No URL encoding or decoding is applied (use the path as it appears in the HTTP request)
- No trailing slash normalization
- Never empty (minimum value is `/`)

**Examples:**
- `/api/users`
- `/api/users/123?active=true&role=admin`
- `/`
- `/api/v2/messages?filter=type%3Durgent&lang=en`

### 3. SIGNED_HEADERS

Selected request headers, sorted and formatted according to the signed headers configuration.

**Rules:**
1. Collect headers matching the configuration:
   - If `include_authorization` is true and `Authorization` header exists, include it
   - If `include_x_headers` is true, include all `X-*` headers EXCEPT those matching `X-Harden-*`
   - Include any headers listed in `additional_headers` (case-insensitive match)
2. Remove any headers listed in `exclude_headers` (case-insensitive match)
3. Always remove `X-Harden-*` headers regardless of configuration, **except** `X-Harden-Client-Id` which is an identity claim and MUST be included when present (it is treated as a regular `X-*` header for signing purposes)
4. Convert each header name to lowercase
5. Trim leading and trailing whitespace from each header value
6. Sort headers alphabetically by lowercase name (lexicographic, ASCII order)
7. Format each header as `name:value` (no space after colon)
8. Join all formatted headers with `\n`

If no headers match after filtering, the SIGNED_HEADERS field is an empty string.

**Examples:**

Given headers: `Authorization: Bearer tok`, `X-Request-Id: abc`, `Content-Type: application/json`, `X-Harden-Signature: xxx`

With `include_authorization=true, include_x_headers=true`:
```
authorization:Bearer tok
x-request-id:abc
```

With `include_authorization=false, include_x_headers=false`:
```
(empty string)
```

With `include_authorization=true, include_x_headers=true, additional_headers=["Content-Type"]`:
```
authorization:Bearer tok
content-type:application/json
x-request-id:abc
```

### 4. BODY

The request body as a string.

**Rules:**
- Use the raw body string as-is (no JSON re-serialization, no whitespace normalization)
- If the request has no body, use an empty string
- UTF-8 encoding is used when computing the HMAC

**Examples:**
- `{"name":"Alice","email":"alice@example.com"}`
- `` (empty string for GET/DELETE with no body)

### 5. TIMESTAMP

The Unix timestamp in seconds, represented as a decimal integer string.

**Rules:**
- Integer number of seconds since Unix epoch (1970-01-01T00:00:00Z)
- No fractional seconds
- No leading zeros (except for the value `0` itself)
- Never empty

**Examples:**
- `1700000000`
- `1700000007`

## Signature Computation

```
signature = HMAC-SHA256(base64_decode(shared_secret), utf8_encode(canonical_string))
```

- **Input key**: The shared secret is stored as a Base64-encoded string. Decode it to raw bytes before use as the HMAC key.
- **Input data**: The canonical string is encoded as UTF-8 bytes.
- **Output**: The HMAC digest is converted to a lowercase hexadecimal string, exactly 64 characters.

## Complete Examples

### Example 1: Basic GET

**Request:**
- Method: `GET`
- Path: `/api/users`
- Body: (none)
- Timestamp: `1700000000`
- Signed headers config: all disabled

**Canonical string** (showing `\n` as actual newlines):
```
GET
/api/users


1700000000
```

Note: The two blank lines between `/api/users` and `1700000000` represent the empty SIGNED_HEADERS and empty BODY fields.

### Example 2: POST with Body and Signed Headers

**Request:**
- Method: `POST`
- Path: `/api/orders`
- Body: `{"item":"widget","qty":5}`
- Timestamp: `1700000004`
- Headers: `Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.test`, `X-Request-Id: req-abc-123`
- Signed headers config: `include_authorization=true, include_x_headers=true`

**Canonical string:**
```
POST
/api/orders
authorization:Bearer eyJhbGciOiJIUzI1NiJ9.test
x-request-id:req-abc-123
{"item":"widget","qty":5}
1700000004
```

### Example 3: Multiple Sorted Headers

**Request:**
- Method: `POST`
- Path: `/api/data`
- Body: `{"key":"value"}`
- Timestamp: `1700000007`
- Headers: `Authorization: Bearer token123`, `Content-Type: application/json`, `X-Custom-A: value-a`, `X-Custom-B: value-b`, `Accept: application/json`
- Signed headers config: `include_authorization=true, include_x_headers=true, additional_headers=["Content-Type"]`

**Canonical string:**
```
POST
/api/data
authorization:Bearer token123
content-type:application/json
x-custom-a:value-a
x-custom-b:value-b
{"key":"value"}
1700000007
```

Note the alphabetical sort order: authorization, content-type, x-custom-a, x-custom-b.

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| No query string | PATH is just the path (e.g., `/api/users`) |
| Empty query string (`/path?`) | PATH includes the `?` (i.e., `/path?`) |
| No body | BODY field is empty string |
| Null/undefined body | Treat as empty string |
| No signed headers match | SIGNED_HEADERS field is empty string |
| Header value with internal whitespace | Preserved (only leading/trailing trimmed) |
| Duplicate header names | Values are joined with `, ` (comma-space), matching HTTP semantics (RFC 9110 Section 5.2) |
| Non-ASCII body | UTF-8 encoded for HMAC computation |
| Path with fragment (`#`) | Fragments are not transmitted in HTTP requests and are not part of the canonical path |

## Versioning

This is version 1.0 of the canonical string specification. Future versions will use a different version identifier and will not change the behavior of v1.0.
