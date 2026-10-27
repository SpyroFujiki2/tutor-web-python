# Review thủ công scaffold — 25/10/2026

Phạm vi: đọc cấu hình backend/frontend, lần theo request từ React đến route
FastAPI, kiểm tra lifecycle request, ưu tiên biến môi trường, CORS, dependency
và hướng dẫn chạy. Review do một agent thực hiện trực tiếp, không phải review
độc lập của người thứ hai. Các kiểm tra tự động hỗ trợ kết luận bên dưới.

## Phát hiện và thay đổi

| Mức độ | Phát hiện ban đầu | Xử lý |
| --- | --- | --- |
| Vừa | Frontend vẫn là template và chưa kiểm chứng kết nối backend | Thay bằng khung Tutor Web và component gọi health API với trạng thái tải/thành công/lỗi, nút thử lại |
| Vừa | `API_BASE_URL` có thể là `undefined` khi thiếu biến môi trường | Thêm mặc định localhost; chuẩn hóa dấu `/` cuối; giá trị rỗng dùng cùng origin |
| Vừa | Cấu hình, CORS và route gộp trong `main.py`; import ghi vào `os.environ` | Tách config/router/schema và `create_app`; đọc `.env` không sửa process environment |
| Vừa | Default CORS chứa domain deploy và mở mọi method/header | Default chỉ localhost; domain deploy khai báo tường minh; hiện chỉ cho GET và các header đang dùng |
| Thấp | `requirements.txt` chứa toàn bộ gói môi trường, gồm CLI/cloud tooling không dùng trực tiếp | Giữ bốn dependency runtime trực tiếp; HTTPX phục vụ test nằm ở requirements-dev |
| Thấp | README tạo venv ở root trong khi dự án có `backend/.venv` | Đồng bộ hướng dẫn và VS Code về `backend/.venv` |
| Thấp | Vite có thể tự đổi port khiến lệch CORS | Cố định port 5173 với `strictPort` |

## Đọc lại code sau thay đổi

- `backend/app/main.py`: factory tạo instance riêng để test cấu hình CORS mà
  không thay global app; giữ nguyên URL và JSON của `/api/health`.
- `backend/app/core/config.py`: kiểm tra đường dẫn `.env` sau khi chuyển module;
  thứ tự ưu tiên process > file > default; cấu hình rỗng không rơi về default.
  Origins có path/query/credentials, wildcard hoặc port không hợp lệ bị từ chối.
- `frontend/src/components/ApiStatus.jsx`: cleanup hủy request, kiểm tra signal
  trước khi set state; dùng số lần thử để không hiện lại kết quả cũ khi retry.
  Luồng cleanup cũng áp dụng cho effect được chạy lại bởi React StrictMode.
- `frontend/src/services/api.js`: kiểm tra HTTP status trước JSON, xác thực shape
  health response, giữ nguyên nguyên nhân lỗi qua `cause`. Khi đọc lại phát hiện
  timeout trong lúc đọc body bị báo nhầm thành JSON lỗi; đã sửa và thêm test.
- Giao diện có label, trạng thái được đọc qua live region, focus bàn phím và
  layout một cột trên màn hình nhỏ. Đây là kiểm tra code, chưa phải xác minh
  giao diện hay accessibility trên trình duyệt.

## Kết quả kiểm tra

- Backend: 12 test qua `unittest`/FastAPI TestClient, gồm health contract,
  OpenAPI, CORS request/preflight được phép và bị từ chối, cấu hình môi trường.
- Frontend: 9 test HTTP client qua Node test runner đều qua; ESLint và production
  build đều thành công. Node test runner và Vite build phải chạy ngoài sandbox
  do sandbox chặn tạo process với `spawn EPERM`.
- `pip check` không phát hiện dependency hỏng trong venv hiện tại;
  `git diff --check` không báo lỗi whitespace trong các file tracked.
- Chưa chạy kiểm thử browser end-to-end hoặc cài thử từ môi trường hoàn toàn
  trống; kết quả dựa trên venv và node_modules đang có trong workspace.

## Giới hạn và việc còn phải làm

1. Chưa có DB, migration, xác thực, phân quyền hoặc CRUD nghiệp vụ. Các quyết định
   cần chốt và thứ tự triển khai được liệt kê trong README.
2. `/api/health` là liveness; bổ sung readiness khi có DB/dịch vụ phụ thuộc.
3. CORS không phải cơ chế xác thực hay chặn request ngoài browser. Khi thêm
   POST/PUT/PATCH/DELETE hoặc Authorization, cập nhật allow_methods/allow_headers
   và kiểm tra preflight tương ứng. Không bật credentials trước khi chọn auth.
4. Pin dependency trực tiếp chưa phải lock đầy đủ dependency bắc cầu của Python;
   cần bổ sung lock/CI và cài từ môi trường sạch trước khi deploy.
5. Chưa có logging và error contract chung cho nghiệp vụ; thiết kế cùng tính
   năng đầu tiên để tránh tạo abstraction không có nhu cầu sử dụng.

## Cập nhật module nghiệp vụ — 27/10/2026

Đã thêm `app/modules/` gồm 24 file tính năng thuộc 5 nhóm. Mỗi file có một hàm
mẫu và TODO mô tả việc/cách làm phần còn lại; chi tiết [modules.md](modules.md).
Model, dependency và router hiện có được giữ nguyên trong đợt này.

Đã đọc lại code theo các ranh giới:

- Danh tính truyền vào phải đến từ auth server; các query booking, subscription,
  đơn nạp/rút và ví giới hạn đúng người tham gia/chủ sở hữu. Admin không tự vượt
  quyền booking, việc phân công tranh chấp vẫn cần luồng riêng.
- Lesson xét type, chủ subscription, status và thời gian thực; hidden course chỉ
  ẩn danh mục. Tiến độ/attendance lịch sử không được dùng để bỏ qua thời hạn media.
- Quyền đọc post được áp dụng trước khi đọc comment/báo cáo; min_role_level chưa
  cấu hình bị từ chối. Không có đường public đọc bài ẩn trong hàm mẫu.
- Lịch sử internal transaction dùng projection, tránh vô tình trả số dư trước/sau
  của ví đối tác; tất cả ORM result vẫn cần response schema có allowlist.
- Mẫu ghi dùng add/flush, không commit; các thay đổi và audit có thể rollback
  cùng transaction caller. Không có hàm cập nhật tiền được triển khai nửa chừng.
- Timestamp do mẫu tạo là UTC không tzinfo để khớp model; phải thống nhất DB
  timezone hoặc migration timestamptz trước khi deploy.

Kiểm tra: import đủ 24 file, mỗi file một function/TODO; tổng **24 test backend
đạt** gồm 9 test mới về quyền, lọc dữ liệu và rollback. Các test nghiệp vụ dùng
SQLite fixture; chưa xác minh lock, race, provider callback hay migration thật.

Các giới hạn còn lại của scaffold vẫn áp dụng: chưa có session production/auth/
API nghiệp vụ. [database-flow.md](database-flow.md) phân biệt luồng đã có code,
luồng thiết kế và các điểm thiếu trong schema/policy trước khi triển khai.

### Bổ sung core/security.py

Thêm một hàm mẫu `hash_password` dùng `pwdlib[argon2]` (Argon2id, salt riêng
mỗi lần), từ chối input rỗng/sai kiểu và giữ nguyên Unicode/khoảng trắng.
Không tự viết thuật toán hash hoặc xử lý salt. Hàm không ghi DB, log hay
commit. Verify/rehash, session/token, current_user và các luồng auth còn TODO.

Đã kiểm tra round trip bằng thư viện, mật khẩu sai, salt khác nhau và input;
tổng **27 test backend đạt**, `pip check` không báo dependency hỏng. Cập nhật
requirements, hướng dẫn module, luồng đăng ký trong DB và README tương ứng.

### JWT Bearer và refresh rotation — 27/10/2026

Đã chọn JWT Bearer với PyJWT: access 15 phút, refresh/phiên tối đa 7 ngày,
TTL qua môi trường, HS256 cố định, không có signing key mặc định. Decoder yêu
cầu issuer/audience, chữ ký, timestamps, UUID và type/header access/refresh riêng.
Secret và token được che trong repr; không đưa role vào JWT để quyết định quyền.

Thêm AuthSession ngoài 24 model DBML để lưu hash refresh, hạn tuyệt đối và thu
hồi. Renew dùng conditional UPDATE/RETURNING để consume refresh một lần; reuse
thu hồi phiên, logout cũng thu hồi phiên. get_authenticated_user kiểm tra JWT,
session trong DB và user active. get_access_claims không tự thay kiểm tra DB.

Review đặc biệt ranh giới transaction: renew trả RenewalResult khi từ chối để
caller commit revocation trước 401, tránh rollback việc phát hiện reuse. Client
phải serialize refresh; chưa có grace window cho mất response sau commit.
CORS cho GET/POST và Authorization, chưa bật cookie credentials hoặc route auth.

44 test backend đạt, pip check không báo dependency hỏng. Test lifecycle dùng
SQLite, metadata được compile qua PostgreSQL dialect; chưa test row contention
thực tế trên PostgreSQL. Cần Session, migration auth_sessions, verify mật khẩu
và router/schema trước khi tích hợp production. Xem [security.md](security.md).

### Kết nối PostgreSQL và cài trên máy khác — 27/10/2026

Đã tạo tutor_web và role tutor_app không superuser trên PostgreSQL 18 local,
chạy migration 0001_initial_schema thành công: 25 bảng ứng dụng, 15 enum.
Alembic check không phát hiện drift; phiên runtime dùng timezone UTC.

Đã thêm engine/pool/Session trong lifespan, dependency get_session/current_user,
readiness kiểm tra kết nối và migration head; secret/SQL không xuất ra response.
Session không tự commit. Với auth dependency đã query, endpoint phải dùng
transaction hiện hành; refresh commit revocation trước lỗi 401 như tài liệu.

Migration là snapshot cố định, không import Base để tạo bảng lúc chạy. Review
đã giữ tên 4 unique constraint phát sinh từ cột và tạo native enum đúng một lần.
Bootstrap không reset mật khẩu role, không lấy database của chủ khác, không sửa
pg_hba hoặc xóa dữ liệu. init_env giữ nguyên secret và bộ cài không có path máy.

Kiểm tra: 53 test backend đạt; health/ready HTTP 200 qua app với DB thật;
rotation/reuse/session rollback trên PostgreSQL thật và không giữ dữ liệu thử.
Dependency resolve từ môi trường giả lập sạch thành công, pip check không lỗi.
Docker Compose đã chuẩn bị theo layout PG18, chưa chạy trên máy này vì chưa có
Docker. Chưa test cạnh tranh nhiều worker. Xem [database-setup.md](database-setup.md).

### Tối giản cấu hình về DATABASE_URL

Runtime chỉ nhận DATABASE_URL, không fallback DB_*. SSL/timeout tùy chỉnh đặt
trong query URL; mặc định connect timeout 5 giây ở code. .env.example chỉ còn
DATABASE_URL và JWT_SECRET_KEY. Giá trị JWT mặc định và URL frontend không cần
khai báo lại; override khác mặc định được giữ nguyên.

init_env chuyển DB_* cũ sang URL đã encode, giữ credential, bỏ biến cũ và không
in secret. Process URL không ghi đè credential cục bộ. Bootstrap thử URL trước,
không hỏi admin nếu DB đã kết nối; lần tạo mới native dùng input ẩn. Docker dùng
password file trong .local; cổng publish được setup suy ra từ DATABASE_URL.

56 test đạt; đã kiểm tra kết nối thật sau chuyển đổi. Docker chưa có trên máy
nên chưa chạy integration Compose. Không đổi mật khẩu role hoặc schema DB.

### Review verify/authenticate và schema login — 27/10/2026

Phạm vi: code người dùng vừa bổ sung trong security.py, auth/authenticate.py và
schemas/auth.py; kiểm tra với module cấp token và router hiện tại. Đợt này cập
nhật tài liệu và thêm test, không sửa implementation ứng dụng hoặc dữ liệu DB.

Phát hiện còn mở, theo mức độ ưu tiên:

1. **Vừa — dummy hash tạo lại mỗi request.** Trong authenticate_user, nhánh thiếu
   user/hash gọi hash_password(token_urlsafe(32)) rồi verify. Spy xác nhận nhánh
   user không tồn tại tạo thêm một hash, nhánh sai mật khẩu tạo thêm 0 hash.
   Điều này tăng chi phí và tạo khác biệt công việc giữa hai loại thất bại.
   Chuyển dummy hash lên biến cấp module, khởi tạo một lần và dùng lại để verify.
2. **Vừa — email schema chưa kiểm tra định dạng/blank.** LoginRequest.email chỉ
   có giới hạn độ dài; chuỗi toàn khoảng trắng được chấp nhận. Bổ sung validation
   và dùng cùng chuẩn hóa strip().lower() ở đăng ký/import. Chưa có API đăng ký.
3. **Thấp — TTL response chấp nhận số âm.** TokenResponse chưa ràng buộc TTL;
   đã kiểm tra có thể tạo model với cả hai TTL=-1. Cân nhắc Field(gt=0) theo hợp
   đồng. Bộ tạo JWT hiện sinh TTL dương; điểm này là khoảng trống validation DTO.

Các phần đã đạt kiểm tra:

- verify_password trả tuple, giữ Unicode/khoảng trắng, từ chối sai/mất/hash lỗi
  và trả hash nâng cấp sau xác thực thành công.
- authenticate_user dùng đúng SQLAlchemy Session, chuẩn hóa email, trả UUID chỉ
  khi tài khoản active; không có user/sai mật khẩu/status khác active trả None.
- Rehash chỉ gán vào Session, không commit; flush rồi rollback khôi phục hash cũ.
- LoginRequest dùng SecretStr; TokenResponse che token trong repr nhưng JSON vẫn
  có token. HTTP layer phải get_secret_value() và không log payload/response.
- Router chỉ đăng ký /api/health và /api/ready; login/refresh/logout còn TODO.

Thêm 9 test trong backend/tests/test_authentication.py; **65 test backend đạt**.
Các test mới dùng SQLite trong bộ nhớ, không tạo user trong PostgreSQL thật.
Chưa có kiểm thử auth endpoint end-to-end vì route chưa được viết. Kết quả test
không bao phủ/sửa các điểm review mở ở trên; chi tiết luồng mới ở security.md,
modules.md và database-flow.md.

### Cập nhật EmailStr và đóng các điểm review schema

LoginRequest.email đã chuyển sang EmailStr của Pydantic, giữ max_length=320 và
khai báo email-validator==2.3.0 trong requirements để cài được trên môi trường mới.
Test xác nhận từ chối email blank/sai định dạng, chuẩn hóa domain và OpenAPI
schema có format=email. Không dùng validation này để kết luận chủ sở hữu hộp thư.

Đồng thời xác nhận các thay đổi người dùng đã thực hiện: dummy_hash được tạo ở
cấp module, không tạo lại mỗi request; hai TTL TokenResponse đã có Field(gt=0).
Thêm test regression cho các trường hợp này. Ba phát hiện ở review trước đã đóng;
auth route và rate limit vẫn chưa triển khai. Tổng 69 test backend đạt, pip check
không phát hiện dependency hỏng. Không sửa model/database cho thay đổi email.
