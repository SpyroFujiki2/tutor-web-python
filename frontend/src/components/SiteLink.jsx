import { navigate } from '../navigation.js'

export default function SiteLink({ href, children, onClick, ...props }) {
  return <a href={href} {...props} onClick={(event) => {
    onClick?.(event)
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || props.target) return
    event.preventDefault()
    navigate(href)
  }}>{children}</a>
}
