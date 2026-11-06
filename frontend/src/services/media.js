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
