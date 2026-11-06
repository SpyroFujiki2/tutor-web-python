// Browser requests stay on the current origin. Vercel Services routes /api
// to FastAPI; standalone Vite development uses its local-only proxy instead.
// A runtime service-binding URL must never be compiled into browser JavaScript.
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '')
  .trim()
  .replace(/\/+$/, '')
