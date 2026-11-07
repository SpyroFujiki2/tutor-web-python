import { browserStorage, readSession, SESSION_KEY, sessionIdentity, validTokens, writeSession } from './session.js'

export async function getHealth(baseUrl, { signal } = {}) {
  const timeout = AbortSignal.timeout(10_000)
  const requestSignal = signal ? AbortSignal.any([signal, timeout]) : timeout
  let response

  try {
    response = await fetch(`${baseUrl}/api/health`, {
      headers: { Accept: 'application/json' },
      signal: requestSignal,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    if (timeout.aborted) throw new Error('API phản hồi quá chậm. Vui lòng thử lại.', { cause: error })
    throw new Error('Không kết nối được API. Kiểm tra backend và cấu hình CORS.', { cause: error })
  }

  if (!response.ok) {
    throw new Error(`API trả về lỗi HTTP ${response.status}.`)
  }

  let data
  try {
    data = await response.json()
  } catch (error) {
    if (signal?.aborted) throw error
    if (timeout.aborted) throw new Error('API phản hồi quá chậm. Vui lòng thử lại.', { cause: error })
    throw new Error('API không trả về dữ liệu JSON hợp lệ.', { cause: error })
  }
  if (data?.status !== 'ok' || typeof data.message !== 'string') {
    throw new Error('Dữ liệu kiểm tra kết nối không đúng định dạng.')
  }
  return data
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function createApiClient(baseUrl, {
  onUnauthorized = () => {}, storage = browserStorage(),
  locks = globalThis.navigator?.locks, eventTarget = globalThis.window,
} = {}) {
  const storageKey = `${SESSION_KEY}:${baseUrl || 'same-origin'}`
  let tokens = readSession(storage, storageKey)
  let saved = JSON.stringify(tokens)
  let generation = 0
  let refreshing = null
  const listeners = new Set()

  function syncSession() {
    if (!storage) return
    const latest = readSession(storage, storageKey)
    const serialized = JSON.stringify(latest)
    if (serialized === saved) return
    const changedSession = sessionIdentity(latest) !== sessionIdentity(tokens)
    tokens = latest
    saved = serialized
    if (changedSession) {
      generation += 1
      refreshing = null
      listeners.forEach((listener) => listener())
    }
  }

  function persist(value) {
    tokens = validTokens(value)
    saved = JSON.stringify(tokens)
    writeSession(storage, storageKey, tokens)
    // A failed write must not make a later read erase the in-memory login.
    if (storage && JSON.stringify(readSession(storage, storageKey)) !== saved) storage = null
  }

  async function send(path, { method = 'GET', body, rawBody, contentType, responseType, signal, accessToken } = {}) {
    const timeout = AbortSignal.timeout(10_000)
    const requestSignal = signal ? AbortSignal.any([signal, timeout]) : timeout
    let response
    try {
      response = await fetch(`${baseUrl}/api${path}`, {
        method,
        signal: requestSignal,
        headers: {
          Accept: 'application/json',
          ...(rawBody !== undefined ? { 'Content-Type': contentType ?? 'application/octet-stream' }
            : body !== undefined ? { 'Content-Type': 'application/json' } : {}),
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        ...(rawBody !== undefined ? { body: rawBody } : body !== undefined ? { body: JSON.stringify(body) } : {}),
      })
      if (response.status === 204) return null
      if (response.ok && responseType === 'blob') return await response.blob()
      const payload = await response.json().catch(() => null)
      if (!response.ok) {
        const detail = payload?.detail
        const message = typeof detail === 'string' ? detail : Array.isArray(detail)
          ? detail.map((item) => `${item.loc?.slice(1).join('.')}: ${item.msg}`).join('; ')
          : `Yêu cầu thất bại (HTTP ${response.status}).`
        throw new ApiError(message, response.status)
      }
      if (payload === null) throw new ApiError('API trả dữ liệu không hợp lệ.', response.status)
      return payload
    } catch (error) {
      if (signal?.aborted || error instanceof ApiError) throw error
      if (timeout.aborted) throw new Error('API phản hồi quá chậm. Vui lòng tải lại trước khi thử tiếp.', { cause: error })
      throw new Error('Không kết nối được API. Vui lòng kiểm tra kết nối.', { cause: error })
    }
  }

  function setTokens(value) {
    generation += 1
    persist(value)
    refreshing = null
  }

  function subscribeSession(listener) {
    listeners.add(listener)
    const handle = (event) => {
      if (event.key === storageKey || event.key === null) syncSession()
    }
    eventTarget?.addEventListener('storage', handle)
    // Detect changes made while this tab was suspended.
    eventTarget?.addEventListener('focus', syncSession)
    return () => {
      listeners.delete(listener)
      eventTarget?.removeEventListener('storage', handle)
      eventTarget?.removeEventListener('focus', syncSession)
    }
  }

  async function request(path, options = {}) {
    syncSession()
    const accessToken = tokens?.access_token
    const startedGeneration = generation
    try {
      return await send(path, { ...options, accessToken })
    } catch (error) {
      const publicAuth = ['/auth/login', '/auth/register', '/auth/refresh'].includes(path)
      if (error.status !== 401 || !accessToken || publicAuth || startedGeneration !== generation) throw error
      // Concurrent requests share one rotation; a late 401 reuses the new access token.
      syncSession()
      if (tokens?.access_token === accessToken) {
        if (!refreshing) {
          const rotate = async () => {
            syncSession()
            if (generation !== startedGeneration || !tokens) throw new ApiError('Phiên đăng nhập đã kết thúc.', 401)
            if (tokens.access_token !== accessToken) return
            const refreshToken = tokens.refresh_token
            const pair = await send('/auth/refresh', { method: 'POST', body: { refresh_token: refreshToken } })
            syncSession()
            if (generation === startedGeneration && tokens?.refresh_token === refreshToken) persist(pair)
          }
          // Refresh tokens are single-use. Serialize rotation across browser tabs.
          const pending = (storage && locks?.request ? locks.request(storageKey, rotate) : rotate())
            .catch((refreshError) => {
              syncSession()
              if ([401, 403].includes(refreshError.status) && generation === startedGeneration) {
                setTokens(null)
                onUnauthorized()
              }
              throw refreshError
            }).finally(() => {
              if (refreshing === pending) refreshing = null
            })
          refreshing = pending
        }
        await refreshing
      }
      if (startedGeneration !== generation || !tokens) throw new ApiError('Phiên đăng nhập đã kết thúc.', 401)
      try {
        return await send(path, { ...options, accessToken: tokens.access_token })
      } catch (retryError) {
        if (retryError.status === 401 && startedGeneration === generation) {
          setTokens(null)
          onUnauthorized()
        }
        throw retryError
      }
    }
  }

  return { request, setTokens, subscribeSession, hasSession: () => { syncSession(); return !!tokens } }
}
