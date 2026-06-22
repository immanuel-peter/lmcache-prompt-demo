"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  fetchConnectivity,
  pinChunk,
  pinPrompt,
  runPinExtrapolation,
} from "@/lib/api";
import type {
  CacheLocation,
  Connectivity,
  PinExtrapolationResponse,
  PinRecommendation,
} from "@/lib/types";
import { LOCATION_LABELS } from "@/lib/types";
import { cn, formatBytes } from "@/lib/utils";
import {
  ArrowRight,
  Cpu,
  HardDrive,
  Pin,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

function tierBadgeVariant(
  location: CacheLocation,
): "cpu" | "disk" | "gpu" | "default" {
  if (location === "LocalCPUBackend") return "cpu";
  if (location === "LocalDiskBackend") return "disk";
  if (location === "LocalGPUBackend") return "gpu";
  return "default";
}

function HitRateCard({
  label,
  rate,
  hitTokens,
  totalTokens,
  accent,
  delayMs,
}: {
  label: string;
  rate: number;
  hitTokens: number;
  totalTokens: number;
  accent: "baseline" | "candidate";
  delayMs: number;
}) {
  const pct = (rate * 100).toFixed(1);
  const isCandidate = accent === "candidate";
  return (
    <div
      className={cn(
        "panel rise relative overflow-hidden p-5",
        isCandidate && "border-[var(--accent-line)]",
      )}
      style={{ animationDelay: `${delayMs}ms` }}
    >
      <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-[var(--fg-subtle)]">
        {label}
      </p>
      <p
        className={cn(
          "mt-2.5 font-mono text-[40px] font-medium leading-none tabular-nums",
          isCandidate ? "text-[var(--accent-bright)]" : "text-[var(--fg)]",
        )}
      >
        {pct}
        <span className="text-[22px] text-[var(--fg-subtle)]">%</span>
      </p>
      <p className="mt-2.5 font-mono text-[11px] text-[var(--fg-subtle)]">
        {hitTokens.toLocaleString()} / {totalTokens.toLocaleString()} tokens hit
      </p>
      <div className="mt-4 h-1 overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-700",
            isCandidate ? "bg-[var(--accent)]" : "bg-[var(--fg-subtle)]",
          )}
          style={{ width: `${Math.min(rate * 100, 100)}%` }}
        />
      </div>
    </div>
  );
}

function RecommendationRow({
  item,
  index,
  tenantId,
  onPinned,
}: {
  item: PinRecommendation;
  index: number;
  tenantId: string;
  onPinned: () => void;
}) {
  const [applying, setApplying] = useState(false);

  async function handleApply() {
    if (item.synthetic) {
      toast.info(
        "Runtime-only chunk — register the prompt in the KV catalog before pinning.",
      );
      return;
    }
    setApplying(true);
    try {
      const result = item.chunk_hash
        ? await pinChunk(item.chunk_hash, tenantId)
        : await pinPrompt(item.prompt_id, tenantId, item.location);
      toast.success(`Pinned · lease ${result.pin_id.slice(0, 12)}…`);
      onPinned();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Pin failed");
    } finally {
      setApplying(false);
    }
  }

  return (
    <div
      className="panel panel-hover rise flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"
      style={{ animationDelay: `${120 + index * 55}ms` }}
    >
      <div className="min-w-0 flex-1">
        <div className="mb-1.5 flex flex-wrap items-center gap-2">
          <span className="font-mono text-[12px] text-[var(--fg-subtle)]">
            {String(index + 1).padStart(2, "0")}
          </span>
          <Badge variant={tierBadgeVariant(item.location)}>
            {LOCATION_LABELS[item.location]}
          </Badge>
          <Badge variant="muted">{item.confidence} confidence</Badge>
          {item.synthetic ? (
            <Badge variant="muted">runtime chunk</Badge>
          ) : null}
        </div>
        <p className="truncate text-[13px] text-[var(--fg)]">
          {item.decoded_preview || item.prompt_id}
        </p>
        <p className="mt-1 text-[11.5px] text-[var(--fg-subtle)]">
          {item.rationale}
        </p>
      </div>

      <div className="flex shrink-0 flex-wrap items-center gap-5">
        <div className="text-right">
          <p className="text-[10px] uppercase tracking-wider text-[var(--fg-subtle)]">
            Est. lift
          </p>
          <p className="font-mono text-[15px] tabular-nums text-[#86efac]">
            +{(item.delta_hit_rate * 100).toFixed(2)}%
          </p>
        </div>
        <div className="text-right">
          <p className="text-[10px] uppercase tracking-wider text-[var(--fg-subtle)]">
            KV size
          </p>
          <p className="font-mono text-[13px] text-[var(--fg-muted)]">
            {formatBytes(item.bytes_to_pin)}
          </p>
        </div>
        <Button
          variant="outline"
          disabled={applying}
          onClick={() => void handleApply()}
        >
          <Pin className="h-3.5 w-3.5" />
          {applying ? "Pinning…" : "Apply pin"}
        </Button>
      </div>
    </div>
  );
}

export function PinAnalysisPanel() {
  const [connectivity, setConnectivity] = useState<Connectivity | null>(null);
  const [result, setResult] = useState<PinExtrapolationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [cpuCapacityGib, setCpuCapacityGib] = useState("8");
  const [diskCapacityGib, setDiskCapacityGib] = useState("64");
  const [requestCount, setRequestCount] = useState("240");

  const tenantId = connectivity?.demo_tenant_id ?? "demo-tenant";

  const runAnalysis = useCallback(async () => {
    setRunning(true);
    try {
      const data = await runPinExtrapolation({
        tenant_id: tenantId,
        tier_capacities_gib: {
          LocalCPUBackend: Number(cpuCapacityGib) || 8,
          LocalDiskBackend: Number(diskCapacityGib) || 64,
        },
        auto_recommend: true,
        max_recommendations: 5,
        request_count: Number(requestCount) || 240,
      });
      setResult(data);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setRunning(false);
      setLoading(false);
    }
  }, [tenantId, cpuCapacityGib, diskCapacityGib, requestCount]);

  useEffect(() => {
    fetchConnectivity()
      .then(setConnectivity)
      .catch((err) =>
        toast.error(err instanceof Error ? err.message : "Failed to load config"),
      );
  }, []);

  useEffect(() => {
    if (connectivity) {
      void runAnalysis();
    }
  }, [connectivity, runAnalysis]);

  const deltaPositive = (result?.delta_hit_rate ?? 0) > 0;
  const sweepBars = useMemo(() => {
    if (!result) return [];
    const baseline = result.baseline_token_hit_rate;
    let cumulative = baseline;
    return result.recommendations.map((rec) => {
      cumulative += rec.delta_hit_rate;
      return {
        label: rec.decoded_preview.slice(0, 24) || rec.prompt_id.slice(0, 12),
        rate: Math.min(cumulative, 1),
        delta: rec.delta_hit_rate,
      };
    });
  }, [result]);

  if (loading && !result) {
    return (
      <div className="flex items-center justify-center py-32">
        <div className="text-center">
          <div className="mx-auto mb-4 h-7 w-7 animate-spin rounded-full border-2 border-[var(--line-strong)] border-t-[var(--accent)]" />
          <p className="text-[13px] text-[var(--fg-muted)]">
            Running extrapolation…
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5 pb-10">
      {/* Controls */}
      <div className="panel rise flex flex-col gap-4 p-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="grid gap-4 sm:grid-cols-3 lg:flex-1">
          <ControlField
            icon={<Cpu className="h-3 w-3" />}
            label="CPU capacity (GiB)"
          >
            <Input
              type="number"
              min={1}
              step={1}
              value={cpuCapacityGib}
              onChange={(e) => setCpuCapacityGib(e.target.value)}
            />
          </ControlField>
          <ControlField
            icon={<HardDrive className="h-3 w-3" />}
            label="Disk capacity (GiB)"
          >
            <Input
              type="number"
              min={1}
              step={1}
              value={diskCapacityGib}
              onChange={(e) => setDiskCapacityGib(e.target.value)}
            />
          </ControlField>
          <ControlField
            icon={<Sparkles className="h-3 w-3" />}
            label="Simulated requests"
          >
            <Input
              type="number"
              min={50}
              step={50}
              value={requestCount}
              onChange={(e) => setRequestCount(e.target.value)}
            />
          </ControlField>
        </div>

        <Button
          onClick={() => void runAnalysis()}
          disabled={running}
          className="self-end"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", running && "animate-spin")} />
          {running ? "Simulating…" : "Re-run analysis"}
        </Button>
      </div>

      {result?.warnings.length ? (
        <div className="rise rounded-xl border border-amber-500/20 bg-amber-500/[0.05] px-4 py-3 text-[12px] text-amber-200/90">
          {result.warnings.join(" · ")}
        </div>
      ) : null}

      {result && (
        <>
          <div className="grid gap-3.5 lg:grid-cols-[1fr_auto_1fr] lg:items-center">
            <HitRateCard
              label="Baseline · LRU only"
              rate={result.baseline_token_hit_rate}
              hitTokens={result.baseline_hit_tokens}
              totalTokens={result.total_tokens}
              accent="baseline"
              delayMs={0}
            />

            <div className="flex flex-col items-center justify-center px-2">
              <div
                className={cn(
                  "flex items-center gap-1.5 rounded-lg border px-3 py-2",
                  deltaPositive
                    ? "border-[#4ade80]/25 text-[#86efac]"
                    : "border-[var(--line-strong)] text-[var(--fg-muted)]",
                )}
              >
                <ArrowRight className="h-4 w-4" />
                <span className="font-mono text-[14px] tabular-nums">
                  {deltaPositive ? "+" : ""}
                  {(result.delta_hit_rate * 100).toFixed(2)}%
                </span>
              </div>
              <p className="mt-2 text-[10px] uppercase tracking-wider text-[var(--fg-subtle)]">
                Projected lift
              </p>
            </div>

            <HitRateCard
              label="With recommended pins"
              rate={result.candidate_token_hit_rate}
              hitTokens={result.candidate_hit_tokens}
              totalTokens={result.total_tokens}
              accent="candidate"
              delayMs={70}
            />
          </div>

          <div className="grid gap-3.5 lg:grid-cols-2">
            <div
              className="panel rise p-5"
              style={{ animationDelay: "100ms" }}
            >
              <h2 className="mb-4 text-[13px] font-semibold text-[var(--fg)]">
                Cumulative lift curve
              </h2>
              {sweepBars.length === 0 ? (
                <p className="text-[13px] text-[var(--fg-subtle)]">
                  No pin candidates improved hit rate under current tier budgets.
                </p>
              ) : (
                <div className="space-y-3.5">
                  {sweepBars.map((bar, index) => (
                    <div key={index}>
                      <div className="mb-1.5 flex justify-between text-[11px]">
                        <span className="truncate pr-2 text-[var(--fg-muted)]">
                          {bar.label}
                        </span>
                        <span className="shrink-0 font-mono text-[#86efac]">
                          +{(bar.delta * 100).toFixed(2)}%
                        </span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                        <div
                          className="h-full rounded-full bg-[var(--accent)] transition-all duration-500"
                          style={{ width: `${bar.rate * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div
              className="panel rise p-5"
              style={{ animationDelay: "140ms" }}
            >
              <h2 className="mb-4 text-[13px] font-semibold text-[var(--fg)]">
                Simulation metadata
              </h2>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-3.5 text-[12px]">
                <MetaItem label="Traffic source" value={result.traffic_source} />
                <MetaItem
                  label="Requests replayed"
                  value={result.total_requests}
                />
                <MetaItem
                  label="Baseline evictions"
                  value={result.baseline_eviction_count}
                />
                <MetaItem
                  label="With pins evictions"
                  value={result.candidate_eviction_count}
                />
                <MetaItem
                  label="Pins applied (sim)"
                  value={result.applied_pin_count}
                />
                <MetaItem label="Mode" value={connectivity?.mode ?? "—"} />
              </dl>
            </div>
          </div>

          <section>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-[17px] font-semibold tracking-tight text-[var(--fg)]">
                Recommended pins
              </h2>
              <Badge variant="muted">
                {result.recommendations.length} suggestion
                {result.recommendations.length === 1 ? "" : "s"}
              </Badge>
            </div>

            {result.recommendations.length === 0 ? (
              <div className="panel px-6 py-10 text-center text-[13px] text-[var(--fg-subtle)]">
                Register more prompts or increase tier pressure (lower capacity)
                to surface pin opportunities.
              </div>
            ) : (
              <div className="space-y-3">
                {result.recommendations.map((item, index) => (
                  <RecommendationRow
                    key={`${item.prompt_id}-${item.location}`}
                    item={item}
                    index={index}
                    tenantId={tenantId}
                    onPinned={() => void runAnalysis()}
                  />
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function ControlField({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="space-y-1.5">
      <span className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-[var(--fg-subtle)]">
        {icon}
        {label}
      </span>
      {children}
    </label>
  );
}

function MetaItem({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div>
      <dt className="text-[var(--fg-subtle)]">{label}</dt>
      <dd className="mt-0.5 font-mono text-[var(--fg)]">{value}</dd>
    </div>
  );
}
