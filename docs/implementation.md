# Trạng thái triển khai — 06/11/2026

Ứng dụng đã nối React với API nghiệp vụ FastAPI. Schema gốc vẫn gồm 24 bảng
DBML và bảng bổ sung `auth_sessions`; không có migration mới trong đợt này.
Các khối TODO trong code gốc được giữ nguyên theo yêu cầu. TODO là ghi chú thiết
kế ban đầu; danh sách dưới đây và OpenAPI `/docs` phản ánh code đang chạy.

## Tài khoản và xác thực

- Đăng ký email chuẩn hóa, hash Argon2id, role `member` do server quyết định.
- Đăng nhập, refresh rotation, logout, logout-all, kiểm tra phiên và user từ DB.
- Đổi mật khẩu/email cần mật khẩu hiện tại, thu hồi tất cả phiên cùng transaction.
- Xem các phiên còn hạn; thu hồi từng phiên đúng chủ. Response không có hash/token.
- Quản trị đổi trạng thái user theo bậc quyền, có audit; không tự khóa chính mình
  hoặc khóa tài khoản hệ thống/head admin.
- Dọn các phiên đã hết hạn hơn 30 ngày qua API quản trị, có nhật ký.
- Frontend giữ token trong bộ nhớ, tự refresh và chỉ cho một refresh chạy đồng thời.
  Tải lại trang cần đăng nhập lại. Rate limit login theo IP trong từng process.

Tạo quản trị đầu tiên (không có tài khoản/mật khẩu mặc định):

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.create_admin --email admin@example.com
```

Lệnh hỏi mật khẩu bằng input ẩn; chỉ tạo tài khoản mới khi chưa có head admin.
Sau đó dùng luồng yêu cầu nâng bậc để cấp quyền cho tài khoản khác.

Schema `users` chỉ có email, mật khẩu, role/status và thời gian hoạt động. Giao
diện không tự thêm nickname/avatar vào bảng; bài viết dùng tên thành viên theo
mã user. Khôi phục mật khẩu qua email cần dịch vụ email và thiết kế token riêng.

## Cộng đồng và kiểm duyệt

- Tạo, sửa, ẩn bài viết/bình luận đúng chủ; quản trị có luồng xem bài ẩn và ẩn/hiện.
- Lọc cấp role trong SQL trước phân trang/tìm kiếm; từ khóa được tìm theo nghĩa đen.
- Bài viết hỗ trợ `before_id`; bình luận hỗ trợ `after_id`, cùng `limit/offset`.
- Parent bình luận cố định sau tạo, cùng post; không thể tạo chu trình bằng API.
  Khi cha bị ẩn, con vẫn hiển thị và chỉ giữ mã cha, không nhúng nội dung cha.
- Báo cáo trùng đang chờ trả lại cùng bản ghi; tối đa 5 báo cáo mới/phút/user.
- Quản trị nhận báo cáo, xem ngữ cảnh được giao, duyệt/từ chối và audit nguyên tử.
  Người liên quan không được tự xử lý báo cáo của mình.
- Nâng đúng một bậc, một yêu cầu pending/user. Duyệt kiểm tra lại snapshot role
  và trạng thái hiện tại. Yêu cầu lỗi thời vẫn có thể bị từ chối để gửi lại.
- Audit chỉ lưu trường được cho phép theo loại đối tượng, có lọc user/target;
  API không hỗ trợ sửa/xóa log. Nội dung cộng đồng hiển thị dưới dạng text React.

## Khóa học và tiến độ

- Danh mục/tìm kiếm khóa visible; quản trị tạo/sửa/ẩn khóa và quản lý thứ tự bài.
- Không đổi loại Live/VOD hoặc thêm/sửa/xóa nội dung bài sau khi đã có học viên;
  đổi thứ tự bài vẫn được hỗ trợ với khóa course và xử lý unique constraint.
- Người mua còn hạn truy cập bài kể cả khi khóa hidden. Lịch sử tiến độ vẫn
  được xem sau khi quyền hết hạn/hủy.
- Điểm danh trực tiếp chỉ do quản trị ghi nhận, kiểm tra bài và quyền cùng khóa.
- Tiến độ/kết quả do server tính: các bài có trọng số ngang nhau, điểm tổng kết
  là trung bình ba điểm giữa kỳ/cuối kỳ/thực hành, làm tròn half-up. Xuất sắc
  từ 85, đạt từ 50, dưới 50 không đạt. Cần đủ bài và đủ điểm mới đạt 100%.
- Tín hiệu xem VOD tự khai không được dùng làm điểm thi tin cậy. Phần nhà cung
  cấp video, seed Drive và cơ chế phát video được thực hiện sau nhóm code này.

## Gia sư, lịch học và trao đổi

- Đơn có ít nhất một buổi; lịch có thể chưa chốt. Khoảng giờ phải có đủ hai đầu,
  kèm múi giờ, kết thúc sau bắt đầu; lưu UTC trong schema timestamp hiện tại.
- Quản trị phân công tutor active, không trùng khách hàng. Sau khi đã có buổi
  hoàn thành không đổi gia sư. Phân công sau bước thanh toán đã có trong luồng.
- Gia sư/quản trị xếp lại, thêm, hủy, hoàn tất buổi; không hủy buổi cuối và không
  hoàn tất trước giờ kết thúc. Khóa tutor để ngăn trùng lịch giữa các booking.
- Chat thường chỉ hai bên; chat tranh chấp thêm admin được phân công. Hai phạm
  vi không trộn dữ liệu. Phân trang theo `(created_at,id)`, hỗ trợ `before_id`.
- Tối đa 30 tin/phút/người/booking; gửi ở đơn đã hủy/hoàn tiền hoặc tranh chấp
  đã đóng bị từ chối. Giao diện tải tin mới mỗi 5 giây khi đang mở.
- Mở/nhận tranh chấp có kiểm tra người liên quan và phân công. Phần quyết toán,
  hoàn credit, công nợ và đối soát nội bộ đã nối; xem [cơ chế tài chính](finance.md).
  Các tác vụ cần VNPAY được tạm gác theo yêu cầu hiện tại.

## Ranh giới transaction và file

Module nhận `Session`, chỉ flush. Router serialize bằng response allowlist rồi
commit một lần; ngoại lệ làm session rollback khi đóng. Không publish sự kiện
trước commit. HTTP: 400 quy tắc nghiệp vụ, 401 xác thực, 403 quyền, 404 dữ liệu
ngoài phạm vi, 409 constraint/xung đột, 422 schema, 429 rate limit, 503 DB.

| File | Trách nhiệm |
| --- | --- |
| `app/api/routes/auth.py` | HTTP auth và phiên đăng nhập |
| `app/api/routes/domain.py` | API nghiệp vụ/quản trị |
| `app/schemas/auth.py`, `domain.py`, `responses.py` | Input kiểm tra chặt, output allowlist |
| `app/modules/users/accounts.py` | Đăng ký, đổi thông tin, thu hồi phiên |
| `app/modules/finance/*.py`, `users/payment_method.py` | Tài chính nội bộ trong từng file; payments giữ import tương thích |
| `app/modules/community/community_service.py` | Ghi nội dung, báo cáo, nâng bậc |
| `app/modules/learning/learning_service.py` | Quản lý khóa/bài và kết quả học |
| `app/modules/tutoring/{booking,booking_session,message,dispute,tutoring_package}.py` | Logic gia sư trong từng file; service giữ import tương thích |
| Các file module gốc | Hàm đọc, public entry point và các TODO giữ nguyên |
| `frontend/src/components/` | Các màn hình học viên, gia sư và quản trị |

Chi tiết vòng đời, quyền, chat/tệp và lệnh test: [module gia sư](tutoring.md).

## Kiểm tra

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
$env:TUTOR_TEST_POSTGRES = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_auth_concurrency.py -v
Remove-Item Env:TUTOR_TEST_POSTGRES
cd ../frontend
npm test
npm run lint
npm run build
```

Test PostgreSQL opt-in chỉ chấp nhận host loopback, tạo schema UUID riêng và dọn
schema đó khi kết thúc. Test mặc định dùng SQLite fixture trong bộ nhớ, có FK;
không dùng dữ liệu thực. Kiểm tra trình duyệt trực tiếp chưa hoàn tất do quyền
truy cập cửa sổ hết thời gian chờ; build/lint/API test không thay thế visual QA.

VNPAY checkout/IPN và trình phát Google Drive đã được bổ sung sau nhóm code ưu
tiên. Seed 10 video cần quyền đọc thư mục; chạy giao dịch sandbox thật cần tài
khoản merchant. Xem [hướng dẫn VNPAY/Drive](vnpay-drive.md) cho cấu hình, giới hạn
và lệnh seed. Không có secret mặc định hoặc secret ở frontend.
