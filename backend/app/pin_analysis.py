# SPDX-License-Identifier: Apache-2.0
"""Multi-tier cache extrapolation for prompt pin recommendations."""

# Standard
from collections import OrderedDict
from dataclasses import dataclass, field
import random
from typing import Iterable

# First Party
from app.models import (
    CacheLocation,
    PinExtrapolationRequest,
    PinExtrapolationResponse,
    PinRecommendation,
)

_GIB = 2**30
_KV_BYTES_PER_TOKEN = 512

_PINNABLE_TIERS = (
    CacheLocation.LOCAL_CPU,
    CacheLocation.LOCAL_DISK,
)

_DEFAULT_LOOKUP_ORDER = (
    CacheLocation.LOCAL_CPU,
    CacheLocation.LOCAL_DISK,
)

_DEFAULT_TIER_CAPACITIES_GIB: dict[CacheLocation, float] = {
    CacheLocation.LOCAL_CPU: 8.0,
    CacheLocation.LOCAL_DISK: 64.0,
}


@dataclass(frozen=True, slots=True)
class PromptRecord:
    """Catalog prompt used to synthesize lookup traffic."""

    prompt_id: str
    decoded_preview: str
    token_count: int
    chunk_hashes: tuple[str, ...]
    chunk_token_counts: tuple[int, ...]
    primary_location: CacheLocation | None = None
    pinned: bool = False


@dataclass(frozen=True, slots=True)
class TrafficRequest:
    """Single replayed lookup request."""

    prompt_id: str
    chunk_hashes: tuple[str, ...]
    seq_len: int
    chunk_size: int


@dataclass(frozen=True, slots=True)
class PinAssignment:
    """Prompt chunks pinned at a specific backend."""

    prompt_id: str
    location: CacheLocation
    chunk_hashes: tuple[str, ...]


@dataclass
class TierCache:
    """LRU tier with pin-immune entries."""

    capacity_bytes: int
    kv_bytes_per_chunk: int
    pinned: set[str] = field(default_factory=set)
    lru: OrderedDict[str, None] = field(default_factory=OrderedDict)
    eviction_count: int = 0

    @property
    def capacity_chunks(self) -> int:
        return max(1, self.capacity_bytes // max(self.kv_bytes_per_chunk, 1))

    def contains(self, key: str) -> bool:
        return key in self.pinned or key in self.lru

    def pin_keys(self, keys: Iterable[str]) -> None:
        for key in keys:
            self.pinned.add(key)
            self.lru.pop(key, None)

    def access(self, key: str) -> None:
        if key in self.pinned:
            return
        if key in self.lru:
            self.lru.move_to_end(key)

    def insert(self, key: str) -> None:
        if key in self.pinned:
            return
        if key in self.lru:
            self.lru.move_to_end(key)
            return
        self._evict_until_room()
        if self._entry_count() < self.capacity_chunks:
            self.lru[key] = None

    def _entry_count(self) -> int:
        return len(self.pinned) + len(self.lru)

    def _evict_until_room(self) -> None:
        while self._entry_count() >= self.capacity_chunks and self.lru:
            self.lru.popitem(last=False)
            self.eviction_count += 1


@dataclass(frozen=True, slots=True)
class SimulationMetrics:
    """Hit-rate statistics from a traffic replay."""

    token_hit_rate: float
    total_requests: int
    total_tokens: int
    total_hit_tokens: int
    miss_tokens_by_tier: dict[str, int]
    eviction_count: int


def build_prompt_records(
    *,
    prompts: list[dict[str, object]],
    chunks_by_hash: dict[str, dict[str, object]],
) -> list[PromptRecord]:
    """Normalize catalog rows into prompt records for simulation."""
    records: list[PromptRecord] = []
    for raw in prompts:
        prompt_id = str(raw["prompt_id"])
        chunk_hashes = tuple(str(h) for h in raw.get("chunk_hashes", []))
        if not chunk_hashes:
            continue

        token_counts: list[int] = []
        locations: list[CacheLocation] = []
        any_pinned = False
        for chunk_hash in chunk_hashes:
            chunk = chunks_by_hash.get(chunk_hash)
            if chunk is None:
                token_counts.append(8)
                continue
            token_counts.append(int(chunk.get("token_count", 8)))
            loc_value = str(chunk.get("location", ""))
            try:
                locations.append(CacheLocation(loc_value))
            except ValueError:
                pass
            any_pinned = any_pinned or bool(chunk.get("pinned"))

        primary_location = locations[0] if locations else None
        records.append(
            PromptRecord(
                prompt_id=prompt_id,
                decoded_preview=str(raw.get("decoded_preview", "")),
                token_count=int(raw.get("token_count", sum(token_counts))),
                chunk_hashes=chunk_hashes,
                chunk_token_counts=tuple(token_counts),
                primary_location=primary_location,
                pinned=any_pinned,
            )
        )
    return records


def synthesize_traffic(
    prompts: list[PromptRecord],
    *,
    request_count: int,
    seed: int = 42,
) -> list[TrafficRequest]:
    """Build a Zipf-weighted request stream from registered prompts."""
    if not prompts:
        return []

    rng = random.Random(seed)
    weights = [1.0 / (index + 1) ** 0.8 for index in range(len(prompts))]
    requests: list[TrafficRequest] = []

    for _ in range(request_count):
        prompt = rng.choices(prompts, weights=weights, k=1)[0]
        avg_chunk = max(
            1,
            round(sum(prompt.chunk_token_counts) / len(prompt.chunk_token_counts)),
        )
        requests.append(
            TrafficRequest(
                prompt_id=prompt.prompt_id,
                chunk_hashes=prompt.chunk_hashes,
                seq_len=prompt.token_count,
                chunk_size=avg_chunk,
            )
        )
    return requests


def _resolve_tier_capacities(
    request: PinExtrapolationRequest,
) -> dict[CacheLocation, int]:
    capacities: dict[CacheLocation, int] = {}
    for location, gib in _DEFAULT_TIER_CAPACITIES_GIB.items():
        capacities[location] = int(gib * _GIB)

    for location_name, gib in request.tier_capacities_gib.items():
        try:
            location = CacheLocation(location_name)
        except ValueError:
            continue
        capacities[location] = max(1, int(gib * _GIB))
    return capacities


def _resolve_lookup_order(request: PinExtrapolationRequest) -> tuple[CacheLocation, ...]:
    if not request.lookup_order:
        return _DEFAULT_LOOKUP_ORDER

    order: list[CacheLocation] = []
    for location_name in request.lookup_order:
        try:
            location = CacheLocation(location_name)
        except ValueError:
            continue
        if location not in order:
            order.append(location)
    return tuple(order or _DEFAULT_LOOKUP_ORDER)


def _prompt_lookup(
    prompts: list[PromptRecord], prompt_id: str
) -> PromptRecord | None:
    for prompt in prompts:
        if prompt.prompt_id == prompt_id:
            return prompt
    return None


def _bytes_for_prompt(prompt: PromptRecord) -> int:
    return sum(count * _KV_BYTES_PER_TOKEN for count in prompt.chunk_token_counts)


def _assignments_from_request(
    request: PinExtrapolationRequest,
    prompts: list[PromptRecord],
) -> list[PinAssignment]:
    assignments: list[PinAssignment] = []
    for proposed in request.proposed_pins:
        prompt = _prompt_lookup(prompts, proposed.prompt_id)
        if prompt is None:
            continue
        if proposed.location == CacheLocation.LOCAL_GPU:
            continue
        assignments.append(
            PinAssignment(
                prompt_id=prompt.prompt_id,
                location=proposed.location,
                chunk_hashes=prompt.chunk_hashes,
            )
        )
    return assignments


def _simulate(
    traffic: list[TrafficRequest],
    *,
    tier_capacities: dict[CacheLocation, int],
    lookup_order: tuple[CacheLocation, ...],
    pin_assignments: list[PinAssignment],
    kv_bytes_per_chunk: int,
    insert_tier: CacheLocation = CacheLocation.LOCAL_CPU,
) -> SimulationMetrics:
    tiers: dict[CacheLocation, TierCache] = {}
    for location in lookup_order:
        capacity = tier_capacities.get(location, _GIB)
        tiers[location] = TierCache(
            capacity_bytes=capacity,
            kv_bytes_per_chunk=kv_bytes_per_chunk,
        )

    for assignment in pin_assignments:
        tier = tiers.get(assignment.location)
        if tier is None:
            continue
        tier.pin_keys(assignment.chunk_hashes)

    total_requests = 0
    total_tokens = 0
    total_hit_tokens = 0
    miss_tokens_by_tier: dict[str, int] = {loc.value: 0 for loc in lookup_order}

    for req in traffic:
        if not req.chunk_hashes:
            continue

        hit_prefix = 0
        for chunk_hash in req.chunk_hashes:
            found = False
            for location in lookup_order:
                tier = tiers.get(location)
                if tier is not None and tier.contains(chunk_hash):
                    tier.access(chunk_hash)
                    hit_prefix += 1
                    found = True
                    break
            if not found:
                break

        hit_tokens = min(hit_prefix * req.chunk_size, req.seq_len)
        miss_tokens = max(0, req.seq_len - hit_tokens)

        total_requests += 1
        total_tokens += req.seq_len
        total_hit_tokens += hit_tokens

        if miss_tokens > 0 and lookup_order:
            miss_tokens_by_tier[lookup_order[0].value] += miss_tokens

        for index, chunk_hash in enumerate(req.chunk_hashes):
            if index < hit_prefix:
                for location in lookup_order:
                    tier = tiers.get(location)
                    if tier is not None and tier.contains(chunk_hash):
                        tier.access(chunk_hash)
                        break
            else:
                insert_target = tiers.get(insert_tier)
                if insert_target is not None:
                    insert_target.insert(chunk_hash)

    token_hit_rate = total_hit_tokens / total_tokens if total_tokens else 0.0
    eviction_count = sum(tier.eviction_count for tier in tiers.values())
    return SimulationMetrics(
        token_hit_rate=token_hit_rate,
        total_requests=total_requests,
        total_tokens=total_tokens,
        total_hit_tokens=total_hit_tokens,
        miss_tokens_by_tier=miss_tokens_by_tier,
        eviction_count=eviction_count,
    )


def _pinned_bytes_at_tier(
    *,
    assignments: list[PinAssignment],
    location: CacheLocation,
    prompts: list[PromptRecord],
) -> int:
    total = 0
    for assignment in assignments:
        if assignment.location != location:
            continue
        prompt = _prompt_lookup(prompts, assignment.prompt_id)
        if prompt is not None:
            total += _bytes_for_prompt(prompt)
    return total


def _greedy_recommendations(
    *,
    traffic: list[TrafficRequest],
    prompts: list[PromptRecord],
    tier_capacities: dict[CacheLocation, int],
    lookup_order: tuple[CacheLocation, ...],
    baseline_rate: float,
    max_recommendations: int,
    existing_assignments: list[PinAssignment],
    kv_bytes_per_chunk: int,
) -> tuple[list[PinAssignment], list[PinRecommendation]]:
    selected = list(existing_assignments)
    used_prompts = {assignment.prompt_id for assignment in selected}
    recommendations: list[PinRecommendation] = []

    for _ in range(max_recommendations):
        best: PinRecommendation | None = None
        best_assignment: PinAssignment | None = None

        for prompt in prompts:
            if prompt.prompt_id in used_prompts:
                continue

            prompt_bytes = _bytes_for_prompt(prompt)
            for location in _PINNABLE_TIERS:
                tier_budget = tier_capacities.get(location, 0)
                pinned_at_tier = _pinned_bytes_at_tier(
                    assignments=selected,
                    location=location,
                    prompts=prompts,
                )
                if pinned_at_tier + prompt_bytes > tier_budget:
                    continue

                candidate_assignments = [
                    *selected,
                    PinAssignment(
                        prompt_id=prompt.prompt_id,
                        location=location,
                        chunk_hashes=prompt.chunk_hashes,
                    ),
                ]
                metrics = _simulate(
                    traffic,
                    tier_capacities=tier_capacities,
                    lookup_order=lookup_order,
                    pin_assignments=candidate_assignments,
                    kv_bytes_per_chunk=kv_bytes_per_chunk,
                )
                delta = metrics.token_hit_rate - baseline_rate
                if delta <= 0.0001:
                    continue

                score = delta / max(prompt_bytes, 1)
                confidence = "high" if len(prompt.chunk_hashes) >= 2 else "medium"
                if prompt.primary_location == location:
                    confidence = "high"

                candidate = PinRecommendation(
                    prompt_id=prompt.prompt_id,
                    chunk_hash=prompt.chunk_hashes[0] if prompt.chunk_hashes else "",
                    synthetic=prompt.prompt_id.startswith("synthetic_"),
                    decoded_preview=prompt.decoded_preview,
                    location=location,
                    delta_hit_rate=round(delta, 6),
                    projected_hit_rate=round(metrics.token_hit_rate, 6),
                    bytes_to_pin=prompt_bytes,
                    score=round(score, 12),
                    confidence=confidence,
                    rationale=(
                        f"Pinning {len(prompt.chunk_hashes)} chunk(s) at "
                        f"{location.value} protects {prompt.token_count} tokens "
                        f"from LRU eviction."
                    ),
                )

                if best is None or candidate.score > best.score:
                    best = candidate
                    best_assignment = candidate_assignments[-1]

        if best is None or best_assignment is None:
            break

        recommendations.append(best)
        selected.append(best_assignment)
        used_prompts.add(best_assignment.prompt_id)

    return selected, recommendations


def catalog_from_chunks(
    chunks: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[str]]:
    """Build prompt and chunk rows from a flat chunk listing."""
    grouped: dict[str, list[dict[str, object]]] = {}
    warnings: list[str] = []
    synthetic_count = 0

    for chunk in chunks:
        if not bool(chunk.get("present", False)):
            continue

        prompt_id = str(chunk.get("prompt_id", "")).strip()
        if not prompt_id:
            chunk_hash = str(chunk.get("chunk_hash", ""))
            if not chunk_hash:
                continue
            prompt_id = f"synthetic_{chunk_hash[:16]}"
            synthetic_count += 1
        grouped.setdefault(prompt_id, []).append(chunk)

    if synthetic_count:
        warnings.append(
            f"{synthetic_count} runtime chunk(s) had no prompt_id; "
            "each was analyzed as an individual synthetic prompt."
        )

    prompts: list[dict[str, object]] = []
    catalog_chunks: list[dict[str, object]] = []

    for prompt_id, prompt_chunks in grouped.items():
        previews = [
            str(item["decoded_preview"])
            for item in prompt_chunks
            if item.get("decoded_preview")
        ]
        chunk_hashes = [str(item["chunk_hash"]) for item in prompt_chunks]
        prompts.append(
            {
                "prompt_id": prompt_id,
                "decoded_preview": previews[0] if previews else prompt_id,
                "token_count": sum(int(item.get("token_count", 0)) for item in prompt_chunks),
                "chunk_hashes": chunk_hashes,
            }
        )
        for item in prompt_chunks:
            catalog_chunks.append(
                {
                    "chunk_hash": str(item["chunk_hash"]),
                    "prompt_id": prompt_id,
                    "token_count": int(item.get("token_count", 0)),
                    "location": str(item.get("location", "")),
                    "pinned": bool(item.get("pinned")),
                    "decoded_preview": str(item.get("decoded_preview", "")),
                }
            )

    return prompts, catalog_chunks, warnings


def run_pin_extrapolation(
    request: PinExtrapolationRequest,
    *,
    prompts: list[dict[str, object]],
    chunks: list[dict[str, object]],
    catalog_warnings: list[str] | None = None,
) -> PinExtrapolationResponse:
    """Run baseline vs candidate pin extrapolation analysis."""
    warnings: list[str] = list(catalog_warnings or [])

    chunks_by_hash = {str(chunk["chunk_hash"]): chunk for chunk in chunks}
    prompt_records = build_prompt_records(
        prompts=prompts,
        chunks_by_hash=chunks_by_hash,
    )

    if not prompt_records:
        return PinExtrapolationResponse(
            baseline_token_hit_rate=0.0,
            candidate_token_hit_rate=0.0,
            delta_hit_rate=0.0,
            total_requests=0,
            total_tokens=0,
            baseline_hit_tokens=0,
            candidate_hit_tokens=0,
            baseline_eviction_count=0,
            candidate_eviction_count=0,
            applied_pin_count=0,
            traffic_source="catalog_replay",
            warnings=["No registered prompts available for analysis."],
        )

    traffic = synthesize_traffic(
        prompt_records,
        request_count=request.request_count,
        seed=request.seed,
    )

    tier_capacities = _resolve_tier_capacities(request)
    lookup_order = _resolve_lookup_order(request)

    if CacheLocation.LOCAL_GPU in lookup_order:
        warnings.append(
            "LocalGPUBackend is observed-only; GPU is excluded from pin targets."
        )

    avg_chunk_tokens = max(
        1,
        round(
            sum(sum(p.chunk_token_counts) for p in prompt_records)
            / sum(len(p.chunk_token_counts) for p in prompt_records)
        ),
    )
    kv_bytes_per_chunk = avg_chunk_tokens * _KV_BYTES_PER_TOKEN

    baseline_assignments = [
        PinAssignment(
            prompt_id=prompt.prompt_id,
            location=prompt.primary_location or CacheLocation.LOCAL_CPU,
            chunk_hashes=prompt.chunk_hashes,
        )
        for prompt in prompt_records
        if prompt.pinned and prompt.primary_location in _PINNABLE_TIERS
    ]

    baseline_metrics = _simulate(
        traffic,
        tier_capacities=tier_capacities,
        lookup_order=lookup_order,
        pin_assignments=baseline_assignments,
        kv_bytes_per_chunk=kv_bytes_per_chunk,
    )

    proposed_assignments = _assignments_from_request(request, prompt_records)
    candidate_assignments = [*baseline_assignments]
    for assignment in proposed_assignments:
        if any(
            existing.prompt_id == assignment.prompt_id
            for existing in candidate_assignments
        ):
            continue
        candidate_assignments.append(assignment)

    recommendations: list[PinRecommendation] = []
    if request.auto_recommend and not proposed_assignments:
        candidate_assignments, recommendations = _greedy_recommendations(
            traffic=traffic,
            prompts=prompt_records,
            tier_capacities=tier_capacities,
            lookup_order=lookup_order,
            baseline_rate=baseline_metrics.token_hit_rate,
            max_recommendations=request.max_recommendations,
            existing_assignments=list(baseline_assignments),
            kv_bytes_per_chunk=kv_bytes_per_chunk,
        )
    elif proposed_assignments:
        for assignment in proposed_assignments:
            prompt = _prompt_lookup(prompt_records, assignment.prompt_id)
            if prompt is None:
                continue
            candidate_assignments.append(assignment)

    candidate_metrics = _simulate(
        traffic,
        tier_capacities=tier_capacities,
        lookup_order=lookup_order,
        pin_assignments=candidate_assignments,
        kv_bytes_per_chunk=kv_bytes_per_chunk,
    )

    if request.auto_recommend and proposed_assignments:
        warnings.append(
            "proposed_pins were supplied; auto_recommend suggestions were skipped."
        )

    delta = candidate_metrics.token_hit_rate - baseline_metrics.token_hit_rate

    return PinExtrapolationResponse(
        baseline_token_hit_rate=round(baseline_metrics.token_hit_rate, 6),
        candidate_token_hit_rate=round(candidate_metrics.token_hit_rate, 6),
        delta_hit_rate=round(delta, 6),
        total_requests=baseline_metrics.total_requests,
        total_tokens=baseline_metrics.total_tokens,
        baseline_hit_tokens=baseline_metrics.total_hit_tokens,
        candidate_hit_tokens=candidate_metrics.total_hit_tokens,
        baseline_miss_tokens_by_tier=baseline_metrics.miss_tokens_by_tier,
        candidate_miss_tokens_by_tier=candidate_metrics.miss_tokens_by_tier,
        baseline_eviction_count=baseline_metrics.eviction_count,
        candidate_eviction_count=candidate_metrics.eviction_count,
        applied_pin_count=len(candidate_assignments) - len(baseline_assignments),
        recommendations=recommendations,
        traffic_source="catalog_replay",
        warnings=warnings,
    )