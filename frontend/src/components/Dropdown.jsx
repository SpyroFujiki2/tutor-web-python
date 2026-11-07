import { useEffect, useId, useRef } from 'react'
import Icon from './Icon.jsx'

export default function Dropdown({ label, icon, active = false, children, className = '', align = 'left' }) {
  const ref = useRef(null)
  const id = useId()
  useEffect(() => {
    const closeOutside = (event) => { if (ref.current && !ref.current.contains(event.target)) ref.current.open = false }
    const escape = (event) => {
      if (event.key === 'Escape' && ref.current?.open) {
        ref.current.open = false
        ref.current.querySelector('summary')?.focus()
      }
    }
    document.addEventListener('pointerdown', closeOutside)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', closeOutside)
      document.removeEventListener('keydown', escape)
    }
  }, [])
  return <details ref={ref} className={`nav-dropdown ${active ? 'is-active' : ''} ${className}`} onToggle={(event) => {
    if (!event.currentTarget.open) return
    document.querySelectorAll('details.nav-dropdown[open]').forEach((element) => { if (element !== ref.current) element.open = false })
  }}><summary aria-controls={id}>{icon && <Icon name={icon} size={18} />}{label}<Icon name="chevron" size={14} className="dropdown-chevron" /></summary>
    <div className={`dropdown-panel dropdown-${align}`} id={id} onClick={(event) => {
      if (ref.current && event.target.closest('a, button')) ref.current.open = false
    }}>{children}</div>
  </details>
}
