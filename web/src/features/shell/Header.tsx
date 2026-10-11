import { Cpu, Database, HardDrive, Monitor, Moon, Phone, Sparkles, Sun } from "lucide-react";

import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useHealth } from "@/lib/api";
import { useTheme } from "@/lib/theme";

function Dot({ ok, label, icon: Icon, detail, unreachable }: {
  ok: boolean | null; label: string; icon: typeof Database; detail: string; unreachable?: string;
}) {
  const tone = unreachable ? "bg-held" : ok === null ? "bg-muted-foreground" : ok ? "bg-paid" : "bg-held";
  const word = unreachable ? "unreachable" : ok === null ? "unknown" : ok ? "ok" : "down";
  const tip = unreachable ?? detail;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground" aria-label={`${label}: ${word}`}>
          <Icon className="size-4" aria-hidden />
          <span className={`inline-block size-2 rounded-full ${tone}`} aria-hidden />
          <span className="hidden lg:inline">{label}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent>{label}: {word}. {tip}</TooltipContent>
    </Tooltip>
  );
}

export function Header() {
  const { data: h, isError, error } = useHealth();
  // Health can fail on its own; the queue and case poll independently (spec 007 R8).
  const down = isError
    ? `Couldn't reach /api/health (${error instanceof Error ? error.message : "no response"}). The queue and case keep updating on their own.`
    : undefined;
  const { theme, setTheme } = useTheme();
  const ThemeIcon = theme === "dark" ? Moon : theme === "system" ? Monitor : Sun;
  const latency = h?.model.latency_ms != null ? `${(h.model.latency_ms / 1000).toFixed(1)} s` : null;

  return (
    <header className="flex h-14 items-center gap-4 whitespace-nowrap border-b border-border px-4">
      <div className="flex items-center gap-3">
        <h1 className="self-center"><Logo /></h1>
        {/* Visible from 1024 px: 1280×720 at 125% zoom is the stage (§14.10, §19.1 "Running on Akamai Cloud"). */}
        {/* 1024–1279 px: "Running on Akamai Cloud" (the label before its comma); 1280+: the full label. */}
        <span className="hidden whitespace-nowrap text-sm text-muted-foreground lg:inline"
              title={h?.deploy_label ? `Running on ${h.deploy_label}` : undefined}>
          Running on <span className="xl:hidden">{h?.deploy_label?.split(",")[0] ?? "…"}</span>
          <span className="hidden xl:inline">{h?.deploy_label ?? "…"}</span>
        </span>
      </div>

      <div className="ml-auto flex items-center gap-4">
        <div className="flex items-center gap-3">
          <Dot ok={h ? h.db : null} label="Database" icon={Database} detail="SQLite in WAL mode." unreachable={down} />
          <Dot ok={h ? h.model.ok : null} label={latency ? `Inference ${latency}` : "Inference"} icon={Cpu}
               detail={latency ? `Akamai inference, median of recent model calls: ${latency}.` : "Akamai inference: no model calls yet."} unreachable={down} />
          <Dot ok={h ? h.twilio.configured : null} label="Twilio" icon={Phone} detail={h?.twilio.configured ? "Live calls enabled." : "Simulated line; answer with the demo controls."} unreachable={down} />
          <Dot ok={h ? h.storage.ok : null} label="Storage" icon={HardDrive} detail="Evidence locker." unreachable={down} />
        </div>

        <span
          className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-sm ${h?.ai_mode === "live" ? "border-ai/40 bg-ai-soft text-ai" : "border-border text-muted-foreground"}`}
          aria-live="polite"
        >
          <Sparkles className="size-4" aria-hidden />
          {down ? "AI: unknown" : h?.ai_mode === "live" ? "AI: live" : "AI: off (rules only)"}
        </span>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" aria-label={`Theme: ${theme}`}>
              <ThemeIcon className="size-4" aria-hidden />
              <span className="capitalize">{theme}</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={() => setTheme("light")}><Sun className="size-4" /> Light</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => setTheme("dark")}><Moon className="size-4" /> Dark</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => setTheme("system")}><Monitor className="size-4" /> System</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
