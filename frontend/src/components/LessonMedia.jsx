import { useEffect, useEffectEvent, useRef, useState } from 'react'
import { driveVideo, externalMediaUrl } from '../services/media.js'
import { formatDuration, playbackDelta } from '../services/watch-time.js'

export default function LessonMedia({ url, title, api, subscriptionId, lessonId, initialWatched = 0, track = false, onSaved, onWatch }) {
  const videoRef = useRef(null)
  const cacheKey = `lesson-watch:${subscriptionId}:${lessonId}`
  const [startingWatched] = useState(() => {
    try {
      const cached = JSON.parse(localStorage.getItem(cacheKey))
      return cached?.url === url && Number.isFinite(cached.seconds) ? Math.max(initialWatched, cached.seconds) : initialWatched
    } catch { return initialWatched }
  })
  const accumulated = useRef(startingWatched)
  const [fallback, setFallback] = useState(false)
  const [duration, setDuration] = useState(null)
  const [watched, setWatched] = useState(startingWatched)
  const [status, setStatus] = useState('Tiến độ tự lưu khi xem video.')
  const saved = useEffectEvent((progress) => onSaved?.(progress))
  const report = useEffectEvent((count, complete) => onWatch?.(count, complete))
  const drive = driveVideo(url)
  const source = drive ? `https://drive.google.com/uc?export=download&id=${drive.id}` : externalMediaUrl(url)

  useEffect(() => {
    const video = videoRef.current
    if (!video || !track || !api || fallback) return
    let total = accumulated.current
    let previous = video.currentTime
    let stamp = performance.now()
    let playing = !video.paused && !video.seeking
    let lastSent = -1
    let lastDuration = null
    let pending = Promise.resolve()
    let disposed = false
    const sample = () => {
      const now = performance.now()
      if (playing && !video.seeking) total += playbackDelta(previous, video.currentTime, (now - stamp) / 1000, video.playbackRate)
      previous = video.currentTime
      stamp = now
      accumulated.current = total
      try { localStorage.setItem(cacheKey, JSON.stringify({ url, seconds: total })) } catch { /* Server autosave still works without browser storage. */ }
      if (!disposed) setWatched(total)
    }
    const save = () => {
      sample()
      const seconds = Number.isFinite(video.duration) && video.duration > 0 ? Math.ceil(video.duration) : null
      const count = Math.min(600000, video.ended ? Math.ceil(total) : Math.floor(total))
      if (count === lastSent && seconds === lastDuration) return
      lastSent = count
      lastDuration = seconds
      report(count, !!seconds && count >= seconds)
      const body = { duration_watched: count, completed: false, ...(seconds && seconds <= 600000 ? { duration_seconds: seconds } : {}) }
      pending = pending.catch(() => {}).then(() => api.request(`/subscriptions/${subscriptionId}/lessons/${lessonId}/watch`, { method: 'POST', body, keepalive: true }))
        .then((progress) => { if (!disposed) { setStatus('Đã lưu tiến độ.'); saved(progress) } })
        .catch(() => { lastSent = -1; if (!disposed) setStatus('Chưa lưu được tiến độ. Đang thử lại…') })
    }
    const start = () => { previous = video.currentTime; stamp = performance.now(); playing = true }
    const stop = () => { sample(); playing = false; save() }
    const seek = () => { sample(); playing = false }
    const seeked = () => { previous = video.currentTime; stamp = performance.now(); playing = !video.paused }
    const metadata = () => { if (Number.isFinite(video.duration)) setDuration(video.duration); save() }
    const hide = () => { if (document.visibilityState === 'hidden') save() }
    const events = { playing: start, pause: stop, waiting: stop, ended: stop, seeking: seek, seeked, timeupdate: sample, loadedmetadata: metadata, durationchange: metadata }
    Object.entries(events).forEach(([name, listener]) => video.addEventListener(name, listener))
    document.addEventListener('visibilitychange', hide)
    window.addEventListener('pagehide', save)
    const interval = setInterval(save, 10000)
    return () => {
      disposed = true
      save()
      clearInterval(interval)
      Object.entries(events).forEach(([name, listener]) => video.removeEventListener(name, listener))
      document.removeEventListener('visibilitychange', hide)
      window.removeEventListener('pagehide', save)
    }
  }, [api, subscriptionId, lessonId, cacheKey, url, track, fallback])

  if (!source) return <p role="alert">Đường dẫn video không hợp lệ.</p>
  return <div>
    {!fallback ? <video ref={videoRef} className="lesson-video" src={source} controls autoPlay playsInline preload="metadata" aria-label={title} onLoadedMetadata={(event) => setDuration(event.currentTarget.duration)} onError={() => setFallback(true)} /> : <>
      {drive && <iframe className="lesson-video" src={drive.previewUrl} title={title} allow="autoplay; fullscreen; encrypted-media" allowFullScreen referrerPolicy="no-referrer" sandbox="allow-scripts allow-same-origin allow-forms allow-presentation" />}
      <p role="alert">{drive ? 'Bạn đang xem bản dự phòng. Tiến độ xem ở chế độ này chưa được lưu.' : 'Chưa phát được video. Vui lòng thử lại sau.'}</p>
      <button onClick={() => setFallback(false)}>Thử phát trực tiếp lại</button>
    </>}
    <div className="lesson-playback-info"><span>Thời lượng: <strong>{formatDuration(duration)}</strong></span><span>Đã học: <strong>{formatDuration(watched)}</strong></span></div>
    {track && !fallback && <p className="muted" role="status">{status}</p>}
  </div>
}
