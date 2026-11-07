import { useState } from 'react'
import ContentDialog from './ContentDialog.jsx'
import { driveVideo, externalMediaUrl } from '../services/media.js'

export default function ExternalContent({ url, title = 'Xem nội dung', className = 'button', meeting = false }) {
  const [open, setOpen] = useState(false)
  const safeUrl = externalMediaUrl(url)
  if (!safeUrl) return null
  return <><button className={className} onClick={() => setOpen(true)}>{title}</button>{open && <ContentDialog title={title} onClose={() => setOpen(false)} className="document-dialog">
    <iframe className="document-preview" src={driveVideo(safeUrl)?.previewUrl ?? safeUrl} title={title} sandbox="allow-scripts allow-same-origin allow-forms allow-presentation" allow={meeting ? 'camera; microphone; fullscreen; display-capture; autoplay' : 'fullscreen'} />
    <p className="muted">Không xem được nội dung? Mở liên kết bên dưới để tiếp tục.</p>
    <a className="button" href={safeUrl} target="_blank" rel="noopener noreferrer">Mở trên trang nhà cung cấp ↗</a>
  </ContentDialog>}</>
}
