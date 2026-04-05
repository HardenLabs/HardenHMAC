/**
 * TypeScript HMAC integration test client — exercises both fetch and axios adapters.
 */

import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import axios from "axios";
import {
  createHmacConfig,
  signRequestHeaders,
  CLIENT_ID_HEADER,
  FetchAdapter,
  AxiosAdapter,
  noneSignedHeadersConfig,
} from "@hardenlabs/hmac";
import type { HttpAdapter } from "@hardenlabs/hmac";

const __dirname = dirname(fileURLToPath(import.meta.url));

const CLIENT_ID = "typescript-client";

const configPath = resolve(__dirname, "..", "..", "config.json");
const rawConfig = JSON.parse(readFileSync(configPath, "utf-8"));

const mySecret: string = rawConfig.clients[CLIENT_ID].sharedSecret;
const ports: Record<string, number> = rawConfig.ports;
const sharedSecret: string = rawConfig.sharedSecret;
const resolverPorts: Record<string, number> = rawConfig.resolverPorts ?? {};
const globalPorts: Record<string, number> = rawConfig.globalPorts ?? {};

const servers = ["csharp", "python", "typescript", "go"];
const hmacConfig = createHmacConfig(mySecret);
const noneHmacConfig = createHmacConfig(mySecret, { signedHeaders: noneSignedHeadersConfig() });

const results: string[] = [];

function isConnectionRefused(e: unknown): boolean {
  if (e instanceof Error && e.cause) {
    return (e.cause as NodeJS.ErrnoException).code === "ECONNREFUSED";
  }
  return false;
}

function isAxiosConnectionError(e: unknown): boolean {
  return typeof e === "object" && e !== null && "code" in e &&
    (e as { code: string }).code === "ECONNREFUSED";
}

async function makeRequest(
  adapter: HttpAdapter,
  tag: string,
  serverName: string,
  baseUrl: string,
  method: string,
  path: string,
  body?: string,
  config?: ReturnType<typeof createHmacConfig>,
  options?: { clientId?: string | null; timestamp?: number; expect4xx?: boolean },
): Promise<void> {
  const cfg = config ?? hmacConfig;
  const clientId = options?.clientId === undefined ? CLIENT_ID : options.clientId;
  const expect4xx = options?.expect4xx ?? false;
  try {
    const headers: Record<string, string> = {};
    if (clientId) {
      headers[CLIENT_ID_HEADER.toLowerCase()] = clientId;
    }
    if (body !== undefined && body !== "") headers["content-type"] = "application/json";

    const sigHeaders = signRequestHeaders(cfg, method, path, body ?? "", headers, options?.timestamp);
    const merged = { ...headers, ...sigHeaders };

    const resp = await adapter.request(`${baseUrl}${path}`, method, body, merged);
    if (expect4xx) {
      if (resp.status >= 400 && resp.status < 500) {
        results.push(`PASS ${tag} -> ${serverName} ${method} ${path} (${resp.status})`);
      } else {
        const text = await resp.text();
        results.push(`FAIL ${tag} -> ${serverName} ${method} ${path} (expected 4xx, got ${resp.status}): ${text}`);
      }
    } else if (resp.status === 200) {
      results.push(`PASS ${tag} -> ${serverName} ${method} ${path} (${resp.status})`);
    } else {
      const text = await resp.text();
      results.push(`FAIL ${tag} -> ${serverName} ${method} ${path} (${resp.status}): ${text}`);
    }
  } catch (e: unknown) {
    if (isConnectionRefused(e) || isAxiosConnectionError(e)) {
      results.push(`SKIP ${tag} -> ${serverName} ${method} ${path} (server not running)`);
    } else if (expect4xx && typeof e === "object" && e !== null && "response" in e) {
      const axiosStatus = (e as { response: { status: number } }).response.status;
      if (axiosStatus >= 400 && axiosStatus < 500) {
        results.push(`PASS ${tag} -> ${serverName} ${method} ${path} (${axiosStatus})`);
      } else {
        results.push(`FAIL ${tag} -> ${serverName} ${method} ${path} (expected 4xx, got ${axiosStatus})`);
      }
    } else {
      results.push(`FAIL ${tag} -> ${serverName} ${method} ${path} (ERR): ${e}`);
    }
  }
}

const fetchAdapter = new FetchAdapter();
const axiosAdapter = new AxiosAdapter(axios.create());

async function makePlainRequest(
  tag: string,
  serverName: string,
  baseUrl: string,
  method: string,
  path: string,
  expectedStatus: number,
): Promise<void> {
  try {
    const resp = await fetch(`${baseUrl}${path}`, { method });
    const ok = expectedStatus === 0
      ? resp.status >= 400 && resp.status < 500
      : resp.status === expectedStatus;
    if (ok) {
      results.push(`PASS ${tag} -> ${serverName} ${method} ${path} (${resp.status})`);
    } else {
      const text = await resp.text();
      const expected = expectedStatus === 0 ? "4xx" : String(expectedStatus);
      results.push(`FAIL ${tag} -> ${serverName} ${method} ${path} (expected ${expected}, got ${resp.status}): ${text}`);
    }
  } catch (e: unknown) {
    if (isConnectionRefused(e)) {
      results.push(`SKIP ${tag} -> ${serverName} ${method} ${path} (server not running)`);
    } else {
      results.push(`FAIL ${tag} -> ${serverName} ${method} ${path} (ERR): ${e}`);
    }
  }
}

for (const server of servers) {
  const port = ports[server];
  if (port === undefined) continue;

  const serverName = `${server}-server`;
  const baseUrl = `http://localhost:${port}`;
  const postBody = JSON.stringify({ from: CLIENT_ID, test: "integration" });

  // Fetch adapter
  await makeRequest(fetchAdapter, "typescript-client/fetch", serverName, baseUrl, "GET", "/api/hello");
  await makeRequest(fetchAdapter, "typescript-client/fetch", serverName, baseUrl, "POST", "/api/echo", postBody);

  // Axios adapter
  await makeRequest(axiosAdapter, "typescript-client/axios", serverName, baseUrl, "GET", "/api/hello");
  await makeRequest(axiosAdapter, "typescript-client/axios", serverName, baseUrl, "POST", "/api/echo", postBody);

  // Granular validation tests (plain requests, no HMAC)
  await makePlainRequest(CLIENT_ID, serverName, baseUrl, "GET", "/health", 200);
  await makePlainRequest(`${CLIENT_ID}/nohmac`, serverName, baseUrl, "GET", "/api/hello", 0); // any 4xx

  // IT-3: Fallback secret (sign with sharedSecret, NO X-Harden-Client-Id)
  const fallbackConfig = createHmacConfig(sharedSecret);
  await makeRequest(fetchAdapter, "typescript-client/fetch/fallback", serverName, baseUrl, "GET", "/api/hello", undefined, fallbackConfig, { clientId: null });
  await makeRequest(axiosAdapter, "typescript-client/axios/fallback", serverName, baseUrl, "GET", "/api/hello", undefined, fallbackConfig, { clientId: null });

  // IT-4: Unknown client rejection
  const bogusSecret = btoa("wrong-secret-for-unknown-client!!!");
  const bogusConfig = createHmacConfig(bogusSecret);
  await makeRequest(fetchAdapter, "typescript-client/fetch/unknown-client", serverName, baseUrl, "GET", "/api/hello", undefined, bogusConfig, { clientId: "nonexistent-client", expect4xx: true });
  await makeRequest(axiosAdapter, "typescript-client/axios/unknown-client", serverName, baseUrl, "GET", "/api/hello", undefined, bogusConfig, { clientId: "nonexistent-client", expect4xx: true });

  // IT-5: Stale timestamp (300s in the past)
  const staleTs = Math.floor(Date.now() / 1000) - 300;
  await makeRequest(fetchAdapter, "typescript-client/fetch/stale-ts", serverName, baseUrl, "GET", "/api/hello", undefined, undefined, { timestamp: staleTs, expect4xx: true });
  await makeRequest(axiosAdapter, "typescript-client/axios/stale-ts", serverName, baseUrl, "GET", "/api/hello", undefined, undefined, { timestamp: staleTs, expect4xx: true });

  // IT-8: Empty body POST
  await makeRequest(fetchAdapter, "typescript-client/fetch/empty-body", serverName, baseUrl, "POST", "/api/echo", "");
  await makeRequest(axiosAdapter, "typescript-client/axios/empty-body", serverName, baseUrl, "POST", "/api/echo", "");

  // IT-9: Wrong SignedHeaders (client uses none, server uses default)
  // Include Authorization header so signed-headers difference actually matters
  const wrongHdrHeaders: Record<string, string> = {
    [CLIENT_ID_HEADER.toLowerCase()]: CLIENT_ID,
    authorization: "Bearer test",
  };
  const wrongSig = signRequestHeaders(noneHmacConfig, "GET", "/api/hello", "", wrongHdrHeaders);
  const wrongMerged = { ...wrongHdrHeaders, ...wrongSig };
  try {
    const wr = await fetchAdapter.request(`${baseUrl}/api/hello`, "GET", undefined, wrongMerged);
    if (wr.status >= 400 && wr.status < 500) {
      results.push(`PASS typescript-client/fetch/wrong-headers -> ${serverName} GET /api/hello (${wr.status})`);
    } else {
      results.push(`FAIL typescript-client/fetch/wrong-headers -> ${serverName} GET /api/hello (expected 4xx, got ${wr.status}): ${await wr.text()}`);
    }
  } catch (e: unknown) {
    if (isConnectionRefused(e)) results.push(`SKIP typescript-client/fetch/wrong-headers -> ${serverName} GET /api/hello (server not running)`);
    else results.push(`FAIL typescript-client/fetch/wrong-headers -> ${serverName} GET /api/hello (ERR): ${e}`);
  }
  try {
    const wr2 = await axiosAdapter.request(`${baseUrl}/api/hello`, "GET", undefined, wrongMerged);
    if (wr2.status >= 400 && wr2.status < 500) {
      results.push(`PASS typescript-client/axios/wrong-headers -> ${serverName} GET /api/hello (${wr2.status})`);
    } else {
      results.push(`FAIL typescript-client/axios/wrong-headers -> ${serverName} GET /api/hello (expected 4xx, got ${wr2.status}): ${await wr2.text()}`);
    }
  } catch (e: unknown) {
    if (isConnectionRefused(e) || isAxiosConnectionError(e)) results.push(`SKIP typescript-client/axios/wrong-headers -> ${serverName} GET /api/hello (server not running)`);
    else if (typeof e === "object" && e !== null && "response" in e) {
      const s = (e as { response: { status: number } }).response.status;
      if (s >= 400 && s < 500) results.push(`PASS typescript-client/axios/wrong-headers -> ${serverName} GET /api/hello (${s})`);
      else results.push(`FAIL typescript-client/axios/wrong-headers -> ${serverName} GET /api/hello (expected 4xx, got ${s})`);
    }
    else results.push(`FAIL typescript-client/axios/wrong-headers -> ${serverName} GET /api/hello (ERR): ${e}`);
  }

  // IT-10: Query string
  await makeRequest(fetchAdapter, "typescript-client/fetch/query", serverName, baseUrl, "GET", "/api/hello?foo=bar&baz=1");
  await makeRequest(axiosAdapter, "typescript-client/axios/query", serverName, baseUrl, "GET", "/api/hello?foo=bar&baz=1");
}

// ============================================================
// Shared-secret server tests
// ============================================================
const sharedPorts: Record<string, number> = rawConfig.sharedPorts ?? {};
const sharedHmacConfig = createHmacConfig(sharedSecret);

for (const server of servers) {
  const sharedPort = sharedPorts[server];
  if (sharedPort === undefined) continue;

  const serverName = `${server}-shared`;
  const baseUrl = `http://localhost:${sharedPort}`;
  const postBody = JSON.stringify({ from: CLIENT_ID, test: "integration-shared" });

  // Fetch adapter
  await makeRequest(fetchAdapter, "typescript-client/shared/fetch", serverName, baseUrl, "GET", "/api/hello", undefined, sharedHmacConfig);
  await makeRequest(fetchAdapter, "typescript-client/shared/fetch", serverName, baseUrl, "POST", "/api/echo", postBody, sharedHmacConfig);

  // Axios adapter
  await makeRequest(axiosAdapter, "typescript-client/shared/axios", serverName, baseUrl, "GET", "/api/hello", undefined, sharedHmacConfig);
  await makeRequest(axiosAdapter, "typescript-client/shared/axios", serverName, baseUrl, "POST", "/api/echo", postBody, sharedHmacConfig);
}

// ============================================================
// Resolver server tests (IT-6)
// ============================================================
for (const server of servers) {
  const resolverPort = resolverPorts[server];
  if (resolverPort === undefined) continue;

  const serverName = `${server}-resolver`;
  const baseUrl = `http://localhost:${resolverPort}`;
  const postBody = JSON.stringify({ from: CLIENT_ID, test: "integration-resolver" });

  await makeRequest(fetchAdapter, "typescript-client/fetch", serverName, baseUrl, "GET", "/api/hello");
  await makeRequest(fetchAdapter, "typescript-client/fetch", serverName, baseUrl, "POST", "/api/echo", postBody);
  await makeRequest(axiosAdapter, "typescript-client/axios", serverName, baseUrl, "GET", "/api/hello");
  await makeRequest(axiosAdapter, "typescript-client/axios", serverName, baseUrl, "POST", "/api/echo", postBody);
}

// ============================================================
// Global middleware server tests (IT-7)
// ============================================================
for (const server of servers) {
  const globalPort = globalPorts[server];
  if (globalPort === undefined) continue;

  const serverName = `${server}-global`;
  const baseUrl = `http://localhost:${globalPort}`;
  const postBody = JSON.stringify({ from: CLIENT_ID, test: "integration-global" });

  // Signed requests should succeed
  await makeRequest(fetchAdapter, "typescript-client/fetch", serverName, baseUrl, "GET", "/api/hello");
  await makeRequest(fetchAdapter, "typescript-client/fetch", serverName, baseUrl, "POST", "/api/echo", postBody);
  await makeRequest(axiosAdapter, "typescript-client/axios", serverName, baseUrl, "GET", "/api/hello");
  await makeRequest(axiosAdapter, "typescript-client/axios", serverName, baseUrl, "POST", "/api/echo", postBody);

  // Signed GET /health should succeed (global mode protects ALL routes)
  await makeRequest(fetchAdapter, "typescript-client/fetch", serverName, baseUrl, "GET", "/health");
  await makeRequest(axiosAdapter, "typescript-client/axios", serverName, baseUrl, "GET", "/health");

  // Unsigned GET /health should be rejected (global mode protects ALL routes)
  await makePlainRequest(`${CLIENT_ID}/nohmac`, serverName, baseUrl, "GET", "/health", 0);
}

for (const result of results) {
  console.log(result);
}

process.exit(results.some((r) => r.startsWith("FAIL")) ? 1 : 0);
