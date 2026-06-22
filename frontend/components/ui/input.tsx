import { cn } from "@/lib/utils";
import { type InputHTMLAttributes, forwardRef } from "react";

export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "h-9 w-full rounded-lg border border-[var(--line-strong)] bg-black/30 px-3 text-[13px] text-[var(--fg)] transition-colors placeholder:text-[var(--fg-subtle)] focus:border-[var(--accent-line)] focus:outline-none",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";
