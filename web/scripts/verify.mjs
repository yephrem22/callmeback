// Behaviour checks (spec 004 phase 4): run against `npm run dev`. node scripts/verify.mjs [base]
// Covers: theme default + persistence + ?theme override, keyboard j/k/Enter, reduced motion.
import { chromium } from "@playwright/test";
const base = process.argv[2] ?? "http://localhost:5173";
const browser = await chromium.launch();
const results = [];
const check = (name, ok, extra = "") => { results.push([ok, name, extra]); };

// 1. Theme: first visit is light; choosing dark persists across reload; ?theme= overrides without persisting.
{
  const ctx = await browser.newContext({ viewport: { width: 1024, height: 576 }, colorScheme: "dark" });
  const page = await ctx.newPage();
  await page.goto(`${base}/?scenario=none`, { waitUntil: "networkidle" });
  check("first visit uses light even when the OS prefers dark", !(await page.evaluate(() => document.documentElement.classList.contains("dark"))));
  await page.evaluate(() => localStorage.setItem("cmb-theme", "dark"));
  await page.reload({ waitUntil: "networkidle" });
  check("stored dark theme survives reload", await page.evaluate(() => document.documentElement.classList.contains("dark")));
  await page.goto(`${base}/?scenario=none&theme=light`, { waitUntil: "networkidle" });
  check("?theme=light overrides the stored choice", !(await page.evaluate(() => document.documentElement.classList.contains("dark"))));
  check("the override does not overwrite storage", (await page.evaluate(() => localStorage.getItem("cmb-theme"))) === "dark");
  await ctx.close();
}

// 2. Keyboard: load all scenarios, then j/k move focus with a visible ring, Enter opens the focused case.
{
  const ctx = await browser.newContext({ viewport: { width: 1024, height: 576 } });
  const page = await ctx.newPage();
  await page.goto(`${base}/?scenario=acme_normal&step=1`, { waitUntil: "networkidle" });
  await page.waitForSelector('body[data-ready="true"]');
  await page.evaluate(() => window.__cmb?.loadAll());
  await page.waitForTimeout(200);
  const rows = await page.$$("button[data-row]");
  check("five queue rows after loadAll", rows.length === 5, `got ${rows.length}`);
  await page.keyboard.press("j");
  await page.keyboard.press("j");
  const focusedText = await page.evaluate(() => (document.activeElement)?.textContent ?? "");
  const ring = await page.evaluate(() => { const el = document.activeElement; if (!el) return ""; const s = getComputedStyle(el); return s.outlineStyle + " " + s.outlineWidth; });
  check("j moves focus onto a queue row", focusedText.length > 0 && (await page.evaluate(() => document.activeElement?.hasAttribute("data-row"))) === true, focusedText.slice(0, 40));
  check("focused row shows a focus ring (outline)", /solid/.test(ring) && !/0px/.test(ring), ring);
  const focusedId = await page.evaluate(() => document.activeElement?.getAttribute("data-id"));
  await page.keyboard.press("Enter");
  await page.waitForTimeout(150);
  const selectedIdAfter = await page.evaluate(() => document.querySelector('button[data-row][aria-current="true"]')?.getAttribute("data-id"));
  check("Enter opens the focused case (focused row becomes the selected row)", !!focusedId && focusedId === selectedIdAfter, `${focusedId} → ${selectedIdAfter}`);
  await page.keyboard.press("k");
  check("k moves focus back up", (await page.evaluate(() => document.activeElement?.hasAttribute("data-row"))) === true);
  // typing in an input must not trigger j/k
  await page.goto(`${base}/?scenario=acme_fraud&step=2&tab=demo`, { waitUntil: "networkidle" });
  await page.waitForSelector("#last4");
  await page.focus("#last4");
  await page.keyboard.press("j");
  check("j inside an input does not move queue focus", (await page.evaluate(() => document.activeElement?.id)) === "last4");
  await ctx.close();
}

// 3. Reduced motion: the stamp has no running animation when the user prefers reduced motion.
{
  const ctx = await browser.newContext({ viewport: { width: 1024, height: 576 }, reducedMotion: "reduce" });
  const page = await ctx.newPage();
  await page.goto(`${base}/?scenario=acme_fraud&step=3&player=0`, { waitUntil: "networkidle" });
  await page.waitForSelector('[role="img"][aria-label^="Decision"]');
  const anim = await page.evaluate(() => getComputedStyle(document.querySelector('[role="img"][aria-label^="Decision"]')).animationName);
  check("stamp animation disabled under prefers-reduced-motion", anim === "none", anim);
  await ctx.close();
}

await browser.close();
let fails = 0;
for (const [ok, name, extra] of results) { if (!ok) fails += 1; console.log(`${ok ? "ok  " : "FAIL"} ${name}${extra ? `  (${extra})` : ""}`); }
console.log(fails ? `\n${fails} failure(s)` : "\nall pass");
process.exit(fails ? 1 : 0);
