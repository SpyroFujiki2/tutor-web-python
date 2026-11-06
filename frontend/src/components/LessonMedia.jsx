import { driveVideo, externalMediaUrl } from '../services/media.js'

export default function LessonMedia({ url, title }) {
  const drive = driveVideo(url)
  if (drive) return <div><iframe className="lesson-video" src={drive.previewUrl} title={title}
    allow="autoplay; fullscreen; encrypted-media" allowFullScreen referrerPolicy="no-referrer"
    sandbox="allow-scripts allow-same-origin allow-forms allow-presentation allow-popups" />
    <p className="muted">Nếu video chưa phát, hãy mở trên Drive và đăng nhập tài khoản có quyền xem.</p>
    <a className="button" href={drive.viewUrl} target="_blank" rel="noreferrer">Mở video trên Google Drive ↗</a></div>
  const external = externalMediaUrl(url)
  return external ? <a className="button" href={external} target="_blank" rel="noreferrer">Mở nội dung bài học ↗</a> : null
}
