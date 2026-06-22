"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  fetchConnectivity,
  fetchInstalledSkills,
  installSkill,
  listSkills,
  searchSkills,
  uninstallSkill,
} from "@/lib/api";
import type { InstalledSkill, SkillSummary } from "@/lib/types";
import { cn, formatInstalls } from "@/lib/utils";
import {
  Download,
  Loader2,
  Pin,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

const STARTUP_SKILLS: SkillSummary[] = [
  {
    id: "vercel-labs/skills/find-skills",
    slug: "find-skills",
    name: "find-skills",
    source: "vercel-labs/skills",
    installs: 2_100_000,
    url: "https://skills.sh/vercel-labs/skills/find-skills",
  },
  {
    id: "anthropics/skills/frontend-design",
    slug: "frontend-design",
    name: "frontend-design",
    source: "anthropics/skills",
    installs: 577_500,
    url: "https://skills.sh/anthropics/skills/frontend-design",
  },
  {
    id: "vercel-labs/agent-skills/vercel-react-best-practices",
    slug: "vercel-react-best-practices",
    name: "vercel-react-best-practices",
    source: "vercel-labs/agent-skills",
    installs: 495_000,
    url: "https://skills.sh/vercel-labs/agent-skills/vercel-react-best-practices",
  },
  {
    id: "vercel-labs/agent-browser/agent-browser",
    slug: "agent-browser",
    name: "agent-browser",
    source: "vercel-labs/agent-browser",
    installs: 473_700,
    url: "https://skills.sh/vercel-labs/agent-browser/agent-browser",
  },
  {
    id: "microsoft/azure-skills/microsoft-foundry",
    slug: "microsoft-foundry",
    name: "microsoft-foundry",
    source: "microsoft/azure-skills",
    installs: 408_900,
    url: "https://skills.sh/microsoft/azure-skills/microsoft-foundry",
  },
  {
    id: "vercel-labs/agent-skills/web-design-guidelines",
    slug: "web-design-guidelines",
    name: "web-design-guidelines",
    source: "vercel-labs/agent-skills",
    installs: 408_800,
    url: "https://skills.sh/vercel-labs/agent-skills/web-design-guidelines",
  },
  {
    id: "microsoft/azure-skills/azure-ai",
    slug: "azure-ai",
    name: "azure-ai",
    source: "microsoft/azure-skills",
    installs: 406_400,
    url: "https://skills.sh/microsoft/azure-skills/azure-ai",
  },
  {
    id: "remotion-dev/skills/remotion-best-practices",
    slug: "remotion-best-practices",
    name: "remotion-best-practices",
    source: "remotion-dev/skills",
    installs: 385_600,
    url: "https://skills.sh/remotion-dev/skills/remotion-best-practices",
  },
  {
    id: "mattpcock/skills/grill-me",
    slug: "grill-me",
    name: "grill-me",
    source: "mattpcock/skills",
    installs: 369_700,
    url: "https://skills.sh/mattpcock/skills/grill-me",
  },
  {
    id: "mattpcock/skills/improve-codebase-architecture",
    slug: "improve-codebase-architecture",
    name: "improve-codebase-architecture",
    source: "mattpcock/skills",
    installs: 303_900,
    url: "https://skills.sh/mattpcock/skills/improve-codebase-architecture",
  },
  {
    id: "mattpcock/skills/tdd",
    slug: "tdd",
    name: "tdd",
    source: "mattpcock/skills",
    installs: 286_700,
    url: "https://skills.sh/mattpcock/skills/tdd",
  },
  {
    id: "anthropics/skills/skill-creator",
    slug: "skill-creator",
    name: "skill-creator",
    source: "anthropics/skills",
    installs: 282_100,
    url: "https://skills.sh/anthropics/skills/skill-creator",
  },
  {
    id: "juliusbrussee/caveman/caveman",
    slug: "caveman",
    name: "caveman",
    source: "juliusbrussee/caveman",
    installs: 274_500,
    url: "https://skills.sh/juliusbrussee/caveman/caveman",
  },
  {
    id: "microsoft/azure-skills/azure-hosted-copilot-sdk",
    slug: "azure-hosted-copilot-sdk",
    name: "azure-hosted-copilot-sdk",
    source: "microsoft/azure-skills",
    installs: 377_900,
    url: "https://skills.sh/microsoft/azure-skills/azure-hosted-copilot-sdk",
  },
  {
    id: "mattpcock/skills/grill-with-docs",
    slug: "grill-with-docs",
    name: "grill-with-docs",
    source: "mattpcock/skills",
    installs: 301_100,
    url: "https://skills.sh/mattpcock/skills/grill-with-docs",
  },
];

function activityWidth(installs: number, maxInstalls: number): number {
  if (maxInstalls <= 0) return 8;
  return Math.max(8, Math.round((installs / maxInstalls) * 100));
}

function SkillRow({
  skill,
  rank,
  maxInstalls,
  installed,
  busy,
  onInstall,
}: {
  skill: SkillSummary;
  rank: number;
  maxInstalls: number;
  installed: boolean;
  busy: boolean;
  onInstall: (skillId: string) => void;
}) {
  const width = activityWidth(skill.installs, maxInstalls);

  return (
    <div className="group grid grid-cols-[2rem_1fr_7rem_5.5rem_6.5rem] items-center gap-3 border-b border-[var(--line)] px-4 py-3 transition-colors last:border-b-0 hover:bg-white/[0.02]">
      <span className="font-mono text-[12px] tabular-nums text-[var(--fg-subtle)]">
        {String(rank).padStart(2, "0")}
      </span>

      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[13px] font-medium text-[var(--fg)]">
            {skill.name}
          </span>
          {installed && <Badge variant="cpu">Installed</Badge>}
        </div>
        <p className="truncate font-mono text-[11px] text-[var(--fg-subtle)]">
          {skill.source}
        </p>
      </div>

      <div className="hidden h-1 overflow-hidden rounded-full bg-white/[0.06] sm:block">
        <div
          className="h-full rounded-full bg-[var(--fg-subtle)] transition-all group-hover:bg-[var(--accent)]"
          style={{ width: `${width}%` }}
        />
      </div>

      <span className="text-right font-mono text-[12px] tabular-nums text-[var(--fg-muted)]">
        {formatInstalls(skill.installs)}
      </span>

      <Button
        variant={installed ? "ghost" : "default"}
        disabled={installed || busy}
        onClick={() => onInstall(skill.id)}
        className="h-8 justify-center px-3"
      >
        {busy ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Download className="h-3.5 w-3.5" />
        )}
        {installed ? "Pinned" : "Install"}
      </Button>
    </div>
  );
}

function InstalledRow({
  skill,
  busy,
  onUninstall,
}: {
  skill: InstalledSkill;
  busy: boolean;
  onUninstall: (skillId: string) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 py-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <Pin className="h-3.5 w-3.5 shrink-0 text-[var(--accent-bright)]" />
          <span className="text-[13px] font-medium text-[var(--fg)]">
            {skill.name}
          </span>
          <Badge variant={skill.pinned ? "cpu" : "muted"}>
            {skill.pinned ? "Pinned · CPU" : "Staged"}
          </Badge>
        </div>
        <p className="mt-0.5 truncate font-mono text-[11px] text-[var(--fg-subtle)]">
          {skill.source}
        </p>
      </div>
      <Button
        variant="ghost"
        disabled={busy}
        onClick={() => onUninstall(skill.skill_id)}
        className="h-8 shrink-0 px-3 text-red-300/90 hover:bg-red-500/10 hover:text-red-200"
      >
        {busy ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Trash2 className="h-3.5 w-3.5" />
        )}
        Uninstall
      </Button>
    </div>
  );
}

export function SkillsPanel() {
  const [query, setQuery] = useState("");
  const [browseSkills, setBrowseSkills] = useState<SkillSummary[]>(STARTUP_SKILLS);
  const [installed, setInstalled] = useState<InstalledSkill[]>([]);
  const [tenantId, setTenantId] = useState("demo-tenant");
  const [skillsEnabled, setSkillsEnabled] = useState(true);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [actionSkillId, setActionSkillId] = useState<string | null>(null);

  const installedIds = useMemo(
    () => new Set(installed.map((skill) => skill.skill_id)),
    [installed],
  );

  const maxInstalls = useMemo(
    () => Math.max(...browseSkills.map((skill) => skill.installs), 1),
    [browseSkills],
  );

  const loadInstalled = useCallback(async (tenant: string) => {
    const skills = await fetchInstalledSkills(tenant);
    setInstalled(skills);
  }, []);

  const loadBrowse = useCallback(async (searchQuery: string) => {
    if (searchQuery.trim().length >= 2) {
      setSearching(true);
      try {
        const results = await searchSkills(searchQuery.trim(), 30);
        setBrowseSkills(results);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Search failed");
      } finally {
        setSearching(false);
      }
      return;
    }

    try {
      const results = await listSkills("all-time", 15);
      if (results.length > 0) {
        setBrowseSkills(results);
      } else {
        setBrowseSkills(STARTUP_SKILLS);
      }
    } catch {
      setBrowseSkills(STARTUP_SKILLS);
    }
  }, []);

  const bootstrap = useCallback(async () => {
    const conn = await fetchConnectivity();
    setTenantId(conn.demo_tenant_id);
    setSkillsEnabled(conn.skills_enabled ?? false);
    await Promise.all([
      loadInstalled(conn.demo_tenant_id),
      loadBrowse(""),
    ]);
  }, [loadBrowse, loadInstalled]);

  useEffect(() => {
    bootstrap()
      .catch((err) =>
        toast.error(err instanceof Error ? err.message : "Failed to load skills"),
      )
      .finally(() => setLoading(false));
  }, [bootstrap]);

  useEffect(() => {
    if (loading) return;
    const handle = window.setTimeout(() => {
      loadBrowse(query).catch((err) =>
        toast.error(err instanceof Error ? err.message : "Search failed"),
      );
    }, 300);
    return () => window.clearTimeout(handle);
  }, [query, loading, loadBrowse]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await Promise.all([loadInstalled(tenantId), loadBrowse(query)]);
      toast.success("Skills refreshed");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  }, [loadBrowse, loadInstalled, query, tenantId]);

  const handleInstall = useCallback(
    async (skillId: string) => {
      setActionSkillId(skillId);
      try {
        const result = await installSkill(skillId, tenantId);
        await loadInstalled(tenantId);
        if (result.pinned) {
          toast.success("Skill staged and pinned to CPU KV");
        } else {
          toast.warning(
            result.warning ||
              "Skill staged in catalog, but pin is unavailable on the remote KV service.",
          );
        }
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Install failed");
      } finally {
        setActionSkillId(null);
      }
    },
    [loadInstalled, tenantId],
  );

  const handleUninstall = useCallback(
    async (skillId: string) => {
      setActionSkillId(skillId);
      try {
        await uninstallSkill(skillId, tenantId);
        await loadInstalled(tenantId);
        toast.success("Skill evicted from cache");
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Uninstall failed");
      } finally {
        setActionSkillId(null);
      }
    },
    [loadInstalled, tenantId],
  );

  if (loading) {
    return (
      <div className="panel rise flex min-h-[320px] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--accent)]" />
      </div>
    );
  }

  if (!skillsEnabled) {
    return (
      <div className="panel rise p-8 text-center">
        <Sparkles className="mx-auto mb-3 h-7 w-7 text-[var(--fg-subtle)]" />
        <p className="text-[16px] font-semibold text-[var(--fg)]">
          Skills catalog unavailable
        </p>
        <p className="mt-2 text-[13px] text-[var(--fg-muted)]">
          Set VERCEL_TOKEN, VERCEL_ORG_ID, VERCEL_PROJECT_ID and start the
          skills-proxy service.
        </p>
      </div>
    );
  }

  const browseTitle =
    query.trim().length >= 2
      ? `Results for “${query.trim()}”`
      : "Top skills in the skills-verse";

  return (
    <div className="rise space-y-4">
      <div className="panel flex flex-col gap-3 p-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-subtle)]" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search skills.sh — react, fastapi, frontend-design…"
            className="h-10 pl-9"
          />
        </div>
        <Button
          variant="ghost"
          onClick={refresh}
          disabled={refreshing || searching}
          className="self-end sm:self-auto"
        >
          <RefreshCw
            className={cn("h-4 w-4", (refreshing || searching) && "animate-spin")}
          />
          Refresh
        </Button>
      </div>

      <section className="panel p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-[var(--fg-subtle)]">
              Installed
            </p>
            <h2 className="text-[15px] font-semibold text-[var(--fg)]">
              Pinned in LMCache KV
            </h2>
          </div>
          <Badge variant="default">{installed.length}</Badge>
        </div>

        {installed.length === 0 ? (
          <p className="rounded-xl border border-dashed border-[var(--line)] px-4 py-8 text-center text-[13px] text-[var(--fg-subtle)]">
            No skills installed yet. Pick one from the catalog below and hit
            Install to stage SKILL.md into CPU cache.
          </p>
        ) : (
          <div className="space-y-2">
            {installed.map((skill) => (
              <InstalledRow
                key={skill.skill_id}
                skill={skill}
                busy={actionSkillId === skill.skill_id}
                onUninstall={handleUninstall}
              />
            ))}
          </div>
        )}
      </section>

      <section className="panel overflow-hidden">
        <div className="border-b border-[var(--line)] px-4 py-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-[var(--fg-subtle)]">
                Browse
              </p>
              <h2 className="text-[15px] font-semibold text-[var(--fg)]">
                {browseTitle}
              </h2>
            </div>
            {searching && (
              <Loader2 className="h-4 w-4 animate-spin text-[var(--fg-muted)]" />
            )}
          </div>
        </div>

        <div className="hidden grid-cols-[2rem_1fr_7rem_5.5rem_6.5rem] gap-3 border-b border-[var(--line)] px-4 py-2.5 text-[10px] font-medium uppercase tracking-[0.14em] text-[var(--fg-subtle)] sm:grid">
          <span>#</span>
          <span>Skill</span>
          <span>Activity</span>
          <span className="text-right">Installs</span>
          <span />
        </div>

        <div>
          {browseSkills.map((skill, index) => (
            <SkillRow
              key={skill.id}
              skill={skill}
              rank={index + 1}
              maxInstalls={maxInstalls}
              installed={installedIds.has(skill.id)}
              busy={actionSkillId === skill.id}
              onInstall={handleInstall}
            />
          ))}
        </div>
      </section>
    </div>
  );
}