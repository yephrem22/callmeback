import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

/**
 * Development-only modules (PLAN.md §14.7: the gallery and the scenario player are "development only").
 * `virtual:dev-only/<name>` resolves to the real module under `vite dev` and to an empty stub in `vite build`,
 * so nothing from those modules reaches the production bundle.
 */
function devOnly(): Plugin {
  const prefix = 'virtual:dev-only/'
  const map: Record<string, string> = {
    gallery: path.resolve(__dirname, 'src/features/gallery/Gallery.tsx'),
    player: path.resolve(__dirname, 'src/features/demo/ScenarioPlayer.tsx'),
  }
  let isBuild = false
  return {
    name: 'cmb-dev-only',
    configResolved(cfg) { isBuild = cfg.command === 'build' },
    resolveId(id) {
      if (!id.startsWith(prefix)) return null
      const name = id.slice(prefix.length)
      if (!(name in map)) return null
      return isBuild ? `\0${id}` : map[name]
    },
    load(id) {
      if (id.startsWith(`\0${prefix}`)) return 'export default function DevOnlyStub() { return null }'
      return null
    },
  }
}

// PLAN.md §14.5: Tailwind v4 via the Vite plugin, "@" → ./src, /api proxied to FastAPI in dev.
export default defineConfig({
  plugins: [react(), tailwindcss(), devOnly()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 700,
  },
})
