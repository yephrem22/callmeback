# Quickstart: UI Design Prototype (spec 004)

## Prerequisites

Node 22 and npm 10 (`export PATH="$HOME/.nvm/versions/node/v22.23.3/bin:$PATH"` if the shell default is still Node 20). No backend, no credentials.

```bash
cd web
npm install
npx playwright install chromium     # once, for the snapshot script
```

## 1. Gallery (milestone U1)

```bash
npm run dev            # http://localhost:5173
open http://localhost:5173/gallery
```

Expected: fourteen numbered cards, each with "shows / serves / fields / components", two rendered variants side by side, and a copy button on the snippet. The page uses only fixture data; the network tab shows no requests except Vite's own.

## 2. Human gate (milestone U2)

Both builders review `/gallery` for 15 minutes and fill the table in `docs/design/decisions.md` (slot → candidate → variant → reason). No prototype work before this file exists.

## 3. Prototype on fixtures (milestone U3)

```bash
npm run dev
open "http://localhost:5173/?scenario=acme_fraud&step=3&theme=light"
```

Expected per scenario (final step): acme_normal PAID; acme_fraud HELD "Held. The vendor said no on the HH:MM call." with the callback transcript; heartland_bank_change PAID with vendor history "verified by callback"; prairie_review PAID after REVIEW; unknown_vendor HELD "Held. No vendor record, so there's no trusted number to call." The scenario player (dev only, bottom-right) steps through every scenario.

Empty state: `http://localhost:5173/?scenario=none` shows "Load a sample invoice to start."

## 4. Checks

```bash
npm run typecheck && npm run lint && npm run build
```

Expected: zero errors; `dist/` contains no `/gallery` chunk (grep `dist/assets` for "gallery" → nothing).

## 5. Snapshots (after every phase)

```bash
npm run dev &                       # or: npm run build && npm run preview
node scripts/snap.mjs --base http://localhost:5173
ls snapshots                        # <scenario>-<nn>-<light|dark>.png, 28 files
```

The script exits non-zero on any console error or any non-localhost request. Review the images, write the top three issues into `docs/design/decisions.md` under "Self-critique", fix them, re-run.

## 6. Hand-off to spec 007

`VITE_API_MODE=live npm run dev` with the FastAPI app on :8000 proxies `/api` and shows the same screens on real data. Fixtures mode must keep working.
