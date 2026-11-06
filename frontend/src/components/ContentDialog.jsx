import { useEffect, useId, useRef } from 'react'
import Icon from './Icon.jsx'

export default function ContentDialog({ title, onClose, children, className = '' }) {
  const ref = useRef(null)
  const titleId = useId()
  useEffect(() => {
    const dialog = ref.current
    const previousOverflow = document.body.style.overflow
    dialog.showModal()
    document.body.style.overflow = 'hidden'
    return () => { dialog.close(); document.body.style.overflow = previousOverflow }
  }, [])
  return <dialog ref={ref} className={`content-dialog ${className}`} aria-labelledby={titleId} onCancel={(event) => { event.preventDefault(); onClose() }} onClick={(event) => {
    if (event.target !== event.currentTarget) return
    const rect = event.currentTarget.getBoundingClientRect()
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) onClose()
  }}><div className="dialog-heading"><span className="eyebrow" id={titleId}>{title}</span><button type="button" className="icon-button" aria-label="Đóng chi tiết" onClick={onClose}><Icon name="close" /></button></div>{children}</dialog>
}

