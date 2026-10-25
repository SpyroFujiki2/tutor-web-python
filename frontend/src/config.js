// An explicit empty value uses the current origin behind a reverse proxy.
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000')
  .trim()
  .replace(/\/+$/, '')
