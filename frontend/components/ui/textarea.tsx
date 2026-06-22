import { cn } from "@/lib/utils";
import { type TextareaHTMLAttributes, forwardRef } from "react";

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "w-full resize-none rounded-lg border border-[var(--line-strong)] bg-black/30 px-3 py-2.5 text-[13px] leading-relaxed text-[var(--fg)] transition-colors placeholder:text-[var(--fg-subtle)] focus:border-[var(--accent-line)] focus:outline-none",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";
