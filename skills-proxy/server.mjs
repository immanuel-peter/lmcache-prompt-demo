import http from "node:http";
import { URL } from "node:url";

const PORT = Number(process.env.PORT || 8787);
const SKILLS_BASE = "https://skills.sh/api/v1";
const TEAM = process.env.VERCEL_ORG_ID || "";
const PROJECT = process.env.VERCEL_PROJECT_ID || "";
const ACCESS_TOKEN = process.env.VERCEL_TOKEN || "";

let cachedToken = "";
let cachedExpiryMs = 0;

function decodeJwtExpiry(token) {
  const payload = token.split(".")[1];
  if (!payload) {
    return Date.now() + 60 * 60 * 1000;
  }
  const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(
    normalized.length + ((4 - (normalized.length % 4)) % 4),
    "=",
  );
  const claims = JSON.parse(Buffer.from(padded, "base64").toString("utf8"));
  if (typeof claims.exp === "number") {
    return claims.exp * 1000;
  }
  return Date.now() + 60 * 60 * 1000;
}

async function bearerToken() {
  const refreshBufferMs = 5 * 60 * 1000;
  const now = Date.now();
  if (cachedToken && now < cachedExpiryMs - refreshBufferMs) {
    return cachedToken;
  }

  const mintUrl = new URL(
    `https://api.vercel.com/v1/projects/${PROJECT}/token`,
  );
  mintUrl.searchParams.set("source", "skills-proxy");
  if (TEAM) {
    mintUrl.searchParams.set("teamId", TEAM);
  }

  const response = await fetch(mintUrl, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${ACCESS_TOKEN}`,
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(
      `Vercel OIDC mint failed (${response.status}): ${detail || response.statusText}`,
    );
  }

  const body = await response.json();
  if (!body?.token || typeof body.token !== "string") {
    throw new Error("Vercel OIDC mint returned an invalid token payload.");
  }

  cachedToken = body.token;
  cachedExpiryMs = decodeJwtExpiry(cachedToken);
  return cachedToken;
}

function sendJson(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(payload),
  });
  res.end(payload);
}

async function proxyToSkills(req, res, upstreamPath, search) {
  if (!TEAM || !PROJECT || !ACCESS_TOKEN) {
    sendJson(res, 503, {
      error: "skills_proxy_unconfigured",
      message: "Set VERCEL_TOKEN, VERCEL_ORG_ID, and VERCEL_PROJECT_ID.",
    });
    return;
  }

  let token;
  try {
    token = await bearerToken();
  } catch (error) {
    sendJson(res, 502, {
      error: "oidc_token_failed",
      message: error instanceof Error ? error.message : "Failed to mint OIDC token.",
    });
    return;
  }

  const target = new URL(`${SKILLS_BASE}${upstreamPath}`);
  if (search) {
    target.search = search;
  }

  const upstream = await fetch(target, {
    method: req.method,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
  });

  const body = await upstream.text();
  res.writeHead(upstream.status, {
    "Content-Type": upstream.headers.get("content-type") || "application/json",
  });
  res.end(body);
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);

  if (req.method === "GET" && url.pathname === "/health") {
    sendJson(res, 200, { status: "ok" });
    return;
  }

  if (req.method !== "GET") {
    sendJson(res, 405, { error: "method_not_allowed", message: "Only GET is supported." });
    return;
  }

  if (!url.pathname.startsWith("/v1/")) {
    sendJson(res, 404, { error: "not_found", message: "Use /v1/skills/* paths." });
    return;
  }

  const upstreamPath = url.pathname.replace(/^\/v1/, "");
  await proxyToSkills(req, res, upstreamPath, url.search);
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`skills-proxy listening on :${PORT}`);
});