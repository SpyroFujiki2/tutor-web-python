import { useEffect, useId, useRef } from 'react'
import Icon from './Icon.jsx'
import { lockPageScroll } from '../services/dialog-scroll.js'

export default function ContentDialog({ title, onClose, children, className = '' }) {
  const ref = useRef(null)
  const titleId = useId()
  useEffect(() => {
    const dialog = ref.current
    dialog.showModal()
    const unlock = lockPageScroll(document.body)
    return () => { dialog.close(); unlock() }
  }, [])
  return <dialog ref={ref} className={`content-dialog ${className}`} aria-labelledby={titleId} onCancel={(event) => { event.preventDefault(); onClose() }} onClick={(event) => {
    if (event.target !== event.currentTarget) return
    const rect = event.currentTarget.getBoundingClientRect()
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) onClose()
  }}><div className="dialog-heading"><span className="eyebrow" id={titleId}>{title}</span><button type="button" className="icon-button" aria-label="Đóng chi tiết" onClick={onClose}><Icon name="close" /></button></div>{children}</dialog>
}

