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

Đây là lệnh CLI tạo dữ liệu phát triển, bao gồm quyền quản trị theo yêu cầu;
không được thêm thành endpoint công khai hoặc tự chạy khi khởi động server.
