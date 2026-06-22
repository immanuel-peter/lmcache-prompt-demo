# SPDX-License-Identifier: Apache-2.0
"""In-memory demo implementation of the LMCache prompt registry API."""

# Standard
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import hashlib
import sqlite3
import threading
import uuid

# First Party
from app.models import (
    BackendCapabilitiesResponse,
    BackendCapability,
    CacheChunkListResponse,
    CacheChunkResponse,
    CacheLocation,
    CachePosition,
    CacheSummaryResponse,
    PromptEvictRequest,
    PromptEvictResponse,
    PromptLookupRequest,
    PromptLookupResponse,
    PromptLocationStatus,
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


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _chunk_hash(token_ids: list[int], salt: str) -> str:
    raw = f"{salt}:{','.join(str(t) for t in token_ids)}"
    return "0x" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def _tokenize_simple(text: str) -> list[int]:
    return [ord(char) for char in text[:256]]


def _decode_preview(token_ids: list[int], limit: int = 64) -> str:
    chars = [chr(t) for t in token_ids[:limit] if 32 <= t <= 126]
    return "".join(chars) if chars else text_from_tokens_fallback(token_ids, limit)


def text_from_tokens_fallback(token_ids: list[int], limit: int) -> str:
    return " ".join(str(t) for t in token_ids[:limit])


@dataclass
class PinLease:
    """Active pin lease record."""

    pin_id: str
    prompt_id: str
    tenant_id: str
    location: CacheLocation
    owner: str
    expires_at: str


@dataclass
class ChunkState:
    """Mutable chunk residency state."""

    chunk_hash: str
    prompt_id: str
    tenant_id: str
    model: str
    cache_salt: str
    token_count: int
    token_ids: list[int]
    decoded_preview: str
    location: CacheLocation
    present: bool = True
    pinned: bool = False
    observed_only: bool = False
    instance_id: str = "lmcache_default_instance"
    last_seen_at: str = field(default_factory=_now_iso)


@dataclass
class PromptState:
    """Registered prompt metadata."""

    prompt_id: str
    tenant_id: str
    model: str
    tokenizer_id: str
    prompt_text: str
    decoded_preview: str
    token_count: int
    chunk_hashes: list[str]
    labels: dict[str, str]
    created_at: str = field(default_factory=_now_iso)


CAPABILITIES = BackendCapabilitiesResponse(
    capabilities=[
        BackendCapability(
            location=CacheLocation.LOCAL_CPU,
            supports_lookup=True,
            supports_pin=True,
            supports_unpin=True,
            supports_targeted_evict=True,
            supports_move_source=True,
            supports_move_target=True,
            supports_copy=True,
            supports_delete=True,
            observed_only=False,
        ),
        BackendCapability(
            location=CacheLocation.LOCAL_DISK,
            supports_lookup=True,
            supports_pin=True,
            supports_unpin=True,
            supports_targeted_evict=True,
            supports_move_source=True,
            supports_move_target=True,
            supports_copy=True,
            supports_delete=True,
            observed_only=False,
        ),
        BackendCapability(
            location=CacheLocation.LOCAL_GPU,
            supports_lookup=True,
            supports_pin=False,
            supports_unpin=False,
            supports_targeted_evict=False,
            supports_move_source=False,
            supports_move_target=False,
            supports_copy=False,
            supports_delete=False,
            observed_only=True,
        ),
    ]
)


class DemoCatalog:
    """SQLite-backed demo catalog with in-memory chunk residency."""

    def __init__(self, sqlite_path: str, instance_id: str, tenant_id: str) -> None:
        self._sqlite_path = sqlite_path
        self._instance_id = instance_id
        self._default_tenant = tenant_id
        self._lock = threading.RLock()
        self._prompts: dict[str, PromptState] = {}
        self._chunks: dict[str, ChunkState] = {}
        self._pin_leases: dict[str, PinLease] = {}
        self._init_db()
        self._seed_demo_data()

    def _init_db(self) -> None:
        with sqlite3.connect(self._sqlite_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS prompts (
                    prompt_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_text TEXT NOT NULL,
                    decoded_preview TEXT NOT NULL,
                    token_count INTEGER NOT NULL,
                    chunk_hashes_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _seed_demo_data(self) -> None:
        if self._prompts:
            return
        samples = [
            (
                "Explain the significance of KV cache reuse in LLM serving workloads.",
                CacheLocation.LOCAL_GPU,
                True,
            ),
            (
                "Summarize the architecture of LMCache prompt registry and chunk catalog.",
                CacheLocation.LOCAL_CPU,
                False,
            ),
            (
                "What are the trade-offs between CPU and disk tiers for KV storage?",
                CacheLocation.LOCAL_DISK,
                False,
            ),
        ]
        for text, location, observed in samples:
            self.register_prompt(
                PromptRegistrationRequest(
                    model="meta-llama/Llama-3.1-8B-Instruct",
                    prompt=text,
                    tokenizer_id="meta-llama/Llama-3.1-8B-Instruct",
                    tenant_id=self._default_tenant,
                    labels={"source": "seed"},
                ),
                force_location=location,
                observed_only=observed,
            )

    def _cache_salt(self, tenant_id: str) -> str:
        raw = f"demo:{tenant_id}:lmcache-prompt-demo"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def register_prompt(
        self,
        request: PromptRegistrationRequest,
        force_location: CacheLocation | None = None,
        observed_only: bool = False,
    ) -> PromptRegistrationResponse:
        with self._lock:
            token_ids = _tokenize_simple(request.prompt)
            preview = _decode_preview(token_ids, request.preview_token_limit)
            salt = self._cache_salt(request.tenant_id)

            for prompt in self._prompts.values():
                if (
                    prompt.tenant_id == request.tenant_id
                    and prompt.prompt_text == request.prompt
                    and prompt.model == request.model
                ):
                    return PromptRegistrationResponse(
                        prompt_id=prompt.prompt_id,
                        token_count=prompt.token_count,
                        chunk_count=len(prompt.chunk_hashes),
                        chunk_hashes=prompt.chunk_hashes,
                        decoded_preview=prompt.decoded_preview,
                    )

            prompt_id = f"prm_{uuid.uuid4().hex[:12]}"
            chunk_size = max(8, min(32, len(token_ids)))
            chunk_hashes: list[str] = []

            for start in range(0, len(token_ids), chunk_size):
                end = min(start + chunk_size, len(token_ids))
                slice_ids = token_ids[start:end]
                chunk_hash = _chunk_hash(slice_ids, salt)
                chunk_hashes.append(chunk_hash)
                location = force_location or CacheLocation.LOCAL_CPU
                self._chunks[chunk_hash] = ChunkState(
                    chunk_hash=chunk_hash,
                    prompt_id=prompt_id,
                    tenant_id=request.tenant_id,
                    model=request.model,
                    cache_salt=salt,
                    token_count=len(slice_ids),
                    token_ids=slice_ids,
                    decoded_preview=_decode_preview(slice_ids),
                    location=location,
                    observed_only=observed_only or location == CacheLocation.LOCAL_GPU,
                    instance_id=self._instance_id,
                )

            prompt = PromptState(
                prompt_id=prompt_id,
                tenant_id=request.tenant_id,
                model=request.model,
                tokenizer_id=request.tokenizer_id,
                prompt_text=request.prompt,
                decoded_preview=preview,
                token_count=len(token_ids),
                chunk_hashes=chunk_hashes,
                labels=request.labels,
            )
            self._prompts[prompt_id] = prompt

            with sqlite3.connect(self._sqlite_path) as conn:
                conn.execute(
                    """
                    INSERT INTO prompts
                    (prompt_id, tenant_id, model, prompt_text, decoded_preview,
                     token_count, chunk_hashes_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        prompt_id,
                        request.tenant_id,
                        request.model,
                        request.prompt,
                        preview,
                        len(token_ids),
                        ",".join(chunk_hashes),
                        prompt.created_at,
                    ),
                )
                conn.commit()

            return PromptRegistrationResponse(
                prompt_id=prompt_id,
                token_count=len(token_ids),
                chunk_count=len(chunk_hashes),
                chunk_hashes=chunk_hashes,
                decoded_preview=preview,
            )

    def lookup_prompt(self, request: PromptLookupRequest) -> PromptLookupResponse:
        with self._lock:
            prompt = self._get_prompt(request.prompt_id, request.tenant_id)
            locations: dict[CacheLocation, PromptLocationStatus] = {}
            matched = 0
            for chunk_hash in prompt.chunk_hashes:
                chunk = self._chunks.get(chunk_hash)
                if chunk is None or not chunk.present:
                    continue
                matched += chunk.token_count
                status = locations.get(chunk.location)
                if status is None:
                    locations[chunk.location] = PromptLocationStatus(
                        instance_id=chunk.instance_id,
                        location=chunk.location,
                        present=True,
                        pinned=chunk.pinned,
                        observed_only=chunk.observed_only,
                        matched_tokens=chunk.token_count,
                    )
                else:
                    status.matched_tokens += chunk.token_count
                    status.pinned = status.pinned or chunk.pinned

            return PromptLookupResponse(
                prompt_id=prompt.prompt_id,
                matched_tokens=matched,
                locations=list(locations.values()),
            )

    def pin_prompt(
        self, prompt_id: str, request: PromptPinRequest
    ) -> PromptPinResponse:
        with self._lock:
            if request.location == CacheLocation.LOCAL_GPU:
                raise ValueError("GPU pinning is not wired yet — observed only.")
            self._get_prompt(prompt_id, request.tenant_id)
            pin_id = f"pin_{uuid.uuid4().hex[:10]}"
            expires = datetime.now(tz=UTC) + timedelta(seconds=request.ttl_seconds)
            self._pin_leases[pin_id] = PinLease(
                pin_id=pin_id,
                prompt_id=prompt_id,
                tenant_id=request.tenant_id,
                location=request.location,
                owner=request.owner,
                expires_at=expires.isoformat(),
            )
            for chunk in self._chunks_for_prompt(prompt_id, request.tenant_id):
                if chunk.location == request.location and chunk.present:
                    chunk.pinned = True
                    chunk.last_seen_at = _now_iso()
            return PromptPinResponse(
                pin_id=pin_id,
                expires_at=expires.isoformat(),
                operation_id=f"op_{uuid.uuid4().hex[:8]}",
            )

    def unpin_prompt(
        self, prompt_id: str, request: PromptUnpinRequest
    ) -> PromptUnpinResponse:
        with self._lock:
            lease = self._pin_leases.get(request.pin_id)
            if lease is None:
                raise KeyError(f"Pin lease {request.pin_id} not found")
            lease_released = True
            num_tokens = 0
            for chunk in self._chunks_for_prompt(prompt_id, request.tenant_id):
                if chunk.location == request.location:
                    chunk.pinned = False
                    num_tokens += chunk.token_count
            del self._pin_leases[request.pin_id]
            return PromptUnpinResponse(
                pin_id=request.pin_id,
                released=lease_released,
                num_tokens=num_tokens,
                operation_id=f"op_{uuid.uuid4().hex[:8]}",
            )

    def evict_prompt(
        self, prompt_id: str, request: PromptEvictRequest
    ) -> PromptEvictResponse:
        with self._lock:
            self._get_prompt(prompt_id, request.tenant_id)
            evicted = 0
            for location in request.locations:
                if location == CacheLocation.LOCAL_GPU:
                    raise ValueError("GPU eviction is not supported — observed only.")
                for chunk in self._chunks_for_prompt(prompt_id, request.tenant_id):
                    if chunk.location == location and chunk.present:
                        if chunk.pinned and not request.force:
                            raise ValueError(
                                "Cannot evict pinned chunks without force=true"
                            )
                        chunk.present = False
                        chunk.pinned = False
                        evicted += chunk.token_count
            return PromptEvictResponse(
                prompt_id=prompt_id,
                evicted_tokens=evicted,
                locations=request.locations,
                operation_id=f"op_{uuid.uuid4().hex[:8]}",
            )

    def plan_move(
        self, prompt_id: str, request: PromptMoveRequest
    ) -> PromptMovePlanResponse:
        with self._lock:
            self._get_prompt(prompt_id, request.tenant_id)
            chunks = [
                c
                for c in self._chunks_for_prompt(prompt_id, request.tenant_id)
                if c.location == request.source.location and c.present
            ]
            warnings: list[str] = []
            target_supported = request.target.location in (
                CacheLocation.LOCAL_CPU,
                CacheLocation.LOCAL_DISK,
            )
            if request.source.location == CacheLocation.LOCAL_GPU:
                warnings.append("GPU is observed-only; move planning is best-effort.")
                target_supported = False
            return PromptMovePlanResponse(
                operation_id=f"op_{uuid.uuid4().hex[:8]}",
                prompt_id=prompt_id,
                affected_chunk_count=len(chunks),
                estimated_bytes=sum(c.token_count * 512 for c in chunks),
                source_present=bool(chunks),
                target_supported=target_supported,
                best_effort=request.source.location == CacheLocation.LOCAL_GPU,
                warnings=warnings,
            )

    def move_prompt(
        self, prompt_id: str, request: PromptMoveRequest
    ) -> PromptMoveResponse:
        with self._lock:
            if request.source.location == CacheLocation.LOCAL_GPU:
                raise ValueError("GPU move is not supported — observed only.")
            if request.target.location == CacheLocation.LOCAL_GPU:
                raise ValueError("GPU pinning is not wired yet.")
            self._get_prompt(prompt_id, request.tenant_id)
            moved = 0
            for chunk in self._chunks_for_prompt(prompt_id, request.tenant_id):
                if chunk.location == request.source.location and chunk.present:
                    if request.copy_requested:
                        new_hash = f"{chunk.chunk_hash}_copy_{uuid.uuid4().hex[:6]}"
                        self._chunks[new_hash] = ChunkState(
                            chunk_hash=new_hash,
                            prompt_id=chunk.prompt_id,
                            tenant_id=chunk.tenant_id,
                            model=chunk.model,
                            cache_salt=chunk.cache_salt,
                            token_count=chunk.token_count,
                            token_ids=list(chunk.token_ids),
                            decoded_preview=chunk.decoded_preview,
                            location=request.target.location,
                            instance_id=request.target.instance_id,
                        )
                        moved += chunk.token_count
                    else:
                        chunk.location = request.target.location
                        chunk.instance_id = request.target.instance_id
                        chunk.last_seen_at = _now_iso()
                        moved += chunk.token_count
            return PromptMoveResponse(
                operation_id=f"op_{uuid.uuid4().hex[:8]}",
                prompt_id=prompt_id,
                moved_tokens=moved,
                source=request.source,
                target=request.target,
                copy_requested=request.copy_requested,
            )

    def move_chunk(
        self,
        chunk_hash: str,
        target: CacheLocation,
        tenant_id: str,
        instance_id: str,
    ) -> CacheChunkResponse:
        """Move a single chunk to a target location (UI drag-drop helper)."""
        with self._lock:
            chunk = self._chunks.get(chunk_hash)
            if chunk is None or chunk.tenant_id != tenant_id:
                raise KeyError(f"Chunk {chunk_hash} not found")
            if chunk.observed_only or chunk.location == CacheLocation.LOCAL_GPU:
                raise ValueError("GPU chunks are observed-only")
            if target == CacheLocation.LOCAL_GPU:
                raise ValueError("GPU pinning is not wired yet")
            if chunk.pinned:
                raise ValueError("Unpin before moving pinned chunks")
            chunk.location = target
            chunk.instance_id = instance_id
            chunk.last_seen_at = _now_iso()
            return self._chunk_to_response(chunk)

    def pin_chunk(
        self, chunk_hash: str, tenant_id: str, ttl_seconds: int = 3600
    ) -> PromptPinResponse:
        """Pin all chunks belonging to the same prompt at the chunk's location."""
        with self._lock:
            chunk = self._chunks.get(chunk_hash)
            if chunk is None or chunk.tenant_id != tenant_id:
                raise KeyError(f"Chunk {chunk_hash} not found")
            return self.pin_prompt(
                chunk.prompt_id,
                PromptPinRequest(
                    tenant_id=tenant_id,
                    location=chunk.location,
                    owner="demo-ui",
                    ttl_seconds=ttl_seconds,
                    instance_id=chunk.instance_id,
                ),
            )

    def list_chunks(
        self,
        tenant_id: str = "",
        location: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> CacheChunkListResponse:
        with self._lock:
            rows = list(self._chunks.values())
            if tenant_id:
                rows = [r for r in rows if r.tenant_id == tenant_id]
            if location:
                rows = [r for r in rows if r.location.value == location]
            rows = [r for r in rows if r.present]
            rows.sort(key=lambda r: (r.location.value, r.prompt_id, r.chunk_hash))
            page = rows[offset : offset + limit]
            return CacheChunkListResponse(
                chunks=[self._chunk_to_response(r) for r in page],
                limit=limit,
                offset=offset,
                total=len(rows),
            )

    def cache_summary(self) -> CacheSummaryResponse:
        with self._lock:
            by_location: dict[str, int] = {}
            pinned = 0
            observed = 0
            bytes_by_loc: dict[str, int] = {}
            for chunk in self._chunks.values():
                if not chunk.present:
                    continue
                key = chunk.location.value
                by_location[key] = by_location.get(key, 0) + 1
                bytes_by_loc[key] = bytes_by_loc.get(key, 0) + chunk.token_count * 512
                if chunk.pinned:
                    pinned += 1
                if chunk.observed_only:
                    observed += 1
            return CacheSummaryResponse(
                total_prompts=len(self._prompts),
                total_chunks=sum(by_location.values()),
                active_pin_leases=len(self._pin_leases),
                chunks_by_location=by_location,
                pinned_chunk_count=pinned,
                estimated_kv_bytes_by_location=bytes_by_loc,
                observed_only_chunk_count=observed,
            )

    def backend_capabilities(self) -> BackendCapabilitiesResponse:
        return CAPABILITIES

    def analysis_catalog(
        self, tenant_id: str
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        """Return prompt and chunk rows for pin extrapolation analysis."""
        with self._lock:
            prompts: list[dict[str, object]] = []
            chunks: list[dict[str, object]] = []

            for prompt in self._prompts.values():
                if prompt.tenant_id != tenant_id:
                    continue
                prompts.append(
                    {
                        "prompt_id": prompt.prompt_id,
                        "decoded_preview": prompt.decoded_preview,
                        "token_count": prompt.token_count,
                        "chunk_hashes": list(prompt.chunk_hashes),
                    }
                )
                for chunk_hash in prompt.chunk_hashes:
                    chunk = self._chunks.get(chunk_hash)
                    if chunk is None or not chunk.present:
                        continue
                    chunks.append(
                        {
                            "chunk_hash": chunk.chunk_hash,
                            "prompt_id": chunk.prompt_id,
                            "token_count": chunk.token_count,
                            "location": chunk.location.value,
                            "pinned": chunk.pinned,
                            "decoded_preview": chunk.decoded_preview,
                        }
                    )
            return prompts, chunks

    def _get_prompt(self, prompt_id: str, tenant_id: str) -> PromptState:
        prompt = self._prompts.get(prompt_id)
        if prompt is None or prompt.tenant_id != tenant_id:
            raise KeyError(f"Prompt {prompt_id} not found")
        return prompt

    def _chunks_for_prompt(
        self, prompt_id: str, tenant_id: str
    ) -> list[ChunkState]:
        return [
            c
            for c in self._chunks.values()
            if c.prompt_id == prompt_id and c.tenant_id == tenant_id
        ]

    def _chunk_to_response(self, chunk: ChunkState) -> CacheChunkResponse:
        return CacheChunkResponse(
            chunk_hash=chunk.chunk_hash,
            tenant_id=chunk.tenant_id,
            model=chunk.model,
            cache_salt=chunk.cache_salt,
            token_count=chunk.token_count,
            instance_id=chunk.instance_id,
            location=chunk.location.value,
            present=chunk.present,
            pinned=chunk.pinned,
            observed_only=chunk.observed_only,
            last_seen_at=chunk.last_seen_at,
            token_ids=chunk.token_ids,
            decoded_preview=chunk.decoded_preview,
            prompt_id=chunk.prompt_id,
        )
