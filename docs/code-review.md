# Review thủ công scaffold — 25/10/2026

Phạm vi: đọc cấu hình backend/frontend, lần theo request từ React đến route
FastAPI, kiểm tra lifecycle request, ưu tiên biến môi trường, CORS, dependency
và hướng dẫn chạy. Review do một agent thực hiện trực tiếp, không phải review
độc lập của người thứ hai. Các kiểm tra tự động hỗ trợ kết luận bên dưới.

## Phát hiện và thay đổi

| Mức độ | Phát hiện ban đầu | Xử lý |
| --- | --- | --- |
| Vừa | Frontend vẫn là template và chưa kiểm chứng kết nối backend | Thay bằng khung Tutor Web và component gọi health API với trạng thái tải/thành công/lỗi, nút thử lại |
| Vừa | `API_BASE_URL` có thể là `undefined` khi thiếu biến môi trường | Thêm mặc định localhost; chuẩn hóa dấu `/` cuối; giá trị rỗng dùng cùng origin |
| Vừa | Cấu hình, CORS và route gộp trong `main.py`; import ghi vào `os.environ` | Tách config/router/schema và `create_app`; đọc `.env` không sửa process environment |
| Vừa | Default CORS chứa domain deploy và mở mọi method/header | Default chỉ localhost; domain deploy khai báo tường minh; hiện chỉ cho GET và các header đang dùng |
| Thấp | `requirements.txt` chứa toàn bộ gói môi trường, gồm CLI/cloud tooling không dùng trực tiếp | Giữ bốn dependency runtime trực tiếp; HTTPX phục vụ test nằm ở requirements-dev |
| Thấp | README tạo venv ở root trong khi dự án có `backend/.venv` | Đồng bộ hướng dẫn và VS Code về `backend/.venv` |
| Thấp | Vite có thể tự đổi port khiến lệch CORS | Cố định port 5173 với `strictPort` |

## Đọc lại code sau thay đổi

- `backend/app/main.py`: factory tạo instance riêng để test cấu hình CORS mà
  không thay global app; giữ nguyên URL và JSON của `/api/health`.
- `backend/app/core/config.py`: kiểm tra đường dẫn `.env` sau khi chuyển module;
  thứ tự ưu tiên process > file > default; cấu hình rỗng không rơi về default.
  Origins có path/query/credentials, wildcard hoặc port không hợp lệ bị từ chối.
- `frontend/src/components/ApiStatus.jsx`: cleanup hủy request, kiểm tra signal
  trước khi set state; dùng số lần thử để không hiện lại kết quả cũ khi retry.
  Luồng cleanup cũng áp dụng cho effect được chạy lại bởi React StrictMode.
- `frontend/src/services/api.js`: kiểm tra HTTP status trước JSON, xác thực shape
  health response, giữ nguyên nguyên nhân lỗi qua `cause`. Khi đọc lại phát hiện
  timeout trong lúc đọc body bị báo nhầm thành JSON lỗi; đã sửa và thêm test.
- Giao diện có label, trạng thái được đọc qua live region, focus bàn phím và
  layout một cột trên màn hình nhỏ. Đây là kiểm tra code, chưa phải xác minh
  giao diện hay accessibility trên trình duyệt.

## Kết quả kiểm tra

- Backend: 12 test qua `unittest`/FastAPI TestClient, gồm health contract,
  OpenAPI, CORS request/preflight được phép và bị từ chối, cấu hình môi trường.
- Frontend: 9 test HTTP client qua Node test runner đều qua; ESLint và production
  build đều thành công. Node test runner và Vite build phải chạy ngoài sandbox
  do sandbox chặn tạo process với `spawn EPERM`.
- `pip check` không phát hiện dependency hỏng trong venv hiện tại;
  `git diff --check` không báo lỗi whitespace trong các file tracked.
- Chưa chạy kiểm thử browser end-to-end hoặc cài thử từ môi trường hoàn toàn
  trống; kết quả dựa trên venv và node_modules đang có trong workspace.

## Giới hạn và việc còn phải làm

1. Chưa có DB, migration, xác thực, phân quyền hoặc CRUD nghiệp vụ. Các quyết định
   cần chốt và thứ tự triển khai được liệt kê trong README.
2. `/api/health` là liveness; bổ sung readiness khi có DB/dịch vụ phụ thuộc.
3. CORS không phải cơ chế xác thực hay chặn request ngoài browser. Khi thêm
   POST/PUT/PATCH/DELETE hoặc Authorization, cập nhật allow_methods/allow_headers
   và kiểm tra preflight tương ứng. Không bật credentials trước khi chọn auth.
4. Pin dependency trực tiếp chưa phải lock đầy đủ dependency bắc cầu của Python;
   cần bổ sung lock/CI và cài từ môi trường sạch trước khi deploy.
5. Chưa có logging và error contract chung cho nghiệp vụ; thiết kế cùng tính
   năng đầu tiên để tránh tạo abstraction không có nhu cầu sử dụng.
