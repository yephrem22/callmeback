#!/usr/bin/env node
// Screenshot every scenario step in light and dark at 1024×576 (PLAN.md §14.7 step 5).
// Fails on any console error or any request to a host other than localhost (SC-006).
//
//   node scripts/snap.mjs [--base http://localhost:5173] [--out snapshots] [--gallery] [--shell] [--reduced-motion]
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

try {
  if (has("--shell") || (!has("--gallery") && !has("--cards") && !has("--steps"))) {
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
  if (!has("--gallery") && !has("--shell") && !has("--cards")) {
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
