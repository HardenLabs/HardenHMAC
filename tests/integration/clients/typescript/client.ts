import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import {
  signRequestHeaders,
  createHmacConfig,
  CLIENT_ID_HEADER,
} from "@hardenlabs/hmac";

const __dirname = dirname(fileURLToPath(import.meta.url));

const CLIENT_ID = "typescript-client";

// Load config.json
const configPath = resolve(__dirname, "..", "..", "config.json");
const rawConfig = JSON.parse(readFileSync(configPath, "utf-8"));

const mySecret: string = rawConfig.clients[CLIENT_ID].sharedSecret;
const ports: Record<string, number> = rawConfig.ports;

const hmacConfig = createHmacConfig(mySecret);

const results: string[] = [];
const servers = ["csharp", "python", "typescript"];

for (const server of servers) {
  const port = ports[server];
  if (port === undefined) continue;

  const serverName = `${server}-server`;
  const baseUrl = `http://localhost:${port}`;

  // GET /api/hello
  try {
    const path = "/api/hello";
    const existingHeaders: Record<string, string> = {
      [CLIENT_ID_HEADER]: CLIENT_ID,
    };
    const sigHeaders = signRequestHeaders(
      hmacConfig,
      "GET",
      path,
      "",
      existingHeaders
    );
    const headers = { ...existingHeaders, ...sigHeaders };

    const resp = await fetch(`${baseUrl}${path}`, { headers });
    if (resp.status === 200) {
      results.push(`PASS ${CLIENT_ID} -> ${serverName} GET /api/hello (${resp.status})`);
    } else {
      const body = await resp.text();
      results.push(`FAIL ${CLIENT_ID} -> ${serverName} GET /api/hello (${resp.status}): ${body}`);
    }
  } catch (e) {
    results.push(`FAIL ${CLIENT_ID} -> ${serverName} GET /api/hello (ERR): ${e}`);
  }

  // POST /api/echo
  try {
    const path = "/api/echo";
    const body = JSON.stringify({ from: CLIENT_ID, test: "integration" });
    const existingHeaders: Record<string, string> = {
      [CLIENT_ID_HEADER]: CLIENT_ID,
      "Content-Type": "application/json",
    };
    const sigHeaders = signRequestHeaders(
      hmacConfig,
      "POST",
      path,
      body,
      existingHeaders
    );
    const headers = { ...existingHeaders, ...sigHeaders };

    const resp = await fetch(`${baseUrl}${path}`, {
      method: "POST",
      headers,
      body,
    });
    if (resp.status === 200) {
      results.push(`PASS ${CLIENT_ID} -> ${serverName} POST /api/echo (${resp.status})`);
    } else {
      const respBody = await resp.text();
      results.push(`FAIL ${CLIENT_ID} -> ${serverName} POST /api/echo (${resp.status}): ${respBody}`);
    }
  } catch (e) {
    results.push(`FAIL ${CLIENT_ID} -> ${serverName} POST /api/echo (ERR): ${e}`);
  }
}

for (const result of results) {
  console.log(result);
}

process.exit(results.some((r) => r.startsWith("FAIL")) ? 1 : 0);
