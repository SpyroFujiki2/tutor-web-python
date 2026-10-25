import ApiStatus from './components/ApiStatus.jsx'
import './App.css'

function App() {
  return (
    <>
      <header className="site-header">
        <a className="brand" href="/">Tutor Web<span>Gia sư & khóa học</span></a>
        <span className="development-badge">Đang phát triển</span>
      </header>
      <main>
        <section className="intro" aria-labelledby="intro-title">
          <p className="eyebrow">Nền tảng học tập</p>
          <h1 id="intro-title">Kết nối tri thức.<br />Mở rộng tương lai.</h1>
          <p className="intro-copy">
            Tutor Web đang được xây dựng để kết nối học viên với gia sư và khóa học phù hợp.
            Các tính năng tìm kiếm và đăng ký học sẽ được bổ sung trong giai đoạn tiếp theo.
          </p>
        </section>
        <ApiStatus />
      </main>
      <footer>Tutor Web · Phiên bản nền tảng 0.1</footer>
    </>
  )
}

export default App
