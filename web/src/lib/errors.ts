// User-facing errors after an action (PLAN.md §14.6: say what happened, then what to do next).
// `http()` in lib/api.ts throws Error("<status>: <detail>"); anything else is a network failure.

export interface UserError { title: string; description: string }

export function describeError(e: unknown): UserError {
  const msg = e instanceof Error ? e.message : String(e);
  const m = /^(\d{3}): ?(.*)$/s.exec(msg);
  const status = m ? Number(m[1]) : null;
  const detail = m?.[2]?.trim() ?? "";
  if (status === 409) {
    return { title: "That action isn't available for this invoice any more.",
             description: "The case was updated; check the current status and try again." };
  }
  if (status === 404) {
    return { title: "That invoice no longer exists.",
             description: "It was probably cleared by a demo reset. Pick another case." };
  }
  if (status === 400 || status === 422) {
    return { title: "The request was refused.", description: detail || "Check the input and try again." };
  }
  return { title: "Couldn't reach the server.", description: "Check the connection; the dashboard keeps retrying." };
}
