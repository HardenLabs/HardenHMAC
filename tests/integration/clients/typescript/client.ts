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
} from "@hardenlabs/hmac";
import type { HttpAdapter } from "@hardenlabs/hmac";

const __dirname = dirname(fileURLToPath(import.meta.url));

const CLIENT_ID = "typescript-client";

const configPath = resolve(__dirname, "..", "..", "config.json");
const rawConfig = JSON.parse(readFileSync(configPath, "utf-8"));

const mySecret: string = rawConfig.clients[CLIENT_ID].sharedSecret;
const ports: Record<string, number> = rawConfig.ports;

const servers = ["csharp", "python", "typescript", "go"];
const hmacConfig = createHmacConfig(mySecret);

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
): Promise<void> {
  try {
    const headers: Record<string, string> = {
      [CLIENT_ID_HEADER.toLowerCase()]: CLIENT_ID,
    };
    if (body) headers["content-type"] = "application/json";

    const sigHeaders = signRequestHeaders(hmacConfig, method, path, body ?? "", headers);
    const merged = { ...headers, ...sigHeaders };

    const resp = await adapter.request(`${baseUrl}${path}`, method, body, merged);
    if (resp.status === 200) {
      results.push(`PASS ${tag} -> ${serverName} ${method} ${path} (${resp.status})`);
    } else {
      const text = await resp.text();
      results.push(`FAIL ${tag} -> ${serverName} ${method} ${path} (${resp.status}): ${text}`);
    }
  } catch (e: unknown) {
    if (isConnectionRefused(e) || isAxiosConnectionError(e)) {
      results.push(`SKIP ${tag} -> ${serverName} ${method} ${path} (server not running)`);
    } else {
      results.push(`FAIL ${tag} -> ${serverName} ${method} ${path} (ERR): ${e}`);
    }
  }
}

const fetchAdapter = new FetchAdapter();
const axiosAdapter = new AxiosAdapter(axios.create());

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
}

for (const result of results) {
  console.log(result);
}

process.exit(results.some((r) => r.startsWith("FAIL")) ? 1 : 0);
