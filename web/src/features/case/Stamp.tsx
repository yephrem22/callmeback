// Candidate 12: the decision stamp (PLAN.md §14.6). The one bold element on the page.
import { CheckCircle2, Hourglass, OctagonX, PhoneCall } from "lucide-react";

import { STAMP_TONE, type StampKind } from "@/lib/decide";
import { cn } from "@/lib/utils";

const ICON = { PAID: CheckCircle2, HELD: OctagonX, REVIEW: Hourglass, CALLING: PhoneCall } as const;

const TONE = {
  paid: { outline: "border-paid text-paid", filled: "bg-paid text-background border-paid" },
  held: { outline: "border-held text-held", filled: "bg-held text-background border-held" },
  review: { outline: "border-review text-review", filled: "bg-review text-background border-review" },
} as const;

export function Stamp({ kind, variant = "outline", size = "lg", animate = true, className }: {
  kind: StampKind; variant?: "outline" | "filled"; size?: "sm" | "lg"; animate?: boolean; className?: string;
}) {
  const Icon = ICON[kind];
  const tone = TONE[STAMP_TONE[kind]][variant];
  const live = kind === "CALLING";
  return (
    <span
      role="img"
      aria-label={`Decision: ${kind.toLowerCase()}`}
      className={cn(
        "inline-flex select-none items-center gap-2 rounded-md border-[3px] font-semibold uppercase tracking-[0.18em] -rotate-6",
        size === "lg" ? "px-4 py-1.5 text-[28px] leading-none" : "px-2 py-0.5 text-sm",
        tone, animate && "stamp-in", className,
      )}
      style={{ transform: "rotate(-6deg)" }}
    >
      <Icon className={cn(size === "lg" ? "size-7" : "size-4", live && "animate-pulse")} strokeWidth={2.5} aria-hidden />
      {kind}
    </span>
  );
}
