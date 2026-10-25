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
