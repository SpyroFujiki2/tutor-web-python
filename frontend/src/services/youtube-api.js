let pending

export function loadYouTubeApi() {
  if (window.YT?.Player) return Promise.resolve(window.YT)
  if (pending) return pending
  pending = new Promise((resolve, reject) => {
    const previous = window.onYouTubeIframeAPIReady
    const script = document.createElement('script')
    let timeout
    function cleanup() {
      clearTimeout(timeout)
      if (window.onYouTubeIframeAPIReady === ready) window.onYouTubeIframeAPIReady = previous
      script.onerror = null
    }
    function ready() {
      cleanup()
      try { previous?.() } finally {
        if (window.YT?.Player) resolve(window.YT)
        else { pending = null; reject(new Error('YouTube player unavailable')) }
      }
    }
    function fail() {
      cleanup()
      script.remove()
      pending = null
      reject(new Error('YouTube player unavailable'))
    }
    window.onYouTubeIframeAPIReady = ready
    script.src = 'https://www.youtube.com/iframe_api'
    script.async = true
    script.referrerPolicy = 'strict-origin-when-cross-origin'
    script.onerror = fail
    timeout = setTimeout(fail, 15000)
    document.head.appendChild(script)
  })
  return pending
}

export function youtubeErrorMessage(code) {
  if ([101, 150].includes(code)) return 'Video này không cho phép phát trên trang. Bạn có thể xem trên YouTube.'
  if (code === 100) return 'Video không còn khả dụng hoặc đang ở chế độ riêng tư.'
  if (code === 2) return 'Liên kết video YouTube không hợp lệ.'
  return 'Chưa phát được video. Vui lòng thử lại hoặc mở trên YouTube.'
}
