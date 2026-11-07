# Seed tài khoản và gói gia sư

Chạy từ thư mục `backend`:

```powershell
.\.venv\Scripts\python.exe -m scripts.seed_demo --dry-run
.\.venv\Scripts\python.exe -m scripts.seed_demo
```

Seed tạo một tài khoản cho từng role trong schema: `guest`, `member`, `student`,
`trainee_tutor`, `tutor`, `admin`, `head_admin`. Email có dạng
`<role>@tutor.example.com`; mật khẩu riêng được sinh ngẫu nhiên, hash Argon2id
trong DB và lưu thông tin đăng nhập vào `.env.seed` ở gốc repo. File này đã được
loại khỏi Git bằng quy tắc `.env.*` và không được Vite phục vụ qua HTTP.
Không gửi email hoặc thay đổi các khóa trong `.env` của ứng dụng.

Ba gói `Gia sư Cơ bản (mẫu)`, `Gia sư Nâng cao (mẫu)`, `Gia sư Chuyên sâu (mẫu)`
có giá khác nhau, ngẫu nhiên trong khoảng 100.000–500.000 **credit**, bước 10.000.
Giá ban đầu được lưu trong `.env.seed`. Đây là gói gia sư (`tutoring_package`);
gói nạp credit và khóa video Drive có script/luồng riêng.

Mỗi tài khoản có ví cá nhân bằng 0; tutor/admin/head admin có thêm ví gia sư.
Ví nền tảng và tài khoản hệ thống không đăng nhập được được khởi tạo riêng.
Seed không tạo số dư, đơn nạp, booking hoặc thanh toán VNPAY.

UUID cố định giúp chạy lại không tạo tài khoản/gói trùng, không đặt lại mật khẩu
hoặc giá đã chỉnh trong DB. Không chiếm email của tài khoản khác, không tự
kích hoạt lại tài khoản/ví đã khóa. Nếu đã đổi email/role của tài khoản seed,
lệnh dừng để tránh ghi đè. Giữ `.env.seed` để dùng lại mật khẩu ban đầu; nếu
đã đổi mật khẩu qua ứng dụng thì dùng mật khẩu mới, seed không đặt lại mật khẩu.
`--dry-run` không ghi file mật khẩu và rollback toàn bộ thay đổi DB.

## Seed trên Supabase sau khi deploy

Deploy code lên Vercel hoặc chạy migration chỉ chuẩn bị ứng dụng/schema;
không sao chép dữ liệu đã seed ở database local sang Supabase. Script seed
ghi vào database mà `DATABASE_URL` đang trỏ tới, theo thứ tự ưu tiên: biến
môi trường của terminal, `.env.local`, rồi `.env`. Cấu hình `CORS_ORIGINS`
không tạo hay chuyển tài khoản.

Đảm bảo `DATABASE_URL` dùng cùng project/database Supabase với biến
`DATABASE_URL` của backend trên Vercel. Giữ file `.env.seed` hiện có để dùng
lại email/mật khẩu đã tạo. Sau khi migration hoàn tất, chạy từ gốc repo:

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/check_db.py --require-supabase
Push-Location backend
.\.venv\Scripts\python.exe -m scripts.seed_demo --dry-run
.\.venv\Scripts\python.exe -m scripts.seed_demo
Pop-Location
```

Chỉ tiếp tục seed khi bước kiểm tra xác nhận Supabase và migration ở head;
chỉ chạy lệnh ghi thật khi `--dry-run` thành công. Nếu thiếu schema hoặc
migration cũ, làm theo [hướng dẫn Supabase](supabase.md) trước.

Ứng dụng dùng bảng `public.users` và JWT của backend, nên các tài khoản này
không xuất hiện trong mục **Authentication → Users** (`auth.users`) của
Supabase. Kiểm tra trong **Table Editor → public → users**, hoặc chạy truy
vấn chỉ đọc trong SQL Editor:

```sql
SELECT email, role, status
FROM public.users
WHERE email LIKE '%@tutor.example.com'
ORDER BY role;
```

Đăng nhập website bằng email/mật khẩu trong `.env.seed`. Không cần upload
file này hay khai báo các biến `SEED_*` trên Vercel; backend xác thực bằng
password hash trong database. Nếu đã seed đúng Supabase nhưng website vẫn
không nhận tài khoản, kiểm tra lại `DATABASE_URL` của môi trường Vercel đang
truy cập và redeploy nếu vừa thay biến môi trường.

Đây là lệnh CLI tạo dữ liệu phát triển, bao gồm quyền quản trị theo yêu cầu;
không được thêm thành endpoint công khai hoặc tự chạy khi khởi động server.
