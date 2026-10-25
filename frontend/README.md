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
