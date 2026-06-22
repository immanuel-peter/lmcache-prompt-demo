# SPDX-License-Identifier: Apache-2.0
"""Pydantic models aligned with LMCache KV service API."""

# Standard
from enum import Enum

# Third Party
from pydantic import BaseModel, Field


class CacheLocation(str, Enum):
    """Runtime cache locations."""

    LOCAL_CPU = "LocalCPUBackend"
    LOCAL_DISK = "LocalDiskBackend"
    LOCAL_GPU = "LocalGPUBackend"


class PromptRegistrationRequest(BaseModel):
    """Request body for registering a prompt."""

    model: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    tokenizer_id: str = Field(min_length=1)
    chat_template_id: str = ""
    tenant_id: str = Field(min_length=1)
    labels: dict[str, str] = Field(default_factory=dict)
    store_text: bool = False
    preview_token_limit: int = Field(default=64, ge=0)


class PromptRegistrationResponse(BaseModel):
    """Response after prompt registration."""

    prompt_id: str
    token_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    chunk_hashes: list[str]
    decoded_preview: str


class PromptLookupRequest(BaseModel):
    """Request body for prompt residency lookup."""

    prompt_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    refresh_runtime: bool = True


class PromptLocationStatus(BaseModel):
    """Runtime residency status for a prompt at a cache location."""

    instance_id: str
    location: CacheLocation
    present: bool
    pinned: bool = False
    observed_only: bool = False
    matched_tokens: int = Field(default=0, ge=0)


class PromptLookupResponse(BaseModel):
    """Response for prompt residency lookup."""

    prompt_id: str
    matched_tokens: int = Field(ge=0)
    locations: list[PromptLocationStatus]


class PromptPinRequest(BaseModel):
    """Request body for creating a prompt pin lease."""

    tenant_id: str = Field(min_length=1)
    location: CacheLocation
    owner: str = Field(min_length=1)
    ttl_seconds: int = Field(gt=0)
    instance_id: str = Field(default="lmcache_default_instance", min_length=1)
    reason: str = ""


class PromptPinResponse(BaseModel):
    """Response after creating a pin lease."""

    pin_id: str
    expires_at: str
    operation_id: str = ""


class PromptUnpinRequest(BaseModel):
    """Request body for releasing a pin lease."""

    tenant_id: str = Field(min_length=1)
    pin_id: str = Field(min_length=1)
    location: CacheLocation


class PromptUnpinResponse(BaseModel):
    """Response after releasing a pin lease."""

    pin_id: str
    released: bool
    num_tokens: int = Field(ge=0)
    operation_id: str = ""


class PromptEvictRequest(BaseModel):
    """Request body for evicting prompt chunks."""

    tenant_id: str = Field(min_length=1)
    locations: list[CacheLocation] = Field(min_length=1)
    delete_catalog_record: bool = False
    force: bool = False
    instance_id: str = Field(default="lmcache_default_instance", min_length=1)


class PromptEvictResponse(BaseModel):
    """Response after prompt eviction."""

    prompt_id: str
    evicted_tokens: int = Field(ge=0)
    locations: list[CacheLocation]
    operation_id: str = ""


class CachePosition(BaseModel):
    """Runtime instance and cache location pair."""

    instance_id: str = Field(min_length=1)
    location: CacheLocation


class PromptMoveRequest(BaseModel):
    """Request body for prompt move planning and execution."""

    model_config = {"populate_by_name": True}

    tenant_id: str = Field(min_length=1)
    source: CachePosition
    target: CachePosition
    copy_requested: bool = Field(default=False, alias="copy")
    ttl_seconds: int = Field(default=0, ge=0)


class PromptMovePlanResponse(BaseModel):
    """Dry-run response for prompt move or copy."""

    operation_id: str
    prompt_id: str
    affected_chunk_count: int = Field(ge=0)
    estimated_bytes: int = Field(ge=0)
    source_present: bool
    target_supported: bool
    best_effort: bool
    warnings: list[str] = Field(default_factory=list)


class PromptMoveResponse(BaseModel):
    """Execution response for prompt move or copy."""

    model_config = {"populate_by_name": True}

    operation_id: str
    prompt_id: str
    moved_tokens: int = Field(ge=0)
    source: CachePosition
    target: CachePosition
    copy_requested: bool = Field(alias="copy")
    pin_id: str = ""
    warnings: list[str] = Field(default_factory=list)


class CacheSummaryResponse(BaseModel):
    """Catalog-backed cache summary."""

    total_prompts: int = Field(ge=0)
    total_chunks: int = Field(ge=0)
    active_pin_leases: int = Field(ge=0)
    chunks_by_location: dict[str, int] = Field(default_factory=dict)
    pinned_chunk_count: int = Field(default=0, ge=0)
    estimated_kv_bytes_by_location: dict[str, int] = Field(default_factory=dict)
    stale_chunk_count: int = Field(default=0, ge=0)
    observed_only_chunk_count: int = Field(default=0, ge=0)
    consistency_model: str = "eventually_consistent"


class CacheChunkResponse(BaseModel):
    """Cache chunk row returned by list APIs."""

    chunk_hash: str
    tenant_id: str
    model: str
    cache_salt: str
    token_count: int = Field(ge=0)
    instance_id: str = ""
    location: str = ""
    present: bool = False
    pinned: bool = False
    observed_only: bool = False
    last_seen_at: str = ""
    token_ids: list[int] = Field(default_factory=list)
    decoded_preview: str = ""
    prompt_id: str = ""


class CacheChunkListResponse(BaseModel):
    """Paginated cache chunk listing response."""

    chunks: list[CacheChunkResponse]
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    total: int = Field(ge=0)


class BackendCapability(BaseModel):
    """Capability flags for a runtime cache backend."""

    location: CacheLocation
    supports_lookup: bool
    supports_pin: bool
    supports_unpin: bool
    supports_targeted_evict: bool
    supports_move_source: bool
    supports_move_target: bool
    supports_copy: bool
    supports_delete: bool
    observed_only: bool


class BackendCapabilitiesResponse(BaseModel):
    """Backend capabilities known to the service."""

    capabilities: list[BackendCapability]


class ConnectivityResponse(BaseModel):
    """Reachability status for configured upstream services."""

    mode: str
    lmcache_kv_service_url: str
    lmcache_controller_url: str
    lmcache_runtime_url: str
    vllm_base_url: str
    lmcache_instance_id: str
    demo_tenant_id: str
