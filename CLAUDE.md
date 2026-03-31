# HardenHMAC — Cross-Language HMAC-SHA256 Request Signing

## What This Is

A free, open-source, cross-language HMAC-SHA256 request signing library for service-to-service authentication. No server component, no key management, no state. The key differentiator is a defined canonical string format that is identical across C#, Python, and TypeScript implementations, guaranteed by a shared cross-language test vector suite.

**License:** Apache 2.0

## Package Names

- **NuGet:** `HardenLabs.Hmac`, `HardenLabs.Hmac.AspNetCore`
- **PyPI:** `hardenlabs-hmac`
- **npm:** `@hardenlabs/hmac`

## Build and Test Commands

```bash
# C# SDK
cd sdk/csharp && dotnet build HardenLabs.Hmac.sln
cd sdk/csharp && dotnet test HardenLabs.Hmac.Tests/

# Python SDK
cd sdk/python && pip install -e ".[dev]"
cd sdk/python && pytest tests/ -v

# TypeScript SDK
cd sdk/typescript/packages/hmac && npm install
cd sdk/typescript/packages/hmac && npm test
```

## Code Style

- **C#:** PascalCase for public members, camelCase for private/local. Nullable reference types enabled. Use `ILogger`, never `Console.WriteLine`. async/await for I/O operations.
- **Python:** snake_case for variables, functions, modules. Type hints required on all function signatures. Black formatting. Docstrings for public functions/classes.
- **TypeScript:** camelCase for variables/functions, PascalCase for types/interfaces. Strict mode enabled. No `any` types.

## Project Structure

```
/sdk/
  /csharp/                              # .NET 8.0 solution
    HardenLabs.Hmac/                    # Core library
    HardenLabs.Hmac.AspNetCore/         # ASP.NET Core middleware
    HardenLabs.Hmac.Tests/              # xUnit tests
  /python/
    src/hardenlabs_hmac/                # Core + FastAPI middleware
    tests/                              # pytest tests
  /typescript/
    packages/hmac/                      # Core + Express middleware (vitest)
/tests/
  /cross-language/
    test-vectors.json                   # Shared test vectors (source of truth)
/docs/
  /analysis/                            # Strategy documents (DO NOT MODIFY)
  ARCHITECTURE.md
  CANONICAL-STRING-SPEC.md
/examples/
  /csharp/BasicExample/
  /python/basic_example/
  /typescript/basic-example/
```

## Canonical String Format (v1.0)

```
METHOD\nPATH\nSIGNED_HEADERS\nBODY\nTIMESTAMP
```

- **METHOD**: HTTP method, UPPERCASE
- **PATH**: Request path including query string, as-is (no normalization)
- **SIGNED_HEADERS**: Headers sorted alphabetically by lowercase name, format `name:trimmed_value`, joined by `\n`. Empty string if no signed headers configured.
- **BODY**: Request body as string. Empty string if no body.
- **TIMESTAMP**: Unix timestamp in seconds (integer as string)

### Signature Computation

```
HMAC-SHA256(shared_secret_bytes, canonical_string_utf8) -> lowercase hex (64 chars)
```

- Shared secret: Base64-encoded byte array provided by configuration
- Output: Lowercase hexadecimal string, exactly 64 characters

### HTTP Headers

- `X-Harden-Signature` — the 64-char hex HMAC signature
- `X-Harden-Timestamp` — Unix timestamp in seconds
- `X-Harden-Signed-Headers` — semicolon-separated sorted list of signed header names (only present if headers are signed)

## Configuration Patterns

### Multi-Target Configuration
- `HmacConfig.Targets` (C#) / `HmacConfig.targets` (Python/TS) holds named service targets
- Each target has `BaseUrl`, `SharedSecret`, and optional overrides for `SignedHeaders` and `TimestampToleranceSeconds`
- Per-target settings override global defaults: `target.field ?? config.field`
- `config.ForTarget(name)` / `config.for_target(name)` / `configForTarget(config, name)` resolves a fully-merged config

### Environment Variable Loading
- All SDKs support `HARDEN_HMAC_` prefix with `__` separator for nesting
- C#: native `IConfiguration` binding via `AddHardenHmac(IConfiguration)`
- Python: `HmacConfig.from_env()` with optional python-dotenv
- TypeScript: `fromEnv()` with optional dotenv peer dependency
- Target names in env vars use `UPPER_SNAKE_CASE` which maps to `lower-kebab-case`

### Client Factory Pattern
- C#: `IHardenHmacClientFactory` (registered by `AddHardenHmac`)
- Python: `HmacClientFactory(config)` with `create_client()` / `create_sync_client()`
- TypeScript: `createHmacClientFactory(config)` with `createFetch(targetName)`

### Secret Resolver (Server-Side)
- Middleware accepts optional `secretResolver` callback for multi-tenant scenarios
- Resolver is called first; if it returns null, falls back to `config.SharedSecretBase64`
- If neither has a secret, middleware returns 401 `no_secret`

## Critical Rules

1. **Cross-language test vectors are authoritative.** If an implementation disagrees with the vectors, the implementation is wrong. Fix the implementation, never the vectors.
2. **Constant-time comparison** for ALL signature verification. No exceptions.
3. **No server component.** This library has no state, no key management, no key rotation, no replay protection. Those are the implementer's responsibility.
4. **No emojis** in log messages or comments.
5. **Do not modify** files in `docs/analysis/` — those are existing strategy documents.
6. Existing implementations must pass ALL test vectors before any PR is merged.
7. **Backwards compatibility required.** Single-secret mode (no targets) must continue to work exactly as before.
