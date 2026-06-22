"use client";

import { Header } from "@/components/header";
import { StatsBar } from "@/components/stats-bar";
import { StorageTierColumn } from "@/components/storage-tier-column";
import { Badge } from "@/components/ui/badge";
import {
  evictPrompt,
  fetchCapabilities,
  fetchChunks,
  fetchConnectivity,
  fetchSummary,
  ingestEvents,
  moveChunk,
  pinChunk,
} from "@/lib/api";
import type {
  BackendCapability,
  CacheChunk,
  CacheLocation,
  CacheSummary,
  Connectivity,
} from "@/lib/types";
import { TIER_ORDER } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { ChunkCard } from "@/components/chunk-card";
import { Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

const DEFAULT_MODEL = "meta-llama/Llama-3.1-8B-Instruct";
const EVICT_ZONE = "evict-zone";

function EvictDropZone() {
  const { setNodeRef, isOver } = useDroppable({ id: EVICT_ZONE });
  return (
    <div
      ref={setNodeRef}
      className={cn(
        "glass flex items-center justify-center gap-2 rounded-xl border border-dashed border-red-500/25 px-4 py-3 text-xs text-red-300/80 transition-all",
        isOver && "drop-zone-active border-red-400/50 bg-red-950/20",
      )}
    >
      <Trash2 className="h-4 w-4" />
      Drop here to evict from tier
    </div>
  );
}

export function PromptRegistryDemo() {
  const [chunks, setChunks] = useState<CacheChunk[]>([]);
  const [summary, setSummary] = useState<CacheSummary | null>(null);
  const [connectivity, setConnectivity] = useState<Connectivity | null>(null);
  const [capabilities, setCapabilities] = useState<BackendCapability[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeChunk, setActiveChunk] = useState<CacheChunk | null>(null);

  const tenantId = connectivity?.demo_tenant_id ?? "demo-tenant";

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  );

  const loadData = useCallback(async () => {
    const [conn, caps] = await Promise.all([
      fetchConnectivity(),
      fetchCapabilities(),
    ]);
    setConnectivity(conn);
    setCapabilities(caps);

    try {
      await ingestEvents();
    } catch {
      // Best-effort in demo mode
    }

    const [chunkList, summaryData] = await Promise.all([
      fetchChunks(conn.demo_tenant_id),
      fetchSummary(),
    ]);
    setChunks(chunkList);
    setSummary(summaryData);
  }, []);

  useEffect(() => {
    loadData()
      .catch((err) =>
        toast.error(err instanceof Error ? err.message : "Failed to load data"),
      )
      .finally(() => setLoading(false));
  }, [loadData]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await loadData();
      toast.success("Registry refreshed");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  }, [loadData]);

  const chunksByTier = useMemo(() => {
    const grouped: Record<CacheLocation, CacheChunk[]> = {
      LocalGPUBackend: [],
      LocalCPUBackend: [],
      LocalDiskBackend: [],
    };
    for (const chunk of chunks) {
      const loc = chunk.location as CacheLocation;
      if (grouped[loc]) grouped[loc].push(chunk);
    }
    return grouped;
  }, [chunks]);

  const capByLocation = useMemo(() => {
    const map = new Map<CacheLocation, BackendCapability>();
    for (const cap of capabilities) {
      map.set(cap.location, cap);
    }
    return map;
  }, [capabilities]);

  function handleDragStart(event: DragStartEvent) {
    const chunk = event.active.data.current?.chunk as CacheChunk | undefined;
    if (chunk?.observed_only) {
      toast.info("GPU residency is observed-only — pinning not wired yet.");
      return;
    }
    setActiveChunk(chunk ?? null);
  }

  async function handleDragEnd(event: DragEndEvent) {
    setActiveChunk(null);
    const chunk = event.active.data.current?.chunk as CacheChunk | undefined;
    if (!chunk || !event.over) return;

    const targetId = event.over.id as string;
    const sourceLocation = chunk.location as CacheLocation;

    if (chunk.observed_only || sourceLocation === "LocalGPUBackend") {
      toast.info("GPU residency is observed-only — pinning not wired yet.");
      return;
    }

    if (targetId === "LocalGPUBackend") {
      toast.info("GPU pinning is not wired yet — chunks are observed only.");
      return;
    }

    if (targetId === EVICT_ZONE) {
      if (chunk.pinned) {
        toast.error("Unpin before evicting pinned chunks.");
        return;
      }
      try {
        await evictPrompt(chunk.prompt_id, tenantId, [sourceLocation]);
        toast.success(`Evicted from ${sourceLocation}`);
        await loadData();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Evict failed");
      }
      return;
    }

    const targetLocation = targetId as CacheLocation;
    if (targetLocation === sourceLocation) return;

    if (
      targetLocation !== "LocalCPUBackend" &&
      targetLocation !== "LocalDiskBackend"
    ) {
      return;
    }

    try {
      await moveChunk(chunk.chunk_hash, targetLocation, tenantId);
      toast.success(`Moved to ${targetLocation}`);
      await loadData();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Move failed");
    }
  }

  async function handleChunkDoubleClick(chunk: CacheChunk) {
    if (chunk.observed_only) {
      toast.info("GPU residency is observed-only — pinning not wired yet.");
      return;
    }
    if (chunk.pinned) {
      toast.info("Chunk is already pinned.");
      return;
    }
    try {
      const result = await pinChunk(chunk.chunk_hash, tenantId);
      toast.success(`Pinned · lease ${result.pin_id.slice(0, 12)}…`);
      await loadData();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Pin failed");
    }
  }

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center py-32">
        <div className="text-center">
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-blue-500/30 border-t-blue-400" />
          <p className="text-sm text-slate-400">Loading prompt registry…</p>
        </div>
      </div>
    );
  }

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <Header
        tenantId={tenantId}
        defaultModel={DEFAULT_MODEL}
        onRefresh={refresh}
        onRegistered={refresh}
        refreshing={refreshing}
      />

      <StatsBar summary={summary} connectivity={connectivity} />

      <div className="mb-4 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
        <Badge variant="muted">double-click chunk → pin</Badge>
        <Badge variant="muted">drag CPU ↔ disk → move</Badge>
        <Badge variant="muted">drop on evict zone → remove</Badge>
        <Badge variant="gpu">GPU → read-only</Badge>
      </div>

      <div
        className="grid gap-4 lg:grid-cols-3"
        onDoubleClick={(e) => {
          const card = (e.target as HTMLElement).closest("[data-chunk-hash]");
          if (!card) return;
          const hash = card.getAttribute("data-chunk-hash");
          const chunk = chunks.find((c) => c.chunk_hash === hash);
          if (chunk) void handleChunkDoubleClick(chunk);
        }}
      >
        {TIER_ORDER.map((location) => {
          const cap = capByLocation.get(location);
          const tierChunks = chunksByTier[location];
          const bytes =
            summary?.estimated_kv_bytes_by_location[location] ??
            tierChunks.reduce((acc, c) => acc + c.token_count * 512, 0);

          return (
            <div key={location} data-chunk-hash={undefined}>
              <StorageTierColumn
                location={location}
                chunks={tierChunks}
                bytesEstimate={bytes}
                observedOnly={cap?.observed_only ?? location === "LocalGPUBackend"}
                supportsPin={cap?.supports_pin ?? location !== "LocalGPUBackend"}
              />
            </div>
          );
        })}
      </div>

      <div className="mt-4">
        <EvictDropZone />
      </div>

      <DragOverlay>
        {activeChunk ? (
          <div className="w-72 rotate-2 opacity-90">
            <ChunkCard chunk={activeChunk} index={0} />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
