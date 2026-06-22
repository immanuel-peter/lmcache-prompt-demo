export type CacheLocation =
  | "LocalGPUBackend"
  | "LocalCPUBackend"
  | "LocalDiskBackend";

export interface CacheChunk {
  chunk_hash: string;
  tenant_id: string;
  model: string;
  cache_salt: string;
  token_count: number;
  instance_id: string;
  location: string;
  present: boolean;
  pinned: boolean;
  observed_only: boolean;
  last_seen_at: string;
  token_ids: number[];
  decoded_preview: string;
  prompt_id: string;
}

export interface CacheSummary {
  total_prompts: number;
  total_chunks: number;
  active_pin_leases: number;
  chunks_by_location: Record<string, number>;
  pinned_chunk_count: number;
  estimated_kv_bytes_by_location: Record<string, number>;
  stale_chunk_count: number;
  observed_only_chunk_count: number;
  consistency_model: string;
}

export interface Connectivity {
  mode: "demo" | "proxy";
  lmcache_kv_service_url: string;
  lmcache_controller_url: string;
  lmcache_runtime_url: string;
  vllm_base_url: string;
  lmcache_instance_id: string;
  demo_tenant_id: string;
  skills_proxy_url?: string;
  skills_enabled?: boolean;
  openwebui_url?: string;
}

export interface SkillSummary {
  id: string;
  slug: string;
  name: string;
  source: string;
  installs: number;
  sourceType?: string;
  installUrl?: string | null;
  url: string;
}

export interface InstalledSkill {
  skill_id: string;
  name: string;
  source: string;
  prompt_id: string;
  location: string;
  pinned: boolean;
  installed_at: string;
  content_hash?: string | null;
  installs?: number | null;
}

export interface SkillInstallResponse {
  skill_id: string;
  prompt_id: string;
  pin_id: string;
  location: string;
  pinned: boolean;
  warning?: string;
}

export interface PromptRegistrationResponse {
  prompt_id: string;
  token_count: number;
  chunk_count: number;
  chunk_hashes: string[];
  decoded_preview: string;
}

export interface BackendCapability {
  location: CacheLocation;
  supports_pin: boolean;
  supports_unpin: boolean;
  supports_targeted_evict: boolean;
  observed_only: boolean;
}

export const LOCATION_LABELS: Record<CacheLocation, string> = {
  LocalGPUBackend: "GPU",
  LocalCPUBackend: "CPU",
  LocalDiskBackend: "External Storage",
};

export const TIER_ORDER: CacheLocation[] = [
  "LocalGPUBackend",
  "LocalCPUBackend",
  "LocalDiskBackend",
];

export interface ProposedPin {
  prompt_id: string;
  location: CacheLocation;
}

export interface PinRecommendation {
  prompt_id: string;
  chunk_hash?: string;
  synthetic?: boolean;
  decoded_preview: string;
  location: CacheLocation;
  delta_hit_rate: number;
  projected_hit_rate: number;
  bytes_to_pin: number;
  score: number;
  confidence: string;
  rationale: string;
}

export interface PinExtrapolationRequest {
  tenant_id: string;
  tier_capacities_gib?: Record<string, number>;
  lookup_order?: string[];
  proposed_pins?: ProposedPin[];
  auto_recommend?: boolean;
  max_recommendations?: number;
  request_count?: number;
  seed?: number;
}

export interface PinExtrapolationResponse {
  baseline_token_hit_rate: number;
  candidate_token_hit_rate: number;
  delta_hit_rate: number;
  total_requests: number;
  total_tokens: number;
  baseline_hit_tokens: number;
  candidate_hit_tokens: number;
  baseline_miss_tokens_by_tier: Record<string, number>;
  candidate_miss_tokens_by_tier: Record<string, number>;
  baseline_eviction_count: number;
  candidate_eviction_count: number;
  applied_pin_count: number;
  recommendations: PinRecommendation[];
  traffic_source: string;
  warnings: string[];
}
