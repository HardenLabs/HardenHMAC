import express from "express";
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import {
  createHmacValidateMiddleware,
  defaultSignedHeadersConfig,
  DEFAULT_TIMESTAMP_TOLERANCE_SECONDS,
  type HmacClientIdentity,
  type HmacConfig,
} from "@hardenlabs/hmac";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Load config.json
const configPath = resolve(__dirname, "..", "..", "config.json");
const rawConfig = JSON.parse(readFileSync(configPath, "utf-8"));

const hmacMode = process.env.HMAC_MODE;

let port: number;
let hmacConfig: HmacConfig;

if (hmacMode === "shared") {
  port = rawConfig.sharedPorts.typescript;
  hmacConfig = {
    sharedSecretBase64: rawConfig.sharedSecret,
    clients: {},
    signedHeaders: defaultSignedHeadersConfig(),
    timestampToleranceSeconds: DEFAULT_TIMESTAMP_TOLERANCE_SECONDS,
  };
} else {
  port = rawConfig.ports.typescript;

  // Build clients dictionary
  const clients: Record<string, HmacClientIdentity> = {};
  for (const [name, data] of Object.entries(rawConfig.clients)) {
    clients[name] = { sharedSecret: (data as { sharedSecret: string }).sharedSecret };
  }

  hmacConfig = {
    sharedSecretBase64: "",
    clients,
    signedHeaders: defaultSignedHeadersConfig(),
    timestampToleranceSeconds: DEFAULT_TIMESTAMP_TOLERANCE_SECONDS,
  };
}

const app = express();

// Parse ALL content types as raw text for HMAC verification
app.use(express.text({ type: "*/*" }));

// Per-route HMAC validation middleware
const hmacValidate = createHmacValidateMiddleware(hmacConfig);

// Protected endpoints — require HMAC validation
app.get("/api/hello", hmacValidate, (_req, res) => {
  res.json({ message: "hello from typescript" });
});

app.post("/api/echo", hmacValidate, (req, res) => {
  let parsed: unknown;
  try {
    parsed = JSON.parse(req.body as string);
  } catch {
    parsed = req.body;
  }
  res.json({ echo: parsed, language: "typescript" });
});

// Unprotected endpoint — no middleware, no HMAC required
app.get("/health", (_req, res) => {
  res.json({ status: "healthy", language: "typescript" });
});

app.listen(port, "0.0.0.0", () => {
  console.log(`TypeScript server listening on port ${port}`);
});
