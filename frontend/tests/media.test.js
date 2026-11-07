import assert from 'node:assert/strict'
import { test } from 'node:test'
import { driveVideo, externalMediaUrl, youtubeVideo, youtubeEmbedUrl } from '../src/services/media.js'

test('Drive view/open/preview links use a canonical Google preview URL', () => {
  const id = 'example_video_123456789'
  for (const link of [`https://drive.google.com/file/d/${id}/view?usp=sharing`, `https://drive.google.com/file/d/${id}/preview`, `https://drive.google.com/open?id=${id}`]) {
    assert.equal(driveVideo(link).previewUrl, `https://drive.google.com/file/d/${id}/preview`)
  }
})

test('folders, lookalike domains and executable URLs cannot become video iframes', () => {
  for (const link of ['https://drive.google.com/drive/folders/example_video_123456789', 'https://drive.google.com.evil.example/file/d/example_video_123456789/view', 'javascript:alert(1)', 'https://evil@drive.google.com/file/d/example_video_123456789/view', null]) {
    assert.equal(driveVideo(link), null)
  }
})

test('external lesson links allow only HTTP(S) URLs without credentials', () => {
  assert.equal(externalMediaUrl('https://example.com/lesson'), 'https://example.com/lesson')
  assert.equal(externalMediaUrl('javascript:alert(1)'), null)
  assert.equal(externalMediaUrl('https://user:secret@example.com/lesson'), null)
})

test('YouTube watch, shared, mobile, Shorts, live and embed URLs select the inline player', () => {
  const id = 'VhZoXUOgHqI'
  for (const url of [
    `https://www.youtube.com/watch?v=${id}&list=playlist`, `https://youtu.be/${id}?si=share`,
    `https://m.youtube.com/watch?v=${id}`, `https://www.youtube.com/shorts/${id}`,
    `https://www.youtube.com/live/${id}`, `https://www.youtube.com/embed/${id}`,
    `https://www.youtube-nocookie.com/embed/${id}`, `youtube.com/watch?v=${id}`,
  ]) {
    assert.equal(youtubeVideo(url).id, id)
    assert.equal(youtubeVideo(url).embedUrl, `https://www.youtube.com/embed/${id}`)
  }
  for (const id of ['EEl9OubU7qY', '2x2f2AQy0gY']) assert.equal(youtubeVideo(`https://www.youtube.com/watch?v=${id}`).id, id)
})

test('YouTube embeds preserve timestamps and identify the correct website origin', () => {
  const video = youtubeVideo('https://youtu.be/VhZoXUOgHqI?t=1m30s')
  const url = new URL(youtubeEmbedUrl(video, 'http://127.0.0.1:5173'))
  assert.equal(url.searchParams.get('start'), '90')
  assert.equal(url.searchParams.get('origin'), 'http://127.0.0.1:5173')
  assert.equal(url.searchParams.get('enablejsapi'), '1')
  assert.equal(url.searchParams.get('playsinline'), '1')
  assert.equal(youtubeVideo('https://www.youtube.com/watch?v=VhZoXUOgHqI#t=45').startSeconds, 45)
  assert.equal(new URL(youtubeEmbedUrl(video, 'javascript:alert(1)')).searchParams.has('origin'), false)
})

test('invalid IDs, playlists, impersonation domains and executable links cannot become YouTube embeds', () => {
  for (const url of [null, 'javascript:alert(1)', 'https://youtube.com.evil.test/watch?v=VhZoXUOgHqI',
    'https://user:secret@youtube.com/watch?v=VhZoXUOgHqI', 'https://youtube.com:444/watch?v=VhZoXUOgHqI',
    'https://youtube.com/playlist?list=VhZoXUOgHqI', 'https://youtu.be/short', 'https://youtube.com/watch?v=<script>']) {
    assert.equal(youtubeVideo(url), null)
  }
})
