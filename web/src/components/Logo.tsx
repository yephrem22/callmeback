// Call Me Back logo, option B ("callmeback" in Sora 600): adapted from the team's logo pack for
// Vite. Sora is bundled through Fontsource in main.tsx (no CDN at runtime, PLAN.md §14.5).
// Phone glyph adapted from Lucide (ISC license).

const PHONE =
  "M13.832 16.568a1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 6.392 6.384";

/** Icon only: indigo tile, phone, green "verified" check. */
export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 34 34" aria-hidden="true" className="shrink-0">
      <rect x="0" y="2" width="32" height="32" rx="8" fill="#6366f1" />
      <g transform="translate(7 9) scale(0.75)">
        <path d={PHONE} fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      </g>
      {/* the ring uses the page background, so the badge looks cut out in light and dark */}
      <circle cx="27" cy="7" r="6.5" fill="#22c55e" stroke="var(--background)" strokeWidth="2.5" />
      <path d="M24.2 7.1l1.9 1.9 3.6-3.7" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Full logo: the mark plus the lowercase wordmark, with "back" in indigo. */
export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <LogoMark />
      <span aria-hidden="true" className="text-[21px] font-semibold leading-none tracking-[-0.035em] text-foreground"
            style={{ fontFamily: "'Sora', var(--font-sans, sans-serif)" }}>
        callme<span className="text-indigo-500 dark:text-indigo-400">back</span>
      </span>
      <span className="sr-only">Call Me Back</span>
    </span>
  );
}
