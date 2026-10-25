# Tutor Web

Website dịch vụ gia sư và khóa học, gồm frontend React/Vite và backend FastAPI.
Scaffold hiện có một luồng hoàn chỉnh: React gọi `GET /api/health`, hiển thị trạng
thái tải, kết quả hoặc lỗi và cho phép kiểm tra lại. Chưa có dữ liệu nghiệp vụ.

## Cấu trúc

```text
backend/
  app/
    main.py              # Tạo app, middleware, đăng ký router
    core/config.py       # Đọc cấu hình và kiểm tra CORS origins
    api/router.py        # Gom route dưới /api
    api/routes/health.py # Endpoint theo tính năng
    schemas/health.py    # Hợp đồng response
    models/              # 24 ORM model từ DBML, mỗi bảng một file
  tests/                 # Kiểm tra API và cấu hình bằng unittest
  requirements.txt       # Dependency runtime trực tiếp
  requirements-dev.txt   # Thêm HTTP client phục vụ kiểm tra
frontend/
  src/
    App.jsx              # Khung trang
    components/          # Thành phần giao diện
    services/api.js       # HTTP, timeout, kiểm tra response
    config.js            # Cấu hình public của frontend
  tests/                 # Kiểm tra HTTP client bằng Node test runner
docs/
  code-review.md          # Kết quả review thủ công và việc cần làm
```

Đã ánh xạ DBML thành SQLAlchemy model cho PostgreSQL; xem [hướng dẫn models](docs/models.md).
Chưa kết nối database hoặc tạo migration. Khi thêm tính năng có database, tách
nghiệp vụ vào service và truy cập dữ liệu vào repository theo nhu cầu thực tế.

## Cấu hình môi trường

Tạo `.env` ở thư mục gốc từ `.env.example` nếu chưa có:

```powershell
Copy-Item .env.example .env
```

Không chạy lệnh sao chép nếu đã có cấu hình riêng. Không commit `.env`.

| Biến | Ý nghĩa | Khi không khai báo |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Base URL backend, không kèm `/api`; bỏ dấu `/` cuối | `http://localhost:8000` |
| `CORS_ORIGINS` | Origin frontend phân cách bằng dấu phẩy, gồm scheme, hostname và port nếu có | `http://localhost:5173,http://127.0.0.1:5173` |

Backend đọc `.env` bằng đường dẫn tuyệt đối; biến môi trường của process được ưu
tiên hơn `.env`. `CORS_ORIGINS` rỗng sẽ không cho phép origin ngoài; wildcard,
credentials và đường dẫn trong origin bị từ chối khi khởi động. Khai báo các
origin production cần dùng trong môi trường deploy; `.env.example` có các domain
đang được dùng trong cấu hình dự án.

Vite đọc `.env` từ thư mục gốc qua `envDir`. Biến `VITE_` được đưa vào mã frontend
khi build: chỉ chứa thông tin public. Khởi động lại dev server sau khi sửa `.env`;
build lại frontend khi thay biến lúc triển khai. Đặt `VITE_API_BASE_URL=` nếu
reverse proxy phục vụ frontend và `/api` cùng origin.

## Chạy trên Windows / PowerShell

Dùng Python 3.14 và Node.js 24 như môi trường phát triển hiện tại. Từ thư mục gốc:

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --app-dir backend
```

Nếu đã có `backend/.venv`, bỏ qua lệnh tạo venv. Backend tại `http://localhost:8000`,
Swagger UI tại `http://localhost:8000/docs`, health tại `http://localhost:8000/api/health`.
Môi trường chỉ chạy ứng dụng có thể cài `backend/requirements.txt`.

Mở terminal thứ hai:

```powershell
cd frontend
npm ci
npm run dev
```

Frontend tại `http://localhost:5173`. Vite dừng nếu port bận để không tự đổi sang
port ngoài danh sách CORS. VS Code được cấu hình dùng interpreter trong `backend/.venv`.

## Kiểm tra

Từ thư mục gốc:

```powershell
Push-Location backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Pop-Location
Push-Location frontend
npm test
npm run lint
npm run build
Pop-Location
```

Kiểm tra tương tác: chạy cả hai server, mở frontend và xem trạng thái API; dừng
backend rồi bấm “Kiểm tra lại” để xem lỗi; chạy backend trở lại và kiểm tra lần nữa.
Client giới hạn mỗi request ở 10 giây và hủy request khi component unmount.
Browser cần hỗ trợ `AbortSignal.timeout` và `AbortSignal.any`.

## Bước tiếp theo

1. Chốt luồng MVP và vai trò: học viên/phụ huynh, gia sư, quản trị; xác định đăng ký
   tư vấn hay đặt lịch học trực tiếp là luồng chính.
2. Cấu hình PostgreSQL, session và Alembic; rà soát rồi tạo migration từ 24 model
   đã ánh xạ theo DBML. Bổ sung repository theo tính năng thực tế.
3. Thêm xác thực và phân quyền; chọn session cookie hay token trước khi bổ sung
   CORS credentials, CSRF hoặc header Authorization.
4. Làm một tính năng từ đầu đến cuối: danh sách gia sư → bộ lọc → hồ sơ → gửi yêu
   cầu học. Thêm validation và test theo quy tắc nghiệp vụ được chốt.
5. Bổ sung CI, logging, xử lý lỗi thống nhất, kiểm thử trình duyệt và cấu hình
   deploy. Health hiện tại chỉ xác nhận process/API hoạt động, chưa kiểm tra DB.

Chi tiết review và giới hạn xem [docs/code-review.md](docs/code-review.md).
