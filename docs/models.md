# Models từ DBML

`backend/app/models/` chứa 24 SQLAlchemy 2 ORM model, mỗi bảng một file.
`base.py` dùng chung metadata và quy tắc đặt tên constraint; `enums.py` chứa 15
enum; `__init__.py` import tất cả model để metadata đủ bảng khi dùng migration.
`app/schemas/` tiếp tục dành cho hợp đồng API Pydantic.

| Nhóm | Model |
| --- | --- |
| Người dùng | `User`, `PaymentMethod`, `ActionLog`, `UserSubscription` |
| Gia sư | `TutoringPackage`, `Booking`, `BookingSession`, `Message`, `Dispute` |
| Đào tạo | `Course`, `Lesson`, `Attendance`, `CourseProgress` |
| Cộng đồng | `Post`, `Comment`, `RoleRequest`, `CommentReport` |
| Tài chính | `Wallet`, `BookingSettlement`, `InternalTransaction`, `ExternalTransaction`, `CreditPackage`, `CashOrder`, `WalletSnapshot` |

## Quy ước ánh xạ

- Giữ nguyên tên bảng/cột, nullability, PK, unique, index, FK và check của DBML.
  Cột không khai báo `not null` và không thuộc PK vẫn nullable, kể cả email,
  password_hash hoặc cột có default. Chưa tự siết các cột này.
- Dùng PostgreSQL: UUID, JSONB, JSON, native enum, `Numeric` trả về `Decimal` và
  `BigInteger` cho các cột bigint. `messages.id` là BIGSERIAL.
- Enum lưu giá trị DBML (`active`, `head_admin`, `in`...), không lưu tên member
  Python viết hoa. Số 0–6 trong ghi chú role không phải giá trị lưu ở database.
- `timestamp` ánh xạ sang timestamp không timezone đúng theo DBML.
- Default được khai báo bằng `server_default` đúng những chỗ DBML có default.
  UUID chưa tự sinh; ứng dụng phải cấp UUID khi tạo bản ghi. `updated_at` không
  tự đổi khi update vì DBML không khai báo trigger hay quy tắc tự cập nhật.
- Quan hệ database được thể hiện bằng FK, gồm bốn FK ghép ở `comments`,
  `messages` và `attendance`. Chưa thêm các thuộc tính điều hướng ORM
  `relationship()` hoặc cascade xóa ngoài quy định của DBML.
- Import model không kết nối database và không tự chạy `create_all`.

```python
from app.models import Base, User
from app.models.enums import UserRole

# Khi cấu hình Alembic: target_metadata = Base.metadata
# Khi xây service: dùng User/UserRole với session được quản lý riêng.
```

## Review và kiểm tra

Đã đối chiếu tự động trực tiếp với DBML đính kèm: 24 bảng khớp về tên cột,
kiểu dữ liệu, nullable, default, enum, PK, unique, index, FK và check. Metadata có
46 FK, 24 index tường minh và 17 check. Không tạo thêm một file schema DBML/SQL.

Đã đọc lại các FK ghép để xác nhận:

- Bình luận cha thuộc cùng bài viết và không thể tự làm cha trực tiếp.
- Tin nhắn tranh chấp thuộc cùng booking với tranh chấp đó.
- Attendance liên kết cả tiến độ đăng ký và bài học trong cùng khóa học.
- Giữ các unique `(id, post_id)`, `(id, booking_id)`, `(id, course_id)` và
  `(subscription_id, course_id)` để PostgreSQL có khóa đích hợp lệ cho FK ghép.

Test trong `backend/tests/test_models.py` kiểm tra cấu hình ORM, biên dịch toàn
bộ CREATE/DROP schema với PostgreSQL dialect và giá trị enum được lưu. Đây là
kiểm tra không kết nối; chưa chạy migration hay kiểm tra constraint trên một
PostgreSQL server thật.

## Việc còn lại

1. Cấu hình PostgreSQL, driver, session và Alembic; tạo migration đầu tiên từ
   `Base.metadata` rồi kiểm tra trên database phát triển.
2. Xác nhận nullability, múi giờ và cách sinh UUID trước khi áp dụng migration.
   Các trường tiền trong transaction đang là `int` trong khi số dư ví dùng
   `bigint`; giữ nguyên DBML nhưng cần chốt giới hạn trước khi dùng dữ liệu thật.
3. Xây service cho các quy tắc DBML giao cho BE: phân quyền, subscription đúng
   loại/chủ sở hữu, booking có ít nhất một buổi, xung đột lịch, xét kết quả học,
   cập nhật ví/quyết toán nguyên tử và chống giải ngân lặp.
4. Check không cho bình luận tự làm cha không ngăn chu trình nhiều bình luận;
   xử lý quy tắc này ở service nếu cho phép đổi `parent_id`.
