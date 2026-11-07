# Kiểm tra chức năng hệ thống — 07/11/2026

Đợt kiểm tra bao gồm API nghiệp vụ, các kiểm thử frontend hiện có, thao tác
đồng thời trên PostgreSQL local, migration và kết nối HTTP qua Vite proxy.
Kết quả áp dụng cho mã trong workspace tại thời điểm kiểm tra, bao gồm các
thay đổi chưa commit. Không phải xác nhận toàn bộ hệ thống production.

## Phạm vi đã kiểm tra

| Nhóm chức năng | Các tình huống được kiểm tra |
| --- | --- |
| Tài khoản và phiên | Đăng ký, đăng nhập, cập nhật họ tên, đổi email/mật khẩu, refresh rotation, thu hồi phiên, đăng xuất, tài khoản bị khóa, rate limit |
| Phân quyền | API riêng tư yêu cầu đăng nhập; quản trị, head admin, chủ dữ liệu và người tham gia có phạm vi truy cập tương ứng; không lộ password hash hoặc refresh hash |
| Khóa học | Danh mục, tìm kiếm/lọc, mua và retry, thiếu số dư, bài ẩn, quyền hết hạn, thứ tự bài, thời lượng video, tiến độ xem dở và hoàn thành, xác nhận bài tập, điểm và hoàn học phí |
| Gia sư | Tạo/thanh toán/hủy đơn, phân công, xếp lịch và trùng lịch, hoàn thành buổi/khóa, chat, upload/download riêng tư trên local, tranh chấp |
| Ví và tài chính | Nạp thủ công, chỉ ví commercial được rút, giữ tiền cho đơn chờ, chuyển ví, khóa ví, ledger, bút toán bù, snapshot, đối soát, quyết toán, hoàn tiền và công nợ |
| VNPAY | Chữ ký, merchant, số tiền, Return URL không tự cộng ví, IPN/QueryDR chống cộng trùng, phản hồi sai/chưa hoàn tất, lỗi transport/commit, xác nhận đến muộn |
| Cộng đồng | Bài viết/bình luận, quyền đọc, nội dung bị ẩn, trả lời, phân trang/cursor, báo cáo và kiểm duyệt, yêu cầu nâng bậc |
| Quản trị và nhật ký | API các danh mục, tên người dùng, REST và dữ liệu lịch sử, lọc trước phân trang, ngày/nguồn/người thao tác, nội dung chi tiết và bảo vệ trường nhạy cảm |
| Frontend | API client và phiên giữa các tab, điều hướng, lọc danh mục/nhật ký, bảng quản trị, chính sách rút tiền, chọn player YouTube/native, recorder thời gian và phép tính tiến độ |
| Database và triển khai local | Kiểm tra schema drift, nâng/hạ migration trong schema riêng, giữ dữ liệu xem cũ, RLS, readiness, Vite proxy và các đường dẫn SPA |

## Kết quả

- Backend: **238/238 kiểm thử đạt, không bỏ qua ca nào**, chạy toàn bộ
  `unittest` với `TUTOR_TEST_POSTGRES=1` trong 120 giây. Bao gồm 17 ca đồng thời
  và 2 ca migration trên PostgreSQL thật trong schema tạm riêng.
- Frontend: **66/66 kiểm thử đạt**; ESLint và production build thành công.
- HTTP local: **274 kiểm tra đạt**, qua `http://127.0.0.1:5173/api`. Sáu vai trò
  đang hoạt động đăng nhập/refresh/đăng xuất và truy cập API đúng quyền.
  Tài khoản seed `trainee_tutor` hiện bị suspended; mật khẩu vẫn khớp và
  đăng nhập bị từ chối đúng chính sách. Không tự mở khóa tài khoản này.
- Kiểm tra lại tiến độ **3 đăng ký khóa học / 5 bài học** trên PostgreSQL local:
  tỷ lệ trả về khớp thời lượng xem và điều kiện bài tập. Không gửi thời gian
  xem giả, điểm hoặc xác nhận bài tập vào dữ liệu người dùng hiện có.
- `alembic check`: không có chênh lệch giữa model và schema local.
  Database local ở migration **`0007_learning_progress`**.
- `pip check`: không phát hiện dependency bị hỏng. `git diff --check` đạt.
- FE và BE local vẫn hoạt động; `/api/ready` trả HTTP 200.

## Thay đổi trong đợt kiểm tra

1. Sửa fixture của kiểm thử IPN đồng thời: gói nạp cũ có giá 200đ, thấp hơn
   mức tối thiểu 5.000đ mà backend đang kiểm tra. Điều chỉnh giá fixture và
   số tiền callback khớp nhau; giữ nguyên số credit và yêu cầu chỉ cộng một lần.
2. Thêm `backend/tests/test_migrations_postgres.py` với hai ca kiểm thử:
   nâng từ database trống rồi hạ sạch; và nâng dữ liệu xem cũ từ 0006 lên head,
   hoàn thành 100% khi chưa có điểm, hạ 0007 rồi nâng lại mà vẫn giữ thời lượng.
   Các ca này chỉ nhận database loopback và chỉ tạo/xóa schema UUID của chính nó.

Lượt kiểm tra ban đầu không thay đổi nghiệp vụ thanh toán. Các lỗi được phát
hiện ở lượt kiểm tra bổ sung được mô tả riêng bên dưới; không bổ sung chức
năng đối soát VNPAY mới.

## Giới hạn còn lại

1. **Tệp đính kèm trên Vercel:** code đang dùng `uploads/tutoring` trên đĩa
   local, chưa có adapter lưu trữ bền vững dùng chung giữa các instance.
   Kiểm thử upload/download local đạt không xác nhận tính năng này hoạt động
   trên Vercel. Xem [giới hạn triển khai](vercel.md#vnpay-and-attachment-storage).
2. **VNPAY thực tế:** kiểm thử dùng dữ liệu ký và transport giả lập, không
   thanh toán bằng tiền thật hoặc xác minh merchant/IPN của deployment.
   Cơ chế hiện có vẫn chưa tự quét toàn bộ đơn chờ bằng tác vụ nền và chưa có
   nút đối soát QueryDR cho head admin; giữ nguyên theo phạm vi đã thống nhất.
3. **Trình duyệt và video:** chưa chạy được kiểm thử tương tác/hiển thị trên
   trình duyệt. SSR, URL parser, SDK loader, recorder và phép tính tiến độ đã
   được kiểm thử; chưa xác minh trực tiếp playback YouTube/Drive trong đợt này.
4. **Supabase production:** không migrate hoặc thay đổi dữ liệu Supabase trong
   đợt kiểm tra. Push GitHub không tự chạy migration với cấu hình repo hiện có;
   cần migration riêng trước khi dùng schema mới trên production.

## Chạy lại

Với môi trường local hiện tại có venv ở gốc repo, từ thư mục `backend`:

```powershell
$env:TUTOR_TEST_POSTGRES = '1'
$env:PYTHONPATH = '.;tests'
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Các kiểm thử PostgreSQL yêu cầu `DATABASE_URL` trỏ loopback và quyền tạo schema.
Từ gốc repo, kiểm tra frontend và schema:

```powershell
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m alembic check
```

Log kiểm tra local nằm trong `.local/` (được gitignore):
`backend-system-final.log`, `frontend-tests.log`, `system-api-results.json`.

## Kiểm tra bổ sung sau lượt đầu

Phát hiện và sửa ba lỗi ở các nhánh ít gặp:

1. **Pop-up lồng nhau:** đóng/unmount nhiều dialog cùng lúc có thể để
   `body.overflow=hidden` sau khi đã đóng hết. Các dialog hiện dùng chung bộ
   đếm khóa cuộn, khôi phục trạng thái ban đầu sau dialog cuối cùng, không
   phụ thuộc thứ tự cleanup. Thêm ba kiểm thử cho thứ tự đóng, cleanup lặp
   và mở lại.
2. **Lỗi đọc response:** timeout, hủy request hoặc mất kết nối khi đang đọc
   JSON từng bị báo thành dữ liệu không hợp lệ. API client hiện giữ đúng
   nguyên nhân, không xóa phiên và không tự gửi lại giao dịch tiền. Thêm bốn
   kiểm thử phân biệt timeout/cancel/network/JSON lỗi.
3. **Đơn nạp đang chờ rồi ví bị khóa:** xác nhận nạp hợp lệ từng bị chặn bởi
   trạng thái ví, gồm IPN, QueryDR và đối soát thủ công. Khoản nạp của đơn đã
   tồn tại hiện được ghi nhận, ví vẫn khóa và không thể chi/rút. Thêm bốn
   kiểm thử API cho khoản nạp/đơn rút khi khóa và một kiểm thử IPN đồng thời
   trên PostgreSQL. Giữ nguyên yêu cầu xác minh thanh toán và chống cộng trùng;
   không thêm tính năng đối soát mới.

Sau sửa, **73/73 kiểm thử frontend**, **60/60 kiểm thử tài chính/VNPAY** và
**18/18 kiểm thử đồng thời PostgreSQL** đạt; ESLint và production build đạt.
Chạy lại **274 kiểm tra HTTP** trên backend đã khởi động lại cũng đạt;
không còn schema tạm của các ca kiểm thử sau cleanup. Kết quả 238 kiểm thử
backend ở trên là lượt kiểm tra tổng thể trước các bản sửa bổ sung.
Log bổ sung: `.local/payment-edge-final.log` và `.local/postgres-edge-final.log`.
