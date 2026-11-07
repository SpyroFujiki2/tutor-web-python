import assert from 'node:assert/strict'
import { test } from 'node:test'
import { adminGroups, adminHref, adminSections, resolveAdminSection } from '../src/admin-navigation.js'
import { resolveRoute, returnDestination } from '../src/navigation.js'

test('all fourteen admin destinations remain reachable through grouped menus', () => {
  assert.equal(adminGroups.length, 5)
  assert.equal(new Set(adminSections.map((section) => section.id)).size, 14)
  for (const section of adminSections) {
    const href = adminHref(section.id)
    assert.equal(resolveRoute(href).page, 'admin')
    assert.equal(resolveAdminSection(href).id, section.id)
    assert.equal(returnDestination(`?${new URLSearchParams({ next: href })}`), href)
  }
})

test('unknown admin selections use a valid default and external login redirects are rejected', () => {
  assert.equal(resolveAdminSection('/admin?section=unknown').id, 'courses')
  assert.equal(resolveAdminSection('/admin').id, 'courses')
  for (const next of ['https://example.com', '//example.com', '/login', '/payment/vnpay-return', '/admin\\external']) {
    assert.equal(returnDestination(`?${new URLSearchParams({ next })}`), '/learning')
  }
})
