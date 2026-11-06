import { useState } from 'react'
import LessonMedia from './LessonMedia.jsx'
import { Action, Badge, Details, Form, Pager, Resource } from './Workspace.jsx'
import { money, useResource } from './workspace-utils.js'
import { useCollection } from './use-collection.js'
import { filterCollection } from './collection-utils.js'
import CollectionToolbar from './CollectionToolbar.jsx'
import ContentDialog from './ContentDialog.jsx'
import Icon from './Icon.jsx'
import SiteLink from './SiteLink.jsx'

const formatOptions = [['all', 'Mọi hình thức'], ['video', 'Học qua video'], ['live', 'Lớp trực tiếp']]
const priceOptions = [['all', 'Mọi mức giá'], ['free', 'Miễn phí'], ['paid', 'Có học phí']]
const sortOptions = [['newest', 'Mới nhất'], ['price_asc', 'Giá tăng dần'], ['price_desc', 'Giá giảm dần'], ['name', 'Tên A → Z']]

export function CourseCover({ course, index = 0 }) {
  const title = (course.title ?? '').toLowerCase()
  const symbol = title.includes('python') ? 'Py' : /toán|math/.test(title) ? '∑' : /anh|english|ngữ/.test(title) ? 'Aa' : '{ }'
  return <div className={`course-cover cover-${index % 4}`}><span className="cover-label">{course.is_live ? 'KẾT NỐI CÙNG GIẢNG VIÊN' : 'KHÁM PHÁ THEO NHỊP RIÊNG'}</span><span className="cover-icon"><Icon name={course.is_live ? 'users' : 'code'} size={24} /></span><span className="cover-symbol" aria-hidden="true">{symbol}</span></div>
}

export function Catalog({ api, user, onLogin, onPurchased, featured = false }) {
  const [query, setQuery] = useState('')
  const [format, setFormat] = useState('all')
  const [price, setPrice] = useState('all')
  const [sort, setSort] = useState('newest')
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState(null)
  const resource = useCollection(api, '/courses')
  const rows = filterCollection(resource.data ?? [], { query, format, price, sort })
  const visible = featured ? rows.slice(0, 3) : rows.slice(offset, offset + 9)
  const change = (setter) => (value) => { setter(value); setOffset(0) }
  const reset = () => { setQuery(''); setFormat('all'); setPrice('all'); setSort('newest'); setOffset(0) }
  return <section className={featured ? 'featured-catalog' : 'catalog-page'}>
    <div className="section-heading"><div><p className="eyebrow">{featured ? 'MỞ RA NHỮNG KHẢ NĂNG MỚI' : 'HỌC THEO NHỊP CỦA BẠN'}</p>{featured ? <h2 className="section-title">Bước tiếp theo, bạn muốn học gì?</h2> : <h1>Khám phá khóa học</h1>}<p className="section-description">Chọn điều bạn quan tâm. Tìm hiểu nội dung và bắt đầu từ nền tảng.</p></div>{featured ? <SiteLink href="/courses" className="button">Tất cả khóa học<Icon name="arrow" size={16} /></SiteLink> : <span className="section-icon"><Icon name="book" size={28} /></span>}</div>
    {!featured && <CollectionToolbar query={query} onQueryChange={change(setQuery)} placeholder="Tìm tên khóa học hoặc nội dung bạn quan tâm…" count={resource.data ? rows.length : null} noun="khóa học" active={query || format !== 'all' || price !== 'all' || sort !== 'newest'} onReset={reset} filters={[
      { label: 'Hình thức học', value: format, onChange: change(setFormat), options: formatOptions },
      { label: 'Học phí khóa học', value: price, onChange: change(setPrice), options: priceOptions },
      { label: 'Sắp xếp khóa học', value: sort, onChange: change(setSort), options: sortOptions },
    ]} />}
    <Resource resource={resource} empty="Khóa học mới đang được chuẩn bị. Hãy quay lại sau nhé.">{() => <>
      {visible.length ? <div className="card-grid">{visible.map((course, index) => <article className="card course-card selectable-card" key={course.id}>
        <CourseCover course={course} index={index} /><div className="card-body"><div className="course-meta"><Icon name={course.is_live ? 'users' : 'video'} size={14} />{course.is_live ? 'Lớp học trực tiếp' : 'Khóa học video'}<span className="dot-separator">·</span>Tutor Web</div><h2>{course.title}</h2><p className="content-preview">{course.description || 'Khám phá nội dung khóa học và bắt đầu hành trình học tập của bạn.'}</p><div className="card-bottom"><strong className="course-price">{Number(course.price) === 0 ? 'Miễn phí' : <>{money(course.price)}<small>credit</small></>}</strong><button className="card-link" onClick={() => setSelected(course)}>Xem khóa học<Icon name="arrow" size={15} /></button></div></div>
      </article>)}</div> : <div className="empty"><Icon name="search" size={30} /><p>Chưa tìm thấy khóa học phù hợp với bộ lọc.</p><button onClick={reset}>Xóa bộ lọc</button></div>}
      {!featured && rows.length > 9 && <Pager offset={offset} setOffset={setOffset} length={Math.min(9, rows.length - offset)} size={9} hasNext={offset + 9 < rows.length} />}
    </>}</Resource>
    {selected && <ContentDialog title="TÌM HIỂU KHÓA HỌC" onClose={() => setSelected(null)}><CourseCover course={selected} /><div className="course-meta"><Icon name={selected.is_live ? 'users' : 'video'} size={15} />{selected.is_live ? 'Lớp học trực tiếp' : 'Học qua video'}</div><h2>{selected.title}</h2><p className="preserve dialog-description">{selected.description || 'Khóa học chưa có mô tả chi tiết.'}</p><div className="dialog-purchase"><div><span className="muted">Học phí khóa học</span><p className="course-price"><strong>{money(selected.price)}</strong><small>credit</small></p></div>{user ? <PurchaseButton api={api} course={selected} onPurchased={onPurchased} /> : <button className="primary" onClick={onLogin}>Đăng nhập để học<Icon name="arrow" size={17} /></button>}</div></ContentDialog>}
  </section>
}

function PurchaseButton({ api, course, onPurchased }) {
  const [review, setReview] = useState(false)
  if (!review) return <button className="primary" onClick={() => setReview(true)}>Đăng ký khóa học<Icon name="arrow" size={17} /></button>
  return <div className="purchase-review"><p>Thanh toán <strong>{money(course.price)} credit</strong> từ ví cá nhân để đăng ký khóa học này?</p><Form fields={[]} submit="Xác nhận đăng ký" onSubmit={async (_, requestId) => {
    await api.request(`/courses/${course.id}/purchase`, { method: 'POST', body: { request_id: requestId } })
    onPurchased()
  }} /><button className="text-button" onClick={() => setReview(false)}>Để sau</button><SiteLink href="/wallet" className="button">Xem ví của tôi</SiteLink></div>
}

export function MyLearning({ api }) {
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState(null)
  const resource = useResource(api, `/me/subscriptions?limit=20&offset=${offset}`)
  if (selected) return <CourseRoom key={selected.id} api={api} subscription={selected} onBack={() => setSelected(null)} />
  return <section><p className="eyebrow">Mỗi ngày một bước tiến</p><h1>Việc học của tôi</h1>
    <Resource resource={resource} empty="Bạn chưa đăng ký khóa học hoặc gói gia sư.">{(rows) => <>
      <div className="card-grid">{rows.map((row) => <article className="card card-body" key={row.id}><Badge value={row.type} /><h2>{row.title_at_purchase}</h2>
        <Details row={row} fields={['status', 'activated_at', 'expired_at', 'price_at_purchase']} />
        {row.type === 'course' && <button className="primary" onClick={() => setSelected(row)}>Mở khóa học</button>}
      </article>)}</div><Pager offset={offset} setOffset={setOffset} length={rows.length} /></>}
    </Resource></section>
}

function CourseRoom({ api, subscription, onBack }) {
  const [version, setVersion] = useState(0)
  const lessons = useResource(api, `/subscriptions/${subscription.id}/lessons`)
  const progress = useResource(api, `/subscriptions/${subscription.id}/progress`, version)
  const course = useResource(api, `/subscriptions/${subscription.id}/course`)
  const attendance = useResource(api, `/subscriptions/${subscription.id}/attendance`, version)
  const refresh = () => setVersion((value) => value + 1)
  return <section><button onClick={onBack}>← Các đăng ký</button><h1>{subscription.title_at_purchase}</h1>
    <Resource resource={progress}>{(row) => <div className="card card-body"><div className="row"><h2>Tiến độ học tập</h2><strong>{row.progress_percent}%</strong></div>
      <progress max="100" value={Number(row.progress_percent)} aria-label="Tiến độ khóa học" /><Details row={row} fields={['result', 'final_score', 'completed_at']} />
      <p className="muted">Hoàn thành các bài học và chờ quản trị chấm điểm để nhận kết quả cuối cùng.</p></div>}</Resource>
    <Resource resource={lessons} empty="Khóa học chưa có bài học.">{(rows) => <div className="stack">{rows.map((lesson) => <article className="card card-body" key={lesson.id}>
      <h2>Bài {lesson.order_idx}</h2><p>{lesson.duration_minutes ? `${lesson.duration_minutes} phút` : 'Buổi học trực tiếp'}</p>
      {lesson.media_url && <LessonMedia url={lesson.media_url} title={`Bài ${lesson.order_idx}`} />}
      {lesson.assignment_url && <a className="button" href={lesson.assignment_url} target="_blank" rel="noreferrer">Bài tập ↗</a>}
      {lesson.media_url && course.data?.is_live === false && <Action onClick={async () => {
        await api.request(`/subscriptions/${subscription.id}/lessons/${lesson.id}/watch`, { method: 'POST', body: { duration_watched: (lesson.duration_minutes ?? 0) * 60, completed: true } }); refresh()
      }}>Ghi nhận đã xem hết bài</Action>}
      {attendance.data?.some((row) => row.lesson_id === lesson.id && !row.is_absent) && <p className="success">Đã ghi nhận việc học.</p>}
    </article>)}</div>}</Resource>
  </section>
}
