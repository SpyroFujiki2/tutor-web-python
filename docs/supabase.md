# Backend FastAPI và Supabase PostgreSQL

Backend giữ SQLAlchemy, Alembic, JWT và các transaction hiện có. Supabase
cung cấp PostgreSQL được quản lý. Không cần chuyển các thao tác ví/booking
sang REST API hoặc thay đăng nhập hiện tại bằng Supabase Auth.

## Thông tin kết nối

`VITE_SUPABASE_URL` và `VITE_SUPABASE_PUBLISHABLE_KEY` là cấu hình API công
khai dành cho frontend. Hai biến này không chứa mật khẩu PostgreSQL và không
thay thế `DATABASE_URL`. Backend SQLAlchemy không cần publishable key hoặc
secret API key để kết nối PostgreSQL.

Trong project Supabase, chọn **Connect → Transaction pooler**, sao chép
connection string và thay phần mật khẩu bằng mật khẩu database. Giữ nguyên
hostname và username do Dashboard cung cấp; không suy đoán pooler host từ
project URL hoặc region.

Đặt chuỗi kết nối vào `DATABASE_URL` trong `.env` hoặc `.env.local`.
Backend ưu tiên theo thứ tự:

1. Biến môi trường của process/Vercel.
2. `.env.local` ở gốc repo.
3. `.env` ở gốc repo.

`.env.seed` chỉ chứa dữ liệu cấu hình seed và không được nạp làm cấu hình
runtime. Giữ mật khẩu DB ở file local hoặc Vercel Environment Variables;
không gửi nguyên connection string lên chat/Git.

Ví dụ cấu trúc, không phải thông tin kết nối thật:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres.PROJECT_REF:ENCODED_PASSWORD@POOLER_HOST:6543/postgres?sslmode=require
```

`postgres://` và `postgresql://` từ Dashboard cũng được chuẩn hóa sang
`postgresql+psycopg`. Các ký tự đặc biệt trong mật khẩu phải được URL-encode.
Với hostname Supabase, backend mặc định thêm `sslmode=require` nếu thiếu;
giữ nguyên `verify-ca`/`verify-full` khi đã cấu hình certificate. Kết nối
Supabase dùng `sslmode=disable`, `allow` hoặc `prefer` bị từ chối.

Pooler ở cổng 6543 không dùng prepared statements hay startup options.
Backend đặt UTC trong từng transaction. Trên Vercel, pool của mỗi instance
giới hạn một connection như cấu hình trong [Vercel Services](vercel.md).

## Schema và kiểm tra

Supabase đã tạo database; không tạo database/role bằng bootstrap local.
Nếu cấu hình Supabase sai hoặc mất kết nối, script bootstrap dừng và không
hỏi mật khẩu quản trị PostgreSQL local để thử tiếp.

Chạy migration bằng direct connection hoặc session pooler, sau đó dùng
transaction pooler cho backend. Khi `DATABASE_URL` trong terminal trỏ đúng
database cần migrate, chạy từ gốc repo:

```powershell
.\backend\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
```

Migration `0002_backend_only_access` bật RLS cho các bảng của ứng dụng và
`alembic_version`, không tạo policy cho Data API. Backend phải dùng database
owner hoặc role có BYPASSRLS; các role `anon`/`authenticated` không được
đọc/ghi trực tiếp dữ liệu qua publishable key. Không sửa các schema
`auth`/`storage` của Supabase.

Kiểm tra cả kết nối, các bảng và phiên bản migration:

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/check_db.py --require-supabase
```

Tùy chọn này từ chối database local trước khi mở connection. Lệnh không
ghi dữ liệu, không seed và không in mật khẩu. Sau khi kiểm tra thành công,
khởi động lại backend và kiểm tra `/api/ready`.

Trên Vercel, đặt `DATABASE_URL` và `JWT_SECRET_KEY` trong Environment
Variables rồi redeploy. Các file `.env*` local không được upload. Nếu dùng
JWT riêng hiện tại, giữ `JWT_SECRET_KEY` riêng; publishable key của Supabase
không phải khóa ký JWT.

Lưu file đính kèm lên Supabase Storage là phần tích hợp riêng, không tự xảy
ra khi đổi `DATABASE_URL`.

Tham khảo:

- [Supabase PostgreSQL connections](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Supabase API keys](https://supabase.com/docs/guides/getting-started/api-keys)
- [Securing Supabase data](https://supabase.com/docs/guides/database/secure-data)
