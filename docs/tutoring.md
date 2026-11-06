# Module gia sư

Logic nằm trực tiếp trong từng file `backend/app/modules/tutoring/`. Các TODO
gốc được giữ nguyên theo yêu cầu. `tutoring_service.py` chỉ là điểm import tương
thích cho API cũ, không còn chứa toàn bộ logic nghiệp vụ.

| File | Hàm chính |
| --- | --- |
| `tutoring_package.py` | Liệt kê/tìm gói, tạo/sửa và ngừng bán có audit |
| `booking.py` | Tạo đơn cùng buổi học, thanh toán/cấp quyền, phân công, hoàn tất/hủy |
| `booking_session.py` | Đọc lịch, kiểm tra timezone, chống trùng, thêm/sửa/hủy/hoàn tất buổi |
| `message.py` | Chat thường/tranh chấp, cursor, rate limit và tin nhắn có tệp |
| `attachments.py` | Lưu tệp riêng, xác minh định dạng/dung lượng và quyền tải |
| `dispute.py` | Đọc/mở tranh chấp, nhận xử lý, xét quyền và giải quyết nguyên tử |
| `access.py` | Chính sách truy cập booking dùng chung |

## Booking và lịch

Khách hàng tạo đơn với 1–100 buổi, có thể chưa chốt giờ. Gói ngừng bán không
xóa đơn hoặc thay snapshot của người đã mua. Sau thanh toán, quản trị phân công
gia sư có tài khoản active và ví gia sư hoạt động, khác người mua.

Lịch gửi từ client phải kèm timezone, có đủ starts/ends và kết thúc sau bắt đầu;
ghi vào DB theo UTC. Khi phân công hoặc xếp lịch, khóa hàng tutor để tránh hai
booking đồng thời nhận lịch chồng nhau. Không đổi tutor sau khi đã hoàn tất buổi.

Gia sư/quản trị thêm hoặc sửa lịch của đơn assigned; tối đa 100 số buổi. Hủy buổi
phải giữ lại ít nhất một buổi hợp lệ. Chỉ hoàn tất buổi sau giờ kết thúc. Khách
hàng/quản trị xác nhận hoàn tất booking khi mọi buổi hợp lệ đã xong và không còn
tranh chấp. Gia sư không được tự xác nhận hoàn tất toàn bộ đơn.

Quyền chuyển trạng thái được kiểm tra trong module, không có endpoint nhận một
status bất kỳ từ client. Các thao tác có tiền gọi service tài chính đã có và giữ
cùng transaction với booking/subscription; module không tự commit.

## Chat và tệp đính kèm

Chat thường chỉ có khách hàng/tutor. Role admin không tự được đọc. Chat tranh
chấp thêm đúng admin được giao và lọc riêng bằng dispute_id. Tin nhắn được phân
trang theo `(created_at,id)`, hỗ trợ before_id/limit/offset. Hai bên được đọc lịch
sử sau khi đóng đơn; gửi mới bị chặn khi đơn đã hủy/hoàn hoặc tranh chấp đã đóng.

Text và tệp dùng chung giới hạn 30 tin/phút/người/booking, khóa booking khi ghi
để nhiều worker không vượt giới hạn. Giao diện cập nhật tin mỗi 5 giây, chỉ thấy
dữ liệu đã commit; hiện dùng polling, không cần WebSocket broker.

Upload:

```text
POST /api/bookings/{booking_id}/attachments?name=filename.pdf[&dispute_id=...]
Authorization: Bearer <access>
Content-Type: application/pdf

<raw file bytes>
```

Chấp nhận PDF, PNG, JPEG hoặc text UTF-8, tối đa 5 MB, kiểm tra nội dung theo định
dạng. Không nhận URL file bên thứ ba từ payload. Tệp lưu bằng UUID trong
`uploads/tutoring/`, không được mount công khai. Đường tải do server tạo và kiểm
tra lại booking/channel/danh tính cho mọi request. Tải bằng Authorization,
Content-Disposition attachment, no-store và nosniff.

Kiểm tra quyền trước khi nhận dữ liệu; không giữ row lock trong lúc truyền tệp.
Sau upload phải kiểm tra lại quyền/trạng thái trước commit. Nếu flush/commit
thất bại, rollback tin nhắn và xóa tệp vừa ghi. Lưu trữ local cần volume bền vững
và dùng chung khi deploy nhiều instance; kiểm tra định dạng không thay phần mềm
quét malware. Không có API xóa lịch sử chat/tệp trong đợt này.

## Tranh chấp

Người tham gia được mở tối đa một tranh chấp/booking trong thời hạn cho phép.
Admin nhận case không được là một bên trong đơn. Chỉ admin được giao được kết
luận; kiểm tra xung đột lợi ích lại khi giải quyết. Từ chối tranh chấp khôi phục
đúng trạng thái confirmed/assigned/completed dựa trên dữ liệu booking.

Hoàn toàn bộ hoặc một phần phối hợp booking, subscription, quyết toán/ví, ledger
và audit cùng transaction. Hoàn một phần chỉ áp dụng sau khi có quyết toán và
trước giải ngân. Case đã đóng không được xử lý hoặc mở lại lần nữa.

## Kiểm tra

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_tutoring.py -v
```

Các test API nghiệp vụ còn bao phủ mua/hoàn một lần, chống trùng lịch, quyền chat,
vòng đời tranh chấp và quyết toán. Test PostgreSQL opt-in xác minh row lock với
hai request đồng thời trong schema tạm, không thay đổi dữ liệu nghiệp vụ thật.
