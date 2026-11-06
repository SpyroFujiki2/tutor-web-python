import assert from 'node:assert/strict'
import { test } from 'node:test'
import { driveVideo, externalMediaUrl } from '../src/services/media.js'

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
