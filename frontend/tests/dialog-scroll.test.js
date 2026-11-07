import assert from 'node:assert/strict'
import { test } from 'node:test'
import { lockPageScroll } from '../src/services/dialog-scroll.js'

test('closing nested popups in either order restores the original page scroll', () => {
  for (const order of [[0, 1], [1, 0]]) {
    const body = { style: { overflow: 'auto' } }
    const release = [lockPageScroll(body), lockPageScroll(body)]
    release[order[0]]()
    assert.equal(body.style.overflow, 'hidden')
    release[order[1]]()
    assert.equal(body.style.overflow, 'auto')
  }
})

test('cleanup can repeat and new popups can open while another one is closing', () => {
  const body = { style: { overflow: '' } }
  const first = lockPageScroll(body)
  const second = lockPageScroll(body)
  first()
  first()
  const third = lockPageScroll(body)
  second()
  assert.equal(body.style.overflow, 'hidden')
  third()
  assert.equal(body.style.overflow, '')
  const reopened = lockPageScroll(body)
  reopened()
  assert.equal(body.style.overflow, '')
})

test('independent documents keep their own original scroll styles', () => {
  const firstBody = { style: { overflow: 'scroll' } }
  const secondBody = { style: { overflow: 'hidden' } }
  const first = lockPageScroll(firstBody)
  const second = lockPageScroll(secondBody)
  first()
  assert.equal(firstBody.style.overflow, 'scroll')
  assert.equal(secondBody.style.overflow, 'hidden')
  second()
  assert.equal(secondBody.style.overflow, 'hidden')
})
