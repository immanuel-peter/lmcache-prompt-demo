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
        animationDelay: `${index * 45}ms`,
      }}
      className={cn(
        "card rise rounded-xl border border-[var(--line)] bg-[var(--panel)] p-3.5",
        chunk.observed_only
          ? "cursor-not-allowed"
          : "cursor-grab active:cursor-grabbing",
        isDragging && "dragging z-50",
      )}
      {...listeners}
      {...attributes}
    >
      <div className="mb-2.5 flex items-start justify-between gap-2">
        <code className="font-mono text-[11px] text-[var(--accent-bright)]">
          {truncateHash(chunk.chunk_hash, 14)}
        </code>
        <div className="flex shrink-0 gap-1">
          {chunk.pinned && (
            <Badge variant="pinned">
              <Pin className="h-2.5 w-2.5" />
              pinned
            </Badge>
          )}
          {chunk.observed_only && (
            <Badge variant="gpu">
              <Lock className="h-2.5 w-2.5" />
              observed
            </Badge>
          )}
        </div>
      </div>

      <p className="mb-3 line-clamp-2 text-[12px] leading-relaxed text-[var(--fg-muted)]">
        {chunk.decoded_preview || (
          <span className="italic text-[var(--fg-subtle)]">
            No decoded preview
          </span>
        )}
      </p>

      <div className="grid grid-cols-2 gap-x-3 gap-y-2 border-t border-[var(--line)] pt-2.5 text-[10.5px]">
        <Field label="tokens" value={String(chunk.token_count)} mono />
        <Field label="est. KV" value={formatBytes(kvEstimate)} mono />
        <Field
          label="prompt"
          value={truncateHash(chunk.prompt_id, 16)}
          mono
          span
        />
        <Field label="model" value={chunk.model} span />
      </div>
    </article>
  );
}

function Field({
  label,
  value,
  mono,
  span,
}: {
  label: string;
  value: string;
  mono?: boolean;
  span?: boolean;
}) {
  return (
    <div className={span ? "col-span-2 min-w-0" : "min-w-0"}>
      <dt className="text-[var(--fg-subtle)]">{label}</dt>
      <dd
        className={cn(
          "truncate text-[var(--fg)]",
          mono && "font-mono tabular-nums",
        )}
      >
        {value}
      </dd>
    </div>
  );
}
