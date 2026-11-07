import { useEffect, useEffectEvent, useRef, useState } from 'react'
import { youtubeEmbedUrl } from '../services/media.js'
import { loadYouTubeApi, youtubeErrorMessage } from '../services/youtube-api.js'
import { createLessonWatch } from '../services/lesson-watch.js'
import { formatDuration } from '../services/watch-time.js'

export default function YouTubeLessonMedia({ video, url, title, api, subscriptionId, lessonId, initialWatched = 0, track = false, onSaved, onWatch }) {
  const host = useRef(null)
  const [startingWatched] = useState(initialWatched)
  const [attempt, setAttempt] = useState(0)
  const [snapshot, setSnapshot] = useState({ duration: null, watched: initialWatched })
  const [status, setStatus] = useState('Tiến độ tự lưu khi xem video.')
  const [error, setError] = useState('')
  const notifySaved = useEffectEvent((progress) => onSaved?.(progress))
  const notifyWatch = useEffectEvent((count, complete, duration) => onWatch?.(count, complete, duration))
  const { id, embedUrl, startSeconds } = video

  useEffect(() => {
    const container = host.current
    if (!container) return
    let disposed = false
    let player = null
    let ready = false
    let storage
    try { storage = localStorage } catch { /* Autosave works without browser storage. */ }
    const recorder = createLessonWatch({
      api, path: `/subscriptions/${subscriptionId}/lessons/${lessonId}/watch`, enabled: track,
      cacheKey: `lesson-watch:${subscriptionId}:${lessonId}`, url, initialWatched: startingWatched, storage,
      onChange: (value) => { if (!disposed) setSnapshot(value) },
      onStatus: (value) => { if (!disposed) setStatus(value) },
      onSaved: (progress) => { if (!disposed) notifySaved(progress) },
      onWatch: (count, complete, duration) => { if (!disposed) notifyWatch(count, complete, duration) },
    })
    // YouTube owns this subtree, so destroying a player is safe in StrictMode.
    const frame = document.createElement('iframe')
    frame.src = youtubeEmbedUrl({ embedUrl, startSeconds }, window.location.origin)
    frame.title = title
    frame.className = 'youtube-iframe'
    frame.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen'
    frame.allowFullscreen = true
    frame.referrerPolicy = 'strict-origin-when-cross-origin'
    container.replaceChildren(frame)
    function sample(state) {
      if (!ready || !player) return
      const currentState = state ?? player.getPlayerState()
      recorder.observe({ currentTime: player.getCurrentTime(), duration: player.getDuration(),
        playbackRate: player.getPlaybackRate(), playing: currentState === 1, ended: currentState === 0 })
    }
    function save() { sample(); recorder.save() }
    loadYouTubeApi().then((YT) => {
      if (disposed) return
      player = new YT.Player(frame, { events: {
        onReady(event) {
          if (disposed) return
          player = event.target
          ready = true
          setError('')
          sample()
          recorder.save()
          player.playVideo()
        },
        onStateChange(event) {
          if (disposed) return
          if (event.data === 1) setError('')
          sample(event.data)
          if (event.data !== 1) recorder.save()
        },
        onPlaybackRateChange() { if (!disposed) sample() },
        onAutoplayBlocked() { if (!disposed) setStatus('Nhấn Phát trên video để bắt đầu bài học.') },
        onError(event) { if (!disposed) { sample(2); recorder.save(); setError(youtubeErrorMessage(event.data)) } },
      } })
    }).catch(() => { if (!disposed) setError('Chưa kết nối được trình phát để lưu tiến độ. Vui lòng thử lại.') })
    const sampleTimer = setInterval(() => sample(), 500)
    const saveTimer = setInterval(save, 10000)
    const hide = () => { if (document.visibilityState === 'hidden') save() }
    document.addEventListener('visibilitychange', hide)
    window.addEventListener('pagehide', save)
    return () => {
      disposed = true
      sample()
      recorder.save()
      clearInterval(sampleTimer)
      clearInterval(saveTimer)
      document.removeEventListener('visibilitychange', hide)
      window.removeEventListener('pagehide', save)
      try { player?.destroy() } catch { /* The provider may already have removed the frame. */ }
      container.replaceChildren()
    }
  }, [api, subscriptionId, lessonId, startingWatched, track, url, id, embedUrl, startSeconds, title, attempt])

  return <div>
    <div className="youtube-player" ref={host} data-youtube-video-id={id} aria-label={title} />
    {error && <div role="alert" className="notice error"><p>{error}</p><div className="actions"><button onClick={() => { setError(''); setAttempt((value) => value + 1) }}>Thử lại</button><a className="button" href={video.watchUrl} target="_blank" rel="noopener noreferrer">Xem trên YouTube</a></div></div>}
    <div className="lesson-playback-info"><span>Thời lượng: <strong>{formatDuration(snapshot.duration)}</strong></span>{track && <span>Đã học: <strong>{formatDuration(snapshot.watched)}</strong></span>}</div>
    {track && !error && <p className="muted" role="status">{status}</p>}
  </div>
}
