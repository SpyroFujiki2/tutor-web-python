# Tutor Web

Website dịch vụ gia sư và khóa học, gồm frontend React/Vite và backend FastAPI.
Đã nối các API tài khoản, khóa học, gia sư, cộng đồng và quản trị với giao diện.
Backend dùng 24 model DBML và AuthSession cho JWT rotation, PostgreSQL, Session
và Alembic. Xem [trạng thái triển khai và cách tạo quản trị](docs/implementation.md)
để phân biệt chức năng đã có với tích hợp tài chính/video đang làm tiếp.

Các khối TODO gốc được giữ nguyên theo yêu cầu, kể cả khi chức năng đã được
triển khai ở service mới. OpenAPI `/api/docs` và `docs/implementation.md` là hợp đồng
hiện tại; các tài liệu thiết kế cũ được giữ làm bối cảnh.

Tích hợp đang dùng: [VNPAY sandbox và video Google Drive](docs/vnpay-drive.md).
Seed Drive cần đủ 10 link thật; VNPAY cần merchant credentials trong `.env`.
Chi tiết phần gia sư đã hoàn thiện: [module tutor](docs/tutoring.md).
Tài chính nội bộ và quy tắc công nợ/đối soát: [finance.md](docs/finance.md).
Seed 7 tài khoản theo role và 3 gói gia sư giá ngẫu nhiên: [seed-data.md](docs/seed-data.md).

## Cấu trúc

```text
backend/
  app/
    main.py              # Tạo app, middleware, đăng ký router
    core/config.py       # Đọc cấu hình và kiểm tra CORS origins
    core/database.py     # PostgreSQL engine, pool và Session factory
    core/security.py     # Hash/verify/rehash Argon2id, tạo/kiểm tra JWT
    api/router.py        # Gom route dưới /api
    api/dependencies/    # Session từng request, JWT/current_user
    api/routes/health.py # Endpoint theo tính năng
    schemas/health.py    # Hợp đồng response
    schemas/auth.py      # Hợp đồng login/refresh/token/current user
    models/              # 24 model DBML + AuthSession cho JWT rotation
    modules/             # Mỗi file một hàm mẫu + TODO hướng dẫn phần còn lại
      users/             # User, ngân hàng, audit, subscription
      tutoring/          # Gói gia sư, booking, buổi học, chat, tranh chấp
      learning/          # Khóa/bài học, điểm danh, tiến độ
      community/         # Bài viết, bình luận, nâng role, báo cáo
      finance/           # Ví, quyết toán, ledger, nạp/rút, snapshot
      auth/              # Xác thực email/mật khẩu, cấp token, refresh và logout
  tests/                 # API/config, metadata và logic module bằng unittest
  requirements.txt       # Dependency runtime trực tiếp
  requirements-dev.txt   # Thêm HTTP client phục vụ kiểm tra
  migrations/            # Migration cố định, hiện 25 bảng + 15 enum
  scripts/               # Sinh .env, tạo role/database, kiểm tra kết nối
scripts/setup.py          # Cài trên Windows/Linux/macOS: native hoặc Docker
alembic.ini               # Cấu hình migration, không chứa mật khẩu
compose.yaml              # PostgreSQL 18 tùy chọn trên máy mới
frontend/
  src/
    App.jsx              # Khung trang
    components/          # Thành phần giao diện
    services/api.js       # HTTP, timeout, kiểm tra response
    config.js            # Cấu hình public của frontend
  tests/                 # Kiểm tra HTTP client bằng Node test runner
docs/
  code-review.md          # Kết quả review thủ công và việc cần làm
  models.md               # Ánh xạ 24 model từ DBML
  modules.md              # Danh mục hàm mẫu, trách nhiệm và cách phát triển tiếp
  database-flow.md        # Luồng đọc/ghi DB, transaction và quyết định cần chốt
  security.md             # JWT Bearer, refresh rotation, cấu hình và luồng auth
  database-setup.md       # Cài máy mới, pgAdmin, backup/restore, migration
```

Đã ánh xạ DBML thành SQLAlchemy model cho PostgreSQL; xem [hướng dẫn models](docs/models.md).
Mỗi file trong `app/modules/` có một hàm mẫu và comment TODO kèm cách làm các
tính năng còn lại. Xem [danh mục module](docs/modules.md) và
[luồng dữ liệu trong DB](docs/database-flow.md).

Module nhận `Session` từ caller, không tự commit. Ba mẫu ghi tin nhắn, báo cáo
bình luận và audit log cùng các hàm auth nhận transaction do caller quản lý.
Đã có kết nối PostgreSQL/Session, migration và router auth, chưa gắn các route nghiệp vụ khác. TODO
không phải tính năng đã hoàn thành. Xem [JWT Bearer và refresh/renew](docs/security.md) để tích hợp
token và lưu quyết định thu hồi phiên đúng transaction.

## Cấu hình môi trường

Tạo `.env` ở thư mục gốc từ `.env.example` nếu chưa có:

```powershell
Copy-Item .env.example .env
```

Không chạy lệnh sao chép nếu đã có cấu hình riêng. Không commit `.env`.

| Biến | Ý nghĩa | Khi không khai báo |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Base URL backend, không kèm `/api`; bỏ dấu `/` cuối | Cùng origin frontend; Vite proxy `/api` tới `127.0.0.1:8000` |
| `CORS_ORIGINS` | Origin frontend phân cách bằng dấu phẩy, gồm scheme, hostname và port nếu có | `http://localhost:5173,http://127.0.0.1:5173` |
| `DATABASE_URL` | URL PostgreSQL chứa user/password/host/port/database; nguồn cấu hình DB duy nhất | Setup sinh nếu thiếu |
| `JWT_SECRET_KEY` | Secret JWT chỉ ở backend, ít nhất 32 byte; bắt buộc khi dùng auth | Không có default |
| `JWT_ISSUER`, `JWT_AUDIENCE` | Issuer/audience được chấp nhận | `tutor-web`, `tutor-web-api` |
| `JWT_ACCESS_TTL_SECONDS` | Hạn access JWT | `900` |
| `JWT_REFRESH_TTL_SECONDS` | Hạn tuyệt đối phiên refresh | `604800` |

`.env.example` chỉ khai báo hai biến bắt buộc DATABASE_URL và JWT_SECRET_KEY.
Các biến khác trong bảng là tùy chọn, chỉ thêm khi đổi giá trị mặc định.
SSL/timeout nếu cần đặt ngay trong URL, ví dụ `?sslmode=require&connect_timeout=8`.
Script init_env tự gộp DB_* cũ thành URL, bỏ tham số trùng và giữ nguyên mật khẩu.

Backend đọc `.env` rồi `.env.local` bằng đường dẫn tuyệt đối; biến môi trường
của process được ưu tiên hơn cả hai file. `CORS_ORIGINS` rỗng sẽ không cho phép origin ngoài; wildcard,
credentials và đường dẫn trong origin bị từ chối khi khởi động. Khai báo các
origin production cần dùng trong môi trường deploy; `.env.example` có các domain
đang được dùng trong cấu hình dự án.

Vite đọc `.env` từ thư mục gốc qua `envDir`. Biến `VITE_` được đưa vào mã frontend
khi build: chỉ chứa thông tin public. Khởi động lại dev server sau khi sửa `.env`;
build lại frontend khi thay biến lúc triển khai. Mặc định frontend gọi `/api`
cùng origin. Khi deploy, cấu hình reverse proxy cho `/api` hoặc đặt
`VITE_API_BASE_URL` trỏ tới backend công khai.

Kết nối backend tới Supabase qua `DATABASE_URL`; project URL và publishable
key của frontend không phải thông tin đăng nhập PostgreSQL. Xem
[hướng dẫn Supabase](docs/supabase.md) để cấu hình SSL, migrate và kiểm tra.

## Chạy trên Windows / PowerShell

Dùng Python 3.14, PostgreSQL 18 và Node.js 24. Máy đã có server PostgreSQL, từ gốc repo:

```powershell
python scripts/setup.py
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --app-dir backend
```

Setup tạo venv/.env nếu thiếu, sinh secret riêng và kiểm tra DATABASE_URL. Chỉ
hỏi mật khẩu postgres bằng input ẩn khi cần tạo role/database; nếu đã kết nối
được thì không cần admin. Giữ nguyên secret đã cấu hình. Backend tại
`http://localhost:8000`, docs tại `/api/docs`, liveness `/api/health`, DB readiness
`/api/ready`. Nếu database gián đoạn hoặc chưa migrate, readiness trả 503.

Máy mới dùng Docker có thể chạy `python scripts/setup.py --docker`; nếu cổng
5432 bận, thêm `--db-port 5433`. Linux/macOS dùng `backend/.venv/bin/python` để
chạy backend. Chi tiết cài, kết nối pgAdmin và chuyển dữ liệu:
[database-setup.md](docs/database-setup.md).

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

Backend hiện có 80 test: 13 API/config, 3 metadata, 9 logic module, 5 password,
11 xác thực/schema, 16 JWT/session/Bearer, 12 database/setup/readiness và 11 auth API/rate limit. Test module
dùng SQLite trong bộ nhớ với metadata fixture thích nghi; không thay model
production. Đã migrate/check và smoke test Session/JWT trên PostgreSQL thật;
chưa có kiểm thử cạnh tranh nhiều worker. Dependency cũng đã được resolve với
`pip --dry-run --ignore-installed` để kiểm tra khả năng cài môi trường mới.

## Bước tiếp theo

1. Chốt luồng MVP và vai trò: học viên/phụ huynh, gia sư, quản trị; xác định đăng ký
   tư vấn hay đặt lịch học trực tiếp là luồng chính.
2. PostgreSQL/Session/Alembic đã có; dùng setup khi đổi máy và tạo migration mới
   khi đổi model. Chốt idempotency và quy tắc tiền trong
   [các quyết định còn thiếu](docs/database-flow.md#các-quyết-định-còn-thiếu-trước-khi-viết-luồng-ghi-thật).
3. API auth đã có `POST /api/auth/login`, `POST /api/auth/refresh`,
   `POST /api/auth/logout` và `GET /api/auth/me`, kèm rate limit login theo IP
   trong từng process. Tiếp theo nối form đăng nhập phía frontend và rate limit
   dùng chung khi triển khai nhiều worker. Xem [hợp đồng API auth](docs/security.md#endpoint-đã-triển-khai).
   CORS đã cho GET/POST và Authorization; chưa bật cookie credentials.
4. Chọn một use case trong module để hoàn thiện TODO, request/response schema,
   router và kiểm thử từ đầu đến cuối. Với booking, ưu tiên tạo đơn + buổi học,
   xác thực chủ sở hữu và luồng chat trước khi nối thanh toán.
5. Bổ sung CI, logging, xử lý lỗi thống nhất, kiểm thử trình duyệt và cấu hình
   deploy. Dùng health cho liveness, ready cho DB/schema.

Chi tiết review và giới hạn xem [docs/code-review.md](docs/code-review.md).

## Deploy trên Vercel

Repo có cấu hình [Vercel Services](docs/vercel.md): một project, frontend Vite ở `/`,
backend FastAPI ở `/api/*`. Chọn Root Directory là gốc repo. Xem hướng dẫn để cấu hình
PostgreSQL/Supabase, biến môi trường, kiểm tra bằng `vercel dev`, URL VNPAY và giới hạn
lưu file đính kèm. Giao diện gọi API cùng domain; không cần URL backend riêng.
