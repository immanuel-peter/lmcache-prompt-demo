import { cn } from "@/lib/utils";

interface BadgeProps {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "gpu" | "cpu" | "disk" | "pinned" | "muted";
}

const variantStyles = {
  default: "text-[var(--accent-bright)] border-[var(--accent-line)]",
  gpu: "text-[#e0b878] border-[#d99a3a]/30",
  cpu: "text-[#8fb6f9] border-[#4f8ff7]/30",
  disk: "text-[#b0b3f7] border-[#8b8ff5]/30",
  pinned: "text-[#86efac] border-[#4ade80]/30",
  muted: "text-[var(--fg-subtle)] border-[var(--line)]",
};

export function Badge({
  children,
  className,
  variant = "default",
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium tracking-wide",
        variantStyles[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
