"use client";

import type { CacheSummary, Connectivity } from "@/lib/types";
import { cn, formatBytes } from "@/lib/utils";
import { Activity, Database, Layers, Pin } from "lucide-react";

interface StatsBarProps {
  summary: CacheSummary | null;
  connectivity: Connectivity | null;
}

const statItems = [
  { key: "prompts", icon: Layers, label: "Prompts" },
  { key: "chunks", icon: Database, label: "Chunks" },
  { key: "pins", icon: Pin, label: "Active Pins" },
  { key: "observed", icon: Activity, label: "GPU Observed" },
] as const;

export function StatsBar({ summary, connectivity }: StatsBarProps) {
  const values: Record<string, string | number> = {
    prompts: summary?.total_prompts ?? "—",
    chunks: summary?.total_chunks ?? "—",
    pins: summary?.active_pin_leases ?? "—",
    observed: summary?.observed_only_chunk_count ?? "—",
  };

  const totalBytes = summary
    ? Object.values(summary.estimated_kv_bytes_by_location).reduce(
        (a, b) => a + b,
        0,
      )
    : 0;

  return (
    <div className="glass fade-up mb-6 rounded-2xl p-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap gap-6">
          {statItems.map(({ key, icon: Icon, label }) => (
            <div key={key} className="flex items-center gap-2">
              <Icon className="h-4 w-4 text-blue-400/70" />
              <div>
                <p className="text-[10px] uppercase tracking-wider text-slate-500">
                  {label}
                </p>
                <p className="font-[family-name:var(--font-syne)] text-lg font-semibold text-white">
                  {values[key]}
                </p>
              </div>
            </div>
          ))}
          <div className="flex items-center gap-2">
            <div>
              <p className="text-[10px] uppercase tracking-wider text-slate-500">
                Total KV
              </p>
              <p className="font-[family-name:var(--font-syne)] text-lg font-semibold text-blue-300">
                {summary ? formatBytes(totalBytes) : "—"}
              </p>
            </div>
          </div>
        </div>

        {connectivity && (
          <div className="flex flex-wrap items-center gap-2 text-[10px]">
            <span
              className={cn(
                "rounded-full border px-2.5 py-1 font-semibold uppercase tracking-wider",
                connectivity.mode === "proxy"
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                  : "border-blue-500/30 bg-blue-500/10 text-blue-300",
              )}
            >
              {connectivity.mode} mode
            </span>
            <span className="text-slate-500">
              tenant: {connectivity.demo_tenant_id}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
