import type {
  BackendCapability,
  CacheChunk,
  CacheSummary,
  Connectivity,
  InstalledSkill,
  PinExtrapolationRequest,
  PinExtrapolationResponse,
  PromptRegistrationResponse,
  SkillInstallResponse,
  SkillSummary,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail =
        typeof body.detail === "string"
          ? body.detail
          : JSON.stringify(body.detail ?? body);
    } catch {
      detail = await response.text();
    }
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export async function fetchConnectivity(): Promise<Connectivity> {
  return request<Connectivity>("/api/connectivity");
}

export async function fetchSummary(): Promise<CacheSummary> {
  return request<CacheSummary>("/api/cache/summary");
}

export async function fetchChunks(tenantId: string): Promise<CacheChunk[]> {
  const data = await request<{ chunks: CacheChunk[] }>(
    `/api/cache/chunks?tenant_id=${encodeURIComponent(tenantId)}&limit=200`,
  );
  return data.chunks;
}

export async function fetchCapabilities(): Promise<BackendCapability[]> {
  const data = await request<{ capabilities: BackendCapability[] }>(
    "/api/cache/capabilities",
  );
  return data.capabilities;
}

export async function registerPrompt(body: {
  model: string;
  prompt: string;
  tokenizer_id: string;
  tenant_id: string;
  labels?: Record<string, string>;
}): Promise<PromptRegistrationResponse> {
  return request<PromptRegistrationResponse>("/api/prompts", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function moveChunk(
  chunkHash: string,
  target: string,
  tenantId: string,
): Promise<void> {
  await request(`/api/chunks/${encodeURIComponent(chunkHash)}/move?target=${encodeURIComponent(target)}&tenant_id=${encodeURIComponent(tenantId)}`, {
    method: "POST",
  });
}

export async function pinChunk(
  chunkHash: string,
  tenantId: string,
): Promise<{ pin_id: string }> {
  return request(`/api/chunks/${encodeURIComponent(chunkHash)}/pin?tenant_id=${encodeURIComponent(tenantId)}`, {
    method: "POST",
  });
}

export async function evictPrompt(
  promptId: string,
  tenantId: string,
  locations: string[],
  force = false,
): Promise<void> {
  await request(`/api/prompts/${encodeURIComponent(promptId)}/evict`, {
    method: "POST",
    body: JSON.stringify({
      tenant_id: tenantId,
      locations,
      force,
    }),
  });
}

export async function ingestEvents(): Promise<void> {
  await request("/api/cache/events:ingest", { method: "POST" });
}

export async function runPinExtrapolation(
  body: PinExtrapolationRequest,
): Promise<PinExtrapolationResponse> {
  return request<PinExtrapolationResponse>("/api/analysis/pin-extrapolation", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function pinPrompt(
  promptId: string,
  tenantId: string,
  location: string,
  ttlSeconds = 3600,
): Promise<{ pin_id: string }> {
  return request(`/api/prompts/${encodeURIComponent(promptId)}/pin`, {
    method: "POST",
    body: JSON.stringify({
      tenant_id: tenantId,
      location,
      owner: "pin-analysis-ui",
      ttl_seconds: ttlSeconds,
    }),
  });
}

export function getOpenWebUiUrl(): string {
  return process.env.NEXT_PUBLIC_OPENWEBUI_URL ?? "http://localhost:8080";
}

export async function searchSkills(
  q: string,
  limit = 50,
): Promise<SkillSummary[]> {
  const data = await request<{ data: SkillSummary[] }>(
    `/api/skills/search?q=${encodeURIComponent(q)}&limit=${limit}`,
  );
  return data.data;
}

export async function listSkills(
  view = "all-time",
  perPage = 15,
): Promise<SkillSummary[]> {
  const data = await request<{ data: SkillSummary[] }>(
    `/api/skills?view=${encodeURIComponent(view)}&per_page=${perPage}`,
  );
  return data.data;
}

export async function fetchInstalledSkills(
  tenantId: string,
): Promise<InstalledSkill[]> {
  const data = await request<{ skills: InstalledSkill[] }>(
    `/api/skills/installed/list?tenant_id=${encodeURIComponent(tenantId)}`,
  );
  return data.skills;
}

export async function installSkill(
  skillId: string,
  tenantId: string,
  location = "LocalCPUBackend",
): Promise<SkillInstallResponse> {
  return request<SkillInstallResponse>("/api/skills/install", {
    method: "POST",
    body: JSON.stringify({
      skill_id: skillId,
      tenant_id: tenantId,
      location,
    }),
  });
}

export async function uninstallSkill(
  skillId: string,
  tenantId: string,
): Promise<void> {
  await request("/api/skills/uninstall", {
    method: "POST",
    body: JSON.stringify({
      skill_id: skillId,
      tenant_id: tenantId,
    }),
  });
}

export { API_BASE };
