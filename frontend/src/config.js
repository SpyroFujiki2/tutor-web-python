// Use the current origin by default; Vite forwards /api to the local backend.
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '')
  .trim()
  .replace(/\/+$/, '')
