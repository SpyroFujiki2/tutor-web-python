// Count playback, not the furthest seek position. Wall time limits seek jumps.
export function playbackDelta(previous, current, elapsed, rate = 1) {
  const delta = current - previous
  if (delta <= 0 || elapsed <= 0 || delta > elapsed * rate + 1) return 0
  return Math.min(delta, elapsed * rate)
}

export function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return '—'
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`
}
