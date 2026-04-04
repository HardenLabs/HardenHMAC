/**
 * TypeScript multi-target HMAC integration test client — exercises HmacClientFactory.
 */

import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import {
  createHmacConfig,
  createHmacClientFactory,
  signRequestHeaders,
  CLIENT_ID_HEADER,
  FetchAdapter,
} from "@hardenlabs/hmac";
import type { HmacTargetConfig } from "@hardenlabs/hmac";

const __dirname = dirname(fileURLToPath(import.meta.url));

const configPath = resolve(__dirname, "..", "..", "config.json");
const rawConfig = JSON.parse(readFileSync(configPath, "utf-8"));

const results: string[] = [];

function isConnectionRefused(e: unknown): boolean {
  if (e instanceof Error && e.cause) {
    return (e.cause as NodeJS.ErrnoException).code === "ECONNREFUSED";
  }
  return false;
}

// Build targets from config
const targets: Record<string, HmacTargetConfig> = {};
for (const [name, t] of Object.entries(rawConfig.multiTargetTests.targets)) {
  const target = t as { baseUrl: string; sharedSecret: string };
  targets[name] = {
    baseUrl: target.baseUrl,
    sharedSecret: target.sharedSecret,
  };
}

const config = createHmacConfig("", { targets });
const factory = createHmacClientFactory(config);

// 1. Multi-target: call each server with correct target-specific secret
for (const [targetName, target] of Object.entries(targets)) {
  const serverName = targetName.replace("-client", "-server");
  const client = factory.createClient(targetName);

  // GET /api/hello
  try {
    const resp = await client.get("/api/hello");
    if (resp.status === 200) {
      results.push(`PASS typescript-multitarget -> ${serverName} GET /api/hello (${resp.status})`);
    } else {
      const text = await resp.text();
      results.push(`FAIL typescript-multitarget -> ${serverName} GET /api/hello (${resp.status}): ${text}`);
    }
  } catch (e: unknown) {
    if (isConnectionRefused(e)) {
      results.push(`SKIP typescript-multitarget -> ${serverName} GET /api/hello (server not running)`);
      results.push(`SKIP typescript-multitarget -> ${serverName} POST /api/echo (server not running)`);
      continue;
    }
    results.push(`FAIL typescript-multitarget -> ${serverName} GET /api/hello (ERR): ${e}`);
    continue;
  }

  // POST /api/echo
  try {
    const postBody = JSON.stringify({ from: targetName, test: "multitarget" });
    const resp = await client.post("/api/echo", postBody, {
      headers: { "content-type": "application/json" },
    });
    if (resp.status === 200) {
      results.push(`PASS typescript-multitarget -> ${serverName} POST /api/echo (${resp.status})`);
    } else {
      const text = await resp.text();
      results.push(`FAIL typescript-multitarget -> ${serverName} POST /api/echo (${resp.status}): ${text}`);
    }
  } catch (e: unknown) {
    if (isConnectionRefused(e)) {
      results.push(`SKIP typescript-multitarget -> ${serverName} POST /api/echo (server not running)`);
    } else {
      results.push(`FAIL typescript-multitarget -> ${serverName} POST /api/echo (ERR): ${e}`);
    }
  }
}

// 2. Cross-client test: send as two different clients to the SAME server (python-server, port 9101)
const crossBase = rawConfig.multiTargetTests.targets["python-client"].baseUrl;
const crossServer = "python-server";
const fetchAdapter = new FetchAdapter();

for (const crossId of ["csharp-client", "go-client"]) {
  const crossSecret: string = rawConfig.multiTargetTests.targets[crossId].sharedSecret;
  const crossConfig = createHmacConfig(crossSecret);

  try {
    const headers: Record<string, string> = {
      [CLIENT_ID_HEADER.toLowerCase()]: crossId,
    };
    const sigHeaders = signRequestHeaders(crossConfig, "GET", "/api/hello", "", headers);
    const merged = { ...headers, ...sigHeaders };
    const resp = await fetchAdapter.request(`${crossBase}/api/hello`, "GET", undefined, merged);
    if (resp.status === 200) {
      results.push(`PASS typescript-multitarget/cross(${crossId}) -> ${crossServer} GET /api/hello (${resp.status})`);
    } else {
      const text = await resp.text();
      results.push(`FAIL typescript-multitarget/cross(${crossId}) -> ${crossServer} GET /api/hello (${resp.status}): ${text}`);
    }
  } catch (e: unknown) {
    if (isConnectionRefused(e)) {
      results.push(`SKIP typescript-multitarget/cross(${crossId}) -> ${crossServer} GET /api/hello (server not running)`);
    } else {
      results.push(`FAIL typescript-multitarget/cross(${crossId}) -> ${crossServer} GET /api/hello (ERR): ${e}`);
    }
  }
}

// 3. Negative test: wrong secret for client ID -> expect 4xx
{
  const wrongSecret: string = rawConfig.multiTargetTests.targets["go-client"].sharedSecret;
  const wrongConfig = createHmacConfig(wrongSecret);

  try {
    const headers: Record<string, string> = {
      [CLIENT_ID_HEADER.toLowerCase()]: "csharp-client", // claim to be csharp-client
    };
    const sigHeaders = signRequestHeaders(wrongConfig, "GET", "/api/hello", "", headers);
    const merged = { ...headers, ...sigHeaders };
    const resp = await fetchAdapter.request(`${crossBase}/api/hello`, "GET", undefined, merged);
    if (resp.status >= 400 && resp.status < 500) {
      results.push(`PASS typescript-multitarget/wrong-secret -> ${crossServer} GET /api/hello (${resp.status})`);
    } else {
      const text = await resp.text();
      results.push(`FAIL typescript-multitarget/wrong-secret -> ${crossServer} GET /api/hello (expected 4xx, got ${resp.status}): ${text}`);
    }
  } catch (e: unknown) {
    if (isConnectionRefused(e)) {
      results.push(`SKIP typescript-multitarget/wrong-secret -> ${crossServer} GET /api/hello (server not running)`);
    } else {
      results.push(`FAIL typescript-multitarget/wrong-secret -> ${crossServer} GET /api/hello (ERR): ${e}`);
    }
  }
}

for (const result of results) {
  console.log(result);
}

process.exit(results.some((r) => r.startsWith("FAIL")) ? 1 : 0);
