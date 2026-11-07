# Cơ chế tài chính nội bộ

Phạm vi này hoàn thiện credit, ví, thanh toán dịch vụ, nạp/rút thủ công,
quyết toán, hoàn tiền, công nợ và đối soát. Các tác vụ cần gọi/cấu hình VNPAY
được tạm gác theo yêu cầu. Không thay đổi schema gốc, không chạy giao dịch tiền
thật và không có migration mới. Các TODO gốc vẫn được giữ nguyên.

## File và trách nhiệm

| File | Chức năng |
| --- | --- |
| `finance/wallet.py` | Mở/đọc/khóa ví, ví nền tảng, hợp đồng, số dư có thể chi và tiền giữ |
| `finance/internal_transaction.py` | Chuyển credit, bút toán bù, trả nợ, sổ giao dịch |
| `finance/external_transaction.py` | Ghi nạp/rút thủ công đã đối soát và bút toán bù tương ứng |
| `finance/cash_order.py` | Snapshot đơn, giữ tiền rút, xác nhận/thất bại/hủy có idempotency |
| `finance/credit_package.py` | Quản lý gói VND/credit, dừng bán, giữ nguyên giá đơn cũ |
| `finance/booking_settlement.py` | Phân bổ, giữ/giải ngân, bù công nợ và hoàn sau giải ngân |
| `finance/wallet_snapshot.py` | Snapshot theo lô và báo cáo đối soát chỉ đọc |
| `finance/ledger_guards.py` | Chặn ORM sửa/xóa lịch sử đã ghi |
| `users/payment_method.py` | Chuẩn hóa, che số và quản lý ngân hàng đúng chủ |
| `finance/payments.py` | Giữ đường import tương thích; không chứa bản sao logic |

Module chỉ flush; caller/router quản lý commit và rollback. Không có endpoint
cho client tự gán số dư, tiền giữ, debt, giá mua, phí hoặc status thanh toán.

## Đơn vị và giới hạn

- Tiền nội bộ dùng số nguyên credit; giá gói nạp và amount_vnd dùng VND. Không
  dùng float, không coi credit và VND là cùng một trường.
- Quy đổi rút hiện giữ chính sách **1 credit = 1 VND**, phí rút 0. Giá bán gói
  nạp độc lập và được snapshot khi tạo đơn. Đây là chính sách hiện tại cần được
  chủ dự án đánh giá trước khi vận hành tiền thật.
- Ledger/snapshot trước-sau trong schema dùng int32. Thao tác ghi từ chối amount
  hoặc số dư trước/sau vượt 2.147.483.647; muốn tăng phải có migration phù hợp.
- Ví hệ thống dùng principal không có email/mật khẩu, status suspended và UUID
  dành riêng. Khởi tạo an toàn khi nhiều worker cùng gọi, không cho API khóa ví này.

Ví cá nhân không có debt/holding/commission/contract theo check của schema. Ví
gia sư được mở cho tutor/admin/head_admin, phí mặc định 10%. Head admin cấu hình
phí 0–100% và mã hợp đồng; quyết toán cũ giữ snapshot nguyên vẹn.

## Số dư và nạp/rút thủ công

Response ví tách `available_balance`, `reserved_withdrawals` và
`spendable_balance`. Số có thể chi trừ các đơn rút pending; ví khóa hoặc có debt
không được chi. Với ví nền tảng, còn trừ thu nhập đang held cho gia sư.

Tạo đơn nạp lấy giá/số credit từ gói active. Tạo đơn rút khóa user/ví, kiểm tra
ngân hàng đúng chủ và snapshot thông tin nhận tiền. **Chỉ ví commercial được rút**;
ví normal không được tạo yêu cầu rút, kể cả tài khoản quản trị. API mặc định
`wallet_type=commercial`, từ chối `normal`; service và bước duyệt/ghi ledger
cũng kiểm tra độc lập. Đơn normal cũ còn pending không thể được duyệt chi;
chủ đơn vẫn được hủy hoặc quản trị từ chối để giải tỏa số tiền giữ.
Request UUID được dùng làm
PK của đơn; retry cùng yêu cầu trả lại đơn cũ, không giữ tiền thêm.

Head admin chỉ xác nhận sau khi đối soát tiền ngoài hệ thống và ghi lý do/tham
chiếu. Xác nhận cùng kết quả không cộng/trừ thêm; kết quả mâu thuẫn bị từ chối.
Wallet, external ledger, cash_order và audit commit cùng transaction.

Chủ đơn được hủy đơn **thủ công** pending. Schema không có enum cancelled cho
cash_order, nên dùng `failed` cùng marker cancelled_by_user, có audit. Hủy giải
tỏa reservation và không ghi tiền giả. Đơn nhà cung cấp bị chặn khỏi luồng này.

Tài khoản ngân hàng được chuẩn hóa khoảng trắng; số tài khoản bỏ dấu cách/gạch
nối và đổi chữ sang uppercase. Chặn trùng sau chuẩn hóa, tối đa 20 phương thức.
Không sửa/xóa khi còn đơn rút pending tham chiếu; danh sách chỉ hiện bốn số cuối.
Head admin xem snapshot nhận tiền qua endpoint riêng, có audit.

Ví khóa vẫn cho chủ tài khoản active xem lịch sử. Hoàn quyền dịch vụ có thể
cộng credit vào ví khóa, nhưng không tự mở khóa hoặc cho rút/chi trở lại.
Đơn nạp đã tạo trước khi khóa ví vẫn được ghi nhận khi có IPN/QueryDR hợp lệ
hoặc head admin xác nhận tiền thực nhận. Ví giữ trạng thái khóa và số có thể
chi bằng 0; xác nhận lặp không cộng thêm credit. Không tạo đơn nạp mới hoặc
duyệt chi đơn rút khi ví đang khóa.

## Chuyển credit và bút toán bù

Chuyển giữa ví cá nhân và ví gia sư **cùng chủ**. Hai ví phải khác nhau; không
có API chuyển sang user khác. Request UUID làm ID internal transaction, retry
không ghi thêm. Ví đích có debt phải dùng luồng trả nợ riêng.

Lịch sử tiền là append-only. ORM chặn sửa số tiền, số dư, chủ ví, thời gian hoặc
xóa ledger/snapshot. Chỉ cho hoàn tất checksum/ref_log_id một lần ở bản ghi vừa
insert trong transaction hiện tại; sau commit cả metadata cũng không được sửa.

Head admin có thể lập bút toán bù cho chuyển credit không gắn subscription và
giao dịch nạp/rút **thủ công** đã kiểm tra. Không sửa/xóa bản gốc, không đảo tiếp
bút toán bù, không bù hai lần cùng bản gốc. Với giao dịch dịch vụ, phải dùng
luồng hoàn khóa học/booking để cập nhật quyền tương ứng.

Bút toán bù nạp/rút chỉ điều chỉnh ledger credit sau đối soát; không tự chuyển
VND ở ngân hàng. Đơn gốc giữ status success để phản ánh sự kiện đã xác nhận.
Audit liên kết bút toán bù với bản gốc. Request UUID làm ID bản ghi mới.

## Quyết toán và công nợ

Khi booking đủ buổi, không còn tranh chấp và được xác nhận hoàn tất:

1. Khóa booking/subscription/ví; snapshot giá và commission hiện tại.
2. Phí nền tảng làm tròn xuống: `total * commission_rate // 100`.
3. Thu nhập = total − fee; giữ 100% thu nhập trong 7 ngày.
4. Tiền vẫn ở ví nền tảng; holding ở ví gia sư là khoản phải trả. Không cộng hai
   đại lượng này để diễn giải là tiền mặt mới của hệ thống.

Đến hạn, chỉ booking completed và settlement held được giải ngân. Gỡ reservation
của đúng settlement, chuyển thu nhập bằng ledger, giảm holding và đổi released
cùng transaction. Retry không trả lại lần hai. Job theo lô xử lý từng settlement
trong một transaction riêng để không giữ wallet lock xuyên nhiều booking.

Hoàn trước giải ngân phối hợp subscription/booking/settlement/ledger trong cùng
transaction. Hoàn một phần kết thúc booking và chi ngay phần thu nhập còn lại
theo tỷ lệ snapshot, sau khi tính lại phần fee trên giá còn lại.

Head admin không phải bên trong booking có thể hoàn **toàn bộ credit sau giải
ngân**, với lý do bắt buộc. Quy trình khóa tutor để ngăn tạo đơn rút mới, khóa và
hủy các đơn rút chưa xác nhận, thu hồi số còn khả dụng tối đa bằng tutor_income.
Phần thiếu ghi vào debt; nền tảng chỉ hoàn được nếu đủ thanh khoản thực có sau
khi trừ các khoản held khác. Không tạo thêm credit để bù thiếu.

Khi có debt, gia sư không rút/chuyển tiền. Thu nhập lần sau được ghi gross bằng
một bút toán revenue, rồi một bút toán refund về nền tảng để giảm debt; phần còn
lại mới dùng được. Chủ ví cũng có thể trả debt từ ví cá nhân. Head admin có thể
bổ sung thanh khoản nền tảng từ **ví cá nhân đã có credit** của chính mình, có
request UUID và audit; chức năng này không mint credit.

## Đối soát và snapshot

`GET /admin/wallets/{id}/reconciliation` khóa ví để đọc nhất quán và kiểm tra:

- Phương trình số dư trước/sau, amount, chiều giao dịch và checksum nội bộ/thủ công.
- Số dư hiện tại so với mốc mở ví cộng các biến động ledger.
- Holding so với các settlement held; debt so với audit công nợ gần nhất.
- Tính hợp lệ số học của snapshot gần nhất.

Ví tạo mới có audit mở ví bằng 0. Ví cũ thiếu mốc này dùng số dư trước giao dịch
đầu tiên làm baseline và ghi cảnh báo **opening_balance_unverified**; không thể
khẳng định đầy đủ lịch sử trước mốc đó. Timestamp trùng gây mơ hồ cũng được báo.
Không tự sửa số dư hoặc tái tạo ledger để làm số liệu khớp. Giao dịch nhà cung cấp
được đánh dấu cần đối soát riêng ở giai đoạn sau.

Snapshot dùng ngày Việt Nam UTC+7 và giữ **mốc đầu tiên được chụp trong ngày**.
Balance_snap = available + holding − debt. Chạy lại cùng ngày không ghi đè.
Job nhận limit/offset (tối đa 100 ví/lô); chưa suy diễn lịch sử hay backfill từ
số dư hiện tại vì schema không có đủ mốc thời gian để chứng minh số dư quá khứ.

Guard ORM không ngăn database operator chạy SQL trực tiếp. Checksum hiện tại là
kiểm tra tính nhất quán, không phải chữ ký chống người có toàn quyền DB sửa dữ liệu.

## Giao diện và kiểm tra

- **Ví:** xem số có thể chi, chuyển ví cùng chủ, trả nợ, sửa ngân hàng, hủy đơn chờ.
- **Quản trị → Ví & đối soát:** khóa/mở ví, hợp đồng, ledger, bút toán bù, thanh
  khoản nền tảng, đối soát, snapshot và job giải ngân.
- **Quản trị → Quyết toán:** hoàn credit sau giải ngân, chỉ hiện cho head admin.

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_finance.py -v
$env:TUTOR_TEST_POSTGRES = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_finance_concurrency.py -v
Remove-Item Env:TUTOR_TEST_POSTGRES
```

Test PostgreSQL chỉ chấp nhận loopback và dùng schema UUID riêng rồi dọn sau khi
chạy. Các test không gọi ngân hàng/VNPAY và không sửa bảng nghiệp vụ hiện có.
