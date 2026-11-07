# Tutor Web frontend

React/Vite, dùng cấu hình `.env` chung ở thư mục gốc.
Xem [README dự án](../README.md) để cài đặt và chạy cả frontend/backend.

```powershell
npm ci
npm run dev
npm test
npm run lint
npm run build
```

`src/config.js` đọc API base URL; `src/services/api.js` quản lý request,
refresh JWT và đồng bộ phiên giữa các tab. `src/services/session.js` lưu cặp
token theo origin/API trong localStorage (fallback bộ nhớ khi storage bị chặn).
App xác minh `/auth/me` trước khi điều hướng trang cần đăng nhập; lỗi mạng có
nút thử lại và không xóa phiên. Hạn phiên vẫn do backend quyết định, mặc định
7 ngày. Xem [cơ chế xác thực](../docs/security.md).

Giao diện có chế độ sáng/tối và bố cục responsive. Light mode dùng xanh lá
và góc vuông. Menu tính năng nằm bên trái; danh mục quản trị gom 14 mục vào
5 nhóm thu gọn trong cùng sidebar. Mục được chọn lưu qua
`/admin?section=...`, hỗ trợ tải lại và Back/Forward.

Bài học phát ngay trên trang, tự lấy thời lượng từ metadata video và lưu
thời gian xem mỗi 10 giây, khi dừng, kết thúc hoặc rời bài. Tua không được
tính thành thời gian xem. Bản lưu trên trình duyệt giúp gửi lại tiến độ khi
mở lại bài sau lỗi mạng. Link YouTube watch/youtu.be/Shorts/live/embed dùng
YouTube IFrame API để phát trên trang, tự đọc thời lượng và theo dõi phát/dừng.
Trình nhúng gửi đúng origin và Referer, không dùng thẻ HTML video cho trang YouTube.
Các URL tệp video trực tiếp dùng HTML video; Drive preview dự phòng không cung cấp
sự kiện theo dõi. Xem [giới hạn video](../docs/vnpay-drive.md).

Tiến độ bài VOD không có bài tập = thời lượng đã xem / tổng thời lượng,
cập nhật trên giao diện khi đang xem và lưu vào backend theo chu kỳ trên.
Tiến độ khóa là trung bình tiến độ các bài. Bài có `assignment_url` chỉ hoàn
thành sau khi quản trị xác nhận bài tập; xem hết video không thay thế xác nhận.
Lớp trực tiếp không có bài tập dùng điểm danh. Hoàn thành học tập có thể đạt
100% trước khi chấm điểm; điểm tổng kết và kết quả vẫn do backend tính từ điểm quản trị nhập.

Trước khi triển khai phiên bản này, chạy `alembic upgrade head` để thêm
`lessons.duration_seconds`, `attendance.assignment_completed` và ràng buộc
hoàn thành học tập độc lập với điểm đánh giá. Các bản ghi xem cũ được tính lại
khi mở tiến độ; không tự chuyển thời gian xem thành xác nhận bài tập.

Nhật ký quản trị hiển thị mã, thời gian, người thao tác/người liên quan và
snapshot trước/sau trong pop-up chi tiết, có bảng so sánh từng trường.
Danh sách phân loại REST: Xem (`GET`), Tạo mới (`POST`), Cập nhật toàn bộ (`PUT`),
Cập nhật một phần (`PATCH`), Xóa (`DELETE`) và Khác. Giá trị database cũ được
chuẩn hóa khi đọc để kết quả hiển thị và bộ lọc luôn khớp nhau. Các migration
audit hiện có vẫn giữ nguyên dữ liệu lịch sử và hỗ trợ cả các giá trị cũ.
Nhật ký lưu trước đây chưa phân biệt được tạo/sửa và thao tác ngoài danh mục nằm ở nhóm Khác;
không sửa lịch sử hoặc suy đoán từ trạng thái hiện tại. Đối tượng lọc theo thực thể.
Tìm kiếm và lọc thao tác, thực thể,
nguồn, người thực hiện, khoảng ngày chạy tại API trước khi phân trang.
Khoảng ngày được chuyển từ múi giờ trình duyệt sang UTC; ngày kết thúc
bao gồm toàn bộ ngày đã chọn. Các ô tìm kiếm khóa học, gia sư, cộng đồng
có bộ lọc theo danh mục tương ứng.

Dropdown REST dùng danh mục cố định ở FE; nhãn database từ metadata đã tải trước
không xuất hiện lại. Lựa chọn cũ được chuẩn hóa trước khi gửi truy vấn.

Bộ lọc nhật ký áp dụng ngay khi chọn/nhập; yêu cầu cũ được hủy khi giá trị đổi.
Chọn nguồn Hệ thống tự xóa điều kiện quản trị viên để tránh bộ lọc mâu thuẫn.
Đặt lại xóa toàn bộ điều kiện và quay về trang đầu. Danh sách quản trị, ví,
sổ giao dịch và nhật ký dùng bảng; thông tin và biểu mẫu quản lý mở trong pop-up.

Migration `0004_user_full_name` bổ sung họ tên. Người dùng cũ cập nhật tên
tại Tài khoản; đăng ký mới có trường họ tên. Họ tên hiển thị trong tài khoản,
menu, danh sách người dùng, lựa chọn gia sư và danh tính trong nhật ký.

Ví tự làm mới mỗi 15 giây khi đang hiển thị. Thanh toán VNPAY thành công được
cộng ví tự động qua IPN hợp lệ; admin chỉ đối soát chuyển khoản thủ công/rút tiền.
Rút tiền chỉ dành cho ví commercial đang hoạt động, không có công nợ. Giao diện
không cho chọn ví normal và chỉ gửi `wallet_type=commercial`; backend chặn
cả tạo yêu cầu normal và xác nhận đơn normal cũ còn chờ.

Triển khai frontend cùng backend bằng một project Vercel:
[Vercel Services](../docs/vercel.md). Giữ `VITE_API_BASE_URL` trống để trình
duyệt gọi `/api` cùng domain. Bộ điều phối Vercel xử lý API, còn fallback
`index.html` trong service frontend hỗ trợ tải lại các trang như `/login`.
