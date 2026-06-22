import { cn } from "@/lib/utils";
import { type ButtonHTMLAttributes, forwardRef } from "react";

type ButtonVariant = "default" | "ghost" | "outline" | "destructive";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

const variants: Record<ButtonVariant, string> = {
  default:
    "bg-[var(--accent)] text-[#06080c] font-semibold hover:bg-[var(--accent-bright)]",
  ghost:
    "text-[var(--fg-muted)] hover:text-[var(--fg)] hover:bg-white/[0.04]",
  outline:
    "border border-[var(--line-strong)] text-[var(--fg)] hover:border-[var(--accent-line)] hover:text-[var(--accent-bright)]",
  destructive:
    "border border-red-500/25 text-red-300/90 hover:bg-red-500/10 hover:text-red-200",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex h-9 items-center justify-center gap-2 rounded-lg px-3.5 text-[13px] font-medium transition-colors disabled:pointer-events-none disabled:opacity-40",
        variants[variant],
        className,
      )}
      {...props}
    />
  ),
);
Button.displayName = "Button";
