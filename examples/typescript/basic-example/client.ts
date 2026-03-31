/**
 * Basic client that signs requests with HardenHMAC.
 *
 * Run: npx tsx client.ts
 */

import {
  createHmacConfig,
  noneSignedHeadersConfig,
  signRequestHeaders,
} from "@hardenlabs/hmac";

// Same shared secret as the server
const sharedSecret = Buffer.from("my-shared-secret-key-32-bytes!!").toString(
  "base64"
);

const config = createHmacConfig(sharedSecret, {
  signedHeaders: noneSignedHeadersConfig(),
});

const BASE_URL = "http://localhost:3000";

async function signedGet(path: string): Promise<Response> {
  const headers = signRequestHeaders(config, "GET", path);
  return fetch(`${BASE_URL}${path}`, { headers });
}

async function signedPost(
  path: string,
  data: Record<string, unknown>
): Promise<Response> {
  const body = JSON.stringify(data);
  const existingHeaders: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const hmacHeaders = signRequestHeaders(
    config,
    "POST",
    path,
    body,
    existingHeaders
  );
  return fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { ...existingHeaders, ...hmacHeaders },
    body,
  });
}

async function main(): Promise<void> {
  console.log("GET /api/hello:");
  const getResp = await signedGet("/api/hello");
  console.log(`  Status: ${getResp.status}`);
  console.log(`  Body:   ${JSON.stringify(await getResp.json())}`);

  console.log("\nPOST /api/echo:");
  const postResp = await signedPost("/api/echo", {
    greeting: "Hello, world!",
  });
  console.log(`  Status: ${postResp.status}`);
  console.log(`  Body:   ${JSON.stringify(await postResp.json())}`);
}

main().catch(console.error);
