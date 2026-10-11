// The queue (winner 13A). "Load a sample" picks a scenario in fixtures mode; spec 007 points it at the API.
import { ChevronDown, Upload } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { QueueRowStacked } from "@/features/queue/QueueRow";
import { isFixtures, postFromSample, useAction, useInvoices } from "@/lib/api";
import { fixtureStore } from "@/lib/fixtures";
import { setQuery } from "@/lib/route";
import { SAMPLE_FOR_SCENARIO, SCENARIO_TITLES, SCENARIOS, type ScenarioName } from "@/lib/types";

export function QueueList({ selectedId, onSelect }: { selectedId: string | null; onSelect: (id: string) => void }) {
  const { data: rows = [], isLoading } = useInvoices();
  const load = useAction(postFromSample);

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

      <ol className="min-h-0 flex-1 space-y-1 overflow-y-auto" aria-label="Invoices">
        {rows.map((r) => (
          <li key={r.id}><QueueRowStacked row={r} selected={r.id === selectedId} onSelect={() => onSelect(r.id)} /></li>
        ))}
        {!isLoading && rows.length === 0 && <li className="px-2 text-sm text-muted-foreground">No invoices yet.</li>}
      </ol>
    </div>
  );
}
