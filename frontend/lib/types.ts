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
