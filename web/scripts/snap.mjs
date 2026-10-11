#!/usr/bin/env node
// Screenshot every scenario step in light and dark at 1024×576 (PLAN.md §14.7 step 5).
// Fails on any console error or any request to a host other than localhost (SC-006).
//
//   node scripts/snap.mjs [--base http://localhost:5173] [--out snapshots] [--gallery] [--shell] [--reduced-motion]
//
// --live runs the PLAN.md §19.1 story against a running API instead of the fixtures (spec 007):
//   node scripts/snap.mjs --live [--base http://localhost:5173] [--api http://localhost:8000] [--user U --pass P]
// It resets the demo, pre-runs Heartland, then drives the story through the UI; it also fails when a
// stamp shows up more than 1.5 s after the API reached that status.
//
import { mkdir } from "node:fs/promises";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = (name, dflt) => { const i = args.indexOf(name); return i >= 0 && args[i + 1] && !args[i + 1].startsWith("--") ? args[i + 1] : dflt; };
const has = (name) => args.includes(name);

const base = opt("--base", "http://localhost:5173").replace(/\/+$/, "");
const out = path.resolve(here, "..", opt("--out", "snapshots"));
const index = JSON.parse(readFileSync(path.resolve(here, "..", "src/fixtures/index.json"), "utf8"));
const themes = ["light", "dark"];
const viewport = { width: 1024, height: 576 };

await mkdir(out, { recursive: true });
const browser = await chromium.launch();
const problems = [];
let shots = 0;

async function shoot(url, file, { fullPage = false, reducedMotion = false } = {}) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 1, reducedMotion: reducedMotion ? "reduce" : "no-preference", colorScheme: "light" });
  const page = await ctx.newPage();
  const errors = [];
  const foreign = new Set();
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("request", (r) => { const h = new URL(r.url()).hostname; if (!["localhost", "127.0.0.1"].includes(h)) foreign.add(h); });
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForSelector('body[data-ready="true"]', { timeout: 10000 }).catch(() => errors.push("timeout waiting for body[data-ready]"));
  await page.waitForTimeout(250); // let the stamp animation finish
  await page.screenshot({ path: path.join(out, file), fullPage });
  shots += 1;
  if (errors.length) problems.push({ file, errors });
  if (foreign.size) problems.push({ file, foreign: [...foreign] });
  await ctx.close();
  process.stdout.write(`  ${file}${errors.length || foreign.size ? "  ✗" : ""}\n`);
}

// ---- --live: the PLAN.md §19.1 story against a running API (spec 007 T017, research R12) -------------
// Setup goes through the API (reset, Heartland pre-run); the story goes through the UI, like the
// presenter. Fails on console errors, requests to other hosts, or a stamp that lags the API by > 1.5 s.
const API = opt("--api", base).replace(/\/+$/, "");
const USER = opt("--user", null), PASS = opt("--pass", null);
const AUTH = USER ? { Authorization: "Basic " + Buffer.from(`${USER}:${PASS ?? ""}`).toString("base64") } : {};
const LATENCY_MS = 1500;
const allowedHosts = new Set(["localhost", "127.0.0.1", new URL(base).hostname, new URL(API).hostname]);

async function api(p, body) {
  const res = await fetch(API + p, body === undefined ? { headers: AUTH }
    : { method: "POST", headers: { ...AUTH, "content-type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`${p} → ${res.status}`);
  return res.json();
}
async function untilApi(id, statuses, ms = 30000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    const d = await api(`/api/invoices/${id}`);
    if (statuses.includes(d.status)) return { d, at: Date.now() };
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error(`${id} never reached ${statuses.join("/")}`);
}

async function liveStory(theme) {
  await api("/api/demo/reset", {});
  const heart = (await api("/api/invoices/from-sample", { name: "03_heartland_bank_change" })).id;   // §19.2 pre-run
  await untilApi(heart, ["CALLING"]);
  await api("/api/demo/simulate-answer", { subject_id: heart, answer: "yes", last4: "4455" });
  await untilApi(heart, ["RELEASED"]);

  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 1, colorScheme: theme,
                                          httpCredentials: USER ? { username: USER, password: PASS ?? "" } : undefined });
  const page = await ctx.newPage();
  const errors = [], foreign = new Set(), timings = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("request", (r) => { const h = new URL(r.url()).hostname; if (!allowedHosts.has(h)) foreign.add(h); });
  let n = 0;
  const shot = async (step) => {
    await page.waitForTimeout(300);                           // stamp animation
    const file = `live-${String(++n).padStart(2, "0")}-${step}-${theme}.png`;
    await page.screenshot({ path: path.join(out, file) });
    shots += 1;
    process.stdout.write(`  ${file}\n`);
  };
  // the API reaching `statuses` vs the stamp `kind` appearing on screen (SC-001)
  const stampFollows = async (label, id, statuses, kind) => {
    const [{ at: apiAt }] = await Promise.all([
      untilApi(id, statuses),
      page.locator(`[aria-label="Decision: ${kind}"]`).waitFor({ timeout: 30000 }),
    ]);
    const lag = Math.max(0, Date.now() - apiAt);
    // the DOM wait resolves after the API poll when the screen lags; measure the screen's own arrival
    timings.push({ label, lag });
    if (lag > LATENCY_MS) problems.push({ file: `${theme}: ${label}`, errors: [`stamp ${lag} ms after the API (> ${LATENCY_MS})`] });
  };
  const newestId = async () => (await api("/api/invoices"))[0].id;
  const tab = async (name) => { await page.getByRole("button", { name, exact: true }).click(); await page.waitForTimeout(500); };
  const loadSample = async (re) => {
    await page.getByRole("button", { name: /Load a sample/ }).click();
    await page.getByRole("menuitem", { name: re }).click();
  };

  await page.goto(`${base}/?theme=${theme}`, { waitUntil: "networkidle" });
  await page.waitForSelector('body[data-ready="true"]', { timeout: 10000 });
  await shot("empty-case");                                                       // 0:00

  await loadSample(/normal/i);                                                    // 0:20 → PAID
  await page.locator('[aria-label^="Decision:"]').waitFor({ timeout: 10000 });
  await stampFollows("normal paid", await newestId(), ["RELEASED"], "paid");
  await shot("acme-normal-paid");

  await loadSample(/urgent bank change/i);                                         // 0:35 → RED, calling
  await page.locator('[aria-label^="Decision:"]').waitFor({ timeout: 10000 });
  const fraud = await newestId();
  await stampFollows("fraud calling", fraud, ["CALLING"], "calling");
  await shot("acme-fraud-calling");

  await tab("Demo controls");                                                     // 1:05 → simulated "no"
  await page.locator('[aria-label="Simulate the vendor\'s answer"]').getByRole("button", { name: "Vendor says no" }).click();
  await stampFollows("fraud held", fraud, ["HELD"], "held");
  await shot("acme-fraud-held");
  await tab("Demo controls");

  await page.getByRole("button", { name: "Try to make the AI pay" }).click();     // 1:55 → blocked
  await page.getByRole("dialog").filter({ hasText: "compromised Payments agent" }).waitFor({ timeout: 30000 });
  await shot("redteam-blocked");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(500);
  await shot("agent-trace");
  await page.keyboard.press("Escape");

  await tab("Audit log");                                                         // 2:15
  await page.getByText(/Chain verified/).first().waitFor({ timeout: 10000 });
  await shot("audit-chain-verified");
  await tab("Vendors");
  await page.getByText(/verified by callback/i).first().waitFor({ timeout: 10000 });
  await shot("vendors-heartland-updated");
  await tab("DevRev cases");                                                      // 2:35
  await shot("devrev-cases");
  await tab("DevRev cases");
  await shot("header-running-on");                                                // 2:50

  if (errors.length) problems.push({ file: `live story (${theme})`, errors });
  if (foreign.size) problems.push({ file: `live story (${theme})`, foreign: [...foreign] });
  console.log(`  ${theme}: stamp lag ${timings.map((t) => `${t.label} ${t.lag} ms`).join(", ")}`);
  await ctx.close();
}

try {
  if (has("--live")) {
    for (const theme of themes) await liveStory(theme);
  } else if (has("--shell") || (!has("--gallery") && !has("--cards") && !has("--steps"))) {
    for (const theme of themes) await shoot(`${base}/?scenario=none&theme=${theme}`, `shell-empty-${theme}.png`);
  }
  if (has("--gallery")) {
    for (const theme of themes) await shoot(`${base}/gallery?theme=${theme}`, `gallery-${theme}.png`, { fullPage: true });
  }
  if (has("--cards")) {
    // One screenshot per candidate card, at a 1100px-wide viewport, light theme (and dark with --cards-dark).
    const cardThemes = has("--cards-dark") ? themes : ["light"];
    for (const theme of cardThemes) {
      const ctx = await browser.newContext({ viewport: { width: 1100, height: 900 }, deviceScaleFactor: 1 });
      const page = await ctx.newPage();
      await page.goto(`${base}/gallery?theme=${theme}`, { waitUntil: "networkidle" });
      await page.waitForSelector('body[data-ready="true"]');
      const cards = await page.$$("article[id^='c']");
      for (const card of cards) {
        const id = await card.getAttribute("id");
        await card.screenshot({ path: path.join(out, `card-${id}-${theme}.png`) });
        shots += 1;
        process.stdout.write(`  card-${id}-${theme}.png\n`);
      }
      await ctx.close();
    }
  }
  if (!has("--live") && !has("--gallery") && !has("--shell") && !has("--cards")) {
    for (const [scenario, steps] of Object.entries(index)) {
      for (let i = 0; i < steps.length; i++) {
        const n = String(i + 1).padStart(2, "0");
        for (const theme of themes) {
          await shoot(`${base}/?scenario=${scenario}&step=${i + 1}&theme=${theme}&player=0`, `${scenario}-${n}-${steps[i].step}-${theme}.png`);
        }
      }
    }
    if (has("--reduced-motion")) {
      await shoot(`${base}/?scenario=acme_fraud&step=3&theme=light&player=0`, `acme_fraud-03-held-light-reduced-motion.png`, { reducedMotion: true });
    }
  }
} finally {
  await browser.close();
}

console.log(`\n${shots} screenshots → ${out}`);
if (problems.length) {
  console.error("\nProblems:");
  for (const p of problems) console.error(" ", p.file, p.errors ?? "", p.foreign ? `third-party hosts: ${p.foreign.join(", ")}` : "");
  process.exit(1);
}
