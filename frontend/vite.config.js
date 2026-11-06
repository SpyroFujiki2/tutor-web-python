import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { env as processEnv } from 'node:process'
import { defineConfig, loadEnv } from 'vite'

const envDir = fileURLToPath(new URL('../', import.meta.url))

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, envDir, 'TUNNEL_')
  const tunnelHostname = env.TUNNEL_HOSTNAME?.trim()
  // Vercel Services routes browser /api requests before they reach Vite.
  // This proxy is only for running Vite and Uvicorn separately on a laptop.
  const standalone = processEnv.VERCEL !== '1'

  return {
    plugins: [react()],
    envDir,
    server: {
      host: '127.0.0.1',
      port: 5173,
      strictPort: true,
      allowedHosts: tunnelHostname ? [tunnelHostname] : [],
      proxy: standalone ? {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      } : undefined,
    },
  }
})
