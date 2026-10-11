// The queue (winner 13A). "Load a sample" picks a scenario in fixtures mode; spec 007 points it at the API.
// Keyboard: j/k (or arrows) move the highlight, Enter opens, focus ring always visible (PLAN.md §14.9, §14.10).
import { ChevronDown, Upload } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { QueueRowStacked } from "@/features/queue/QueueRow";
import { isFixtures, postFromSample, useAction, useInvoices } from "@/lib/api";
import { fixtureStore } from "@/lib/fixtures";
import { setQuery } from "@/lib/route";
import { SAMPLE_FOR_SCENARIO, SCENARIO_TITLES, SCENARIOS, type ScenarioName } from "@/lib/types";

function isTyping(target: EventTarget | null) {
  const el = target as HTMLElement | null;
  return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
}

export function QueueList({ selectedId, onSelect }: { selectedId: string | null; onSelect: (id: string) => void }) {
  const { data: rows = [], isLoading } = useInvoices();
  const load = useAction(postFromSample);
  const listRef = useRef<HTMLOListElement>(null);
  // Roving focus: the user's last keyboard position, or the selected row, or the first row (derived, no effect).
  const [userIdx, setUserIdx] = useState<number | null>(null);
  const selectedIdx = rows.findIndex((r) => r.id === selectedId);
  const focusIdx = userIdx != null && userIdx < rows.length ? userIdx : selectedIdx >= 0 ? selectedIdx : rows.length ? 0 : -1;
  const setFocusIdx = setUserIdx;

  const focusRow = (i: number) => {
    if (!rows.length) return;
    const next = Math.min(Math.max(i, 0), rows.length - 1);
    setFocusIdx(next);
    const btn = listRef.current?.querySelectorAll<HTMLButtonElement>("button[data-row]")[next];
    btn?.focus();
    btn?.scrollIntoView({ block: "nearest" });
  };

  // Global j/k so the specialist can move without first clicking the queue (ignored while typing).
  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || isTyping(e.target)) return;
      if (e.key === "j") { e.preventDefault(); focusRow(focusIdx + 1); }
      else if (e.key === "k") { e.preventDefault(); focusRow(focusIdx - 1); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const onListKey = (e: KeyboardEvent<HTMLOListElement>) => {
    if (e.key === "ArrowDown") { e.preventDefault(); focusRow(focusIdx + 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); focusRow(focusIdx - 1); }
    else if (e.key === "Enter" && focusIdx >= 0 && rows[focusIdx]) { e.preventDefault(); onSelect(rows[focusIdx].id); }
    else if (e.key === "Home") { e.preventDefault(); focusRow(0); }
    else if (e.key === "End") { e.preventDefault(); focusRow(rows.length - 1); }
  };

  const loadSample = (s: ScenarioName) => {
    load.mutate([SAMPLE_FOR_SCENARIO[s]], {
      onSuccess: (r) => { if (isFixtures) setQuery({ scenario: s, step: 1 }); onSelect(r.id); },
      onError: (e) => toast.error(`Couldn't load the sample: ${e.message}`),
    });
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex gap-2 pb-3">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button className="flex-1" disabled={load.isPending}>Load a sample <ChevronDown className="size-4" aria-hidden /></Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-64">
            {SCENARIOS.map((s) => (
              <DropdownMenuItem key={s} onSelect={() => loadSample(s)} disabled={isFixtures && fixtureStore.isLoaded(s)}>
                {SCENARIO_TITLES[s]}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        <Tooltip>
          <TooltipTrigger asChild>
            <span><Button variant="outline" size="icon" aria-label="Upload .eml" disabled={isFixtures}><Upload className="size-4" aria-hidden /></Button></span>
          </TooltipTrigger>
          <TooltipContent>{isFixtures ? "Upload needs the live API (spec 007)" : "Upload an .eml file"}</TooltipContent>
        </Tooltip>
      </div>

      <ol ref={listRef} className="min-h-0 flex-1 space-y-1 overflow-y-auto" aria-label="Invoices (j and k to move, Enter to open)" onKeyDown={onListKey}>
        {rows.map((r, i) => (
          <li key={r.id}>
            <QueueRowStacked row={r} selected={r.id === selectedId} onSelect={() => { setFocusIdx(i); onSelect(r.id); }}
                             tabIndex={i === focusIdx ? 0 : -1} />
          </li>
        ))}
        {!isLoading && rows.length === 0 && <li className="px-2 text-sm text-muted-foreground">No invoices yet.</li>}
      </ol>
      {rows.length > 1 && <p className="pt-2 text-xs text-muted-foreground">j / k to move, Enter to open</p>}
    </div>
  );
}
