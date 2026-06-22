import { cn } from "@/lib/utils";

interface BadgeProps {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "gpu" | "cpu" | "disk" | "pinned" | "muted";
}

const variantStyles = {
  default: "bg-blue-500/15 text-blue-300 border-blue-500/25",
  gpu: "bg-amber-500/15 text-amber-300 border-amber-500/25",
  cpu: "bg-cyan-500/15 text-cyan-300 border-cyan-500/25",
  disk: "bg-indigo-500/15 text-indigo-300 border-indigo-500/25",
  pinned: "bg-emerald-500/15 text-emerald-300 border-emerald-500/25",
  muted: "bg-slate-500/10 text-slate-400 border-slate-500/20",
};

export function Badge({
  children,
  className,
  variant = "default",
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
        variantStyles[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
