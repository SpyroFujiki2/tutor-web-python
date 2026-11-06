export function searchText(value) {
  return String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLocaleLowerCase('vi').trim()
}

export function matchesPrice(price, range) {
  const value = Number(price ?? 0)
  if (range === 'free') return value === 0
  if (range === 'paid') return value > 0
  if (range === 'under500') return value < 500
  if (range === '500to1000') return value >= 500 && value <= 1000
  if (range === 'over1000') return value > 1000
  return true
}

export function filterCollection(rows, { query = '', format = 'all', price = 'all', sort = 'default', author = 'all', userId } = {}) {
  const needle = searchText(query)
  const filtered = rows.filter((row) => {
    const searchable = [row.title, row.name, row.description, row.content, row.author_nickname].join(' ')
    return (!needle || searchText(searchable).includes(needle)) &&
      (format === 'all' || (format === 'live' ? row.is_live === true : row.is_live === false)) &&
      matchesPrice(row.price, price) && (author !== 'mine' || row.author_id === userId)
  })
  if (sort === 'price_asc') filtered.sort((a, b) => Number(a.price ?? 0) - Number(b.price ?? 0))
  if (sort === 'price_desc') filtered.sort((a, b) => Number(b.price ?? 0) - Number(a.price ?? 0))
  if (sort === 'name') filtered.sort((a, b) => (a.title ?? a.name ?? '').localeCompare(b.title ?? b.name ?? '', 'vi'))
  if (sort === 'newest' || sort === 'oldest') filtered.sort((a, b) => {
    const first = Date.parse(a.created_at ?? '') || 0
    const second = Date.parse(b.created_at ?? '') || 0
    return sort === 'oldest' ? first - second : second - first
  })
  return filtered
}

// Fetch every server page before filtering, rather than hiding results that
// happen to be outside the first API page.
export async function loadCollection(api, path, signal) {
  const result = []
  const identities = new Set()
  const separator = path.includes('?') ? '&' : '?'
  for (let offset = 0; ; offset += 100) {
    const rows = await api.request(`${path}${separator}limit=100&offset=${offset}`, { signal })
    if (!Array.isArray(rows)) throw new Error('Danh sách trả về không đúng định dạng.')
    if (signal?.aborted) throw signal.reason ?? new Error('Đã hủy tải dữ liệu.')
    let added = 0
    for (const row of rows) {
      if (identities.has(row.id)) continue
      identities.add(row.id); result.push(row); added += 1
    }
    if (rows.length < 100) return result
    if (!added) throw new Error('Không thể tải trang tiếp theo. Vui lòng thử lại.')
  }
}

