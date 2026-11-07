export function driveVideo(url) {
  try {
    const parsed = new URL(url)
    if (parsed.protocol !== 'https:' || parsed.hostname !== 'drive.google.com' || parsed.username || parsed.password) return null
    const match = parsed.pathname.match(/^\/file\/d\/([A-Za-z0-9_-]{10,200})(?:\/|$)/)
    const id = match?.[1] ?? (['/open', '/uc'].includes(parsed.pathname) ? parsed.searchParams.get('id') : null)
    if (!id || !/^[A-Za-z0-9_-]{10,200}$/.test(id)) return null
    return { id, previewUrl: `https://drive.google.com/file/d/${id}/preview`, viewUrl: `https://drive.google.com/file/d/${id}/view` }
  } catch { return null }
}

export function externalMediaUrl(url) {
  try {
    const parsed = new URL(url)
    return ['http:', 'https:'].includes(parsed.protocol) && !parsed.username && !parsed.password ? parsed.href : null
  } catch { return null }
}

export function youtubeVideo(url) {
  try {
    if (typeof url !== 'string') return null
    let value = url.trim()
    if (/^(?:(?:www|m|music)\.)?(?:youtube\.com|youtu\.be)\//i.test(value)) value = `https://${value}`
    const parsed = new URL(value)
    if (!['https:', 'http:'].includes(parsed.protocol) || parsed.username || parsed.password || parsed.port) return null
    const hosts = ['youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtube-nocookie.com', 'www.youtube-nocookie.com']
    const short = ['youtu.be', 'www.youtu.be'].includes(parsed.hostname)
    if (!short && !hosts.includes(parsed.hostname)) return null
    const parts = parsed.pathname.split('/').filter(Boolean)
    const id = short ? parts[0] : parts[0] === 'watch' ? parsed.searchParams.get('v') : ['embed', 'shorts', 'live', 'v'].includes(parts[0]) ? parts[1] : null
    if (!/^[A-Za-z0-9_-]{11}$/.test(id ?? '')) return null
    const rawStart = parsed.searchParams.get('start') ?? parsed.searchParams.get('t') ?? new URLSearchParams(parsed.hash.slice(1)).get('t') ?? ''
    const match = rawStart.match(/^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/)
    const seconds = /^\d+$/.test(rawStart) ? Number(rawStart) : match ? Number(match[1] ?? 0) * 3600 + Number(match[2] ?? 0) * 60 + Number(match[3] ?? 0) : 0
    return { id, watchUrl: `https://www.youtube.com/watch?v=${id}`, embedUrl: `https://www.youtube.com/embed/${id}`, startSeconds: Math.min(600000, seconds) }
  } catch { return null }
}

export function youtubeEmbedUrl(video, origin) {
  const url = new URL(video.embedUrl)
  for (const [key, value] of Object.entries({ enablejsapi: 1, playsinline: 1, rel: 0, hl: 'vi', autoplay: 1 })) url.searchParams.set(key, value)
  if (video.startSeconds) url.searchParams.set('start', video.startSeconds)
  try {
    const site = new URL(origin)
    if (['http:', 'https:'].includes(site.protocol) && !site.username && !site.password) url.searchParams.set('origin', site.origin)
  } catch { /* The server-rendered fallback does not have a browser origin. */ }
  return url.href
}
