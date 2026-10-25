import { useEffect, useState } from 'react'
import { API_BASE_URL } from '../config.js'
import { getHealth } from '../services/api.js'

export default function ApiStatus() {
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState(null)
  const currentResult = result?.attempt === attempt ? result : null

  useEffect(() => {
    const controller = new AbortController()
    getHealth(API_BASE_URL, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setResult({ attempt, data })
      })
      .catch((error) => {
        if (!controller.signal.aborted) setResult({ attempt, error: error.message })
      })
    return () => controller.abort()
  }, [attempt])

  const loading = currentResult === null
  return (
    <section className="connection-card" aria-labelledby="connection-title">
      <div className="card-heading">
        <h2 id="connection-title">Kết nối hệ thống</h2>
        <span className={`status-dot ${currentResult?.data ? 'connected' : ''}`} aria-hidden="true" />
      </div>
      <p role="status" aria-live="polite">
        {loading ? 'Đang kiểm tra API…' : currentResult.error ?? currentResult.data.message}
      </p>
      <button type="button" disabled={loading} onClick={() => setAttempt((value) => value + 1)}>
        {loading ? 'Đang kiểm tra…' : 'Kiểm tra lại'}
      </button>
    </section>
  )
}
