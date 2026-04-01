# Adversarial Security Review: HardenHMAC

**Date:** 2026-03-31
**Reviewer:** QA Engineer (Red Team)
**Scope:** All 4 SDK implementations (C#, Python, TypeScript, Go)
**Risk Level:** Medium
**Verdict:** PASS WITH NOTES

---

## Executive Summary

HardenHMAC is a well-designed HMAC-SHA256 signing library with consistent cross-language behavior and reasonable security properties for its threat model. No **critical** vulnerabilities that allow signature bypass without the shared secret were found. However, several **medium** and **high** findings exist that could weaken the system under specific conditions -- most notably the lack of replay protection, a canonical string injection vector via newlines in paths/headers, and a secret resolver failure mode that can differ between SDKs.

---

## Attack 1: Canonical String Newline Injection

**Severity:** HIGH
**Exploitability:** Medium -- requires control over path or header values
**Affected SDKs:** All (C#, Python, TypeScript, Go)

### Analysis

The canonical string format is:
```
METHOD\nPATH\nSIGNED_HEADERS\nBODY\nTIMESTAMP
```

The PATH field is used **as-is with no normalization** (per `CANONICAL-STRING-SPEC.md` line 30). If an attacker can inject a literal newline (`\n`) into the HTTP path, they can inject fake fields into the canonical string.

**Example attack:** If `path = "/api\nfake-headers\nmalicious-body\n1700000000"`, the canonical string becomes:
```
GET
/api
fake-headers
malicious-body
1700000000
\n
\nTIMESTAMP
```

This would produce a canonical string where the attacker controls the "signed headers" and "body" fields.

### Why this is mitigated in practice

HTTP/1.1 and HTTP/2 specifications prohibit literal newlines in request-target (RFC 9112 Section 3.2.1). Compliant HTTP servers and proxies will reject such requests before they reach application code. All four middleware implementations receive the path from the HTTP framework (ASP.NET Core, FastAPI/Starlette, Express, Go net/http), which have already parsed and validated the request-target.

**However:** This is defense-in-depth reliance on the HTTP layer. The canonical string builder itself has NO validation that the path is free of newlines. If the library is used in a non-HTTP context (e.g., message queue signing, gRPC metadata signing) where the path parameter is user-controlled, this becomes exploitable.

### Code References

- Python `canonical.py:36-44` -- `path` used directly in `"\n".join([...])`
- Go `canonical.go:23-29` -- `path` used directly in `strings.Join`
- TypeScript `canonical.ts:43-49` -- `path` used directly in `.join("\n")`
- C# `CanonicalStringBuilder.cs:43` -- `sb.Append(path)` with no validation

### Proof of Concept

```python
from hardenlabs_hmac.canonical import build_canonical_string

# Attacker-controlled path with newline injection
malicious_path = "/api\nauthorization:Bearer admin-token\n{\"role\":\"admin\"}\n1700000000"

# This produces a canonical string that looks like a completely different request
result = build_canonical_string("GET", malicious_path, "", 9999999999)
# Result: "GET\n/api\nauthorization:Bearer admin-token\n{\"role\":\"admin\"}\n1700000000\n\n\n9999999999"
```

If an attacker can predict the timestamp and body of a legitimate request, they could construct a malicious path that produces the same canonical string as that legitimate request.

### Mitigation

Validate that `path`, `body`, and header names/values do not contain `\n` characters in the canonical string builder. Reject or escape them. This is a one-line check per field.

---

## Attack 2: Signature Replay Within Tolerance Window

**Severity:** MEDIUM
**Exploitability:** HIGH -- trivially exploitable
**Affected SDKs:** All (by design)

### Analysis

The only replay protection is the 30-second timestamp tolerance window. Within that window, an attacker who observes a signed request can replay it verbatim. There is **no nonce, no sequence counter, no replay cache**.

- **Code:** All four `validateRequest` functions check only `delta > tolerance` and `delta < -tolerance`.
- **No middleware** maintains a replay cache or nonce check.

### Attack scenario

1. Attacker intercepts `POST /api/transfer {"amount": 1000}` with valid signature and timestamp T.
2. Attacker replays the exact same request within 30 seconds.
3. Server validates the signature and processes the transfer again.

### Why this is partially mitigated

This is an acknowledged design limitation of HMAC-only authentication. The spec does not define a nonce mechanism. Applications using HardenHMAC MUST implement their own idempotency (e.g., via `X-Request-Id` or application-level dedup) if replay is a concern.

### Recommendation

Document this explicitly in the README or security considerations section. Consider adding an optional nonce field (e.g., sign `X-Request-Id` and maintain a server-side seen-nonce cache) as an opt-in feature.

---

## Attack 3: Client ID Spoofing When `includeXHeaders` is Disabled

**Severity:** HIGH
**Exploitability:** High -- configuration-dependent
**Affected SDKs:** All

### Analysis

`X-Harden-Client-Id` is signed **only when** `includeXHeaders` is `true` in the `SignedHeadersConfig`. If a server operator configures `includeXHeaders: false` (and doesn't add `X-Harden-Client-Id` to `additionalHeaders`), the client ID header is NOT part of the signature.

In this configuration, an attacker who knows the shared secret for Client A can:
1. Sign a request as Client A
2. Change the `X-Harden-Client-Id` header to `"Client-B"`
3. The signature still validates because the client ID wasn't signed

The middleware's secret resolution chain makes this worse: if the attacker sends `X-Harden-Client-Id: Client-B`, the server looks up Client B's secret and validates against that -- which will fail (different secret). But if there's only a single global `sharedSecretBase64` (no per-client secrets), the client ID is purely advisory and can be spoofed.

### Code References

The `_select_headers` function in all SDKs explicitly gates `X-Harden-Client-Id` inclusion on `includeXHeaders`:

- Python `canonical.py:99-103`: `if config.include_x_headers and lower_name.startswith(X_HEADER_PREFIX) and (not lower_name.startswith(HARDEN_HEADER_PREFIX) or lower_name == CLIENT_ID_HEADER_LOWER)`
- Go `canonical.go:87-89`: Same logic
- TypeScript `canonical.ts:115-119`: Same logic
- C# `CanonicalStringBuilder.cs:110-116`: Same logic

The default `SignedHeadersConfig` has `includeXHeaders: true`, so the **default** configuration IS safe. But users who customize `SignedHeadersConfig` can inadvertently create this gap.

### Mitigation

Two options:
1. **Always sign `X-Harden-Client-Id`** regardless of `includeXHeaders`. It's an identity claim, not metadata. The code already has a special carve-out for it (excluding it from the general `X-Harden-*` exclusion) -- extend this to always include it.
2. **Document clearly** that disabling `includeXHeaders` also disables client ID signing.

Option 1 is stronger.

---

## Attack 4: Secret Resolver Exception Handling Divergence

**Severity:** MEDIUM
**Exploitability:** Low -- requires a buggy `secretResolver` callback
**Affected SDKs:** Go, TypeScript (Express)

### Analysis

What happens when the `secretResolver` callback throws an exception or returns an error?

| SDK | Behavior on exception |
|-----|------|
| **C# (ASP.NET)** | Exception propagates up, ASP.NET pipeline returns 500. Fails **closed**. |
| **Python (FastAPI)** | Exception propagates up, Starlette returns 500. Fails **closed**. |
| **Go** | Error from resolver returns 401 with `"secret_resolver_error"` message that **includes `err.Error()`**. Fails closed, but **leaks error details**. |
| **TypeScript (Express)** | Promise rejection passes to `next(err)`, which goes to Express error handler. Fails closed. Synchronous exception **is not caught** -- it would crash the request. |

The Go SDK leaks internal error details to the client:

```go
// middleware.go:101-102
message: "Secret resolver returned an error: " + err.Error(),
```

If the secret resolver's error contains internal paths, database connection strings, or other sensitive information, this is sent directly to the attacker.

### Code References

- Go `middleware.go:97-105`: Returns `err.Error()` in response body
- TypeScript `middleware/express.ts:157`: `result.then(resolveAndValidate).catch((err: unknown) => { next(err); })` -- this passes to Express, which by default renders error details in development mode

### Mitigation

- **Go:** Strip `err.Error()` from the response. Log it server-side instead. Return a generic "Secret resolution failed" message.
- **TypeScript:** Already correct for the Promise path. Verify the synchronous path handles exceptions too (it does catch non-`HmacValidationError` at line 112 with `throw error`).

---

## Attack 5: Timing Side Channels

**Severity:** LOW
**Exploitability:** Very Low
**Affected SDKs:** All (inherent to the design)

### Analysis

All four SDKs correctly use constant-time comparison for signature verification:
- C#: `CryptographicOperations.FixedTimeEquals` (line `HmacSigner.cs:50`)
- Python: `hmac.compare_digest` (line `signing.py:42`)
- Go: `hmac.Equal` (line `signing.go:50`)
- TypeScript: `timingSafeEqual` (line `signing.ts:78`)

**However**, there are unavoidable timing differences for different error types:

1. **Missing header vs invalid signature**: Missing signature returns immediately (no HMAC computation). Invalid signature returns after HMAC computation. An attacker can distinguish these, but this leaks no useful information.

2. **Timestamp check before signature**: All SDKs check timestamp freshness BEFORE computing the HMAC. An attacker can determine whether a timestamp is within the tolerance window without knowing the signature. This is a minor information leak but has no practical impact.

3. **Go length check before constant-time compare**: Go `signing.go:46` checks `len(expected) != len(signature)` before `hmac.Equal`. Since both are always 64-char hex strings when the signature is well-formed, this is harmless. A non-64-char input returns faster, but this tells the attacker nothing useful.

### Verdict

No actionable timing vulnerability. The constant-time comparison is correctly implemented where it matters.

---

## Attack 6: Key Extraction / Secret Exposure

**Severity:** MEDIUM (Go), LOW (others)
**Exploitability:** Low
**Affected SDKs:** Go (error message), Python (key material in memory)

### Analysis

**Key material in memory:**

| SDK | Key zeroing after use |
|-----|------|
| C# | YES -- `CryptographicOperations.ZeroMemory(keyBytes)` in `HmacSigner.cs:31` |
| Go | YES -- `defer func() { for i := range keyBytes { keyBytes[i] = 0 } }` in `signing.go:21-25` |
| TypeScript | YES -- `keyBytes.fill(0)` in `signing.ts:53` |
| Python | **NO** -- Comment at `signing.py:18-20` explains Python's `bytes` are immutable and cannot be reliably zeroed. `hmac.new()` also copies the key internally. |

The Python limitation is inherent to the language runtime. The Go implementation correctly zeros the decoded key bytes, but `hmac.New(sha256.New, keyBytes)` may internally copy the key before zeroing.

**Error message leaks:**

- Go `signing.go:63`: `"shared secret is not valid Base64: " + err.Error()` -- if this propagates to a client, it confirms the secret format. This is only triggered during signing, not validation, so it's server-internal.
- Go `middleware.go:102`: Secret resolver error message is returned to the client (see Attack 4).

**No SDKs log the shared secret itself.** The Go logger (`middleware.go:75`) logs only the error type and message, not the secret.

### Recommendation

- Python: Document the limitation. Consider using `bytearray` and zeroing after HMAC computation even if it's imperfect (the `hmac` module may still hold a reference).
- Go: Don't propagate `err.Error()` from the secret resolver to the client response.

---

## Attack 7: Body Manipulation / JSON Re-serialization

**Severity:** MEDIUM (mitigated by TypeScript Express middleware)
**Exploitability:** Medium -- requires misconfiguration
**Affected SDKs:** TypeScript (Express) -- **explicitly defended against**

### Analysis

The TypeScript Express middleware at `middleware/express.ts:42-60` explicitly detects when `req.body` is a parsed object (from `express.json()`) and returns a 400 error:

```typescript
// req.body is a parsed object (e.g. from express.json()). This is not safe for HMAC
// because JSON.stringify may differ from the original wire bytes.
res.status(400).json({
  error: "body_not_raw",
  message: "HardenHMAC middleware requires the raw request body..."
});
```

This is excellent defensive programming. The middleware explicitly rejects the dangerous configuration.

**Remaining concern:** The middleware treats an empty object `{}` as empty body (line 48-49). If `express.json()` parses an empty JSON body `"{}"` into `{}`, this would become `""` instead. However, `Object.keys({}).length === 0` only catches truly empty objects from middleware defaults, and `express.json()` would parse `"{}"` into `{}` which has zero keys -- this IS a mismatch. But the likelihood of sending `"{}"` as a body and expecting it to be signed is very low.

**Other SDKs:**
- C# (ASP.NET): `ReadToEndAsync()` reads the raw body stream -- correct.
- Python (FastAPI): `await request.body()` returns raw bytes -- correct.
- Go: `io.ReadAll(r.Body)` reads raw bytes -- correct.

### Verdict

Well-defended. The Express middleware's explicit detection of parsed bodies is a good pattern.

---

## Attack 8: Multi-Value Header Exploitation

**Severity:** LOW
**Exploitability:** Low
**Affected SDKs:** All (by design)

### Analysis

All four middleware implementations comma-join duplicate headers:

- Python `middleware/fastapi.py:69-72`: Manual comma-join loop
- Go `middleware.go:138-146`: `strings.Join(values, ", ")`
- TypeScript `middleware/express.ts:68-74`: Array check + `.join(", ")`
- C# `HardenHmacMiddleware.cs:61-64`: `header.Value.ToString()` (ASP.NET StringValues auto-joins with `, `)

This follows RFC 9110 Section 5.2 correctly. The potential attack is: an attacker sends two `X-Custom` headers with values `"a"` and `"b"`. The server joins them as `"a, b"`. But the original client signed `"a, b"` as a single value. The signatures match.

The risk is that HTTP intermediaries might reorder or split multi-value headers differently. But since both client and server implementations use the same comma-join strategy, and the signed canonical string uses the joined form, this is consistent.

**The `Set-Cookie` exception**: HTTP `Set-Cookie` headers cannot be safely comma-joined because cookie values may contain commas. However, `Set-Cookie` is a response header, not a request header, so it would never be signed by HardenHMAC (which signs request headers). Non-issue.

---

## Attack 9: Environment Variable Injection

**Severity:** INFORMATIONAL
**Exploitability:** Requires env var control (shared hosting, compromised CI)
**Affected SDKs:** All

### Analysis

All four `fromEnv()`/`from_env()` functions read from environment variables:

1. **Secret injection**: `HARDEN_HMAC_SHARED_SECRET_BASE64` controls the signing key. If an attacker can set this, they can replace the key with their own.
2. **Tolerance widening**: `HARDEN_HMAC_TIMESTAMP_TOLERANCE_SECONDS` controls the replay window. Setting this to `999999999` effectively disables timestamp checking.
3. **Signed header disabling**: `HARDEN_HMAC_SIGNED_HEADERS__INCLUDE_AUTHORIZATION=false` disables Authorization header signing.

**Python dotenv**: Python's `env_loader.py:9-15` auto-loads `.env` files via `python-dotenv`. If an attacker can write a `.env` file to the working directory, they can inject configuration. TypeScript does the same (`env-loader.ts:17-24`).

### Verdict

This is inherent to env-var-based configuration and not a vulnerability in HardenHMAC specifically. The dotenv auto-loading is a convenience feature with standard risks. Document that `.env` files should not be writable by untrusted users.

---

## Attack 10: Cross-Language Divergence Exploitation

**Severity:** LOW (no divergence found)
**Exploitability:** N/A
**Affected SDKs:** None

### Analysis

I examined the canonical string construction across all 4 SDKs and found them consistent:

| Feature | C# | Python | TypeScript | Go |
|---------|-----|--------|------------|-----|
| Method uppercasing | `ToUpperInvariant()` | `.upper()` | `.toUpperCase()` | `strings.ToUpper()` |
| Header name lowering | `ToLowerInvariant()` | `.lower()` | `.toLowerCase()` | `strings.ToLower()` |
| Header value trim | `.Trim()` | `.strip()` | `.trim()` | `strings.TrimSpace()` |
| Sort order | `StringComparison.Ordinal` | default Python sort | `< / >` operator | default Go `<` |
| Body null handling | `?? string.Empty` | `body or ""` | `body ?? ""` | used as-is (Go strings can't be null) |
| Timestamp format | `.ToString()` | `str(timestamp)` | `String(timestamp)` | `fmt.Sprintf("%d", timestamp)` |
| Base64 decoding | `Convert.FromBase64String` | `base64.b64decode(..., validate=True)` | `Buffer.from(stripped, "base64")` | `base64.StdEncoding.DecodeString` |

**One subtle difference:** Python's `body or ""` at `canonical.py:42` treats `body=0` or `body=False` as empty string. But the parameter type is `str`, so this should never happen in practice. TypeScript's `body ?? ""` only catches `null`/`undefined`, not empty string -- but again the parameter is typed as `string`.

The 20 cross-language test vectors all verify identical canonical strings and signatures across all 4 SDKs, covering edge cases like Unicode bodies, empty headers, header trimming, and X-Harden-* exclusions.

### Verdict

No exploitable cross-language divergence found. The test vectors are well-designed and cover the important edge cases.

---

## Attack 11: Downgrade Attack -- Forcing Middleware to Skip Validation

**Severity:** LOW
**Exploitability:** Requires misconfiguration
**Affected SDKs:** None -- all fail closed

### Analysis

I traced the code path when no secret is available:

| SDK | No resolver + No clients + No global secret | Behavior |
|-----|------|------|
| C# | `effectiveSecret` is null/empty | Returns 401 `"no_secret"` (line 86-93) |
| Python | `effective_secret` is falsy | Returns 401 `"no_secret"` (line 94-106) |
| Go | `config.SharedSecretBase64` is empty | Returns 401 `"no_secret"` (line 130-135) |
| TypeScript | `config.sharedSecretBase64` is falsy | Returns 401 `"no_secret"` (line 148-151) |

**All SDKs fail closed.** There is no code path where a request is passed through without validation.

**Edge case: secret resolver returns empty string.** In all SDKs, an empty string from the resolver falls through to the next resolution step (clients dict, then global secret). If all return empty, it's a 401.

---

## Attack 12: Secret Resolver Bypass

**Severity:** MEDIUM
**Exploitability:** Low -- requires async exception in specific SDKs
**Affected SDKs:** TypeScript (Express) -- edge case

### Analysis

**TypeScript Express middleware synchronous resolver path:**

At `middleware/express.ts:154-165`:
```typescript
if (secretResolver) {
  const result = secretResolver(req);
  if (result instanceof Promise) {
    result.then(resolveAndValidate).catch((err: unknown) => {
      next(err);
    });
    return;
  }
  resolveAndValidate(result);
} else {
  resolveAndValidate(null);
}
```

If `secretResolver` is a synchronous function that throws, the exception propagates up and is NOT caught by the middleware. This would crash the Express request handler (unless Express has a top-level try-catch, which it does for synchronous middleware).

However, Express middleware that throws synchronously is caught by Express's try-catch at the router level, resulting in a 500 error. So this fails **closed** but with a less informative error than the Promise rejection path.

**All other SDKs** handle resolver errors gracefully (Go returns a structured error, Python/C# let exceptions propagate to the framework's error handler).

---

## Summary of Findings

| # | Attack | Severity | Exploitable? | Status |
|---|--------|----------|-------------|--------|
| 1 | Canonical string newline injection | HIGH | Medium (non-HTTP contexts) | Open |
| 2 | Replay within tolerance window | MEDIUM | High (by design) | By design -- document |
| 3 | Client ID spoofing (includeXHeaders=false) | HIGH | High (misconfiguration) | Open |
| 4 | Secret resolver error leaks (Go) | MEDIUM | Low | Open |
| 5 | Timing side channels | LOW | Very Low | Acceptable |
| 6 | Key material in memory (Python) | LOW | Very Low | Acceptable (language limitation) |
| 7 | Body manipulation (Express) | MEDIUM | Mitigated | Defended |
| 8 | Multi-value header semantics | LOW | Low | Acceptable |
| 9 | Env var injection | INFO | Requires env control | By design |
| 10 | Cross-language divergence | LOW | None found | Clean |
| 11 | Downgrade / skip validation | LOW | None found | All fail closed |
| 12 | Secret resolver exception handling | MEDIUM | Low | Edge case in TS |

---

## Prioritized Recommendations

### Must Fix (before any security claims in marketing)

1. **Attack 1 -- Newline injection:** Add validation in all 4 canonical string builders that `path` does not contain `\n`. Either reject or replace with an escaped form. Same for header names/values (header values could contain newlines in theory).

2. **Attack 3 -- Always sign X-Harden-Client-Id:** Change the `_select_headers` logic in all 4 SDKs to always include `X-Harden-Client-Id` if present, regardless of `includeXHeaders` setting. The code already treats it as special (the `X-Harden-*` exclusion carve-out) -- extend this to always-include.

### Should Fix

3. **Attack 4 -- Go error message leak:** Replace `err.Error()` in Go `middleware.go:102` with a generic message. Log the full error server-side.

4. **Attack 2 -- Document replay risk:** Add a "Security Considerations" section to the README explicitly stating that HardenHMAC does NOT provide replay protection and applications must implement their own idempotency.

### Nice to Have

5. **Python key zeroing:** Investigate using `ctypes.memset` or `bytearray` for best-effort key zeroing in Python, even if imperfect.

6. **TypeScript Express sync throw:** Wrap the synchronous `secretResolver` call in a try-catch for consistent error handling.
