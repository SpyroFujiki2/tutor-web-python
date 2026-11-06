import { useRef, useState } from 'react'
import Icon from './Icon.jsx'
import SiteLink from './SiteLink.jsx'

export default function AuthPage({ mode, expired, next, onAuthenticate }) {
  const register = mode === 'register'
  const [visible, setVisible] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const lock = useRef(false)
  const alternate = `${register ? '/login' : '/register'}${next ? `?${new URLSearchParams({ next })}` : ''}`
  async function submit(event) {
    event.preventDefault()
    if (lock.current) return
    const values = new FormData(event.currentTarget)
    if (register && values.get('password') !== values.get('confirm_password')) {
      setError('Mật khẩu xác nhận chưa khớp. Vui lòng kiểm tra lại.')
      return
    }
    lock.current = true
    setBusy(true); setError('')
    try { await onAuthenticate({ email: values.get('email').trim(), password: values.get('password') }, register) }
    catch (error) { setError(error.message) }
    finally { lock.current = false; setBusy(false) }
  }
  return <section className="auth-page">
    <aside className="auth-story"><span className="story-tag"><Icon name="spark" size={16} />KHỞI ĐẦU TỪ SỰ TÒ MÒ</span><h2>Một tài khoản.<br />Nhiều cơ hội<br /><span>để tiến xa.</span></h2><p>Khóa học bạn yêu thích, người hướng dẫn phù hợp và một cộng đồng cùng tiến bộ.</p><div className="auth-story-art" aria-hidden="true"><div className="story-orbit" /><div className="story-book"><Icon name="book" size={74} /><span>YOUR NEXT CHAPTER</span></div><span className="story-spark spark-one">✦</span><span className="story-spark spark-two">✦</span></div><ul className="auth-benefits"><li><Icon name="check" size={17} />Học theo nhịp của riêng bạn</li><li><Icon name="check" size={17} />Theo dõi việc học trong một không gian</li><li><Icon name="check" size={17} />Kết nối và trao đổi cùng gia sư</li></ul></aside>
    <div className="auth-form-panel"><SiteLink href="/" className="back-link"><Icon name="back" size={17} />Về trang chủ</SiteLink><div className="auth-form-content"><div className="auth-form-icon"><Icon name={register ? 'cap' : 'book'} size={27} /></div><p className="eyebrow">KHÔNG GIAN HỌC TẬP CỦA BẠN</p><h1>{register ? 'Bắt đầu hành trình.' : 'Chào mừng trở lại.'}</h1><p className="auth-description">{register ? 'Tạo tài khoản để khám phá và lưu giữ từng bước tiến.' : 'Đăng nhập để tiếp tục những điều bạn đang khám phá.'}</p>
      {expired && !register && <p className="notice error" role="alert"><Icon name="alert" size={18} />Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.</p>}
      <form className="form auth-form" onSubmit={submit}><fieldset disabled={busy}>
        <label htmlFor="auth-email">Địa chỉ email<div className="input-with-icon"><Icon name="mail" size={18} /><input id="auth-email" name="email" type="email" autoComplete="email" placeholder="ban@example.com" required maxLength={320} /></div></label>
        <label htmlFor="auth-password">Mật khẩu<div className="input-with-icon"><Icon name="lock" size={18} /><input id="auth-password" name="password" type={visible ? 'text' : 'password'} autoComplete={register ? 'new-password' : 'current-password'} placeholder={register ? 'Ít nhất 8 ký tự' : 'Nhập mật khẩu của bạn'} required minLength={register ? 8 : 1} maxLength={1024} /><button type="button" className="password-toggle icon-button" aria-label={visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'} aria-pressed={visible} onClick={() => setVisible(!visible)}><Icon name={visible ? 'eyeOff' : 'eye'} size={18} /></button></div></label>
        {register && <label htmlFor="auth-confirm-password">Xác nhận mật khẩu<div className="input-with-icon"><Icon name="lock" size={18} /><input id="auth-confirm-password" name="confirm_password" type={visible ? 'text' : 'password'} autoComplete="new-password" placeholder="Nhập lại mật khẩu" required minLength={8} maxLength={1024} /></div></label>}
        {error && <p className="notice error" role="alert"><Icon name="alert" size={18} />{error}</p>}
        <button className="primary auth-submit" type="submit">{busy ? <><span className="spinner" />Đang xử lý…</> : <>{register ? 'Tạo tài khoản' : 'Đăng nhập'}<Icon name="arrow" size={18} /></>}</button>
      </fieldset></form><p className="auth-switch">{register ? 'Bạn đã có tài khoản?' : 'Chưa có tài khoản?'} <SiteLink href={alternate}>{register ? 'Đăng nhập' : 'Đăng ký ngay'}</SiteLink></p><div className="auth-reassurance"><Icon name="shield" size={16} /><span>Tài khoản riêng cho hành trình học tập của bạn.</span></div>
    </div></div>
  </section>
}
