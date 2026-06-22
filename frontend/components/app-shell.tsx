"use client";

import { PinAnalysisPanel } from "@/components/pin-analysis-panel";
import { PromptRegistryDemo } from "@/components/prompt-registry";
import { SkillsPanel } from "@/components/skills-panel";
import { getOpenWebUiUrl } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ArrowUpRight, Layers, LineChart, Sparkles } from "lucide-react";
import { useState } from "react";

type AppTab = "registry" | "analysis" | "skills";

const TABS: {
  id: AppTab;
  label: string;
  title: string;
  blurb: string;
  icon: typeof Layers;
}[] = [
  {
    id: "registry",
    label: "Registry",
    title: "KV Chunk Residency",
    blurb:
      "Decoded KV chunks across GPU, CPU, and external storage. Drag between CPU and disk to move, double-click to pin, drop on the evict zone to remove.",
    icon: Layers,
  },
  {
    id: "analysis",
    label: "Pin Analysis",
    title: "Pin Extrapolation",
    blurb:
      "Replay catalog traffic against tiered LRU caches to estimate how pinning prompts to CPU or disk shifts the token hit rate.",
    icon: LineChart,
  },
  {
    id: "skills",
    label: "Skills",
    title: "Agent Skills",
    blurb:
      "Browse skills.sh, stage SKILL.md into LMCache KV, and pin hot skills for cache hits. Uninstall evicts the staged chunks.",
    icon: Sparkles,
  },
];

export function AppShell() {
  const [tab, setTab] = useState<AppTab>("registry");
  const active = TABS.find((t) => t.id === tab)!;
  const openWebUiUrl = getOpenWebUiUrl();

  return (
    <div className="flex min-h-screen flex-col">
      <header className="rise">
        {/* Brand row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--accent)] shadow-[0_0_10px_var(--accent)]" />
            <span className="font-mono text-[11px] uppercase tracking-[0.28em] text-[var(--fg-muted)]">
              LMCache
            </span>
            <span className="text-[var(--fg-subtle)]">/</span>
            <span className="font-mono text-[11px] uppercase tracking-[0.28em] text-[var(--fg-subtle)]">
              Prompt Registry
            </span>
          </div>

          <a
            href={openWebUiUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="group inline-flex items-center gap-1.5 text-[12px] text-[var(--fg-muted)] transition-colors hover:text-[var(--fg)]"
          >
            Open WebUI
            <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
          </a>
        </div>

        {/* Title + description */}
        <div className="mt-7 max-w-2xl">
          <h1 className="text-[28px] font-semibold leading-tight tracking-tight text-[var(--fg)] sm:text-[32px]">
            {active.title}
          </h1>
          <p className="mt-2.5 text-[13.5px] leading-relaxed text-[var(--fg-muted)]">
            {active.blurb}
          </p>
        </div>

        {/* Tabs */}
        <nav
          className="mt-7 flex items-center gap-7 border-b border-[var(--line)]"
          aria-label="Main navigation"
        >
          {TABS.map(({ id, label, icon: Icon }) => {
            const isActive = tab === id;
            return (
              <button
                key={id}
                type="button"
                onClick={() => setTab(id)}
                className={cn(
                  "group relative -mb-px flex items-center gap-2 border-b-2 pb-3 pt-1 text-[13px] font-medium transition-colors",
                  isActive
                    ? "border-[var(--accent)] text-[var(--fg)]"
                    : "border-transparent text-[var(--fg-subtle)] hover:text-[var(--fg-muted)]",
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            );
          })}
        </nav>
      </header>

      <div className="flex-1 pt-7">
        {tab === "registry" ? (
          <PromptRegistryDemo />
        ) : tab === "analysis" ? (
          <PinAnalysisPanel />
        ) : (
          <SkillsPanel />
        )}
      </div>
    </div>
  );
}
