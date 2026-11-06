import { useState } from 'react'
import { Action, Form, Pager, Resource } from './Workspace.jsx'
import { date, numberField, textField, useResource } from './workspace-utils.js'
import { useCollection } from './use-collection.js'
import { filterCollection } from './collection-utils.js'
import CollectionToolbar from './CollectionToolbar.jsx'
import ContentDialog from './ContentDialog.jsx'
import Icon from './Icon.jsx'

const postFields = [textField('title', 'Tiêu đề', { maxLength: 200, placeholder: 'Một câu hỏi hay, một điều mới học được…' }), textField('content', 'Nội dung', { type: 'textarea', placeholder: 'Chia sẻ câu chuyện hoặc câu hỏi của bạn…' }), numberField('min_role_level', 'Bậc đọc tối thiểu (0–6)', { max: 6, default: 0, hint: 'Để 0 nếu bạn muốn mọi thành viên đều có thể đọc.' })]

export default function Community({ api, user }) {
  const [selected, setSelected] = useState(null)
  const [composing, setComposing] = useState(false)
  const [offset, setOffset] = useState(0)
  const [query, setQuery] = useState('')
  const [author, setAuthor] = useState('all')
  const [sort, setSort] = useState('newest')
  const resource = useCollection(api, '/posts')
  const rows = filterCollection(resource.data ?? [], { query, author, sort, userId: user.id })
  const change = (setter) => (value) => { setter(value); setOffset(0) }
  const reset = () => { setQuery(''); setAuthor('all'); setSort('newest'); setOffset(0) }
  if (selected) return <PostRoom key={selected} api={api} user={user} id={selected} onBack={() => { setSelected(null); resource.reload() }} />
  return <section className="community-page"><div className="section-heading"><div><p className="eyebrow">MỖI GÓC NHÌN, MỘT ĐIỀU MỚI</p><h1>Học hỏi cùng cộng đồng</h1><p className="section-description">Một câu hỏi, một kinh nghiệm hay một điều vừa khám phá. Cùng chia sẻ nhé.</p></div><button className="primary community-compose-toggle" onClick={() => setComposing(true)}><Icon name="chat" size={17} />Viết bài mới</button></div>
    <CollectionToolbar query={query} onQueryChange={change(setQuery)} placeholder="Tìm bài viết, nội dung hoặc tác giả…" count={resource.data ? rows.length : null} noun="bài viết" active={query || author !== 'all' || sort !== 'newest'} onReset={reset} filters={[
      { label: 'Tác giả bài viết', value: author, onChange: change(setAuthor), options: [['all', 'Tất cả bài viết'], ['mine', 'Bài viết của tôi']] },
      { label: 'Sắp xếp bài viết', value: sort, onChange: change(setSort), options: [['newest', 'Mới nhất'], ['oldest', 'Cũ nhất']] },
    ]} />
    <Resource resource={resource} empty="Cộng đồng đang chờ câu chuyện đầu tiên. Hãy bắt đầu bằng một bài chia sẻ nhé.">{() => <>
      {rows.length ? <div className="card-grid">{rows.slice(offset, offset + 9).map((row) => <article key={row.id} className="card card-body post-card selectable-card"><div className="post-byline"><span className="avatar">{(row.author_nickname ?? 'T').charAt(0).toUpperCase()}</span><div><strong>{row.author_nickname || 'Thành viên Tutor Web'}</strong><small>{date(row.created_at)}</small></div></div><h2>{row.title}</h2><p className="content-preview">{row.content}</p><div className="card-bottom"><span className="post-access"><Icon name="chat" size={14} />Cùng thảo luận</span><button className="card-link" onClick={() => setSelected(row.id)}>Đọc bài viết<Icon name="arrow" size={15} /></button></div></article>)}</div> : <div className="empty"><Icon name="search" size={30} /><p>Chưa tìm thấy bài viết phù hợp.</p><button onClick={reset}>Xóa bộ lọc</button></div>}
      {rows.length > 9 && <Pager offset={offset} setOffset={setOffset} length={Math.min(9, rows.length - offset)} size={9} hasNext={offset + 9 < rows.length} />}
    </>}</Resource>
    {composing && <ContentDialog title="CHIA SẺ CÙNG CỘNG ĐỒNG" onClose={() => setComposing(false)}><h2>Mỗi chia sẻ đều có giá trị.</h2><p className="dialog-description">Viết điều bạn muốn chia sẻ, đặt câu hỏi hoặc mở đầu một cuộc thảo luận.</p><Form fields={postFields} submit="Đăng bài viết" onSubmit={async (values) => { const row = await api.request('/posts', { method: 'POST', body: values }); setComposing(false); setSelected(row.id) }} /></ContentDialog>}
  </section>
}

function PostRoom({ api, user, id, onBack }) {
  const [offset, setOffset] = useState(0)
  const post = useResource(api, `/posts/${id}`)
  const comments = useResource(api, `/posts/${id}/comments?limit=20&offset=${offset}`)
  const [parent, setParent] = useState(null)
  return <section><button onClick={onBack}>← Cộng đồng</button><Resource resource={post}>{(row) => <article className="card card-body">
    <p className="muted">{row.author_nickname} · {date(row.created_at)}</p><h1>{row.title}</h1><p className="preserve prose">{row.content}</p>
    {row.author_id === user.id && <details><summary>Chỉnh sửa bài viết</summary><Form fields={postFields} initial={row} onSubmit={async (values) => { await api.request(`/posts/${id}`, { method: 'PUT', body: values }); post.reload() }} />
      <Action onClick={async () => { await api.request(`/posts/${id}/visibility`, { method: 'POST', body: { is_hidden: true, reason: 'Tác giả ẩn bài' } }); onBack() }}>Ẩn bài viết</Action></details>}
  </article>}</Resource><h2>Thảo luận</h2><Resource resource={comments} empty="Hãy mở đầu cuộc thảo luận.">{(rows) => <><div className="stack">{rows.map((row) => <article className="card card-body" key={row.id}>
    <small>Thành viên {row.user_id.slice(0, 8)} · {date(row.created_at)}</small>{row.parent_id && <small>Trả lời bình luận {row.parent_id.slice(0, 8)}</small>}<p className="preserve">{row.content}</p>
    <button onClick={() => setParent(row.id)}>Trả lời</button>
    {row.user_id === user.id && <details><summary>Sửa bình luận</summary><Form fields={[textField('content', 'Nội dung', { type: 'textarea', maxLength: 5000 })]} initial={row} onSubmit={async (values) => { await api.request(`/comments/${row.id}`, { method: 'PUT', body: values }); comments.reload() }} />
      <Action onClick={async () => { await api.request(`/comments/${row.id}/visibility`, { method: 'POST', body: { is_hidden: true, reason: 'Tác giả ẩn bình luận' } }); comments.reload() }}>Ẩn bình luận</Action></details>}
    <details><summary>Báo cáo vi phạm</summary><Form fields={[textField('reason_category', 'Lý do', { maxLength: 200 }), textField('reason_details', 'Chi tiết', { type: 'textarea', optional: true, maxLength: 2000 })]} submit="Gửi báo cáo" onSubmit={async (values) => { await api.request(`/comments/${row.id}/reports`, { method: 'POST', body: { ...values, reason_details: values.reason_details ?? '' } }) }} /></details>
  </article>)}</div><Pager offset={offset} setOffset={setOffset} length={rows.length} /></>}</Resource>
    <div className="card card-body"><h3>{parent ? `Trả lời ${parent.slice(0, 8)}` : 'Viết bình luận'}</h3>{parent && <button onClick={() => setParent(null)}>Hủy trả lời</button>}
      <Form fields={[textField('content', 'Bình luận', { type: 'textarea', maxLength: 5000 })]} submit="Đăng bình luận" reset onSubmit={async (values) => {
        await api.request(`/posts/${id}/comments`, { method: 'POST', body: { ...values, parent_id: parent } }); setParent(null); comments.reload()
      }} /></div>
  </section>
}
