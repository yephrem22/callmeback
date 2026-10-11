// Light / dark / system theme (shadcn Vite pattern). Light is the default: projectors wash out dark themes.
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import type { ThemeName } from "@/lib/route";

const STORAGE_KEY = "cmb-theme";

interface ThemeCtx { theme: ThemeName; resolved: "light" | "dark"; setTheme: (t: ThemeName) => void }

const Ctx = createContext<ThemeCtx>({ theme: "light", resolved: "light", setTheme: () => {} });

function systemTheme(): "light" | "dark" {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children, override }: { children: ReactNode; override: ThemeName | null }) {
  const [theme, setThemeState] = useState<ThemeName>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "dark" || stored === "system" || stored === "light" ? stored : "light";
  });
  const effective = override ?? theme;
  const [resolved, setResolved] = useState<"light" | "dark">(() => (effective === "system" ? systemTheme() : effective));

  useEffect(() => {
    const apply = () => {
      const r = effective === "system" ? systemTheme() : effective;
      setResolved(r);
      document.documentElement.classList.toggle("dark", r === "dark");
      document.documentElement.style.colorScheme = r;
    };
    apply();
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, [effective]);

  const value = useMemo<ThemeCtx>(() => ({
    theme: effective,
    resolved,
    setTheme: (t) => { localStorage.setItem(STORAGE_KEY, t); setThemeState(t); },
  }), [effective, resolved]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTheme() { return useContext(Ctx); }
