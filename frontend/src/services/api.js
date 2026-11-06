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

// Tokens live only in memory. A reload requires sign-in again.
export function createApiClient(baseUrl, { onUnauthorized = () => {} } = {}) {
  let tokens = null
  let generation = 0
  let refreshing = null

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
    tokens = value
    refreshing = null
  }

  async function request(path, options = {}) {
    const accessToken = tokens?.access_token
    const startedGeneration = generation
    try {
      return await send(path, { ...options, accessToken })
    } catch (error) {
      const publicAuth = ['/auth/login', '/auth/register', '/auth/refresh'].includes(path)
      if (error.status !== 401 || !accessToken || publicAuth || startedGeneration !== generation) throw error
      // Concurrent requests share one rotation; a late 401 reuses the new access token.
      if (tokens?.access_token === accessToken) {
        if (!refreshing) {
          const pending = send('/auth/refresh', { method: 'POST', body: { refresh_token: tokens.refresh_token } })
            .then((pair) => {
              if (generation === startedGeneration) tokens = pair
            }).catch((refreshError) => {
              if (generation === startedGeneration) {
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

  return { request, setTokens }
}
