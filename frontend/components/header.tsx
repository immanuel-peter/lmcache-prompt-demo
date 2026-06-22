"use client";

import { RegisterPromptDialog } from "@/components/register-prompt-dialog";
import { Button } from "@/components/ui/button";
import { getOpenWebUiUrl } from "@/lib/api";
import { ExternalLink, RefreshCw } from "lucide-react";

interface HeaderProps {
  tenantId: string;
  defaultModel: string;
  onRefresh: () => void;
  onRegistered: () => void;
  refreshing: boolean;
}

export function Header({
  tenantId,
  defaultModel,
  onRefresh,
  onRegistered,
  refreshing,
}: HeaderProps) {
  const openWebUiUrl = getOpenWebUiUrl();

  return (
    <header className="fade-up mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-400/70">
          LMCache · Prompt Registry
        </p>
        <h1 className="font-[family-name:var(--font-syne)] text-3xl font-bold tracking-tight text-white glow-text sm:text-4xl">
          KV Chunk Residency
        </h1>
        <p className="mt-2 max-w-xl text-sm text-slate-400">
          Inspect decoded chunks across GPU, CPU, and external storage. Drag
          between CPU and disk to move · double-click to pin · drop on evict
          zone to remove.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          onClick={onRefresh}
          disabled={refreshing}
          className="gap-2"
        >
          <RefreshCw
            className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
          />
          Refresh
        </Button>
        <RegisterPromptDialog
          tenantId={tenantId}
          defaultModel={defaultModel}
          onRegistered={onRegistered}
        />
        <a href={openWebUiUrl} target="_blank" rel="noopener noreferrer">
          <Button variant="ghost" className="gap-2">
            <ExternalLink className="h-4 w-4" />
            Open WebUI
          </Button>
        </a>
      </div>
    </header>
  );
}
