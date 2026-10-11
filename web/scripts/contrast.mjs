#!/usr/bin/env node
// WCAG contrast check for the design tokens in src/index.css (PLAN.md §14.6, §14.10).
// Text tokens must reach 4.5:1 and icon/status marks 3:1 against the page and card backgrounds, in both themes.
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const css = readFileSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src/index.css"), "utf8");

function block(selector) {
  const m = css.match(new RegExp(`${selector.replace(".", "\\.")}\\s*\\{([^}]*)\\}`));
  const vars = {};
  for (const [, k, v] of (m?.[1] ?? "").matchAll(/--([a-z0-9-]+):\s*(#[0-9a-f]{6})/gi)) vars[k] = v.toLowerCase();
  return vars;
}
const lum = (hex) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
};
const ratio = (a, b) => { const [l1, l2] = [lum(a), lum(b)].sort((x, y) => y - x); return (l1 + 0.05) / (l2 + 0.05); };

const TEXT = ["foreground", "muted-foreground", "primary", "paid", "review", "held", "ai"];
// `border` is a decorative rule, not a component boundary, so it is reported but not gated.
const MARKS = ["primary", "paid", "review", "held", "ai"];
let failures = 0;
for (const theme of [":root", ".dark"]) {
  const t = block(theme);
  console.log(`\n${theme === ":root" ? "light" : "dark"} theme`);
  for (const bg of ["background", "card"]) {
    for (const name of TEXT) {
      const r = ratio(t[name], t[bg]);
      const ok = r >= 4.5;
      if (!ok) failures += 1;
      console.log(`  ${ok ? "ok  " : "FAIL"} text  ${name.padEnd(17)} on ${bg.padEnd(10)} ${r.toFixed(2)}:1`);
    }
    for (const name of MARKS) {
      const r = ratio(t[name], t[bg]);
      const ok = r >= 3;
      if (!ok) failures += 1;
      console.log(`  ${ok ? "ok  " : "FAIL"} mark  ${name.padEnd(17)} on ${bg.padEnd(10)} ${r.toFixed(2)}:1`);
    }
  }
  // status text on its own soft background (chips)
  for (const s of ["paid", "review", "held", "ai"]) {
    const r = ratio(t[s], t[`${s}-soft`]);
    const ok = r >= 4.5;
    if (!ok) failures += 1;
    console.log(`  ${ok ? "ok  " : "FAIL"} chip  ${s.padEnd(17)} on ${(s + "-soft").padEnd(10)} ${r.toFixed(2)}:1`);
  }
  // labels on filled status (stamp variant B, bar segments) use the page background color, not white
  for (const s of ["paid", "review", "held", "primary"]) {
    const r = ratio(t.background, t[s]);
    const ok = r >= 4.5;
    if (!ok) failures += 1;
    console.log(`  ${ok ? "ok  " : "FAIL"} label background on ${s.padEnd(10)}      ${r.toFixed(2)}:1`);
  }
  console.log(`  info  rule  border on background ${ratio(t.border, t.background).toFixed(2)}:1 (decorative)`);
}
console.log(failures ? `\n${failures} failure(s)` : "\nall pass");
process.exit(failures ? 1 : 0);
