"use client";

import { ChunkCard } from "@/components/chunk-card";
import { Badge } from "@/components/ui/badge";
import type { CacheChunk, CacheLocation } from "@/lib/types";
import { LOCATION_LABELS } from "@/lib/types";
import { cn, formatBytes } from "@/lib/utils";
import { useDroppable } from "@dnd-kit/core";
import { HardDrive, Cpu, Zap } from "lucide-react";

const TIER_ICONS = {
  LocalGPUBackend: Zap,
  LocalCPUBackend: Cpu,
  LocalDiskBackend: HardDrive,
};

const TIER_STYLES = {
  LocalGPUBackend: {
    border: "border-amber-500/20",
    header: "text-amber-300",
    glow: "shadow-[inset_0_1px_0_rgba(245,158,11,0.15)]",
    badge: "gpu" as const,
  },
  LocalCPUBackend: {
    border: "border-cyan-500/20",
    header: "text-cyan-300",
    glow: "shadow-[inset_0_1px_0_rgba(34,211,238,0.15)]",
    badge: "cpu" as const,
  },
  LocalDiskBackend: {
    border: "border-indigo-500/20",
    header: "text-indigo-300",
    glow: "shadow-[inset_0_1px_0_rgba(129,140,248,0.15)]",
    badge: "disk" as const,
  },
};

interface StorageTierColumnProps {
  location: CacheLocation;
  chunks: CacheChunk[];
  bytesEstimate: number;
  observedOnly: boolean;
  supportsPin: boolean;
}

export function StorageTierColumn({
  location,
  chunks,
  bytesEstimate,
  observedOnly,
  supportsPin,
}: StorageTierColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: location });
  const Icon = TIER_ICONS[location];
  const styles = TIER_STYLES[location];

  return (
    <section
      ref={setNodeRef}
      className={cn(
        "glass flex min-h-[420px] flex-col rounded-2xl border p-4 transition-all",
        styles.border,
        styles.glow,
        isOver && "drop-zone-active animate-pulse-glow",
      )}
    >
      <header className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-lg bg-white/5",
              styles.header,
            )}
          >
            <Icon className="h-4 w-4" />
          </div>
          <div>
            <h2
              className={cn(
                "font-[family-name:var(--font-syne)] text-sm font-semibold tracking-wide",
                styles.header,
              )}
            >
              {LOCATION_LABELS[location]}
            </h2>
            <p className="text-[10px] text-slate-500">{location}</p>
          </div>
        </div>
        <Badge variant={styles.badge}>{chunks.length} chunks</Badge>
      </header>

      <div className="mb-3 flex items-center justify-between text-[10px] text-slate-500">
        <span>{formatBytes(bytesEstimate)} estimated</span>
        {observedOnly ? (
          <span className="text-amber-400/80">read-only</span>
        ) : supportsPin ? (
          <span className="text-emerald-400/70">pin · evict · move</span>
        ) : null}
      </div>

      <div className="flex flex-1 flex-col gap-3 overflow-y-auto pr-1">
        {chunks.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-white/10 py-12 text-center">
            <p className="text-xs text-slate-500">Drop chunks here</p>
            {!observedOnly && (
              <p className="mt-1 text-[10px] text-slate-600">
                Drag from CPU ↔ External
              </p>
            )}
          </div>
        ) : (
          chunks.map((chunk, index) => (
            <ChunkCard key={chunk.chunk_hash} chunk={chunk} index={index} />
          ))
        )}
      </div>
    </section>
  );
}
