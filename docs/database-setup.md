# PostgreSQL với cấu hình tối giản DATABASE_URL

## Hai biến bắt buộc

`.env.example` chỉ cần:

```dotenv
DATABASE_URL=
JWT_SECRET_KEY=
```

Chạy setup để tự sinh giá trị cục bộ nếu thiếu. Format URL:

```text
postgresql+psycopg://tutor_app:<encoded-password>@127.0.0.1:5432/tutor_web
```

URL là nguồn cấu hình DB duy nhất: chứa user, password, host, port, database và
các tùy chọn kết nối. Backend cũng chấp nhận prefix postgresql:// và chuẩn hóa
sang Psycopg 3. Không khai báo DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD nữa.

Khi tự nhập URL, percent-encode ký tự đặc biệt trong password. Script init_env
dùng URL.create/render để chuyển credential cũ an toàn, không đổi mật khẩu DB.
Process DATABASE_URL ưu tiên hơn giá trị trong `.env`; script không chép secret
process đè lên credential cục bộ.

## Những gì không cần đặt lại trong env

| Tùy chọn | Mặc định |
| --- | --- |
| Frontend API | http://localhost:8000 |
| CORS | http://localhost:5173 và http://127.0.0.1:5173 |
| JWT issuer / audience | tutor-web / tutor-web-api |
| Access / refresh TTL | 900 / 604800 giây |
| DB connect timeout | 5 giây |
| DB session timezone | UTC |

CORS_ORIGINS, VITE_API_BASE_URL và các biến JWT tùy chỉnh vẫn được hỗ trợ, chỉ
cần thêm khi đổi default, ví dụ domain deploy. init_env bỏ override trùng default
nhưng giữ giá trị khác default. CORS production đang có trong `.env` được giữ.

SSL/timeout đặt trong URL nếu cần, không thêm biến riêng:

```text
postgresql+psycopg://user:encoded_password@host:5432/database?sslmode=require&connect_timeout=8
```

## Máy đã cài PostgreSQL

Cần Python 3.14, PostgreSQL 18 đang chạy. pgAdmin4 dùng để quản lý; pgAdmin không
thay thế server. Từ thư mục gốc repo:

```powershell
python scripts/setup.py
```

Script tạo venv, cài requirements, tạo/chuyển `.env`, thử kết nối DATABASE_URL.
Nếu đã kết nối bằng role không superuser thì bỏ qua admin. Nếu phải tạo DB/role,
script hỏi mật khẩu postgres bằng input ẩn, không lưu mật khẩu admin vào `.env`.
Role mới không có superuser/create-db/create-role. Không reset password role cũ
hoặc chiếm DB của chủ khác; URL phải chứa credential đúng nếu đối tượng đã có.

Sau đó script chạy migration và check_db. Dùng được trên Windows/Linux/macOS;
Python dùng đường dẫn venv tương ứng, không hardcode đường dẫn cài PostgreSQL.
Nếu admin có tên khác postgres, chạy bootstrap thủ công với --admin-user.

Chạy backend trên Windows:

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --app-dir backend
```

Linux/macOS dùng `backend/.venv/bin/python` thay đường dẫn Scripts/python.exe.

## Máy mới dùng Docker

Cần Python 3.14 và Docker có Compose, bật Docker engine rồi chạy:

```powershell
python scripts/setup.py --docker
```

Cổng DB lấy từ DATABASE_URL. Nếu 5432 bận:

```powershell
python scripts/setup.py --docker --db-port 5433
```

--db-port sửa port trong DATABASE_URL, không tạo DB_PORT. Nếu URL do process
environment cung cấp, sửa port trực tiếp ở URL thay vì dùng --db-port.

Admin Docker lưu bằng password file `.local/postgres-admin-password`, mount
qua Compose secret, không thêm admin password vào `.env`. File được tạo một lần,
giữ nguyên khi chạy lại và đã được gitignore. Backend vẫn dùng role ứng dụng
riêng, không dùng tài khoản admin container.

Setup truyền cổng suy ra từ URL vào tiến trình Compose, không lưu thêm cấu hình
cổng trong `.env`. Dùng setup khi tạo/cập nhật container với cổng tùy chỉnh;
`docker compose up` trực tiếp mặc định publish 5432. `docker compose down` dừng
container và giữ volume postgres_data. PostgreSQL 18 dùng volume tại
/var/lib/postgresql. Docker chưa được chạy thử trên máy phát triển hiện tại.

## Chuyển từ cấu hình DB_* cũ

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/init_env.py
```

Nếu dùng Docker đã có volume, chạy thêm --docker ngay lần chuyển để giữ admin
credential cũ trong password file. Script gộp host/port/user/password/database
và các SSL/timeout khác default vào URL; xóa các biến cũ cùng PG_ADMIN_* khỏi
`.env`. Không thay mật khẩu PostgreSQL hoặc JWT secret. DATABASE_URL đã có thì
được giữ; code runtime không còn đọc DB_*.

## pgAdmin4

Register → Server → Connection. Tách các phần từ DATABASE_URL:

| Trường | Giá trị hiện tại |
| --- | --- |
| Host / port | 127.0.0.1 / 5432, hoặc port đã đổi trong URL |
| Maintenance database | tutor_web |
| Username | tutor_app |
| Password | Phần password của DATABASE_URL sau khi URL-decode |

Mật khẩu mở pgAdmin khác mật khẩu database. Sau kết nối, xem public → Tables:
25 bảng ứng dụng và alembic_version. Dùng role riêng trong URL khi triển khai
môi trường khác; không đưa URL hoặc password vào frontend/VITE_.

## Kiểm tra và migration

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/check_db.py
.\backend\.venv\Scripts\python.exe -m alembic -c alembic.ini current
.\backend\.venv\Scripts\python.exe -m alembic -c alembic.ini check
```

`/api/health` là liveness, `/api/ready` kiểm tra DB/schema/migration head và trả
503 an toàn nếu lỗi. Lifespan tạo engine/pool và dispose khi tắt; Session mỗi
request không tự commit. Không tự create_all khi startup.

Khi đổi model, tạo revision mới bằng `alembic revision --autogenerate -m "change"`,
review enum/data migration, chạy upgrade head rồi check. Migration đầu tiên là
snapshot cố định 25 bảng/15 enum; không sửa revision đã áp dụng.

Nếu auth dependency đã query Session thì transaction đã autobegin: endpoint
commit tường minh sau use case, không begin lồng. Refresh phải commit quyết
định thu hồi trước 401: [security.md](security.md#transaction-khi-renew-bị-từ-chối).

## Chuyển máy và dữ liệu

Clone + setup tạo schema rỗng. Venv, `.env` và `.local` không commit/copy giữa
các máy; tạo lại bằng setup. Kiểm tra `.python-version` là Python 3.14.

Nếu cần dữ liệu cũ: backup Custom bằng pgAdmin/pg_dump, bootstrap database trống,
restore no-owner/no-privileges **trước** migration tạo bảng, rồi upgrade head và
check_db. Dump có cả bảng và alembic_version, không restore bừa vào schema đã
migrate. JWT secret mới làm token cũ vô hiệu dù restore auth_sessions.

Quy trình thủ công khi cần restore:

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\backend\.venv\Scripts\python.exe backend/scripts/init_env.py
.\backend\.venv\Scripts\python.exe backend/scripts/bootstrap_db.py
# Restore full dump vào database trống tại đây nếu cần.
.\backend\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
.\backend\.venv\Scripts\python.exe backend/scripts/check_db.py
```

Tham khảo [SQLAlchemy/Psycopg](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg),
[Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html),
[PostgreSQL image](https://hub.docker.com/_/postgres).
