"use client";

import type { CacheSummary, Connectivity } from "@/lib/types";
import { cn, formatBytes } from "@/lib/utils";

interface StatsBarProps {
  summary: CacheSummary | null;
  connectivity: Connectivity | null;
}

export function StatsBar({ summary, connectivity }: StatsBarProps) {
  const totalBytes = summary
    ? Object.values(summary.estimated_kv_bytes_by_location).reduce(
        (a, b) => a + b,
        0,
      )
    : 0;

  const stats = [
    { label: "Prompts", value: summary?.total_prompts ?? "—" },
    { label: "Chunks", value: summary?.total_chunks ?? "—" },
    { label: "Active pins", value: summary?.active_pin_leases ?? "—" },
    { label: "GPU observed", value: summary?.observed_only_chunk_count ?? "—" },
    {
      label: "Total KV",
      value: summary ? formatBytes(totalBytes) : "—",
      accent: true,
    },
  ];

  return (
    <div className="panel rise mb-5 flex flex-wrap items-stretch divide-x divide-[var(--line)]">
      {stats.map((s) => (
        <div key={s.label} className="flex flex-col gap-1 px-5 py-3.5">
          <span className="text-[10px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            {s.label}
          </span>
          <span
            className={cn(
              "font-mono text-[19px] leading-none tabular-nums",
              s.accent ? "text-[var(--accent-bright)]" : "text-[var(--fg)]",
            )}
          >
            {s.value}
          </span>
        </div>
      ))}

      {connectivity && (
        <div className="ml-auto flex items-center gap-2.5 px-5">
          <span
            className={cn(
              "inline-flex items-center gap-1.5 text-[11px] font-medium",
              connectivity.mode === "proxy"
                ? "text-[#86efac]"
                : "text-[var(--accent-bright)]",
            )}
          >
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                connectivity.mode === "proxy"
                  ? "bg-[#4ade80]"
                  : "bg-[var(--accent)]",
              )}
            />
            {connectivity.mode} mode
          </span>
          <span className="font-mono text-[11px] text-[var(--fg-subtle)]">
            {connectivity.demo_tenant_id}
          </span>
        </div>
      )}
    </div>
  );
}
