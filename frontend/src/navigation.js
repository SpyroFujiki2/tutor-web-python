import { useSyncExternalStore } from 'react'

export const routes = {
  '/': { page: 'home', title: 'Trang chủ' },
  '/courses': { page: 'catalog', title: 'Khám phá khóa học' },
  '/login': { page: 'login', title: 'Đăng nhập', auth: true },
  '/register': { page: 'register', title: 'Tạo tài khoản', auth: true },
  '/learning': { page: 'learning', title: 'Việc học của tôi', protected: true },
  '/tutoring': { page: 'tutoring', title: 'Gia sư & lịch học' },
  '/community': { page: 'community', title: 'Cộng đồng', protected: true },
  '/wallet': { page: 'wallet', title: 'Ví & thanh toán', protected: true },
  '/disputes': { page: 'disputes', title: 'Tranh chấp', protected: true },
  '/account': { page: 'account', title: 'Tài khoản', protected: true },
  '/admin': { page: 'admin', title: 'Quản trị', protected: true },
  '/payment/vnpay-return': { page: 'payment', title: 'Kết quả thanh toán' },
}

export function resolveRoute(location) {
  const pathname = location.split('?')[0].replace(/\/+$/, '') || '/'
  return routes[pathname] ?? { page: 'not-found', title: 'Không tìm thấy trang' }
}

export function returnDestination(search = '') {
  const target = new URLSearchParams(search).get('next')
  return target && target.startsWith('/') && !target.startsWith('//') &&
    !target.includes('\\') && !Array.from(target).some((character) => character.charCodeAt(0) < 32) &&
    routes[target.split('?')[0]] && !resolveRoute(target).auth &&
    !['payment', 'not-found'].includes(resolveRoute(target).page)
    ? target : '/learning'
}

export const loginDestination = (next) => `/login?${new URLSearchParams({ next })}`

export function navigate(to, { replace = false } = {}) {
  if (`${window.location.pathname}${window.location.search}` === to) return
  window.history[replace ? 'replaceState' : 'pushState']({}, '', to)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

function subscribe(callback) {
  window.addEventListener('popstate', callback)
  return () => window.removeEventListener('popstate', callback)
}

export function useLocation() {
  return useSyncExternalStore(subscribe, () => `${window.location.pathname}${window.location.search}`)
}
