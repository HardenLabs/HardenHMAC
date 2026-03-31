/**
 * Basic Express server with HardenHMAC validation.
 *
 * Run: npx tsx server.ts
 */

import express from "express";
import {
  createHmacConfig,
  hardenHmacMiddleware,
  noneSignedHeadersConfig,
} from "@hardenlabs/hmac";

// Shared secret (in production, load from environment/secrets manager)
const sharedSecret = Buffer.from("my-shared-secret-key-32-bytes!!").toString(
  "base64"
);

const config = createHmacConfig(sharedSecret, {
  signedHeaders: noneSignedHeadersConfig(),
  timestampToleranceSeconds: 30,
});

const app = express();
app.use(express.text({ type: "*/*" }));
app.use(hardenHmacMiddleware(config));

app.get("/api/hello", (_req, res) => {
  res.json({ message: "Hello from HardenHMAC!" });
});

app.post("/api/echo", (req, res) => {
  res.json({ echo: req.body });
});

app.listen(3000, () => {
  console.log("Server listening on http://localhost:3000");
});
