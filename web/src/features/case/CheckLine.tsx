// The bottom line of a check: transit symbol, routing, transit symbol, account. Plex Mono, digits people compare.
import { cn } from "@/lib/utils";

/** Bank transit symbol ⑆ drawn inline so it never depends on font support (PLAN.md §14.6). */
export function Transit({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 10 14" className={cn("inline-block h-[1em] w-[0.7em] align-[-0.1em]", className)} aria-hidden>
      <rect x="1" y="2" width="2.2" height="10" fill="currentColor" />
      <rect x="4.5" y="2" width="1.3" height="10" fill="currentColor" />
      <rect x="7" y="2" width="2.2" height="3.5" fill="currentColor" />
      <rect x="7" y="8.5" width="2.2" height="3.5" fill="currentColor" />
    </svg>
  );
}

export function CheckLine({ routing, account, changedRouting = false, changedAccount = false, size = "md", className }: {
  routing: string | null; account: string | null; changedRouting?: boolean; changedAccount?: boolean; size?: "md" | "lg"; className?: string;
}) {
  const hot = "rounded-sm bg-held-soft px-1 text-held";
  return (
    <span className={cn("mono inline-flex items-center gap-1 whitespace-nowrap", size === "lg" ? "text-[22px]" : "text-base", className)}>
      <Transit /> <span className={cn(changedRouting && hot)}>{routing ?? "—"}</span> <Transit />
      <span className={cn("ml-2", changedAccount && hot)}>{account ?? "—"}</span>
    </span>
  );
}
