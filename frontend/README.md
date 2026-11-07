# Tutor Web frontend

React/Vite, dùng cấu hình `.env` chung ở thư mục gốc.
Xem [README dự án](../README.md) để cài đặt và chạy cả frontend/backend.

```powershell
npm ci
npm run dev
npm test
npm run lint
npm run build
```

`src/config.js` đọc API base URL; `src/services/api.js` quản lý request,
refresh JWT và đồng bộ phiên giữa các tab. `src/services/session.js` lưu cặp
token theo origin/API trong localStorage (fallback bộ nhớ khi storage bị chặn).
App xác minh `/auth/me` trước khi điều hướng trang cần đăng nhập; lỗi mạng có
nút thử lại và không xóa phiên. Hạn phiên vẫn do backend quyết định, mặc định
7 ngày. Xem [cơ chế xác thực](../docs/security.md).

Giao diện có chế độ sáng/tối và bố cục responsive. Light mode dùng xanh lá
và góc vuông. Menu tính năng nằm bên trái; danh mục quản trị gom 14 mục vào
5 nhóm thu gọn trong cùng sidebar. Mục được chọn lưu qua
`/admin?section=...`, hỗ trợ tải lại và Back/Forward.

Bài học phát ngay trên trang, tự lấy thời lượng từ metadata video và lưu
thời gian xem mỗi 10 giây, khi dừng, kết thúc hoặc rời bài. Tua không được
tính thành thời gian xem. Bản lưu trên trình duyệt giúp gửi lại tiến độ khi
mở lại bài sau lỗi mạng. Nguồn cần hỗ trợ HTML video; Drive preview dự phòng
không cung cấp sự kiện theo dõi. Xem [giới hạn Drive](../docs/vnpay-drive.md).

Trước khi triển khai phiên bản này, chạy `alembic upgrade head` để thêm
`lessons.duration_seconds`. Chỉ dữ liệu metadata được bổ sung; điểm đánh giá
vẫn do backend/quản trị quyết định.

Ví tự làm mới mỗi 15 giây khi đang hiển thị. Thanh toán VNPAY thành công được
cộng ví tự động qua IPN hợp lệ; admin chỉ đối soát chuyển khoản thủ công/rút tiền.

Triển khai frontend cùng backend bằng một project Vercel:
[Vercel Services](../docs/vercel.md). Giữ `VITE_API_BASE_URL` trống để trình
duyệt gọi `/api` cùng domain. Bộ điều phối Vercel xử lý API, còn fallback
`index.html` trong service frontend hỗ trợ tải lại các trang như `/login`.
