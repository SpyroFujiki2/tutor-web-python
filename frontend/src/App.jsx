import { useEffect, useMemo, useState } from 'react'
import { createApiClient } from './services/api.js'
import { API_BASE_URL } from './config.js'
import { loginDestination, navigate, resolveRoute, returnDestination, useLocation } from './navigation.js'
import { isAdmin } from './components/workspace-utils.js'
import { Header, Footer, WorkspaceNav } from './components/SiteLayout.jsx'
import Home from './components/Home.jsx'
import AuthPage from './components/AuthPage.jsx'
import Icon from './components/Icon.jsx'
import SiteLink from './components/SiteLink.jsx'
import { Catalog, MyLearning } from './components/Learning.jsx'
import { Disputes, Tutoring } from './components/Tutoring.jsx'
import Wallet from './components/Wallet.jsx'
import Community from './components/Community.jsx'
import Account from './components/Account.jsx'
import Admin from './components/Admin.jsx'
import PaymentReturn from './components/PaymentReturn.jsx'
import './App.css'

function App() {
  const [user, setUser] = useState(null)
  const [expired, setExpired] = useState(false)
  const [sessionStatus, setSessionStatus] = useState('loading')
  const [sessionError, setSessionError] = useState('')
  const [sessionRevision, setSessionRevision] = useState(0)
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light')
  const location = useLocation()
  const route = resolveRoute(location)
  const pathname = location.split('?')[0]
  const search = location.includes('?') ? location.slice(location.indexOf('?')) : ''
  const payment = route.page === 'payment' || new URLSearchParams(search).has('vnp_TxnRef')
  const needsLogin = sessionStatus === 'ready' && route.protected && !user && !payment
  const api = useMemo(() => createApiClient(API_BASE_URL, { onUnauthorized: () => {
    setUser(null); setExpired(true); setSessionStatus('ready')
    if (resolveRoute(window.location.pathname).protected) {
      navigate(loginDestination(`${window.location.pathname}${window.location.search}`), { replace: true })
    }
  } }), [])

  useEffect(() => api.subscribeSession(() => {
    setUser(null); setSessionStatus('loading'); setSessionError('')
    setSessionRevision((value) => value + 1)
  }), [api])

  useEffect(() => {
    const controller = new AbortController()
    const restore = api.hasSession() ? api.request('/auth/me', { signal: controller.signal }) : Promise.resolve(null)
    restore.then((current) => {
      if (!controller.signal.aborted) { setUser(current); setSessionStatus('ready'); setSessionError('') }
    }).catch((error) => {
      if (controller.signal.aborted) return
      if ([401, 403].includes(error.status)) {
        setUser(null); setSessionStatus('ready')
      } else {
        setSessionError(error.message); setSessionStatus('error')
      }
    })
    return () => controller.abort()
  }, [api, sessionRevision])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
    try { localStorage.setItem('tutor-web-theme', theme) } catch { /* Storage may be disabled. */ }
  }, [theme])

  useEffect(() => {
    document.title = `${route.title} · Tutor Web`
    if (needsLogin) navigate(loginDestination(location), { replace: true })
    else if (sessionStatus === 'ready' && user && route.auth) navigate(returnDestination(search), { replace: true })
  }, [location, needsLogin, route.auth, route.title, search, sessionStatus, user])

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' })
    if (!needsLogin && !route.auth) document.getElementById('main-content')?.focus({ preventScroll: true })
  }, [location, needsLogin, route.auth])

  function clearSession() {
    api.setTokens(null); setUser(null); setExpired(false); setSessionStatus('ready'); setSessionError(''); navigate('/login')
  }
  async function authenticate(values, register) {
    if (register) await api.request('/auth/register', { method: 'POST', body: values })
    const tokens = await api.request('/auth/login', { method: 'POST', body: values })
    api.setTokens(tokens)
    try {
      const current = await api.request('/auth/me')
      setUser(current); setExpired(false); setSessionStatus('ready')
      navigate(returnDestination(search), { replace: true })
    } catch (error) {
      if ([401, 403].includes(error.status)) api.setTokens(null)
      else { setSessionError(error.message); setSessionStatus('error') }
      throw error
    }
  }
  const onLogin = (next = '/courses') => navigate(loginDestination(next))
  const onPurchased = () => navigate('/learning')

  return <div className="app-shell"><a className="skip-link" href="#main-content">Đến nội dung chính</a>
    <Header key={location} user={user} pathname={pathname} theme={theme} onThemeChange={() => setTheme(theme === 'light' ? 'dark' : 'light')} onLogout={async () => { try { await api.request('/auth/logout', { method: 'POST' }) } finally { clearSession() } }} />
    {user && !payment && <WorkspaceNav user={user} pathname={pathname} />}
    <main id="main-content" tabIndex={-1} className={`container main-content ${route.auth ? 'auth-main' : ''} ${route.page === 'home' ? 'home-main' : ''}`} key={user?.id ?? 'public'}>
      {sessionStatus === 'loading' ? <div className="session-screen" role="status"><span className="session-emblem"><Icon name="cap" size={32} /></span><span className="spinner" /><h1>Đang mở không gian của bạn</h1><p>Khôi phục phiên đăng nhập…</p></div> : sessionStatus === 'error' ? <div className="session-screen"><span className="session-emblem"><Icon name="alert" size={30} /></span><h1>Chưa kết nối được tài khoản</h1><p role="alert">{sessionError}</p><p>Phiên của bạn vẫn được lưu. Hãy thử lại khi kết nối ổn định.</p><div className="actions"><button className="primary" onClick={() => { setSessionStatus('loading'); setSessionRevision((value) => value + 1) }}>Kết nối lại</button><button onClick={clearSession}>Đăng nhập lại</button></div></div> : payment ? <PaymentReturn api={api} user={user} /> : needsLogin ? <div className="route-loading" role="status"><span className="spinner" />Đang mở trang đăng nhập…</div> : <>
        {route.page === 'home' && <Home api={api} user={user} onLogin={() => onLogin('/courses')} onPurchased={onPurchased} />}
        {route.auth && !user && <AuthPage key={route.page} mode={route.page} expired={expired} next={new URLSearchParams(search).get('next')} onAuthenticate={authenticate} />}
        {route.page === 'catalog' && <Catalog api={api} user={user} onLogin={() => onLogin(location)} onPurchased={onPurchased} />}
        {route.page === 'tutoring' && <Tutoring api={api} user={user} onLogin={() => onLogin('/tutoring')} />}
        {user && <>
          {route.page === 'learning' && <MyLearning api={api} />}
          {route.page === 'community' && <Community api={api} user={user} />}
          {route.page === 'wallet' && <Wallet api={api} user={user} />}
          {route.page === 'disputes' && <Disputes api={api} user={user} />}
          {route.page === 'account' && <Account api={api} user={user} onLogout={clearSession} />}
          {route.page === 'admin' && (isAdmin(user) ? <Admin api={api} user={user} /> : <div className="empty-page"><Icon name="shield" size={42} /><h1>Bạn chưa có quyền truy cập</h1><p>Khu vực này dành cho quản trị viên.</p><SiteLink className="button primary" href="/learning">Về việc học của tôi</SiteLink></div>)}
        </>}
        {route.page === 'not-found' && <div className="empty-page"><span className="error-code">404</span><h1>Trang này chưa có trong hành trình.</h1><p>Hãy quay về trang chủ để tiếp tục khám phá.</p><SiteLink href="/" className="button primary">Về trang chủ<Icon name="arrow" size={18} /></SiteLink></div>}
      </>}
    </main><Footer />
  </div>
}
export default App
