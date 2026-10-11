// Display helpers: integer cents in, formatted strings out; UTC in, America/Chicago out (PLAN.md §6).

const CHICAGO = "America/Chicago";

export function formatCents(cents: number | null | undefined, opts: { compact?: boolean } = {}): string {
  if (cents == null) return "—";
  const dollars = cents / 100;
  if (opts.compact && Math.abs(dollars) >= 1000) {
    return `$${(dollars / 1000).toLocaleString("en-US", { maximumFractionDigits: dollars >= 100000 ? 0 : 1 })}k`;
  }
  return `$${dollars.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatChicago(iso: string | null | undefined, style: "time" | "datetime" | "date" | "weekday-time" = "time"): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const f: Intl.DateTimeFormatOptions =
    style === "time" ? { hour: "numeric", minute: "2-digit" } :          // 12-hour, like the ledger (spec 007 R9)
    style === "date" ? { month: "short", day: "numeric" } :
    style === "weekday-time" ? { weekday: "short", hour: "numeric", minute: "2-digit" } :
    { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" };
  return new Intl.DateTimeFormat("en-US", { timeZone: CHICAGO, ...f }).format(d);
}

export function formatDateLong(isoDate: string | null | undefined): string {
  if (!isoDate) return "—";
  const [y, m, d] = isoDate.split("-").map(Number);
  if (!y || !m || !d) return isoDate;
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(new Date(Date.UTC(y, m - 1, d, 12)));
}

export function relativeAge(iso: string, now = Date.now()): string {
  const ms = now - new Date(iso).getTime();
  if (!Number.isFinite(ms) || ms < 0) return "just now";
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function titleCase(s: string): string {
  return s.toLowerCase().replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export function ratioText(r: number | null | undefined): string | null {
  if (r == null) return null;
  return `${r.toFixed(1)}×`;
}

/** Split a check line into its parts for rendering: routing (9 digits) and masked account. */
export function checkLine(routing: string | null | undefined, accountMasked: string | null | undefined) {
  return { routing: routing ?? "—", account: accountMasked ?? "—" };
}
