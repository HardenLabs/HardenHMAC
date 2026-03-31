import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, it, expect } from "vitest";
import { buildCanonicalString } from "../src/canonical.js";
import type { SignedHeadersConfig } from "../src/config.js";
import { sign, verify } from "../src/signing.js";

interface TestVector {
  id: string;
  description: string;
  method: string;
  path: string;
  body: string;
  timestamp: number;
  signed_headers_config: {
    include_authorization: boolean;
    include_x_headers: boolean;
    additional_headers: string[];
    exclude_headers: string[];
  };
  request_headers: Record<string, string>;
  shared_secret_base64: string;
  expected_canonical_string: string;
  expected_signature: string;
}

interface TestVectorFile {
  version: string;
  description: string;
  vectors: TestVector[];
}

function loadVectors(): TestVector[] {
  const vectorPath = resolve(
    __dirname,
    "../../../../../tests/cross-language/test-vectors.json"
  );
  const content = readFileSync(vectorPath, "utf-8");
  const file = JSON.parse(content) as TestVectorFile;
  return file.vectors;
}

function mapConfig(
  config: TestVector["signed_headers_config"]
): SignedHeadersConfig {
  return {
    includeAuthorization: config.include_authorization,
    includeXHeaders: config.include_x_headers,
    additionalHeaders: config.additional_headers,
    excludeHeaders: config.exclude_headers,
  };
}

describe("cross-language test vectors", () => {
  const vectors = loadVectors();

  it("all vectors produce expected canonical string", () => {
    for (const vector of vectors) {
      const config = mapConfig(vector.signed_headers_config);
      const canonical = buildCanonicalString({
        method: vector.method,
        path: vector.path,
        body: vector.body,
        timestamp: vector.timestamp,
        signedHeadersConfig: config,
        requestHeaders: vector.request_headers,
      });
      expect(canonical, `Vector '${vector.id}' canonical string mismatch`).toBe(
        vector.expected_canonical_string
      );
    }
  });

  it("all vectors produce expected signature", () => {
    for (const vector of vectors) {
      const config = mapConfig(vector.signed_headers_config);
      const canonical = buildCanonicalString({
        method: vector.method,
        path: vector.path,
        body: vector.body,
        timestamp: vector.timestamp,
        signedHeadersConfig: config,
        requestHeaders: vector.request_headers,
      });
      const signature = sign(vector.shared_secret_base64, canonical);
      expect(signature, `Vector '${vector.id}' signature mismatch`).toBe(
        vector.expected_signature
      );
    }
  });

  it("all vectors verify successfully", () => {
    for (const vector of vectors) {
      const result = verify(
        vector.shared_secret_base64,
        vector.expected_canonical_string,
        vector.expected_signature
      );
      expect(result, `Vector '${vector.id}' should verify`).toBe(true);
    }
  });
});
