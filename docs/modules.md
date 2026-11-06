# Module nghiệp vụ — 27/10/2026

> Đây là ghi chép thiết kế ban đầu. Code đã được mở rộng; xem
> [trạng thái triển khai](implementation.md) và OpenAPI `/api/docs` cho chức năng
> hiện tại. Các TODO gốc được giữ nguyên.

## Phần đã có

`backend/app/modules/` có 5 package nghiệp vụ với 24 file tương ứng 24 model DBML
và package auth bổ sung 5 file xác thực/JWT/session, tổng 29 file tính năng.
Mỗi file có đúng **một hàm với SQLAlchemy Session**;
những tính năng còn lại là comment `TODO` ghi việc cần làm và cách thực hiện.
`__init__.py` chỉ mô tả package, không chứa hàm nghiệp vụ.

Đã có PostgreSQL engine, Session từng request, migration và dependency current_user;
đã kiểm tra trên server PostgreSQL local. Chưa có API đăng nhập/nghiệp vụ.
FastAPI hiện đăng ký `/api/health` và `/api/ready`.
Hàm mẫu chưa đồng nghĩa tính năng đã có trên website.

`app/core/security.py` chứa tiện ích hash Argon2id, tạo và decode JWT. Cơ chế đã
chọn là JWT Bearer, refresh một lần có rotation, thu hồi phiên khi logout/reuse.
Auth có verify/rehash mật khẩu, authenticate_user, cấp token, renew, kiểm tra
JWT + phiên DB + user và logout. LoginRequest/TokenResponse đã có trong schemas/auth.py;
endpoint auth còn TODO. get_access_claims chỉ kiểm tra JWT ở HTTP layer.
Cấu hình, review validation/dummy hash, transaction khi renew bị từ chối và schema:
[security.md](security.md). Quy tắc một hàm mỗi file áp dụng cho modules; core
chứa các primitive bảo mật dùng chung.

## Danh mục file và tính năng

Đường dẫn trong bảng tính từ `backend/app/modules/`.

| File | Hàm mẫu đã viết | Các phần TODO chính |
| --- | --- | --- |
| `users/user.py` | `get_active_user` | Đăng ký, xác thực, profile, khóa tài khoản |
| `users/payment_method.py` | `list_my_payment_methods` | Thêm/sửa/xóa đúng chủ, snapshot và che số tài khoản |
| `users/action_log.py` | `record_admin_action` | Snapshot có allowlist, tìm lịch sử, gắn log vào transaction nghiệp vụ |
| `users/user_subscription.py` | `list_my_active_subscriptions` | Kích hoạt sau thanh toán, hết hạn, thu hồi quyền/hoàn tiền |
| `tutoring/tutoring_package.py` | `list_active_tutoring_packages` | Quản trị bảng giá, dừng bán, phân trang |
| `tutoring/booking.py` | `get_booking_for_participant` | Tạo booking + buổi học, thanh toán, gán gia sư, chuyển trạng thái |
| `tutoring/booking_session.py` | `list_booking_sessions` | Xếp lịch, chống trùng, thêm/hủy và hoàn thành buổi |
| `tutoring/message.py` | `send_booking_message` | Đọc có cursor, chat tranh chấp, upload file, realtime sau commit |
| `tutoring/dispute.py` | `get_booking_dispute` | Mở tranh chấp, phân công admin, phán quyết và giao dịch bù |
| `learning/course.py` | `list_visible_courses` | Quản trị khóa học, ẩn, mua quyền học |
| `learning/lesson.py` | `list_my_course_lessons` | Thứ tự bài, media có kiểm soát, chính sách xóa/phiên bản |
| `learning/course_progress.py` | `get_my_course_progress` | Khởi tạo, tính tiến độ, chấm điểm và hoàn thành nguyên tử |
| `learning/attendance.py` | `list_my_attendance` | Điểm danh/VOD heartbeat, upsert chống ghi lặp, tính lại tiến độ |
| `community/post.py` | `get_readable_post` | Đăng/sửa, snapshot tác giả, tìm bài theo quyền, kiểm duyệt |
| `community/comment.py` | `list_visible_comments` | Trả lời, cây bình luận, chống chu trình, ẩn có audit |
| `community/role_request.py` | `list_my_role_requests` | Đề nghị nâng một bậc, duyệt/từ chối có khóa và kiểm tra role lại |
| `community/comment_report.py` | `report_comment` | Chống spam/trùng, nhận xử lý, quyết định kiểm duyệt |
| `finance/wallet.py` | `get_my_wallet` | Mở ví, chính sách commercial, khóa ví khi cập nhật số dư |
| `finance/booking_settlement.py` | `get_my_booking_settlement` | Phân bổ thu nhập, giải ngân đến hạn, hoàn và thu hồi |
| `finance/internal_transaction.py` | `list_my_internal_transactions` | Chuyển/chi/thu/hoàn tiền nội bộ, idempotency, ledger bất biến |
| `finance/external_transaction.py` | `list_my_external_transactions` | Callback nạp/rút, xác minh nhà cung cấp, đối soát |
| `finance/credit_package.py` | `list_active_credit_packages` | Quản trị gói nạp, snapshot giá và đơn vị VND/credit |
| `finance/cash_order.py` | `get_my_cash_order` | Tạo đơn nạp/rút, giữ tiền pending, xác nhận một lần |
| `finance/wallet_snapshot.py` | `list_my_wallet_snapshots` | Chụp số dư theo ngày, đối soát, backfill có audit |
| `auth/login.py` | `issue_login_tokens` | Nối authenticate_user + LoginRequest/TokenResponse vào router và transaction |
| `auth/authenticate.py` | `authenticate_user` | Dummy hash đã dùng lại; thống nhất chuẩn hóa email với đăng ký và nối vào login |
| `auth/refresh.py` | `renew_tokens` | Nối endpoint, commit revocation trước 401, test concurrency PostgreSQL |
| `auth/current_user.py` | `get_authenticated_user` | Dùng dependency get_current_user đã có cho protected endpoint, giữ kiểm tra ownership riêng |
| `auth/logout.py` | `revoke_token_session` | Nối endpoint, logout_all và thu hồi khi đổi mật khẩu |

## Cách dùng hàm mẫu

### Xác thực email và mật khẩu

authenticate_user(session, email, password) chuẩn hóa email bằng strip().lower(),
query User, gọi verify_password và trả UUID khi mật khẩu đúng/tài khoản active.
Không tìm thấy, sai mật khẩu, hash NULL/lỗi hoặc status không active đều trả None.
Đăng ký/import user phải dùng cùng chính sách chuẩn hóa email; chưa có API đăng ký.

verify_password trả tuple (valid, updated_hash), không dùng trực tiếp tuple trong
if. Rehash thành công chỉ gán User.password_hash vào Session; caller phải commit
cùng lúc tạo AuthSession. Hàm xác thực không commit và chưa tự cấp token.

Ở HTTP layer, lấy password qua LoginRequest.password.get_secret_value(). Khi
xác thực trả None, router tương lai map chung sang 401, không tiết lộ user tồn tại.
Dummy hash hiện dùng lại ở cấp module; email dùng EmailStr và TTL TokenResponse
bắt buộc dương. Cần nối router/rate limit và dùng cùng policy email ở đăng ký.

### Session và transaction

Caller cung cấp một `Session` cho mỗi request/use case. Module không tạo engine,
không tự kết nối DB, không `commit()` hoặc `rollback()`. Ba mẫu ghi dữ liệu là
`send_booking_message`, `report_comment` và `record_admin_action`: chúng
`add()` rồi `flush()` để nhận ID/phát hiện lỗi; **flush không phải commit**.
Auth cũng không commit. renew_tokens trả kết quả thay vì raise khi phát hiện
reuse để caller commit thu hồi phiên rồi mới trả HTTP 401; xem [security.md](security.md).

Engine/session factory được tạo trong lifespan. Dependency get_session cấp/đóng
Session, không tự commit. get_current_user đã query Session, có thể bật autobegin;
endpoint dùng transaction hiện hành và commit sau use case, không begin lồng.
Cài và kiểm tra DB: [database-setup.md](database-setup.md).

Sau khi có engine và xác thực, một use case có thể gọi như sau:

```python
from sqlalchemy.orm import Session
from app.modules.tutoring.message import send_booking_message

# engine: cấu hình ở tầng DB trong bước tiếp theo.
# current_user.id: lấy từ xác thực phía server, không lấy sender_id từ request body.
with Session(engine) as session:
    with session.begin():  # bắt đầu trước các query trong Session này
        message = send_booking_message(
            session,
            booking_id=booking_id,
            sender_id=current_user.id,
            content="Chào thầy/cô!",
        )
        result = {"id": message.id, "content": message.content}
    # Chỉ publish WebSocket/event sau khi đã thoát begin() thành công.
```

Exception phải đi ra khỏi `session.begin()` để context manager rollback. Nếu bắt
lỗi để chuyển thành HTTP response, bắt ở ngoài block này. Một session không dùng
chung giữa các request, thread hoặc task. Chưa đưa API ra ngoài trước khi hoàn
thiện schema, auth, kiểm soát giao dịch và các TODO liên quan.

### Quyền và dữ liệu trả về

- Các tham số `user_id`, `sender_id`, `reporter_id`, `admin_id`, `tutor_id` đại diện
  danh tính đã xác thực. Router tương lai phải lấy chúng từ dependency auth.
  Gửi UUID vào hàm không tự tạo ra bằng chứng xác thực.
- Tài khoản không active bị từ chối ở các mẫu có dữ liệu riêng. Booking thường
  chỉ đọc/gửi bởi customer hoặc tutor được gán. Role admin không tự vượt qua
  quyền booking; luồng admin được phân công tranh chấp vẫn là TODO.
- Catalog gói học, khóa học visible và gói credit là dữ liệu công khai. Bài viết
  xét cấp role từ 0 đến 6; bài có quyền chưa cấu hình (`min_role_level=NULL` hoặc
  ngoài khoảng) bị từ chối. Không có ngoại lệ admin xem nội dung ẩn ở mẫu hiện tại.
- Nội dung lesson kiểm tra subscription đúng chủ, loại course, active và còn
  thời hạn. Course hidden không thu hồi quyền đã mua. Tiến độ/attendance lịch sử
  vẫn được chủ tài khoản active xem sau khi quyền học hết hạn.
- Các module lịch sử ví chỉ nhận ví active của chính user. Lịch sử internal
  transaction chỉ chọn `id/type/amount/created_at`, không trả số dư của bên đối tác.
- Kết quả ORM là dữ liệu nội bộ. Router phải dùng response schema có allowlist;
  không serialize nguyên `User`, `PaymentMethod`, `CashOrder` hay ledger vào API.

### Lỗi và thời gian

| Lỗi ở mẫu | Ý nghĩa | HTTP mapping dự kiến ở router |
| --- | --- | --- |
| `ValueError` | Input mẫu không hợp lệ | 422 hoặc 400 theo error contract |
| `LookupError` | Không tìm thấy bản ghi thuộc phạm vi được phép | 404 |
| `PermissionError` | Tài khoản/quyền không cho phép | 403 |
| SQLAlchemy/DB exception | Constraint hoặc kết nối/giao dịch lỗi | Rollback, log nội bộ; không trả SQL/chi tiết nhạy cảm |

Chưa có exception handler hoặc error contract nghiệp vụ trong FastAPI. Với quyền
truy cập riêng tư, mẫu có thể gộp không tồn tại và không thuộc chủ sở hữu thành
404 để không tiết lộ bản ghi của người khác.

Mẫu dùng UTC rồi bỏ `tzinfo` để khớp `timestamp` hiện có. Trước khi deploy, thống
nhất timezone UTC cho database/session hoặc chuyển schema sang `timestamptz`
bằng migration có kế hoạch. Không trộn giờ local với UTC trong các cột hiện tại.

## Hoàn thiện một tính năng như thế nào

1. Đọc model và TODO trong file tương ứng; chốt quy tắc còn thiếu trước khi viết.
2. Thêm request/response schema Pydantic theo từng use case; chỉ nhận field client
   được quyền quyết định, không cho mass assignment vào ORM model.
3. Dùng dependency Session/current_user đã có, sau đó tạo router gọi module. Giữ transaction
   ở biên use case; query nghiệp vụ hiện đặt trực tiếp trong module, chỉ tách
   repository khi có nhu cầu tái sử dụng hoặc độ phức tạp thực tế.
4. Với thao tác ghi: khóa hàng cần thiết, kiểm tra quyền/trạng thái từ DB, cập nhật
   liên bảng cùng transaction và xử lý retry có idempotency. Notification sau commit.
5. Kiểm thử truy cập chéo user, input sai, cạnh tranh và rollback trên PostgreSQL;
   đăng ký router vào `api/router.py` và cập nhật CORS method/header khi có endpoint mới.

## Xác minh hiện tại

- Có 29 file nghiệp vụ/auth, mỗi file một hàm; authenticate_user mới đã được kiểm tra.
- Có 9 test mới cho quyền booking, tin nhắn/rollback, subscription hết hạn,
  hidden course, quyền cộng đồng, lịch sử ví và log admin.
- Password có 5 test kiểm tra hash/verify, salt, input, Unicode/khoảng trắng và rehash.
- Auth/schema có 11 test về email chuẩn hóa/định dạng, active/inactive, sai/mất hash,
  dùng lại dummy hash, transaction rehash, che secret và TTL dương.
- JWT có 16 test về claim, key/config, Bearer, rotation/reuse, logout, phiên hết
  hạn, user bị khóa và rollback; CORS thêm một test Authorization/POST.
- Database có 12 test về URL/secret, chuyển đổi env cũ, init_env, migration offline,
  lifespan, readiness và rollback Session. Tổng backend: **69 test đạt**.
- Test nghiệp vụ chạy SQLite trong bộ nhớ; chỉ metadata bản sao của fixture được
  đổi JSONB/BIGSERIAL/default thời gian để tương thích. Model production không đổi.
  Đã migrate/check schema và smoke test Session/JWT trên PostgreSQL thật, rollback
  toàn bộ dữ liệu thử. Chưa xác minh transaction đồng thời nhiều worker.

Luồng đọc/ghi từng nhóm bảng: [database-flow.md](database-flow.md).
