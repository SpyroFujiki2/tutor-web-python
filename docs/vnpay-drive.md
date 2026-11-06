# VNPAY sandbox và bài giảng Google Drive

Các chức năng tài khoản/cộng đồng/lịch học được hoàn thiện và kiểm tra trước.
Tài liệu này mô tả phần tích hợp tiếp theo, gồm các việc cần quyền ngoài repo.

## VNPAY

Đăng ký thông tin kết nối sandbox từ [trang giới thiệu chính thức](https://sandbox.vnpayment.vn/apis/docs/gioi-thieu/).
Sau khi được cấp thông tin, điền vào `.env` ở gốc repo, không đưa secret lên chat/Git:

```dotenv
VNPAY_TMN_CODE=<TmnCode sandbox được cấp>
VNPAY_HASH_SECRET=<HashSecret sandbox được cấp>
VNPAY_PAYMENT_URL=https://sandbox.vnpayment.vn/paymentv2/vpcpay.html
VNPAY_RETURN_URL=https://<public-host>/payment/vnpay-return
```

`vnp_TmnCode`, `vnp_HashSecret`, `vnp_Url` trong email tương ứng ba biến
`VNPAY_TMN_CODE`, `VNPAY_HASH_SECRET`, `VNPAY_PAYMENT_URL`. Tài khoản/mật khẩu
Merchant Admin và SIT chỉ dùng đăng nhập portal, không cần điền vào backend.

Mặc định dùng `https://sandbox.vnpayment.vn/paymentv2/vpcpay.html`, API 2.1.0,
HMAC-SHA512, thời hạn 15 phút và giờ Việt Nam. Không có credential mặc định.
Khi chưa cấu hình, `/api/payments/vnpay/status` trả `enabled=false`; checkout
trả 503 rõ ràng và không tạo đơn nạp. Cấu hình VNPAY được đọc theo request;
tải lại trang Ví sau khi điền xong `.env`. Các gói nạp qua VNPAY cần
giá tối thiểu **5.000 VND**, theo [FAQ VNPAY](https://sandbox.vnpayment.vn/apis/docs/faqs/).

Gửi cho VNPAY địa chỉ **IPN HTTPS có thể truy cập từ Internet** theo yêu cầu
email, hoặc nhập vào mục cấu hình IPN nếu portal merchant hỗ trợ:

```text
https://<backend-public-host>/api/payments/vnpay/ipn
```

Localhost không nhận được IPN từ máy chủ VNPAY. Khi thử local, dùng hostname
HTTPS/tunnel trỏ tới backend và cấu hình đúng trên portal. Nếu backend sau proxy,
chỉ cho Uvicorn tin proxy headers từ địa chỉ proxy đã xác định.

Khi dùng Quick Tunnel cho cả giao diện và API, chạy backend ở cổng 8000,
frontend ở cổng 5173, rồi chạy `cloudflared tunnel --url http://127.0.0.1:5173`.
Đặt `TUNNEL_HOSTNAME=<hostname mới>.trycloudflare.com` trong `.env.local` ở gốc
repo và khởi động lại Vite. Chỉ điền hostname, không có `https://` hoặc đường dẫn.
Frontend mặc định gọi `/api` cùng origin; Vite chuyển tiếp tới backend cổng 8000.
IPN khi đó là `https://<hostname mới>.trycloudflare.com/api/payments/vnpay/ipn`.
Quick Tunnel đổi URL mỗi lần chạy lại; cập nhật hostname trong `.env.local` và
URL đã đăng ký với VNPAY. Giữ tiến trình cloudflared chạy trong suốt thời gian thử.

Kiểm tra cấu hình và đường dẫn công khai từ thư mục `backend`:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_vnpay --probe
```

Lệnh chỉ đọc cấu hình, readiness, trạng thái VNPAY và gửi một IPN không có chữ ký
để kiểm tra bị từ chối với `RspCode=97`. Không tạo đơn, không cộng ví, không in
TmnCode/HashSecret và không xác nhận thay VNPAY rằng IPN đã được đăng ký.
IPN chưa cấu hình trả HTTP 503; IPN thiếu/sai chữ ký sau khi cấu hình hợp lệ trả
HTTP 200 kèm `RspCode=97`, đây là kết quả mong đợi khi mở URL trống trên trình duyệt.

Nếu chưa có gói nạp phù hợp, đăng nhập tài khoản quản trị ứng dụng và tạo gói
trong mục quản lý gói credit, với giá tối thiểu 5.000đ. Tài khoản Merchant Admin
VNPAY và tài khoản quản trị ứng dụng là hai tài khoản riêng.

Sau khi VNPAY đăng ký IPN, thử giao dịch từ **Ví → chọn gói nạp từ 5.000đ →
VNPAY sandbox**. Sử dụng thẻ test trong email: NCB, `9704198526191432198`,
`NGUYEN VAN A`, ngày phát hành `07/15`, OTP `123456`. Thông tin này chỉ dành cho
môi trường sandbox. Đối chiếu mã đơn/số tiền với
[Merchant Admin](https://sandbox.vnpayment.vn/merchantv2/) và chạy các kịch bản
được yêu cầu tại [SIT](https://sandbox.vnpayment.vn/vnpaygw-sit-testing/user/login).
Kiểm tra giao dịch thành công cộng đúng credit một lần, hủy/thất bại không cộng
credit, callback lặp không cộng lại và Return URL không tự cộng ví khi IPN đến chậm.

Luồng giao diện: **Ví → chọn gói nạp → VNPAY sandbox → tạo đơn → mở VNPAY**.
Cổng thanh toán được mở ở tab riêng để giữ phiên trong tab Tutor Web ban đầu.
Sau thanh toán, quay lại mục Ví và cập nhật số dư/đơn.

- Giá VND/credit lấy từ gói trong DB và snapshot vào `cash_order`.
- Mã tham chiếu là UUID đơn dạng hex; các lần thử lại cùng request không tạo đơn mới.
- Tất cả tham số `vnp_` được sắp xếp, URL encode rồi ký HMAC-SHA512; amount gửi
  sang VNPAY là số VND nhân 100 theo giao thức.
- Chỉ IPN hợp lệ, đúng merchant/đơn/số tiền và hai mã trạng thái `00` mới cộng ví.
- Callback khóa đơn/ví, cộng credit, ghi ledger/audit và cập nhật trạng thái cùng
  một transaction. Lỗi commit rollback cả quy trình; callback lặp không cộng lại.
- Return URL chỉ xác minh và hiển thị. Redirect của trình duyệt không cộng tiền.
- Đơn VNPAY không được xác nhận thủ công qua API admin.
- Metadata VNPAY được lưu trong JSON `cash_order.bank_info` của đơn nạp;
  số tài khoản của đơn rút vẫn dùng snapshot cũ. Response chỉ thêm provider và
  thời hạn thanh toán, không trả JSON nội bộ hoặc thông tin ngân hàng.

Mã IPN: `00` cập nhật thành công, `02` đã xử lý, `01` không tìm thấy đơn, `04`
sai số tiền, `97` chữ ký sai, `99` chờ xử lý cuối/lỗi cần thử lại. Quy tắc tham số
và IPN tham chiếu [tài liệu PAY chính thức](https://sandbox.vnpayment.vn/apis/docs/thanh-toan-pay/pay.html).

Tích hợp này phục vụ nạp credit. Rút tiền được quản trị đối soát; hoàn credit cho
khóa/booking là bút toán nội bộ. API hoàn VND sang ngân hàng qua VNPAY cần triển
khai riêng theo hợp đồng merchant. Test tự động dùng chữ ký và callback giả lập;
chỉ xem kiểm thử sandbox thực tế hoàn tất sau khi thẻ test đã thanh toán, IPN
VNPAY thực sự cập nhật đúng ví và các kịch bản SIT đạt yêu cầu.

## Google Drive

Thư mục nguồn do người dùng cung cấp:
[10 video bài giảng](https://drive.google.com/drive/folders/1WM8foEk5gsIMs0OikFlnIiKwp7MvYplF).

Giao diện bài học nhận link `file/d/.../view`, `/preview` hoặc `open?id=...`,
chuẩn hóa về iframe preview Google Drive và có nút mở trên Drive. Chỉ trang bài
học có quyền còn hạn mới nhận URL media từ backend. Không proxy tải video qua
backend và không đổi quyền chia sẻ file/thư mục.

Quyền Drive vẫn cần phù hợp với người xem. Người có link và quyền Drive có thể
mở video ngoài website; cách lưu trữ tạm này không tạo DRM hoặc URL hết hạn.

Seed được chuẩn bị tại `backend/seed/drive-course.json`. Cần đúng **10 link video
thật, khác nhau**; không dùng link thư mục thay link video. Phần videos đang để
trống khi tài khoản kết nối chưa đọc được thư mục, vì vậy chưa tạo khóa giả.
Ví dụ cấu trúc một phần tử (thay bằng link thật, đủ 10 phần tử):

```json
{"url": "https://drive.google.com/file/d/<file-id>/view", "title": "Tên bài", "duration_minutes": null}
```

Từ thư mục backend:

```powershell
.\.venv\Scripts\python.exe -m scripts.seed_drive_course --dry-run
.\.venv\Scripts\python.exe -m scripts.seed_drive_course
```

Script kiểm tra manifest trước khi kết nối DB; tạo một course và 10 lesson
trong cùng transaction. UUID được suy ra từ thư mục/file ID. Chạy lại cùng nội
dung không tạo trùng, không ghi đè khóa đã có dữ liệu khác. Giá seed mặc định 0
credit. Khi chưa biết thời lượng, để null; không tự tạo thời lượng video. Nút
đánh dấu đã xem là tự khai và vẫn cần điểm do quản trị chấm để có kết quả cuối.

Không có title riêng trong model `lessons`, nên tên gốc được giữ ở manifest;
giao diện hiển thị thứ tự Bài 1–10 theo schema hiện có.
