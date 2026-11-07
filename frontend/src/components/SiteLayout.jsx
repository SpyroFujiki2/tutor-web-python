import { useState } from 'react'
import { Action, Badge } from './Workspace.jsx'
import { isAdmin } from './workspace-utils.js'
import Icon from './Icon.jsx'
import SiteLink from './SiteLink.jsx'
import Dropdown from './Dropdown.jsx'
import { adminGroups, adminHref } from '../admin-navigation.js'

const publicLinks = [['/', 'Trang chủ'], ['/courses', 'Khóa học'], ['/tutoring', 'Gia sư'], ['/community', 'Cộng đồng']]
const workspaceLinks = [['/learning', 'book', 'Việc học'], ['/tutoring', 'calendar', 'Gia sư & lịch học'], ['/wallet', 'wallet', 'Ví & thanh toán'], ['/disputes', 'shield', 'Tranh chấp'], ['/account', 'settings', 'Tài khoản']]

export function Brand() {
  return <SiteLink href="/" className="brand" aria-label="Tutor Web — Trang chủ"><span className="brand-icon"><Icon name="cap" size={26} /></span><span>Tutor<span className="brand-accent">Web</span><small>HỌC HÔM NAY. TIẾN XA NGÀY MAI.</small></span></SiteLink>
}

export function Header({ user, pathname, theme, onThemeChange, onLogout }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const initial = (user?.email ?? 'T').charAt(0).toUpperCase()
  return <header className="site-header"><div className="header-inner container">
    <Brand />
    <nav className="desktop-nav" aria-label="Điều hướng chính">{publicLinks.map(([href, label]) => <SiteLink href={href} key={href} aria-current={pathname === href ? 'page' : undefined}>{label}</SiteLink>)}{isAdmin(user) && <Dropdown label="Quản trị" icon="grid" active={pathname === '/admin'} className="header-admin" align="right"><div className="admin-mega-menu">{adminGroups.map((group) => <div className="menu-group" key={group.id}><p><Icon name={group.icon} size={15} />{group.label}</p>{group.items.map((item) => <SiteLink href={adminHref(item.id)} key={item.id}>{item.label}<Icon name="arrow" size={13} /></SiteLink>)}</div>)}</div></Dropdown>}</nav>
    <div className="header-actions">
      <button type="button" className="icon-button theme-toggle" onClick={onThemeChange} aria-label={theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'} title={theme === 'dark' ? 'Giao diện sáng' : 'Giao diện tối'}><Icon name={theme === 'dark' ? 'sun' : 'moon'} /></button>
      {user ? <Dropdown className="account-dropdown" align="right" label={<><span className="avatar">{initial}</span><span className="account-name">{user.email?.split('@')[0]}</span><span className="sr-only">Menu tài khoản</span></>}><div className="dropdown-user"><span className="dropdown-caption">ĐANG ĐĂNG NHẬP</span><strong>{user.email}</strong><Badge value={user.role} /></div>
        {workspaceLinks.map(([href, icon, label]) => <SiteLink key={href} href={href}><Icon name={icon} size={17} />{label}</SiteLink>)}
        {isAdmin(user) && <SiteLink href="/admin"><Icon name="shield" size={17} />Quản trị</SiteLink>}
        <Action className="logout-button" onClick={onLogout}><Icon name="logout" size={17} />Đăng xuất</Action>
      </Dropdown> : <div className="auth-actions"><SiteLink href="/login" className="login-link" aria-current={pathname === '/login' ? 'page' : undefined}>Đăng nhập</SiteLink><SiteLink href="/register" className="button primary button-sm">Bắt đầu học<Icon name="arrow" size={16} /></SiteLink></div>}
      <button type="button" className="icon-button mobile-menu-toggle" aria-expanded={menuOpen} aria-controls="mobile-navigation" aria-label={menuOpen ? 'Đóng menu điều hướng' : 'Mở menu điều hướng'} onClick={() => setMenuOpen(!menuOpen)}><Icon name={menuOpen ? 'close' : 'menu'} /></button>
    </div>
  </div>{menuOpen && <nav id="mobile-navigation" className="mobile-nav container" aria-label="Điều hướng trên điện thoại">{publicLinks.map(([href, label]) => <SiteLink key={href} href={href} aria-current={pathname === href ? 'page' : undefined} onClick={() => setMenuOpen(false)}>{label}<Icon name="arrow" size={16} /></SiteLink>)}{!user && <><SiteLink href="/login">Đăng nhập</SiteLink><SiteLink href="/register">Tạo tài khoản</SiteLink></>}</nav>}</header>
}

export function WorkspaceNav({ user, pathname, adminSection }) {
  return <aside className="workspace-nav"><nav className="container workspace-nav-inner" aria-label="Không gian cá nhân"><span className="workspace-label">KHÔNG GIAN CỦA BẠN</span>{workspaceLinks.map(([href, icon, label]) => <SiteLink key={href} href={href} aria-current={pathname === href ? 'page' : undefined}><Icon name={icon} size={17} />{label}</SiteLink>)}{isAdmin(user) && <SiteLink href="/admin" aria-current={pathname === '/admin' ? 'page' : undefined}><Icon name="shield" size={17} />Quản trị</SiteLink>}</nav>{isAdmin(user) && pathname === '/admin' && <AdminNavigation selected={adminSection} />}</aside>
}

export function AdminNavigation({ selected }) {
  return <nav className="admin-sidebar" aria-label="Danh mục quản trị">{adminGroups.map((group) => <details key={`${group.id}-${selected}`} open={group.items.some((item) => item.id === selected)}><summary><Icon name={group.icon} size={16} />{group.label}</summary>{group.items.map((item) => <SiteLink href={adminHref(item.id)} key={item.id} aria-current={selected === item.id ? 'page' : undefined}><Icon name={item.icon} size={16} />{item.label}</SiteLink>)}</details>)}</nav>
}

export function Footer() {
  return <footer className="site-footer"><div className="container footer-top"><div><Brand /><p>Mỗi ngày một điều mới.<br />Mỗi bước tiến một tương lai.</p></div><nav aria-label="Liên kết cuối trang"><SiteLink href="/courses">Khám phá khóa học</SiteLink><SiteLink href="/tutoring">Tìm gia sư đồng hành</SiteLink><SiteLink href="/community">Kết nối cộng đồng</SiteLink></nav><div className="footer-note"><span className="online-dot" />Sẵn sàng cho bước tiến của bạn.<small>Học hôm nay, mở ngày mai.</small></div></div><div className="container footer-bottom"><span>© {new Date().getFullYear()} Tutor Web</span><span>Được xây dựng cho những người luôn muốn học hỏi.<Icon name="spark" size={14} /></span></div></footer>
}
