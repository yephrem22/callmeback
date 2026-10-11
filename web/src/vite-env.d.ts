/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_MODE?: "fixtures" | "live";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// Development-only modules; see devOnly() in vite.config.ts.
declare module "virtual:dev-only/gallery" {
  const Gallery: () => import("react").ReactElement | null;
  export default Gallery;
}
declare module "virtual:dev-only/player" {
  const ScenarioPlayer: (props: Record<string, unknown>) => import("react").ReactElement | null;
  export default ScenarioPlayer;
}
