# API Response Standard (nguồn sự thật duy nhất)

> **Dành cho AI/coding assistant:** Mọi API viết trong project này PHẢI tuân theo file này.
> - KHÔNG tự bịa format response, tên field, mã lỗi, status code hay kiểu phân trang khác với file này.
> - Nếu tình huống chưa được file này quy định: **dừng lại và hỏi**, hoặc đề xuất bổ sung vào file này trước khi code.
> - Tái sử dụng code có sẵn: `app/schemas.py` (ErrorResponse, Page, Pagination, encode_cursor/decode_cursor) và `app/errors.py` (AppException, NotFoundError, ConflictError). KHÔNG tự viết lại.



## 1. Quy tắc cốt lõi

1. **Thành công** → HTTP status 2xx đúng nghĩa, body là **resource trả thẳng** (không bọc `success`, không bọc `data` với resource đơn).
2. **Thất bại** → HTTP status 4xx/5xx đúng nghĩa, body theo **một format lỗi duy nhất** (mục 3).
3. **CẤM** trả `200` kèm `success: false` hoặc báo lỗi trong body của response thành công.
4. **CẤM** dùng các key envelope như `success`, `result`, `status`, `payload`, `response`.
5. Router/service **chỉ `raise` exception** (`NotFoundError`, `ConflictError`, `AppException`). KHÔNG tự dựng `JSONResponse` cho lỗi.

---

## 2. Quy tắc đặt tên

| Hạng mục | Quy tắc | Ví dụ đúng | Ví dụ sai |
|---|---|---|---|
| Prefix | Luôn có `/api/v1` | `/api/v1/users` | `/users`, `/api/users` |
| URL path | kebab-case, danh từ **số nhiều**, không có động từ | `/api/v1/workout-routines/{id}` | `/WorkoutRoutines`, `/getUser`, `/user` |
| Query param | snake_case | `?page_size=20&sort=-created_at` | `?pageSize=20` |
| JSON field | **snake_case** | `first_name`, `created_at` | `firstName` |
| `error.code` | lower_snake_case, ổn định, máy đọc được | `user_not_found` | `UserNotFound`, `Người dùng không tồn tại` |
| Thời gian | ISO 8601, UTC, hậu tố `Z` | `2026-10-05T08:30:00Z` | `05/10/2026`, timestamp số |
| ID | **string** | `"id": "0001"` | `"id": 1` |
| Hành động không CRUD | sub-resource + POST | `POST /api/v1/orders/{id}/cancel` | `POST /api/v1/cancelOrder` |
| Boolean | tiền tố `is_` / `has_` | `is_active` | `active_flag` |

- Field không có giá trị: trả `null`, **không bỏ field**.
- Chỉ tăng version (`/v2`) khi có breaking change (đổi tên/xóa field, đổi kiểu). Thêm field mới KHÔNG cần tăng version.

---

## 3. Format lỗi (dùng cho MỌI lỗi, MỌI endpoint)

```json
{
  "error": {
    "code": "user_not_found",
    "message": "Người dùng không tồn tại",
    "details": [],
    "request_id": "req_8f3a2c1d"
  }
}
```

| Field | Kiểu | Quy tắc |
|---|---|---|
| `code` | string | Bắt buộc. Mã ổn định, frontend chỉ `switch` theo field này |
| `message` | string | Bắt buộc. Chỉ để hiển thị, có thể đổi. Frontend KHÔNG so sánh theo message |
| `details` | array | Bắt buộc, mặc định `[]`. Dùng cho lỗi validation |
| `request_id` | string | Lấy từ `X-Request-ID` |

Phần tử của `details`:

```json
{ "field": "email", "message": "value is not a valid email address", "code": "value_error" }
```

- `field` là đường dẫn field bị lỗi (vd `"email"`, `"address.city"`), `null` nếu lỗi không gắn với field cụ thể.
- Không bao giờ trả stack trace, câu SQL, đường dẫn file hay thông tin nội bộ trong lỗi. Lỗi 500 luôn dùng message chung.

---

## 4. HTTP Method và Status Code

| Method | Mục đích | Thành công | Body thành công |
|---|---|---|---|
| GET (list) | Lấy danh sách | **200** | `{ "data": [...], "pagination": {...} }` |
| GET (one) | Lấy một resource | **200** | object resource |
| POST (tạo mới) | Tạo resource | **201** + header `Location: /api/v1/<resource>/<id>` | object resource vừa tạo |
| POST (hành động) | Thực thi hành động | **200**, hoặc **202** nếu xử lý bất đồng bộ | kết quả hành động / thông tin job |
| PUT | Thay thế toàn bộ (phải gửi đủ field) | **200** | object resource sau cập nhật |
| PATCH | Cập nhật một phần | **200** | object resource sau cập nhật |
| DELETE | Xóa | **204** | **không có body** |

### Mã lỗi được phép dùng

| Status | `error.code` gợi ý | Khi nào dùng |
|---|---|---|
| 400 | `bad_request` | Request sai cú pháp (JSON hỏng, header sai) |
| 401 | `unauthorized` | Thiếu / sai / hết hạn token |
| 403 | `permission_denied` | Đã đăng nhập nhưng không đủ quyền |
| 404 | `<resource>_not_found` | Không tìm thấy resource (vd `user_not_found`) |
| 409 | `<mô_tả>` (vd `email_already_exists`) | Xung đột dữ liệu: trùng unique, sai version |
| 422 | `validation_error` | Đúng cú pháp nhưng sai validation / nghiệp vụ (FastAPI mặc định) |
| 429 | `rate_limit_exceeded` | Vượt rate limit |
| 500 | `internal_error` | Lỗi server không lường trước |
| 502/503 | `service_unavailable` | Phụ thuộc bên ngoài lỗi / bảo trì |

- Danh sách rỗng vẫn là **200** với `"data": []`. KHÔNG trả 404.
- Không dùng status code ngoài bảng này khi chưa hỏi.

---

## 5. Phân trang (cursor-based, mặc định)

**Request:** `GET /api/v1/users?limit=20&cursor=<next_cursor>`

| Param | Kiểu | Mặc định | Ràng buộc |
|---|---|---|---|
| `limit` | int | 20 | 1 ≤ limit ≤ 100 |
| `cursor` | string | không có | Lấy từ `next_cursor` của response trước, là chuỗi mờ (opaque) |

**Response:**

```json
{
  "data": [ { "id": "0001", "...": "..." } ],
  "pagination": {
    "next_cursor": "eyJpZCI6IjAwMDIifQ",
    "has_more": true
  }
}
```

- Trang cuối: `"has_more": false`, `"next_cursor": null`.
- Cài đặt: lấy `limit + 1` bản ghi để xác định `has_more`. KHÔNG dùng `COUNT(*)`.
- Cursor encode/decode bằng `encode_cursor` / `decode_cursor` trong `app/schemas.py`. Client không được tự tạo cursor.
- Response danh sách luôn dùng `Page[T]` từ `app/schemas.py`.
- **CẤM** tự thêm `page`, `total`, `total_pages`, `offset` vào response nếu chưa được duyệt.
- Ngoại lệ: màn hình admin cần nhảy trang thì dùng offset (`page`, `page_size`) và phải ghi rõ endpoint đó trong mục 11 của file này.

**Sắp xếp và lọc:** `?sort=-created_at` (dấu `-` là giảm dần), `?status=active`. Field filter dùng snake_case.

---

## 6. Header chuẩn

| Header | Hướng | Quy tắc |
|---|---|---|
| `Authorization: Bearer <token>` | request | Xác thực |
| `X-Request-ID` | request/response | Nếu client không gửi thì server tạo (`req_<8 hex>`). Luôn trả lại trong response |
| `Location` | response | Bắt buộc với 201 |
| `Idempotency-Key` | request | Dùng cho POST quan trọng (thanh toán, tạo đơn) để retry không tạo trùng |
| `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining` | response | Kèm với 429 và (khuyến nghị) mọi response có rate limit |

---

## 7. Ví dụ response chuẩn

### GET list → 200
```json
{
  "data": [
    { "id": "0001", "first_name": "An", "last_name": "Nguyen", "email": "an@example.com", "created_at": "2026-10-05T08:30:00Z" }
  ],
  "pagination": { "next_cursor": "eyJpZCI6IjAwMDEifQ", "has_more": true }
}
```

### GET one → 200
```json
{ "id": "0001", "first_name": "An", "last_name": "Nguyen", "email": "an@example.com", "created_at": "2026-10-05T08:30:00Z" }
```

### POST → 201 (header `Location: /api/v1/users/0051`)
```json
{ "id": "0051", "first_name": "An", "last_name": "Nguyen", "email": "an@example.com", "created_at": "2026-10-05T09:12:41Z" }
```

### PATCH / PUT → 200
```json
{ "id": "0001", "first_name": "Bình", "last_name": "Nguyen", "email": "an@example.com", "created_at": "2026-10-05T08:30:00Z" }
```

### DELETE → 204
Không có body.

### 404
```json
{ "error": { "code": "user_not_found", "message": "Người dùng không tồn tại", "details": [], "request_id": "req_b27c90aa" } }
```

### 409
```json
{ "error": { "code": "email_already_exists", "message": "Email đã được sử dụng", "details": [], "request_id": "req_c3d1e7f2" } }
```

### 422
```json
{
  "error": {
    "code": "validation_error",
    "message": "Dữ liệu gửi lên không hợp lệ",
    "details": [
      { "field": "email", "message": "value is not a valid email address", "code": "value_error" },
      { "field": "last_name", "message": "Field required", "code": "missing" }
    ],
    "request_id": "req_a91b44e0"
  }
}
```

### 401 / 403 / 429 / 500
```json
{ "error": { "code": "unauthorized", "message": "Token không hợp lệ hoặc đã hết hạn", "details": [], "request_id": "req_f6a0c3d5" } }
{ "error": { "code": "permission_denied", "message": "Bạn không có quyền thực hiện thao tác này", "details": [], "request_id": "req_07b1d4e6" } }
{ "error": { "code": "rate_limit_exceeded", "message": "Bạn gửi quá nhiều yêu cầu, vui lòng thử lại sau 30 giây", "details": [], "request_id": "req_18c2e5f7" } }
{ "error": { "code": "internal_error", "message": "Lỗi hệ thống, vui lòng thử lại sau", "details": [], "request_id": "req_3ae40719" } }
```

---

## 8. Mẫu code bắt buộc (FastAPI)

```python
from fastapi import APIRouter, Query, Response
from app.errors import NotFoundError, ConflictError
from app.schemas import ErrorResponse, Page, Pagination, encode_cursor, decode_cursor

router = APIRouter(prefix="/api/v1/<resources>", tags=["<resources>"])

ERROR_RESPONSES = {404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}

@router.get("", response_model=Page[ItemOut], responses=ERROR_RESPONSES)      # list
@router.get("/{item_id}", response_model=ItemOut, responses=ERROR_RESPONSES)  # one
@router.post("", response_model=ItemOut, status_code=201, responses=ERROR_RESPONSES)
@router.patch("/{item_id}", response_model=ItemOut, responses=ERROR_RESPONSES)
@router.delete("/{item_id}", status_code=204, responses=ERROR_RESPONSES)
```

Quy tắc code:
- Mọi endpoint khai báo `response_model` và `status_code` rõ ràng, kèm `responses=ERROR_RESPONSES` để Swagger đúng.
- Schema tách riêng: `XxxCreate` (input tạo), `XxxUpdate` (input sửa, field optional), `XxxOut` (output). Không trả thẳng model DB.
- Lỗi: `raise NotFoundError("<resource>_not_found", "...")`, `raise ConflictError("<mô_tả>", "...")`. Không `return {"error": ...}`, không `raise HTTPException(...)` trực tiếp.
- Handler lỗi toàn cục đã đăng ký bằng `register_exception_handlers(app)`. Không đăng ký handler riêng khác format.
- Đầu ra thời gian dùng `datetime` timezone-aware UTC.

---

## 9. Checklist trước khi AI hoàn thành một endpoint

- [ ] URL có `/api/v1`, kebab-case, danh từ số nhiều
- [ ] JSON field và query param đều snake_case
- [ ] Status code thành công đúng bảng mục 4 (POST=201+Location, DELETE=204)
- [ ] Resource trả thẳng, danh sách dùng `Page[T]`
- [ ] Lỗi qua `raise` exception, có `error.code` snake_case ổn định
- [ ] Phân trang cursor, `limit` có `ge=1, le=100`
- [ ] Có `response_model`, `status_code`, `responses=ERROR_RESPONSES`
- [ ] ID là string, thời gian ISO 8601 UTC
- [ ] Không có `success`, `result`, `status` ngoài format này
- [ ] Không có field/mã lỗi/status nào mà file này chưa quy định

---

## 10. Danh sách `error.code` đã đăng ký

> Thêm code mới phải ghi vào bảng này trước. AI KHÔNG tự bịa code ngoài bảng.

| code | Status | Ý nghĩa |
|---|---|---|
| `bad_request` | 400 | Request sai cú pháp |
| `unauthorized` | 401 | Thiếu/sai/hết hạn token |
| `permission_denied` | 403 | Không đủ quyền |
| `not_found` | 404 | Mặc định cho tài nguyên không xác định |
| `user_not_found` | 404 | Không có user |
| `conflict` | 409 | Mặc định cho xung đột |
| `email_already_exists` | 409 | Email trùng |
| `validation_error` | 422 | Dữ liệu không hợp lệ (có `details`) |
| `rate_limit_exceeded` | 429 | Vượt rate limit |
| `internal_error` | 500 | Lỗi hệ thống |
| `http_<status>` | khác | Lỗi mặc định của framework (route không tồn tại, 405...) |

---

## 11. Ngoại lệ đã được duyệt

> Chưa có. Mọi ngoại lệ so với file này phải được ghi vào đây (endpoint, lý do, người duyệt) trước khi code.