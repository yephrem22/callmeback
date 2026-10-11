import { lazy, Suspense } from "react";

import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Layout } from "@/features/shell/Layout";
import { isDev, useRoute } from "@/lib/route";
import { ThemeProvider } from "@/lib/theme";

// Development-only: resolves to an empty stub in production builds (devOnly() in vite.config.ts).
const Gallery = lazy(() => import("virtual:dev-only/gallery"));

export default function App() {
  const route = useRoute();
  return (
    <ThemeProvider override={route.theme}>
      <TooltipProvider delayDuration={200}>
        {route.path === "/gallery" ? (
          isDev ? (
            <Suspense fallback={<div className="p-8 text-muted-foreground">Loading gallery…</div>}>
              <Gallery />
            </Suspense>
          ) : (
            <div className="p-8">Not found.</div>
          )
        ) : (
          <Layout route={route} />
        )}
        <Toaster position="bottom-center" richColors closeButton />
      </TooltipProvider>
    </ThemeProvider>
  );
}
