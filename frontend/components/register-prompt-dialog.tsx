"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { registerPrompt } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Loader2, Plus, X } from "lucide-react";
import { useState } from "react";

interface RegisterPromptDialogProps {
  tenantId: string;
  defaultModel: string;
  onRegistered: () => void;
}

export function RegisterPromptDialog({
  tenantId,
  defaultModel,
  onRegistered,
}: RegisterPromptDialogProps) {
  const [open, setOpen] = useState(false);
  const [model, setModel] = useState(defaultModel);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await registerPrompt({
        model,
        prompt,
        tokenizer_id: model,
        tenant_id: tenantId,
        labels: { source: "demo-ui" },
      });
      setPrompt("");
      setOpen(false);
      onRegistered();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Button onClick={() => setOpen(true)} className="gap-2">
        <Plus className="h-4 w-4" />
        Register Prompt
      </Button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />
          <form
            onSubmit={handleSubmit}
            className={cn(
              "glass relative z-10 w-full max-w-lg rounded-2xl p-6",
              "fade-up shadow-[0_0_60px_rgba(59,130,246,0.15)]",
            )}
          >
            <div className="mb-5 flex items-center justify-between">
              <h3 className="font-[family-name:var(--font-syne)] text-lg font-semibold text-white glow-text">
                Register Prompt
              </h3>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-lg p-1 text-slate-400 hover:bg-white/5 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs text-slate-400">
                  Model / Tokenizer
                </label>
                <Input
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="meta-llama/Llama-3.1-8B-Instruct"
                  required
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs text-slate-400">
                  Prompt text
                </label>
                <Textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Enter prompt to tokenize and catalog…"
                  rows={5}
                  required
                />
              </div>
              {error && (
                <p className="rounded-lg border border-red-500/30 bg-red-950/30 px-3 py-2 text-xs text-red-300">
                  {error}
                </p>
              )}
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={loading}>
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  "Register"
                )}
              </Button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
