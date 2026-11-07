const locks = new WeakMap()

// Multiple dialogs can unmount together, in either cleanup order.
export function lockPageScroll(body) {
  let lock = locks.get(body)
  if (!lock) {
    lock = { count: 0, overflow: body.style.overflow }
    locks.set(body, lock)
    body.style.overflow = 'hidden'
  }
  lock.count += 1
  let released = false
  return () => {
    if (released) return
    released = true
    lock.count -= 1
    if (lock.count === 0) {
      body.style.overflow = lock.overflow
      locks.delete(body)
    }
  }
}
