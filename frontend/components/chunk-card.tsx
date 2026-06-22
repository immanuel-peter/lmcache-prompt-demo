"use client";

import { Badge } from "@/components/ui/badge";
import type { CacheChunk } from "@/lib/types";
import { cn, formatBytes, truncateHash } from "@/lib/utils";
import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { Lock, Pin } from "lucide-react";

interface ChunkCardProps {
  chunk: CacheChunk;
  index: number;
}

export function ChunkCard({ chunk, index }: ChunkCardProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: chunk.chunk_hash,
      data: { chunk },
      disabled: chunk.observed_only,
    });

  const style = transform
    ? { transform: CSS.Translate.toString(transform) }
    : undefined;

  const kvEstimate = chunk.token_count * 512;

  return (
    <article
      ref={setNodeRef}
      data-chunk-hash={chunk.chunk_hash}
      style={{
        ...style,
        animationDelay: `${index * 60}ms`,
      }}
      className={cn(
        "chunk-card glass fade-up group cursor-grab rounded-xl p-4 active:cursor-grabbing",
        isDragging && "dragging z-50",
        chunk.observed_only && "cursor-not-allowed opacity-90",
      )}
      {...listeners}
      {...attributes}
    >
      <div className="mb-3 flex items-start justify-between gap-2">
        <code className="text-[11px] text-blue-300/80">
          {truncateHash(chunk.chunk_hash, 14)}
        </code>
        <div className="flex shrink-0 gap-1">
          {chunk.pinned && (
            <Badge variant="pinned">
              <Pin className="mr-0.5 h-2.5 w-2.5" />
              pinned
            </Badge>
          )}
          {chunk.observed_only && (
            <Badge variant="gpu">
              <Lock className="mr-0.5 h-2.5 w-2.5" />
              observed
            </Badge>
          )}
        </div>
      </div>

      <p className="mb-3 line-clamp-3 text-xs leading-relaxed text-slate-300">
        {chunk.decoded_preview || (
          <span className="text-slate-500 italic">No decoded preview</span>
        )}
      </p>

      <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[10px]">
        <div>
          <dt className="text-slate-500">tokens</dt>
          <dd className="font-medium text-slate-200">{chunk.token_count}</dd>
        </div>
        <div>
          <dt className="text-slate-500">est. KV</dt>
          <dd className="font-medium text-slate-200">{formatBytes(kvEstimate)}</dd>
        </div>
        <div className="col-span-2">
          <dt className="text-slate-500">prompt</dt>
          <dd className="truncate font-medium text-slate-300">
            {truncateHash(chunk.prompt_id, 16)}
          </dd>
        </div>
        <div className="col-span-2">
          <dt className="text-slate-500">model</dt>
          <dd className="truncate text-slate-400">{chunk.model}</dd>
        </div>
      </dl>
    </article>
  );
}
