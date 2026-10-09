# CLAUDE.md — Luật bắt buộc cho AI/coding assistant

> File này là **bản đồ tài liệu**. Nó KHÔNG thay thế các file trong `docs/`: nó chỉ cho biết khi chạm vào phần nào thì PHẢI đọc file nào, và file nào thắng khi các file mâu thuẫn.
> Từ khoá PHẢI / KHÔNG ĐƯỢC / NÊN theo nghĩa RFC 2119.

---

## 1. Luật số 1: đọc tài liệu trước, code sau

Trước khi viết hoặc sửa **bất kỳ** code, SQL, migration, test, nhánh hay commit nào:

1. Xác định công việc chạm vào khu vực nào (bảng ở mục 2). Một việc có thể chạm nhiều khu vực, khi đó đọc **tất cả** file tương ứng.
2. **Đọc toàn bộ** các file bắt buộc của khu vực đó bằng công cụ đọc file. KHÔNG dựa vào trí nhớ, phiên làm việc trước hay "quy ước phổ biến".
3. Trước khi code, nêu ngắn cho người dùng: đã đọc file nào, áp dụng quy tắc nào (ví dụ: "Theo `Claude_api_respone.md` §4: POST trả 201 + Location").
4. Code **đúng theo** tài liệu: tên field, mã lỗi, status code, kiểu ID, đơn vị, enum, cấu trúc thư mục, tên nhánh, commit message.
5. Trước khi báo xong, chạy lại **checklist** của các file đã đọc và nêu kết quả.

KHÔNG ĐƯỢC:
- Tự bịa format response, `error.code`, status code, enum, cột DB, permission, role, tiền tố route, tên nhánh hay kiểu commit không có trong tài liệu.
- Bỏ qua tài liệu vì việc "nhỏ" hay "chỉ sửa một dòng".

Khi tài liệu **không quy định** tình huống đang gặp, hoặc yêu cầu của người dùng **trái** tài liệu: **dừng lại và hỏi**, nêu rõ chỗ thiếu/mâu thuẫn và đề xuất bổ sung vào file tài liệu tương ứng trước khi code.

---

## 2. Bản đồ: chạm vào đâu thì đọc gì

| Công việc chạm vào | PHẢI đọc trước |
|---|---|
| **Bất kỳ endpoint/API nào** (route, schema Pydantic, response, lỗi, phân trang, header) | [docs/architecture/Claude_api_respone.md](docs/architecture/Claude_api_respone.md) · [docs/architecture/05-tooling-workflow.md](docs/architecture/05-tooling-workflow.md) §1, §2, §4, §5, §6 |
| Đăng nhập, token, refresh, mật khẩu, role, permission, `get_current_user`, `require_permission`, thiết bị | [docs/architecture/04-auth-strategy.md](docs/architecture/04-auth-strategy.md) (toàn bộ) · [Claude_api_respone.md](docs/architecture/Claude_api_respone.md) |
| File core: `backend/app/core/*`, `middleware/`, `schemas/base.py`, `models/enums.py`, `main.py`, `api/v1/router.py` | [05-tooling-workflow.md](docs/architecture/05-tooling-workflow.md) §7, §9.4 · [Claude_api_respone.md](docs/architecture/Claude_api_respone.md) §8 · nếu là `security.py`/`dependencies.py`: [04-auth-strategy.md](docs/architecture/04-auth-strategy.md) §8 |
| Model SQLAlchemy, truy vấn, CRUD, service đọc/ghi DB | [docs/database/design-overview.md](docs/database/design-overview.md) · [docs/database/data-dictionary.md](docs/database/data-dictionary.md) (phần schema liên quan) · [05-tooling-workflow.md](docs/architecture/05-tooling-workflow.md) §2.2–2.4, §2.6, §6 |
| Thêm/sửa bảng, cột, index, view, migration Alembic | Như dòng trên + [docs/database/erd.md](docs/database/erd.md) · [docs/database/normalization.md](docs/database/normalization.md) · [database/postgresql/README.md](database/postgresql/README.md) · [05-tooling-workflow.md](docs/architecture/05-tooling-workflow.md) §8 |
| Seed, dữ liệu test, fixture, persona test | [docs/database/test-dataset.md](docs/database/test-dataset.md) · [04-auth-strategy.md](docs/architecture/04-auth-strategy.md) §9 · [05-tooling-workflow.md](docs/architecture/05-tooling-workflow.md) §10 |
| Mock API | [05-tooling-workflow.md](docs/architecture/05-tooling-workflow.md) §5 · [Claude_api_respone.md](docs/architecture/Claude_api_respone.md) |
| Viết test | [05-tooling-workflow.md](docs/architecture/05-tooling-workflow.md) §10 · [docs/database/test-dataset.md](docs/database/test-dataset.md) |
| Frontend gọi API, lưu token, interceptor | [04-auth-strategy.md](docs/architecture/04-auth-strategy.md) §5, §7 · [Claude_api_respone.md](docs/architecture/Claude_api_respone.md) §3, §5, §7 · [frontend/README.md](frontend/README.md) |
| AI services, worker | [ai-services/README.md](ai-services/README.md) · [05-tooling-workflow.md](docs/architecture/05-tooling-workflow.md) §1.3, §6.3 (route `/ai/*`) |
| Cấu hình, biến môi trường, Docker | [05-tooling-workflow.md](docs/architecture/05-tooling-workflow.md) §7.3, §7.6, §8.2 · [04-auth-strategy.md](docs/architecture/04-auth-strategy.md) §6.4 |
| **Tạo nhánh, commit, PR** | [docs/architecture/Claude_git.md](docs/architecture/Claude_git.md) (toàn bộ) · [05-tooling-workflow.md](docs/architecture/05-tooling-workflow.md) §9.3–9.4 |

---

## 3. Thứ tự ưu tiên khi tài liệu mâu thuẫn

Các tài liệu được viết ở các thời điểm khác nhau và có chỗ lệch nhau. Áp dụng theo thứ tự sau; KHÔNG tự chọn theo cảm tính.

| Chủ đề | File thắng | Phần bị thay thế |
|---|---|---|
| Cấu trúc bảng, cột, kiểu dữ liệu, enum, ràng buộc | `database/postgresql/` → `docs/database/` | Mọi mô tả DB trong doc 04, 05 nếu lệch |
| **Format response thành công/lỗi, `error.code`, status code, phân trang, header** | **`Claude_api_respone.md`** | Doc 05 §2.5, §3, §4 (phần `response_model`), §7.4 (tên lớp/`error_code`); doc 04 §4 (câu về envelope), §5 (dạng viết hoa của mã), §7 (cách đọc response trong interceptor) |
| Kiểu ID trong JSON | **DB**, theo doc 05 §2.2, §2.4: UUID (chuỗi) cho dữ liệu user, **số nguyên** cho danh mục | Ví dụ `"id": "0001"` trong `Claude_api_respone.md` chỉ là minh hoạ |
| Nghiệp vụ auth (luồng token, rotation, RBAC, khoá tài khoản) | `04-auth-strategy.md` | — |
| **Nhánh, commit message** | **`Claude_git.md`** | Doc 05 §9.1, §9.2 và `CONTRIBUTING.md` |
| Kiến trúc tầng, layout thư mục, mock, test, migration | `05-tooling-workflow.md` | — |

### 3.1. Hệ quả cụ thể (áp dụng ngay, không cần hỏi lại)

**API**
- Không envelope: resource trả thẳng; danh sách dùng `Page[T]` = `{ "data": [...], "pagination": { "next_cursor", "has_more" } }`. KHÔNG dùng `BaseResponse`, `PaginatedResponse`, `success`, `page`, `total`, `total_pages`.
- Lỗi luôn là `{ "error": { "code", "message", "details", "request_id" } }`, `code` **lower_snake_case**.
- Mã lỗi trong doc 04 §5 và doc 05 §3.3 dùng ở dạng chữ thường, và PHẢI được đăng ký trong `Claude_api_respone.md` §10 trước khi dùng:
  `INVALID_CREDENTIALS` → `invalid_credentials`, `TOKEN_EXPIRED` → `token_expired`, `TOKEN_INVALID` → `token_invalid`, `TOKEN_REUSED` → `token_reused`, `ACCOUNT_LOCKED` → `account_locked`, `ACCOUNT_DISABLED` → `account_disabled`, `EMAIL_NOT_VERIFIED` → `email_not_verified`, `WEAK_PASSWORD` → `weak_password`, `PERMISSION_DENIED` → `permission_denied`, `VALIDATION_ERROR` → `validation_error`, `EMAIL_ALREADY_EXISTS` → `email_already_exists`, `CONFLICT` → `conflict`, `BAD_REQUEST` → `bad_request`.
  Đổi tên: `RATE_LIMITED` → `rate_limit_exceeded`; `INTERNAL_SERVER_ERROR` → `internal_error`; `SERVICE_UNAVAILABLE` → `service_unavailable`; `NOT_FOUND` → `<resource>_not_found` (vd `exercise_not_found`).
- Mã chưa có trong §10 (`invalid_credentials`, `token_*`, `account_*`, `423`…): **hỏi người dùng/đề xuất thêm vào §10 trước**, không tự dùng.
- Phân trang mặc định là **cursor** (`limit`, `cursor`). Màn hình cần nhảy trang (admin) thì phải được ghi vào §11 của `Claude_api_respone.md` trước.
- Frontend đọc lỗi qua `error.response.data.error.code`, đọc dữ liệu qua `res.data` (không có `.data.data`). Mẫu interceptor ở doc 04 §7 phải điều chỉnh theo đúng điểm này.

**Vị trí code** (tên lớp theo `Claude_api_respone.md`, vị trí file theo layout doc 05 §6.2, §7.2 — đúng với cấu trúc thư mục hiện có):
- `ErrorResponse`, `Page`, `Pagination`, `encode_cursor`, `decode_cursor` → `backend/app/schemas/base.py`.
- `AppException`, `NotFoundError`, `ConflictError` (và các lớp lỗi khác) + `register_exception_handlers` → `backend/app/core/exceptions.py`.
- KHÔNG tạo `app/schemas.py` hay `app/errors.py` (sẽ xung đột với package `app/schemas/`).

**Git** (theo `Claude_git.md`)
- Nhánh: `<type>/<mo-ta-tieng-anh>`, ví dụ `feat/add-exercise-search`; tạo từ `main` mới nhất. KHÔNG dùng `feature/...`.
- Commit: tiếng Anh, thể mệnh lệnh, type trong danh sách của `Claude_git.md` (KHÔNG có `design`).
- **KHÔNG** thêm `Co-Authored-By`, `Generated with Claude Code` hay chữ ký AI nào; KHÔNG đổi git config, KHÔNG dùng `--author`.
- Chỉ tạo nhánh/commit/push khi người dùng yêu cầu.

---

## 4. Quy trình mỗi lần nhận việc

```
1. Hiểu việc  → chưa rõ thì hỏi
2. Tra mục 2  → liệt kê file phải đọc
3. Đọc hết    → nêu file đã đọc + quy tắc áp dụng
4. Kiểm tra mâu thuẫn → áp dụng mục 3; không có trong mục 3 thì hỏi
5. Code       → đúng tài liệu, tái sử dụng code có sẵn, không viết lại helper
6. Checklist  → chạy checklist của từng file đã đọc, báo kết quả
```

Checklist nằm ở: `Claude_api_respone.md` §9 · `04-auth-strategy.md` §10 · `05-tooling-workflow.md` §11 · `Claude_git.md` §3.

---

## 5. Khi sửa chính tài liệu

- Tài liệu là nguồn sự thật. Nếu code cần khác tài liệu, **sửa tài liệu trước** (được người dùng đồng ý), rồi mới code.
- `docs/database/data-dictionary.md` là file **tự sinh**: KHÔNG sửa tay, sửa `COMMENT ON` trong `database/postgresql/schemas/*.sql` rồi sinh lại.
- Thêm tài liệu mới trong `docs/`: PHẢI thêm một dòng vào bảng mục 2 của file này.
