# SPDX-License-Identifier: Apache-2.0
"""FastAPI routes for the prompt registry demo."""

# Third Party
from fastapi import APIRouter, HTTPException, Query, Request

# First Party
from app.models import (
    BackendCapabilitiesResponse,
    CacheChunkListResponse,
    CacheSummaryResponse,
    CacheLocation,
    ConnectivityResponse,
    PromptEvictRequest,
    PromptEvictResponse,
    PromptLookupRequest,
    PromptLookupResponse,
    PromptMovePlanResponse,
    PromptMoveRequest,
    PromptMoveResponse,
    PromptPinRequest,
    PromptPinResponse,
    PromptRegistrationRequest,
    PromptRegistrationResponse,
    PromptUnpinRequest,
    PromptUnpinResponse,
)

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@router.get("/api/connectivity", response_model=ConnectivityResponse)
async def connectivity(request: Request) -> ConnectivityResponse:
    """Return configured upstream service URLs and operating mode."""
    settings = request.app.state.settings
    return ConnectivityResponse(
        mode="proxy" if settings.use_proxy else "demo",
        lmcache_kv_service_url=settings.lmcache_kv_service_url,
        lmcache_controller_url=settings.lmcache_controller_url,
        lmcache_runtime_url=settings.lmcache_runtime_url,
        vllm_base_url=settings.vllm_base_url,
        lmcache_instance_id=settings.lmcache_instance_id,
        demo_tenant_id=settings.demo_tenant_id,
    )


@router.post("/api/prompts", response_model=PromptRegistrationResponse)
async def register_prompt(
    request: Request, body: PromptRegistrationRequest
) -> PromptRegistrationResponse:
    """Register a prompt in the catalog."""
    if request.app.state.proxy:
        data = await request.app.state.proxy.register_prompt(body.model_dump())
        return PromptRegistrationResponse.model_validate(data)
    return request.app.state.catalog.register_prompt(body)


@router.post("/api/prompts/lookup", response_model=PromptLookupResponse)
async def lookup_prompt(
    request: Request, body: PromptLookupRequest
) -> PromptLookupResponse:
    """Look up prompt residency across cache tiers."""
    if request.app.state.proxy:
        data = await request.app.state.proxy.lookup_prompt(body.model_dump())
        return PromptLookupResponse.model_validate(data)
    try:
        return request.app.state.catalog.lookup_prompt(body)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/prompts/{prompt_id}/pin", response_model=PromptPinResponse)
async def pin_prompt(
    prompt_id: str, request: Request, body: PromptPinRequest
) -> PromptPinResponse:
    """Pin a prompt at a cache location."""
    if request.app.state.proxy:
        data = await request.app.state.proxy.pin_prompt(prompt_id, body.model_dump())
        return PromptPinResponse.model_validate(data)
    try:
        return request.app.state.catalog.pin_prompt(prompt_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/prompts/{prompt_id}/unpin", response_model=PromptUnpinResponse)
async def unpin_prompt(
    prompt_id: str, request: Request, body: PromptUnpinRequest
) -> PromptUnpinResponse:
    """Release a pin lease."""
    if request.app.state.proxy:
        data = await request.app.state.proxy.unpin_prompt(prompt_id, body.model_dump())
        return PromptUnpinResponse.model_validate(data)
    try:
        return request.app.state.catalog.unpin_prompt(prompt_id, body)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/prompts/{prompt_id}/evict", response_model=PromptEvictResponse)
async def evict_prompt(
    prompt_id: str, request: Request, body: PromptEvictRequest
) -> PromptEvictResponse:
    """Evict prompt chunks from selected locations."""
    if request.app.state.proxy:
        data = await request.app.state.proxy.evict_prompt(prompt_id, body.model_dump())
        return PromptEvictResponse.model_validate(data)
    try:
        return request.app.state.catalog.evict_prompt(prompt_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/api/prompts/{prompt_id}/move:plan", response_model=PromptMovePlanResponse
)
async def plan_move(
    prompt_id: str, request: Request, body: PromptMoveRequest
) -> PromptMovePlanResponse:
    """Dry-run a move or copy plan."""
    if request.app.state.proxy:
        data = await request.app.state.proxy.plan_move(prompt_id, body.model_dump())
        return PromptMovePlanResponse.model_validate(data)
    try:
        return request.app.state.catalog.plan_move(prompt_id, body)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/prompts/{prompt_id}/move", response_model=PromptMoveResponse)
async def move_prompt(
    prompt_id: str, request: Request, body: PromptMoveRequest
) -> PromptMoveResponse:
    """Execute a move or copy between cache tiers."""
    if request.app.state.proxy:
        data = await request.app.state.proxy.move_prompt(prompt_id, body.model_dump())
        return PromptMoveResponse.model_validate(data)
    try:
        return request.app.state.catalog.move_prompt(prompt_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/chunks/{chunk_hash}/move")
async def move_chunk(
    chunk_hash: str,
    request: Request,
    target: CacheLocation = Query(...),
    tenant_id: str = "",
) -> dict[str, object]:
    """Move a single chunk (drag-and-drop helper for the demo UI)."""
    settings = request.app.state.settings
    resolved_tenant = tenant_id or settings.demo_tenant_id
    if request.app.state.proxy:
        chunks = await request.app.state.proxy.list_chunks(
            tenant_id=resolved_tenant, include_debug=True
        )
        match = next(
            (c for c in chunks["chunks"] if c["chunk_hash"] == chunk_hash), None
        )
        if match is None:
            raise HTTPException(status_code=404, detail="Chunk not found")
        body = {
            "tenant_id": resolved_tenant,
            "source": {
                "instance_id": match.get("instance_id", settings.lmcache_instance_id),
                "location": match["location"],
            },
            "target": {
                "instance_id": settings.lmcache_instance_id,
                "location": target.value,
            },
            "copy": False,
        }
        prompt_id = match.get("prompt_id")
        if prompt_id:
            data = await request.app.state.proxy.move_prompt(prompt_id, body)
            return data
        data = await request.app.state.proxy.move_chunk(
            chunk_hash,
            target=target.value,
            tenant_id=resolved_tenant,
            source_location=match["location"],
            source_instance_id=match.get("instance_id", settings.lmcache_instance_id),
            target_instance_id=match.get("instance_id", settings.lmcache_instance_id),
            copy=False,
        )
        return data
    try:
        chunk = request.app.state.catalog.move_chunk(
            chunk_hash,
            target,
            resolved_tenant,
            settings.lmcache_instance_id,
        )
        return chunk.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/chunks/{chunk_hash}/pin", response_model=PromptPinResponse)
async def pin_chunk(
    chunk_hash: str,
    request: Request,
    tenant_id: str = "",
    ttl_seconds: int = 3600,
) -> PromptPinResponse:
    """Pin the prompt associated with a chunk."""
    settings = request.app.state.settings
    resolved_tenant = tenant_id or settings.demo_tenant_id
    if request.app.state.proxy:
        chunks = await request.app.state.proxy.list_chunks(
            tenant_id=resolved_tenant, include_debug=True
        )
        match = next(
            (c for c in chunks["chunks"] if c["chunk_hash"] == chunk_hash), None
        )
        if match is None:
            raise HTTPException(status_code=404, detail="Chunk not found")
        if match.get("observed_only"):
            raise HTTPException(
                status_code=400, detail="GPU pinning is not wired yet — observed only."
            )
        body = {
            "tenant_id": resolved_tenant,
            "location": match["location"],
            "owner": "demo-ui",
            "ttl_seconds": ttl_seconds,
            "instance_id": match.get("instance_id", settings.lmcache_instance_id),
        }
        data = await request.app.state.proxy.pin_prompt(match["prompt_id"], body)
        return PromptPinResponse.model_validate(data)
    try:
        return request.app.state.catalog.pin_chunk(
            chunk_hash, resolved_tenant, ttl_seconds
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/cache/summary", response_model=CacheSummaryResponse)
async def cache_summary(request: Request) -> CacheSummaryResponse:
    """Return catalog-backed cache summary."""
    if request.app.state.proxy:
        data = await request.app.state.proxy.cache_summary()
        return CacheSummaryResponse.model_validate(data)
    return request.app.state.catalog.cache_summary()


@router.get("/api/cache/chunks", response_model=CacheChunkListResponse)
async def list_chunks(
    request: Request,
    tenant_id: str = "",
    location: str = "",
    limit: int = 100,
    offset: int = 0,
) -> CacheChunkListResponse:
    """List cache chunks with optional filters."""
    settings = request.app.state.settings
    resolved_tenant = tenant_id or settings.demo_tenant_id
    if request.app.state.proxy:
        data = await request.app.state.proxy.list_chunks(
            tenant_id=resolved_tenant,
            location=location,
            limit=limit,
            offset=offset,
            include_debug=True,
        )
        return CacheChunkListResponse.model_validate(data)
    return request.app.state.catalog.list_chunks(
        tenant_id=resolved_tenant,
        location=location,
        limit=limit,
        offset=offset,
    )


@router.get("/api/cache/capabilities", response_model=BackendCapabilitiesResponse)
async def backend_capabilities(request: Request) -> BackendCapabilitiesResponse:
    """Return backend capability flags per cache tier."""
    if request.app.state.proxy:
        data = await request.app.state.proxy.backend_capabilities()
        return BackendCapabilitiesResponse.model_validate(data)
    return request.app.state.catalog.backend_capabilities()


@router.post("/api/cache/events:ingest")
async def ingest_events(request: Request, since: str = "") -> dict[str, object]:
    """Poll and ingest runtime cache events from LMCache."""
    if request.app.state.proxy:
        return await request.app.state.proxy.ingest_events(since)
    return {"ingested_events": 0, "ingested_chunks": 0, "next_cursor": ""}
