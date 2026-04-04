# Contributing to HardenHMAC

Thank you for your interest in contributing to HardenHMAC. This guide explains how to report issues, suggest improvements, and submit pull requests.

## Reporting Issues

Open an issue on [GitHub Issues](https://github.com/HardenLabs/HardenHMAC/issues) with:

- A clear, descriptive title
- Steps to reproduce the problem
- Expected vs actual behavior
- Which SDK(s) are affected (C#, Python, TypeScript, Go)
- Language/runtime version (e.g., .NET 8, Python 3.12, Node 20, Go 1.21)

For security vulnerabilities, **do not open a public issue**. Email security@hardenlabs.com instead.

## Development Setup

Clone the repository and install the tools for whichever SDK(s) you plan to work on:

| SDK | Requirements |
|-----|-------------|
| C# | .NET 8 SDK |
| Python | Python 3.10+ with pip |
| TypeScript | Node.js 20+ with npm |
| Go | Go 1.21+ |

### Running Tests

```bash
# C#
cd sdk/csharp && dotnet test

# Python
pip install -e "sdk/python[fastapi,dev]"
cd sdk/python && pytest tests/ -v

# TypeScript
cd sdk/typescript/packages/hmac && npm ci && npm run build && npx vitest run

# Go
cd sdk/go && go test ./... -v

# Cross-language integration tests (requires all 4 SDKs)
cd tests/integration && bash run.sh
```

All SDK tests must pass before submitting a PR.

## Submitting Pull Requests

1. **Fork the repository** and create a branch from `main`.
2. **Make your changes.** Keep the scope focused -- one fix or feature per PR.
3. **Add or update tests.** If your change affects the canonical string or signature, add entries to `tests/cross-language/test-vectors.json`.
4. **Run the tests** for every SDK affected by your change. Cross-language changes require all four SDKs to pass.
5. **Open a pull request** against `main` with:
   - A clear title (under 70 characters)
   - A summary of what changed and why
   - Which SDKs are affected

### PR Requirements

- All CI checks must pass (C#, Python, TypeScript, Go, cross-language vectors)
- New features must include tests
- Changes to the canonical string format must update `docs/CANONICAL-STRING-SPEC.md`
- Keep commits focused and well-described

### What Makes a Good PR

- Fixes a reported issue or addresses a clear need
- Follows existing code patterns in the relevant SDK
- Doesn't introduce unnecessary dependencies
- Includes tests that fail without the change and pass with it

## Cross-Language Consistency

HardenHMAC guarantees identical signatures across all four SDKs. This is enforced by a shared test vector suite at `tests/cross-language/test-vectors.json`.

**The test vectors are authoritative.** If an implementation produces a different result than the vectors specify, the implementation is wrong -- not the vectors.

When adding a new feature that affects signing:

1. Add test vectors to `test-vectors.json` first
2. Implement in all four SDKs
3. Verify all SDKs produce identical results against the new vectors

## Code Style

Follow the conventions already established in each SDK. There are no strict linting rules enforced, but consistency within each SDK matters more than personal preference.

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
