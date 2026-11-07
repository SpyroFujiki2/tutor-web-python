export const SESSION_KEY = 'tutor-web-session:v1'

export function browserStorage() {
  try { return globalThis.localStorage ?? null } catch { return null }
}

export function validTokens(value) {
  return value && typeof value.access_token === 'string' && value.access_token.length > 0 &&
    typeof value.refresh_token === 'string' && value.refresh_token.length > 0
    ? value : null
}

// Used only to recognize a rotation of the same session; the API verifies JWTs.
export function sessionIdentity(tokens) {
  if (!tokens) return null
  try {
    const payload = tokens.refresh_token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    const claims = JSON.parse(atob(payload))
    if (typeof claims.sid === 'string') return claims.sid
  } catch { /* Non-JWT credentials cannot be identified across rotations. */ }
  return tokens.refresh_token
}

export function readSession(storage, key) {
  try { return validTokens(JSON.parse(storage?.getItem(key) ?? 'null')) } catch { return null }
}

export function writeSession(storage, key, tokens) {
  try {
    if (tokens) storage?.setItem(key, JSON.stringify(tokens))
    else storage?.removeItem(key)
  } catch { /* Keep the in-memory session usable if browser storage is disabled. */ }
}
