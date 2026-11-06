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

`src/config.js` đọc API base URL; `src/services/api.js` thực hiện health request;
`src/components/ApiStatus.jsx` quản lý trạng thái và hủy request khi unmount.

Triển khai frontend cùng backend bằng một project Vercel:
[Vercel Services](../docs/vercel.md). Giữ `VITE_API_BASE_URL` trống để trình
duyệt gọi `/api` cùng domain. Bộ điều phối Vercel xử lý API, còn fallback
`index.html` trong service frontend hỗ trợ tải lại các trang như `/login`.
