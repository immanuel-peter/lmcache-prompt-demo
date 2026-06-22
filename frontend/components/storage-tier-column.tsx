"use client";

import { ChunkCard } from "@/components/chunk-card";
import type { CacheChunk, CacheLocation } from "@/lib/types";
import { LOCATION_LABELS } from "@/lib/types";
import { cn, formatBytes } from "@/lib/utils";
import { useDroppable } from "@dnd-kit/core";
import { Cpu, HardDrive, Zap } from "lucide-react";

const TIER_ICONS = {
  LocalGPUBackend: Zap,
  LocalCPUBackend: Cpu,
  LocalDiskBackend: HardDrive,
};

const TIER_CLASS = {
  LocalGPUBackend: "tier-gpu",
  LocalCPUBackend: "tier-cpu",
  LocalDiskBackend: "tier-disk",
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

  return (
    <section
      ref={setNodeRef}
      className={cn(
        "panel flex h-[clamp(420px,calc(100vh_-_340px),720px)] flex-col p-3.5 transition-colors",
        TIER_CLASS[location],
        isOver && "drop-active",
      )}
    >
      <header className="mb-3.5 flex items-center justify-between border-b border-[var(--line)] pb-3.5">
        <div className="flex items-center gap-2.5">
          <span className="tier-dot" />
          <Icon className="h-4 w-4 text-[var(--fg-muted)]" />
          <div className="leading-tight">
            <h2 className="text-[13px] font-semibold text-[var(--fg)]">
              {LOCATION_LABELS[location]}
            </h2>
            <p className="font-mono text-[10px] text-[var(--fg-subtle)]">
              {location}
            </p>
          </div>
        </div>
        <div className="text-right leading-tight">
          <p className="font-mono text-[13px] tabular-nums text-[var(--fg)]">
            {chunks.length}
          </p>
          <p className="text-[10px] text-[var(--fg-subtle)]">chunks</p>
        </div>
      </header>

      <div className="mb-3 flex items-center justify-between text-[10.5px]">
        <span className="font-mono text-[var(--fg-subtle)]">
          {formatBytes(bytesEstimate)}
        </span>
        {observedOnly ? (
          <span className="text-[#e0b878]">read-only</span>
        ) : supportsPin ? (
          <span className="text-[var(--fg-subtle)]">pin · evict · move</span>
        ) : null}
      </div>

      <div className="scroll-thin flex flex-1 flex-col gap-2.5 overflow-y-auto pr-0.5">
        {chunks.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-[var(--line)] py-12 text-center">
            <p className="text-[12px] text-[var(--fg-subtle)]">
              {observedOnly ? "Nothing resident" : "Drop chunks here"}
            </p>
            {!observedOnly && (
              <p className="mt-1 text-[10.5px] text-[var(--fg-subtle)]/70">
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
