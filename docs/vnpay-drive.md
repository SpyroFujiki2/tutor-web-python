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

Trường **Website/AddressWebsite** trong form đăng ký sandbox chỉ khai báo địa
chỉ website; điền URL IPN vào trường đó chưa xác nhận IPN đã được cấu hình.
Theo [hướng dẫn PAY](https://sandbox.vnpayment.vn/apis/docs/thanh-toan-pay/pay.html),
sau khi cài đặt endpoint cần gửi URL này cho VNPAY. Liên hệ kỹ thuật tại
`kythuatctt@vnpay.vn` theo [trang liên hệ chính thức](https://sandbox.vnpayment.vn/apis/contact/),
ghi rõ môi trường sandbox, TmnCode hiện tại và URL IPN HTTPS; yêu cầu xác nhận
URL đã được gắn cho đúng TmnCode. Không gửi HashSecret hoặc mật khẩu.
Đổi merchant cần cấu hình IPN cho merchant mới; đổi biến `.env`/Vercel không
tự cập nhật cấu hình ở hệ thống VNPAY.

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

`--probe` còn ký một request cho UUID ngẫu nhiên không tồn tại, không gửi trạng
thái thành công: backend phải trả `RspCode=01`. Nếu probe không chữ ký qua nhưng
probe có chữ ký trả 97, kiểm tra lại TmnCode/HashSecret theo môi trường Vercel
và redeploy. Không chỉ dùng phản hồi 97 của URL trống để kết luận cấu hình đúng.

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

Ví tự làm mới số dư và đơn mỗi 15 giây khi trang đang hiển thị. Đơn VNPAY
thành công được cập nhật `success` và cộng credit ngay trong transaction xử lý
IPN hợp lệ, không có bước admin duyệt. Giao diện ví và quản trị hiển thị rõ
cơ chế tự động này; chỉ đơn chuyển khoản thủ công và rút tiền giữ bước đối soát.

- Giá VND/credit lấy từ gói trong DB và snapshot vào `cash_order`.
- Mã tham chiếu là UUID đơn dạng hex; các lần thử lại cùng request không tạo đơn mới.
- Tất cả tham số `vnp_` được sắp xếp, URL encode rồi ký HMAC-SHA512; amount gửi
  sang VNPAY là số VND nhân 100 theo giao thức.
- Chỉ IPN hoặc QueryDR đã xác minh, đúng merchant/đơn/số tiền và trạng thái
  thanh toán `00` mới cộng ví. Với QueryDR, mã API `00` chưa đủ: phải kiểm tra
  cả `vnp_TransactionStatus=00` và `vnp_TransactionType=01`.
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

### Khi thanh toán thành công nhưng ví còn chờ

Trang kết quả giữ `GET /api/payments/vnpay/return` chỉ đọc. Nếu người dùng đang
đăng nhập và đơn vẫn pending sau 15 giây, trang gửi một POST có xác thực tới
`/api/payments/vnpay/orders/{order_id}/verify`. Chủ đơn cũng có nút kiểm tra
trong trang kết quả và mục Ví. Không dùng tham số từ trình duyệt để cộng ví.

Backend lấy mã tham chiếu, ngày tạo giao dịch và số tiền từ đơn đã lưu, gọi
QueryDR server-to-server, xác minh HMAC-SHA512 theo định dạng pipe riêng của
QueryDR và đối chiếu lại phản hồi với đơn. Network timeout, phản hồi lỗi 99,
JSON không hợp lệ, chữ ký sai hoặc dữ liệu không khớp đều giữ đơn pending.
Đơn cũ thuộc merchant khác không được truy vấn bằng khóa của merchant mới.

`vnp_IpAddr` của QueryDR lấy từ cấu hình `VNPAY_QUERY_IP` nếu có, hoặc địa chỉ
server trong ASGI; trường hợp server không có địa chỉ IP hợp lệ dùng loopback
`127.0.0.1`. Không dùng IP khách hàng hoặc header forwarded cho truy vấn này.
Địa chỉ listener có thể là IP nội bộ/loopback và không xác định được IP public
sau NAT. Nếu VNPAY yêu cầu IP public của server, cần đặt `VNPAY_QUERY_IP` theo
cấu hình mạng đã xác nhận của môi trường chạy; không đoán từ IP người dùng.
Cấu hình IP QueryDR sai chỉ làm bước kiểm tra đơn thất bại, không tắt IPN.

Theo đặc tả, `vnp_Command` trong phản hồi QueryDR là tùy chọn. Backend xác minh
HMAC trên dữ liệu gốc, chấp nhận thiếu/rỗng trường này; nếu có giá trị phải là
`querydr`. Không tự chèn giá trị mặc định vào dữ liệu trước khi kiểm chữ ký.

Mỗi đơn chỉ được truy vấn lại sau 5 phút, được bảo vệ bằng metadata
trong DB để nhiều tab/worker không gọi dồn API. Reservation được commit và
nhả connection/khóa trước khi gọi VNPAY; sau phản hồi, backend khóa và đọc lại
đơn. IPN và QueryDR dùng chung transaction ghi ví/ledger, nên IPN đến trong
lúc truy vấn hoặc đến muộn không cộng trùng. Audit phân biệt `vnpay.ipn` và
`vnpay.querydr`.

Trong Vercel Runtime Logs, lọc `VNPAY IPN` / `VNPAY QueryDR` để thấy mã phản
hồi, mã đơn và loại lỗi. Không log HashSecret, chữ ký hoặc toàn bộ query string.
Lỗi QueryDR được phân loại `http_<status>`, `timeout`, `tls_error`, `dns_error`,
`network_error`, `http_protocol_error`, `invalid_json`, `response_too_large`
hoặc lỗi kiểm chữ ký/dữ liệu. Mã nhà cung cấp `99` được giữ nguyên và chưa đủ
để xác định nguyên nhân hoặc kết luận giao dịch thanh toán thất bại.
HTTP 200 của IPN không đủ để kết luận đã cộng ví: cần kiểm tra JSON RspCode
và audit/ledger. Nếu không có request IPN từ VNPAY, kiểm tra đăng ký URL theo
đúng TmnCode và kiểm tra Deployment Protection/Firewall; ứng dụng không thể
tự nhận một webhook chưa được VNPAY gửi tới.
Việc chưa thấy IPN trong log cũng chưa đủ chứng minh URL chưa đăng ký; cần
đối chiếu cấu hình riêng của đúng merchant và lịch sử gửi callback phía VNPAY.

## YouTube

Link `watch?v=...`, `youtu.be/...`, `/shorts/...`, `/live/...` và `/embed/...`
được chuẩn hóa thành trình phát nhúng YouTube trên trang bài học. IFrame API
cung cấp thời lượng và vị trí phát để tự lưu qua `/watch` mỗi 10 giây, khi
dừng/kết thúc/đổi bài. Thời gian tua không được tính; dữ liệu chờ lưu được
giữ trong trình duyệt để thử gửi lại sau lỗi mạng.

Iframe dùng `enablejsapi`, origin thực tế của website và
`referrerPolicy=strict-origin-when-cross-origin` để giữ định danh website.
Không tải/xử lý lại luồng video YouTube và không cần API key. Video riêng tư,
bị xóa, hạn chế quyền nhúng hoặc bị trình duyệt chặn được báo bằng thông báo
hướng tới người học, có lựa chọn thử lại/xem trên YouTube.
Xem [tài liệu IFrame API](https://developers.google.com/youtube/iframe_api_reference).

## Google Drive

Thư mục nguồn do người dùng cung cấp:
[10 video bài giảng](https://drive.google.com/drive/folders/1WM8foEk5gsIMs0OikFlnIiKwp7MvYplF).

Giao diện bài học nhận link `file/d/.../view`, `/preview` hoặc `open?id=...`.
Trình phát thử URL tải trực tiếp bằng HTML video để lấy metadata thời lượng
và sự kiện phát. Nếu Drive không cho phát trực tiếp, giao diện chuyển sang
iframe preview ngay trên trang và thông báo tiến độ ở chế độ dự phòng chưa
được lưu. Không suy đoán thời gian xem từ thời gian iframe đang mở.
Chỉ trang bài học có quyền còn hạn mới nhận URL media từ backend. Không proxy
tải video qua backend và không đổi quyền chia sẻ file/thư mục. Để theo dõi
đầy đủ trong production, dùng URL video hỗ trợ phát trực tiếp; Drive preview
không hỗ trợ lấy sự kiện phát của video qua iframe khác origin.

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
credit. Khi chưa biết thời lượng, để null; không tự tạo thời lượng video.
Trình phát tự gửi thời lượng (giây) khi lấy được metadata và thời gian xem
qua API `/watch`. Metadata này giống thời gian xem: do trình duyệt báo về,
không phải bằng chứng chống gian lận. Vẫn cần điểm do quản trị chấm để có
kết quả cuối. Nút đánh dấu thủ công đã được bỏ khỏi giao diện.

Không có title riêng trong model `lessons`, nên tên gốc được giữ ở manifest;
giao diện hiển thị thứ tự Bài 1–10 theo schema hiện có.
