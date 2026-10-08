# Task 4 — Chiến lược Xác thực & Phân quyền (Auth Strategy)

> **Trạng thái:** Chuẩn thống nhất — mọi thành viên PHẢI tuân theo.
> **Cập nhật:** 2026-10-08 · **Stack:** FastAPI · python-jose (JWT) · passlib[bcrypt] · PostgreSQL (schema `auth`) · Redis
> **Nguồn sự thật:** `database/postgresql/schemas/02_auth.sql` và `database/postgresql/seeds/01_rbac.sql`. Nếu doc này mâu thuẫn với DB, **DB đúng**, và doc phải được sửa.
> **Từ khoá:** PHẢI / KHÔNG ĐƯỢC / NÊN có nghĩa như trong RFC 2119.

Tài liệu đi kèm: [`05-tooling-workflow.md`](05-tooling-workflow.md) (envelope phản hồi, mã lỗi chung, quy trình mock).

---

## 0. Tóm tắt một trang (đọc phần này nếu bạn vội)

| Hạng mục | Quyết định |
|---|---|
| Cơ chế | **Access token** JWT (HS256) stateless + **Refresh token** opaque lưu trong DB, có xoay vòng (rotation) |
| Gắn token | Header `Authorization: Bearer <access_token>` |
| Access token | TTL **30 phút**, payload: `sub`, `roles`, `did`, `type`, `iat`, `exp`, `jti` |
| Refresh token | Chuỗi ngẫu nhiên **trả trong body JSON**, TTL **7 ngày**, client lưu `expo-secure-store`. **KHÔNG dùng cookie** |
| Phía DB | Chỉ lưu **SHA-256** của refresh token (`auth.refresh_tokens.token_hash`) |
| Vai trò | 3 role: `admin`, `content_editor`, `user`. **KHÔNG có `premium`** |
| Phân quyền | Kiểm tra bằng **permission** dạng `resource:action` (đã seed 26 quyền), không kiểm tra theo tên role |
| ID người dùng | UUID v4 (`sub`) — KHÔNG BAO GIỜ dùng số nguyên |
| Mật khẩu | bcrypt (passlib), ≥ 8 ký tự, ≤ 72 byte, có chữ và số |
| Chống brute-force | 5 lần sai / 15 phút → khoá 15 phút (đếm từ `auth.login_attempts`) |
| Ngoài phạm vi MVP | OAuth Google/Apple/Facebook (bảng đã có, endpoint làm sau), 2FA |

---

## 1. Mô hình dữ liệu (đúng theo DB — KHÔNG tự thêm cột)

```
auth.users ──1:1── auth.user_profiles
    │
    ├──N:N── auth.roles  (qua auth.user_roles, có expires_at)
    │            └──N:N── auth.permissions (qua auth.role_permissions)
    ├──1:N── auth.user_devices ──1:N── auth.refresh_tokens (family_id, parent_token_id)
    ├──1:N── auth.verification_tokens   (xác thực email, đặt lại mật khẩu)
    ├──1:N── auth.oauth_accounts        (chưa dùng ở MVP)
    └──1:N── auth.login_attempts        (append-only)
```

Điểm hay nhầm (PHẢI nhớ):

| Dữ liệu | Nằm ở đâu | KHÔNG nằm ở |
|---|---|---|
| Email, mật khẩu băm, trạng thái | `auth.users` | — |
| `display_name` (bắt buộc), `full_name` (tuỳ chọn), `locale`, `timezone`, `unit_system` | `auth.user_profiles` | `auth.users` |
| Vai trò | `auth.user_roles` → `auth.roles` | cột `role` trên `users` (**không tồn tại**) |
| Trạng thái hoạt động | `users.status` ∈ `pending_verification` \| `active` \| `locked` \| `disabled` | cột `is_active` (**không tồn tại**) |
| Chiều cao, cân nặng, giới tính, ngày sinh | `body.*` | `auth.*` |
| Người dùng đã xoá | `users.deleted_at IS NOT NULL` | — |

Quy tắc truy vấn người dùng:

- Mọi truy vấn user hợp lệ PHẢI có điều kiện `deleted_at IS NULL`. Người dùng đã xoá mềm KHÔNG ĐƯỢC đăng nhập và KHÔNG ĐƯỢC xuất hiện trong bất kỳ API nào.
- `email` là `citext` (không phân biệt hoa thường), duy nhất trong số tài khoản chưa xoá.
- `password_hash` có thể `NULL` (tài khoản chỉ OAuth): đăng nhập bằng mật khẩu với tài khoản này PHẢI trả `INVALID_CREDENTIALS`.

---

## 2. Vai trò & Phân quyền (RBAC)

### 2.1. Vai trò

| Role (`auth.roles.code`) | Mô tả | Gán thế nào |
|---|---|---|
| `user` | Người tập. Mặc định khi đăng ký | Tự động khi `register` |
| `content_editor` | Biên tập thư viện bài tập, thiết bị, nhóm cơ, giáo án mẫu | Chỉ `admin` gán |
| `admin` | Toàn quyền hệ thống | Chỉ `admin` gán |

- Một user có thể giữ nhiều role. `user_roles.expires_at` có giá trị và đã quá hạn thì role đó PHẢI bị bỏ qua (ví dụ persona `trainer`).
- Tên role cố định trong Enum Python `RoleCode` ở `app/models/enums.py`. KHÔNG hard-code chuỗi `"admin"` rải rác trong code.
- **Không có role `premium`.** Mọi tính năng AI (kể cả upload video phân tích) dùng chung quyền `ai:use` của role `user`. Nếu sau này cần gói trả phí, phải sửa `seeds/01_rbac.sql` và `docs/database/` trước.

### 2.2. Quyền (permission) — đơn vị kiểm tra duy nhất

Permission là cặp `(resource, action)`, ghép thành chuỗi `resource:action` ở tầng ứng dụng. Danh sách đầy đủ (từ `seeds/01_rbac.sql`):

| Nhóm | Permission |
|---|---|
| Thư viện | `exercise:read` `exercise:create` `exercise:update` `exercise:delete` `exercise:publish` · `equipment:read` `equipment:manage` · `muscle_group:read` `muscle_group:manage` · `plan_template:read` `plan_template:manage` · `media:upload` `media:moderate` |
| Dữ liệu cá nhân | `workout:manage_own` · `body_metric:manage_own` · `progress_photo:manage_own` · `report:export_own` · `ai:use` |
| Quản trị | `user:read` `user:update` `user:lock` `user:delete` · `role:assign` · `ai_job:read` `ai_job:retry` · `system_report:read` |

### 2.3. Ma trận Role × Quyền

| Permission | `user` | `content_editor` | `admin` |
|---|:-:|:-:|:-:|
| `exercise:read`, `equipment:read`, `muscle_group:read`, `plan_template:read` | ✅ | ✅ | ✅ |
| `media:upload` | ✅ | ✅ | ✅ |
| `workout:manage_own`, `body_metric:manage_own`, `progress_photo:manage_own`, `report:export_own`, `ai:use` | ✅ | ❌ | ✅ |
| `exercise:create/update/delete/publish`, `equipment:manage`, `muscle_group:manage`, `plan_template:manage` | ❌ | ✅ | ✅ |
| `media:moderate` | ❌ | ❌ | ✅ |
| `user:*`, `role:assign`, `ai_job:*`, `system_report:read` | ❌ | ❌ | ✅ |

> `content_editor` KHÔNG có `workout:manage_own` / `ai:use` — muốn tập luyện, tài khoản đó cần giữ thêm role `user` (đăng ký luôn gán `user`, nên trường hợp thường gặp là có cả hai).

### 2.4. Quy tắc áp dụng

1. **Server quyết định bằng permission**, không dựa vào claim `roles` trong token. Claim `roles` chỉ để UI ẩn/hiện menu.
2. Endpoint nào cũng PHẢI khai báo rõ yêu cầu: công khai / đăng nhập / permission cụ thể (ghi trong `description` của Swagger).
3. Dữ liệu cá nhân (`*:manage_own`) còn PHẢI kiểm tra **quyền sở hữu**: `resource.user_id == current_user.id`. Có permission mà không phải chủ sở hữu → `404 NOT_FOUND` (không lộ sự tồn tại), trừ khi `admin` có permission quản trị tương ứng.
4. Permission của user được cache ở Redis key `perm:{user_id}`, TTL 5 phút (giá trị: danh sách chuỗi `resource:action`, đã loại role hết hạn). PHẢI xoá key này khi gán/thu hồi role. Cache miss → truy vấn `user_roles ⋈ role_permissions ⋈ permissions`.

---

## 3. Token

### 3.1. Access token (JWT, HS256)

- Gửi qua header: `Authorization: Bearer <access_token>`.
- TTL: `JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30`.
- Payload CỐ ĐỊNH (không thêm claim ngoài danh sách này mà không cập nhật doc):

```json
{
  "sub": "5eed0000-0000-4000-8000-000000000003",
  "roles": ["user"],
  "did": "c1a7f1e0-2b53-4d57-9d2c-8d0d3a8f2a10",
  "type": "access",
  "iat": 1780000000,
  "exp": 1780001800,
  "jti": "0b9f7c2e-6f5b-4d0e-9a54-1f6f3b6e9c11"
}
```

| Claim | Kiểu | Ý nghĩa |
|---|---|---|
| `sub` | string (UUID v4) | `auth.users.id` |
| `roles` | string[] | Mã các role còn hiệu lực lúc cấp token (chỉ để UI) |
| `did` | string (UUID) | `auth.user_devices.id` — thiết bị đang đăng nhập |
| `type` | `"access"` | PHẢI kiểm tra mỗi lần giải mã |
| `iat`, `exp` | số (epoch giây, UTC) | Thời điểm cấp / hết hạn |
| `jti` | string (UUID) | ID token (phục vụ log/truy vết) |

- KHÔNG đưa email, tên, số điện thoại hay bất kỳ PII nào vào token (token chỉ được mã hoá base64, ai cũng đọc được).
- Server PHẢI từ chối access token có `iat` < `users.password_changed_at` (token cấp trước khi đổi mật khẩu).
- Server PHẢI kiểm tra user vẫn tồn tại, `deleted_at IS NULL` và `status = 'active'` mỗi request (một truy vấn theo PK; có thể cache ngắn ở Redis nhưng không quá 60 giây).
- Access token KHÔNG bị thu hồi chủ động khi logout (chấp nhận tối đa 30 phút còn hiệu lực). Muốn vô hiệu ngay, đổi mật khẩu hoặc khoá tài khoản (`status`).

### 3.2. Refresh token (opaque, lưu DB)

- Là chuỗi ngẫu nhiên không đoán được: `secrets.token_urlsafe(48)`. **Không phải JWT**, không chứa thông tin gì.
- TTL: `JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7`.
- **Trả về trong body JSON** của `login` / `refresh`; client lưu ở `expo-secure-store`. **KHÔNG dùng cookie** (app React Native không có cookie jar đáng tin cậy).
- DB chỉ lưu `token_hash = SHA-256(token)` dạng hex 64 ký tự (`auth.refresh_tokens.token_hash`). KHÔNG BAO GIỜ lưu hay log token gốc.
- Mỗi refresh token thuộc về một thiết bị (`device_id`) và một "gia đình" (`family_id`). User được suy ra qua `device_id → user_devices.user_id` (bảng `refresh_tokens` không có `user_id`).
- `refresh_tokens.id` được dùng làm `jti` nội bộ để truy vết.

### 3.3. Xoay vòng (rotation) & phát hiện dùng lại

```
Login            : tạo device (nếu chưa có) + token T1 (family F, parent NULL)
Refresh bằng T1  : T1.revoked_at=now, reason='rotated' → tạo T2 (family F, parent T1)
Refresh bằng T2  : T2 rotated → T3 (family F, parent T2) ...
Ai đó gửi lại T1 : T1 đã 'rotated' ⇒ nghi bị đánh cắp
                   → thu hồi TOÀN BỘ token cùng family F (reason='reuse_detected')
                   → 401 TOKEN_REUSED; client PHẢI xoá token và bắt đăng nhập lại
```

Thuật toán `POST /auth/refresh` (PHẢI chạy trong một transaction, khoá hàng bằng `SELECT … FOR UPDATE` để chống race khi 2 request refresh cùng lúc):

1. `h = sha256(refresh_token)`; tìm theo `token_hash = h`. Không có → `401 TOKEN_INVALID`.
2. Nếu `revoked_at IS NOT NULL`:
   - `revoke_reason = 'rotated'` → thu hồi cả family (`reuse_detected`) → `401 TOKEN_REUSED`.
   - lý do khác (`logout`, `admin_revoked`, `password_changed`, `device_revoked`, `reuse_detected`) → `401 TOKEN_INVALID`.
3. `expires_at <= now()` → `401 TOKEN_EXPIRED` (client chuyển sang màn Login).
4. Thiết bị có `revoked_at` hoặc user không còn hợp lệ (xoá/`disabled`/`locked`) → thu hồi token (`device_revoked`/`admin_revoked`) → `401 TOKEN_INVALID` (hoặc `403 ACCOUNT_DISABLED`/`423 ACCOUNT_LOCKED` nếu muốn báo rõ).
5. Thu hồi token cũ (`rotated`), tạo token mới (cùng `family_id`, `parent_token_id` = token cũ, `expires_at = now()+7d`, `ip_address`, `user_agent`).
6. Cập nhật `user_devices.last_seen_at`. Trả cặp token mới (access + refresh).

> Lưu ý: `TOKEN_EXPIRED` ở đây là hết hạn **refresh token** (đăng nhập lại). `TOKEN_EXPIRED` của **access token** là tín hiệu để client gọi `/auth/refresh` — xem mục 7.

---

## 4. Đặc tả API

Prefix chung `/api/v1`. Mọi phản hồi dùng envelope trong `05-tooling-workflow.md` (mục 3): thành công `{success:true, data, message}`, lỗi `{success:false, error_code, message, details}`. Ví dụ dưới đây chỉ trình bày phần `data` khi không cần thiết.

### 4.1. Tổng quan

| Method | Path | Quyền | Mô tả |
|---|---|---|---|
| POST | `/auth/register` | Công khai | Đăng ký |
| POST | `/auth/login` | Công khai | Đăng nhập, tạo/nhận diện thiết bị |
| POST | `/auth/refresh` | Công khai (cần refresh token) | Xoay vòng token |
| POST | `/auth/logout` | Đăng nhập | Thu hồi refresh token hiện tại |
| POST | `/auth/logout-all` | Đăng nhập | Thu hồi mọi refresh token của user |
| GET | `/auth/me` | Đăng nhập | Thông tin tài khoản + hồ sơ + roles |
| PATCH | `/auth/me` | Đăng nhập | Sửa `display_name`, `full_name`, `locale`, `timezone`, `unit_system` |
| PATCH | `/auth/change-password` | Đăng nhập | Đổi mật khẩu |
| POST | `/auth/verify-email` | Công khai | Xác thực email bằng token |
| POST | `/auth/forgot-password` | Công khai | Gửi token đặt lại mật khẩu |
| POST | `/auth/reset-password` | Công khai | Đặt mật khẩu mới bằng token |
| GET | `/auth/devices` | Đăng nhập | Danh sách thiết bị của mình |
| DELETE | `/auth/devices/{device_id}` | Đăng nhập | Đăng xuất thiết bị từ xa |
| PUT | `/auth/devices/{device_id}/push-token` | Đăng nhập | Cập nhật FCM/APNs token |
| GET | `/users` | `user:read` | Danh sách người dùng (phân trang) |
| GET | `/users/{user_id}` | `user:read` | Chi tiết người dùng |
| PUT | `/users/{user_id}/roles` | `role:assign` | Gán danh sách role |
| POST | `/users/{user_id}/lock` · `/unlock` | `user:lock` | Khoá / mở khoá |

### 4.2. `POST /auth/register` → `201`

Request:

```json
{
  "email": "an@example.com",
  "password": "Demo@1234",
  "display_name": "An",
  "full_name": "Nguyễn Văn An"
}
```

Quy tắc:
- Tạo trong **một transaction**: `auth.users` + `auth.user_profiles` + `auth.user_roles(role=user)`. Lỗi bất kỳ bước nào → rollback toàn bộ.
- Email đã tồn tại (tài khoản chưa xoá) → `409 EMAIL_ALREADY_EXISTS`. Email của tài khoản đã xoá mềm có thể đăng ký lại.
- Mật khẩu không đạt chính sách (mục 6) → `422 WEAK_PASSWORD`.
- Trạng thái ban đầu:
  - Cấu hình `REQUIRE_EMAIL_VERIFICATION=false` (**mặc định ở dev**): `status='active'`, `email_verified_at=now()`.
  - `=true` (production): `status='pending_verification'`, tạo `verification_tokens(purpose='email_verification')`, gửi email chứa token (TTL 24 giờ).
- KHÔNG trả token ở bước này. Phản hồi (`data`) là thông tin user:

```json
{ "id": "…uuid…", "email": "an@example.com", "display_name": "An", "full_name": "Nguyễn Văn An", "roles": ["user"], "status": "active" }
```

### 4.3. `POST /auth/login` → `200`

Request:

```json
{
  "email": "demo@smartworkout.local",
  "password": "Demo@123",
  "device": {
    "device_id": null,
    "platform": "android",
    "device_name": "Pixel 8",
    "os_version": "14",
    "app_version": "0.1.0",
    "push_token": null
  }
}
```

- `device.platform` ∈ `ios` | `android` | `web`. `device.device_id` = giá trị client đã lưu từ lần đăng nhập trước (nếu có và thuộc đúng user và chưa thu hồi thì dùng lại; ngược lại tạo thiết bị mới). `push_token` tuỳ chọn.

Response `data`:

```json
{
  "access_token": "eyJhbGciOi…",
  "refresh_token": "u3Pq…43+ký tự…",
  "token_type": "bearer",
  "expires_in": 1800,
  "device_id": "c1a7f1e0-2b53-4d57-9d2c-8d0d3a8f2a10",
  "user": { "id": "…uuid…", "email": "demo@smartworkout.local", "display_name": "An", "roles": ["user"] }
}
```

Thứ tự kiểm tra (PHẢI ghi một dòng `auth.login_attempts` cho **mọi** lần thử, kể cả thất bại):

1. Tìm user theo email (`deleted_at IS NULL`). Không tồn tại hoặc `password_hash IS NULL` hoặc sai mật khẩu → `401 INVALID_CREDENTIALS` (cùng một thông báo, để không lộ email nào tồn tại). Thực hiện `verify_password` cả khi không tìm thấy user (dùng hash giả) để thời gian phản hồi không lộ thông tin.
2. `status='disabled'` → `403 ACCOUNT_DISABLED`.
3. `status='locked'` hoặc `locked_until > now()` → `423 ACCOUNT_LOCKED` (`details.retry_after_seconds`).
4. `status='pending_verification'` → `403 EMAIL_NOT_VERIFIED`.
5. Thành công: ghi `succeeded=true`; tạo/cập nhật `user_devices`; tạo refresh token mới (family mới); cấp access token.

> Thứ tự 2–4 chỉ được kiểm tra **sau khi mật khẩu đúng** thì mới trả lỗi cụ thể; nếu mật khẩu sai luôn trả `INVALID_CREDENTIALS`. Riêng khoá tạm vì brute-force thì kiểm tra trước (mục 6.2) để không tốn CPU bcrypt.

### 4.4. `POST /auth/refresh` → `200`

Request: `{ "refresh_token": "…" }` (không cần header Authorization). Response `data` cùng cấu trúc `login` nhưng không có `user`: `{access_token, refresh_token, token_type, expires_in, device_id}`. Thuật toán ở mục 3.3.

### 4.5. `POST /auth/logout` → `200`

Header Bearer + body `{ "refresh_token": "…" }`. Thu hồi token đó (`revoke_reason='logout'`). Idempotent: token không tồn tại/đã thu hồi vẫn trả `200` (client luôn xoá SecureStore). Chỉ thu hồi được token thuộc user hiện tại.

`POST /auth/logout-all`: thu hồi mọi refresh token chưa thu hồi của mọi thiết bị của user (`logout`).

### 4.6. `GET /auth/me`

`data`: `{ id, email, status, email_verified_at, display_name, full_name, avatar_media_id, locale, timezone, unit_system, roles, permissions }`. `permissions` là danh sách `resource:action` để FE điều khiển UI (nguồn: cache `perm:{user_id}`).

### 4.7. `PATCH /auth/change-password` → `200`

Request: `{ "current_password": "…", "new_password": "…" }`.
- Sai `current_password` → `401 INVALID_CREDENTIALS`. Tài khoản không có mật khẩu (OAuth-only) dùng luồng `forgot/reset-password` để đặt mật khẩu lần đầu.
- Đạt: cập nhật `password_hash`, `password_changed_at = now()`, thu hồi **mọi** refresh token của user (`password_changed`), xoá cache liên quan. Client PHẢI đăng nhập lại.

### 4.8. Xác thực email & đặt lại mật khẩu

- `POST /auth/verify-email` `{token}`: token là chuỗi ngẫu nhiên 32 byte, DB lưu SHA-256 (`verification_tokens`). Hợp lệ khi chưa dùng (`consumed_at IS NULL`), chưa hết hạn. Đạt → `email_verified_at=now()`, `status='active'` (nếu đang `pending_verification`), `consumed_at=now()`. Sai/hết hạn/đã dùng → `400 TOKEN_INVALID`.
- `POST /auth/forgot-password` `{email}`: **luôn** trả `200` cùng thông điệp dù email có tồn tại hay không (chống dò). Tạo `purpose='password_reset'`, TTL **30 phút**; vô hiệu các token reset cũ chưa dùng của user.
- `POST /auth/reset-password` `{token, new_password}`: như đổi mật khẩu, thêm `consumed_at`, thu hồi mọi refresh token. Cho phép đặt mật khẩu lần đầu cho tài khoản OAuth-only.
- Giới hạn tần suất: `forgot-password` tối đa 3 lần/giờ/email và 10 lần/giờ/IP (Redis, xem mục 6.3).

### 4.9. Thiết bị

`GET /auth/devices`: danh sách thiết bị chưa thu hồi `{id, platform, device_name, app_version, last_seen_at, is_current}`. `DELETE /auth/devices/{id}`: đặt `user_devices.revoked_at`, thu hồi mọi refresh token của thiết bị đó (`device_revoked`), xoá `push_token`. Không được thao tác trên thiết bị của người khác (→ `404`).

### 4.10. Quản trị người dùng (admin)

- `PUT /users/{id}/roles` body `{ "roles": ["user","content_editor"] }`: thay thế tập role hiện tại (ghi `granted_by = admin.id`). Role `user` PHẢI luôn có; không cho phép tự gỡ role `admin` của chính mình nếu là admin cuối cùng (`409 CONFLICT`). Xoá cache `perm:{id}`.
- `POST /users/{id}/lock`: `status='locked'`, thu hồi refresh token (`admin_revoked`). `unlock`: `status='active'`, `locked_until=NULL`.
- Mọi thao tác quản trị PHẢI ghi log có `actor_id`, `target_id`, hành động (log ứng dụng; không nằm trong DB hiện tại).

---

## 5. Bảng mã lỗi xác thực

Mã lỗi dùng chung envelope `ErrorResponse` (xem `05-tooling-workflow.md`). Frontend PHẢI phân nhánh theo `error_code`, KHÔNG so khớp chuỗi `message`.

| `error_code` | HTTP | Khi nào | Hành động của client |
|---|:-:|---|---|
| `INVALID_CREDENTIALS` | 401 | Sai email/mật khẩu, hoặc sai mật khẩu hiện tại | Hiện lỗi tại form |
| `TOKEN_EXPIRED` | 401 | **Access token** hết hạn | Gọi `/auth/refresh` rồi thử lại **một lần** |
| `TOKEN_INVALID` | 401 | Token sai chữ ký/định dạng/sai `type`/đã thu hồi/user không còn | Xoá SecureStore, về Login |
| `TOKEN_REUSED` | 401 | Refresh token đã xoay vòng bị gửi lại | Xoá SecureStore, về Login (+ cảnh báo bảo mật) |
| `ACCOUNT_LOCKED` | 423 | Tài khoản bị khoá | Hiện thời gian mở khoá (`details.retry_after_seconds`) |
| `ACCOUNT_DISABLED` | 403 | Admin vô hiệu hoá | Hiện thông báo liên hệ hỗ trợ; logout |
| `EMAIL_NOT_VERIFIED` | 403 | Chưa xác thực email | Chuyển màn "Xác thực email" |
| `PERMISSION_DENIED` | 403 | Thiếu permission | Hiện "không có quyền" |
| `EMAIL_ALREADY_EXISTS` | 409 | Đăng ký trùng email | Hiện lỗi tại form |
| `WEAK_PASSWORD` | 422 | Mật khẩu không đạt chính sách | Hiện gợi ý chính sách |
| `VALIDATION_ERROR` | 422 | Sai định dạng input (Pydantic) | Hiện lỗi từng field theo `details` |
| `RATE_LIMITED` | 429 | Vượt giới hạn tần suất (mục 6.3) | Báo thử lại sau, tôn trọng header `Retry-After` |

> Quy ước phân biệt hết hạn access token: backend PHẢI trả `TOKEN_EXPIRED` **chỉ** khi chữ ký hợp lệ nhưng `exp` đã qua. Mọi lỗi giải mã khác là `TOKEN_INVALID`. (Hàm `decode_token` hiện tại nuốt hết lỗi và trả `None` nên chưa phân biệt được — xem mục 8.3.)

---

## 6. Chính sách bảo mật

### 6.1. Mật khẩu

- Độ dài **8–72 byte UTF-8** (bcrypt cắt từ byte thứ 72, nên giới hạn tối đa để tránh mật khẩu "giống nhau" ngầm), có ít nhất 1 chữ cái và 1 chữ số.
- Băm bằng `passlib` `CryptContext(schemes=["bcrypt"])`. KHÔNG tự viết thuật toán băm. KHÔNG trả `password_hash` ở bất kỳ response nào. KHÔNG log mật khẩu.
- Mật khẩu seed `Demo@123` thoả chính sách.

### 6.2. Khoá tài khoản chống brute-force

- Đếm số lần `succeeded=false` của cùng `user_id` trong 15 phút gần nhất từ `auth.login_attempts`. Khi **đạt 5**, đặt `users.locked_until = now() + 15 phút` và ghi các lần sau với `failure_reason='account_locked'`.
- Đăng nhập thành công hoặc hết `locked_until` thì tự mở (không cần xoá lịch sử). `status='locked'` do admin đặt thì chỉ admin mở.
- Giới hạn theo IP: ≥ 20 lần thất bại / 15 phút / IP → `429 RATE_LIMITED` (đếm bằng `login_attempts.ip_address`, hoặc Redis `rl:login:ip:{ip}`).

### 6.3. Rate limit (Redis)

| Khoá | Giới hạn | Phản hồi |
|---|---|---|
| `rl:login:ip:{ip}` | 20 lần thất bại / 15 phút | `429 RATE_LIMITED` |
| `rl:forgot:email:{email}` | 3 / giờ | trả 200 như bình thường (không lộ) |
| `rl:forgot:ip:{ip}` | 10 / giờ | `429 RATE_LIMITED` |
| `rl:register:ip:{ip}` | 10 / giờ | `429 RATE_LIMITED` |

### 6.4. Cấu hình bí mật

- `JWT_SECRET_KEY` đọc từ biến môi trường, tối thiểu 32 ký tự ngẫu nhiên; ở môi trường khác `development`, ứng dụng PHẢI từ chối khởi động nếu còn giá trị mặc định `change-this-secret-key`.
- Cookie không dùng nên không có cấu hình `Secure/SameSite` cho auth. CORS ở production PHẢI giới hạn origin (không `*`).
- Hết hạn token và ngưỡng khoá đặt trong `Settings` (không hard-code trong hàm).

### 6.5. Vệ sinh dữ liệu

- Chỉ SHA-256 của refresh/verification token nằm trong DB. Token gốc chỉ tồn tại ở email/response/SecureStore.
- Dọn dẹp: xoá `refresh_tokens` đã hết hạn > 30 ngày; `login_attempts` > 180 ngày (job định kỳ — theo `docs/database/design-overview.md`).

---

## 7. Quy tắc cho Frontend (React Native + Expo)

PHẢI:
1. Lưu `access_token`, `refresh_token`, `device_id` trong `expo-secure-store`. KHÔNG dùng AsyncStorage/MMKV thường/Redux persist cho token.
2. Gắn `Authorization: Bearer <access_token>` bằng **request interceptor** của Axios; KHÔNG gắn thủ công từng lời gọi.
3. Xử lý `TOKEN_EXPIRED` bằng **single-flight refresh**: chỉ một lần gọi `/auth/refresh` tại một thời điểm, các request 401 khác đợi chung kết quả rồi retry **đúng một lần**. Nếu không có cơ chế này, nhiều request song song sẽ dùng cùng một refresh token → server coi là dùng lại (`TOKEN_REUSED`) và đá người dùng ra.
4. Sau `refresh` thành công PHẢI ghi **cả hai** token mới vào SecureStore trước khi retry (refresh token cũ đã vô hiệu).
5. `TOKEN_INVALID`, `TOKEN_REUSED`, `ACCOUNT_DISABLED`, hoặc refresh thất bại → xoá SecureStore, huỷ mọi request đang chờ, điều hướng Login.
6. Khi logout: gọi `POST /auth/logout` (bỏ qua lỗi mạng), rồi luôn xoá SecureStore.
7. Dùng `permissions` từ `GET /auth/me` (không suy luận từ tên role) để ẩn/hiện chức năng.
8. Với ngôn ngữ/múi giờ/đơn vị, dùng `locale`, `timezone`, `unit_system` từ `me`; dữ liệu API luôn là SI (xem doc 05).

KHÔNG ĐƯỢC: lưu mật khẩu ở máy; log token; gửi token qua query string; tự giải mã JWT để suy luận quyền ngoài mục đích hiển thị.

Mẫu interceptor (TypeScript, `src/services/api.ts`):

```ts
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import * as SecureStore from 'expo-secure-store';

const api = axios.create({ baseURL: process.env.EXPO_PUBLIC_API_URL + '/api/v1' });

let refreshing: Promise<string> | null = null;      // single-flight

async function doRefresh(): Promise<string> {
  const refresh_token = await SecureStore.getItemAsync('refresh_token');
  if (!refresh_token) throw new Error('NO_REFRESH_TOKEN');
  // dùng axios trần (không qua interceptor) để tránh lặp vô hạn
  const res = await axios.post(`${api.defaults.baseURL}/auth/refresh`, { refresh_token });
  const d = res.data.data;
  await SecureStore.setItemAsync('access_token', d.access_token);
  await SecureStore.setItemAsync('refresh_token', d.refresh_token);
  return d.access_token;
}

api.interceptors.request.use(async (config) => {
  const token = await SecureStore.getItemAsync('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError<{ error_code?: string }>) => {
    const original = error.config as InternalAxiosRequestConfig & { _retried?: boolean };
    const code = error.response?.data?.error_code;

    if (code === 'TOKEN_EXPIRED' && original && !original._retried) {
      original._retried = true;
      try {
        refreshing ??= doRefresh().finally(() => { refreshing = null; });
        const newToken = await refreshing;
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      } catch {
        await clearSessionAndGoToLogin();   // xoá SecureStore + navigation.reset('Login')
      }
    } else if (['TOKEN_INVALID', 'TOKEN_REUSED', 'ACCOUNT_DISABLED'].includes(code ?? '')) {
      await clearSessionAndGoToLogin();
    }
    return Promise.reject(error);
  },
);
export default api;
```

---

## 8. Quy tắc cho Backend

### 8.1. Nguyên tắc

1. **Chỉ** `app/core/security.py` được tạo/giải mã token, băm/kiểm tra mật khẩu, băm SHA-256 token. Module khác KHÔNG import `jose`/`passlib` trực tiếp.
2. Logic nghiệp vụ auth nằm ở `app/services/auth_service.py`; endpoint chỉ gọi service (xem doc 05, mục 6).
3. Bảo vệ endpoint bằng dependency, không tự kiểm tra thủ công trong thân hàm:
   - `Depends(get_current_user)` — yêu cầu đăng nhập.
   - `Depends(require_permission("exercise", "create"))` — yêu cầu permission.
4. Sai quyền → `ForbiddenException` (`PERMISSION_DENIED`), chưa đăng nhập/token hỏng → `UnauthorizedException` (có header `WWW-Authenticate: Bearer`).
5. Mọi lỗi auth là `AppException` có `error_code` (xem doc 05, mục 7.4).

### 8.2. Mẫu `app/core/security.py` (đích đến)

```python
import hashlib, secrets, uuid
from datetime import datetime, timedelta, timezone
from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedException

settings = get_settings()
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def create_access_token(*, user_id: uuid.UUID, roles: list[str], device_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "roles": roles,
        "did": str(device_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Trả payload hoặc ném UnauthorizedException(TOKEN_EXPIRED | TOKEN_INVALID)."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except ExpiredSignatureError:
        raise UnauthorizedException("Access token đã hết hạn", error_code="TOKEN_EXPIRED")
    except JWTError:
        raise UnauthorizedException("Token không hợp lệ", error_code="TOKEN_INVALID")
    if payload.get("type") != "access":
        raise UnauthorizedException("Sai loại token", error_code="TOKEN_INVALID")
    return payload


def generate_refresh_token() -> tuple[str, str]:
    """Trả (token_gốc, sha256_hex). Chỉ lưu sha256_hex vào DB."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()   # 64 ký tự hex = char(64)
```

### 8.3. Mẫu `app/core/dependencies.py` (đích đến)

```python
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    if creds is None:
        raise UnauthorizedException("Thiếu access token", error_code="TOKEN_INVALID")
    payload = decode_access_token(creds.credentials)
    user = await user_crud.get_active(db, id=payload["sub"])     # deleted_at IS NULL AND status='active'
    if user is None:
        raise UnauthorizedException("Tài khoản không khả dụng", error_code="TOKEN_INVALID")
    if user.password_changed_at and payload["iat"] < int(user.password_changed_at.timestamp()):
        raise UnauthorizedException("Token cấp trước khi đổi mật khẩu", error_code="TOKEN_INVALID")
    return user


def require_permission(resource: str, action: str):
    async def checker(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        perms = await permission_service.get_permissions(db, user.id)   # cache Redis perm:{user_id}
        if f"{resource}:{action}" not in perms:
            raise ForbiddenException("Không có quyền thực hiện thao tác này")
        return user
    return checker
```

> Dùng `HTTPBearer` (không dùng `OAuth2PasswordBearer`) vì `/auth/login` nhận JSON, không phải form `username/password`; nếu dùng `OAuth2PasswordBearer` thì nút Authorize của Swagger sẽ gửi sai định dạng.

### 8.4. Việc cần sửa trong code hiện có (giao cho Core owner — xem doc 05, mục 12)

| File | Vấn đề hiện tại | Cần làm |
|---|---|---|
| `backend/app/core/security.py` | `create_*_token(data: dict)` tự do; không có `jti/did/roles`; `create_refresh_token` tạo JWT; `decode_token` nuốt mọi lỗi trả `None` → không phân biệt `TOKEN_EXPIRED`/`TOKEN_INVALID` | Thay theo mẫu 8.2; refresh token là opaque + SHA-256 |
| `backend/app/core/dependencies.py` | `OAuth2PasswordBearer`; `get_current_user` là placeholder trả `{"id": ...}`; không kiểm tra `type`, trạng thái user | Thay theo mẫu 8.3; thêm `require_permission` |
| `backend/app/core/exceptions.py` | Các lớp kế thừa `HTTPException`, không có `error_code` → không khớp envelope | Chuyển sang `AppException(status_code, error_code, message, details)` (doc 05, 7.4) |
| `backend/app/core/config.py` | Thiếu `REQUIRE_EMAIL_VERIFICATION`, ngưỡng khoá, `CORS_ORIGINS`; cho phép secret mặc định | Bổ sung + kiểm tra khi khởi động (6.4) |
| `docker-compose.yml` / `.env.example` | `JWT_SECRET_KEY` mặc định | Dùng giá trị dev rõ ràng, ghi chú KHÔNG dùng ở production |

---

## 9. Dữ liệu test dùng ngay (từ `database/postgresql/seeds/90_test_users.sql`)

Mật khẩu chung `Demo@123`, email dạng `<tên>@smartworkout.local`. Chỉ có khi `SW_SEED_TEST=true` (mặc định ở `docker-compose.yml`).

| Email | Mục đích test |
|---|---|
| `admin@` | role `admin`: quản trị, gán role |
| `editor@` | role `content_editor`: CRUD thư viện |
| `demo@` | **happy path** user thường (cũng dùng cho Dashboard/giáo án) |
| `power@` | dữ liệu 6 tháng (phân trang, biểu đồ) |
| `newbie@` | trạng thái rỗng |
| `pending@` | `pending_verification` → `EMAIL_NOT_VERIFIED` |
| `locked@` | `locked` → `ACCOUNT_LOCKED` |
| `disabled@` | `disabled` → `ACCOUNT_DISABLED` |
| `deleted@` | xoá mềm → coi như không tồn tại (`INVALID_CREDENTIALS`) |
| `oauth@` | không có mật khẩu → `INVALID_CREDENTIALS` khi đăng nhập mật khẩu |
| `trainer@` | role `content_editor` đã **hết hạn** → phải bị bỏ qua |

Token thô dùng để test trực tiếp `/auth/refresh` và các luồng token một lần (DB chỉ lưu hash):

| Token | Kỳ vọng |
|---|---|
| `seed-refresh-demo-2` | hợp lệ (xoay vòng được) |
| `seed-refresh-demo-1` | đã `rotated` → `TOKEN_REUSED` (và thu hồi cả family) |
| `seed-refresh-dung-exp` | hết hạn → `TOKEN_EXPIRED` |
| `seed-refresh-locked-2` | `reuse_detected` → `TOKEN_INVALID` |
| `seed-refresh-disabled-1` | `admin_revoked` → `TOKEN_INVALID` |
| `seed-verify-pending-valid` / `seed-verify-pending-expired` | `verify-email` thành công / thất bại |
| `seed-reset-trainer-valid` / `-expired` / `-used` | `reset-password` thành công / hết hạn / đã dùng |

> Lưu ý: chạy test `seed-refresh-demo-2` làm thay đổi DB (token bị xoay vòng). Test PHẢI chạy trên DB dựng lại (xem doc 05, mục 10) hoặc dùng transaction rollback; KHÔNG chạy thử trên DB dùng chung của nhóm.

---

## 10. Checklist trước khi merge PR có liên quan auth

- [ ] Endpoint khai báo rõ quyền (công khai / đăng nhập / permission) trong Swagger.
- [ ] Dùng `require_permission`, không so sánh tên role.
- [ ] Truy vấn user có `deleted_at IS NULL`; dữ liệu cá nhân có kiểm tra chủ sở hữu.
- [ ] Không trả/log `password_hash`, refresh token gốc, access token.
- [ ] Mọi lỗi auth dùng đúng `error_code` ở mục 5.
- [ ] Có test: thành công, sai thông tin, token hết hạn, thiếu quyền (≥ 2 test mỗi endpoint).
- [ ] Không thêm claim/cột/role/permission mới mà chưa sửa doc này và `docs/database/`.

---

## 11. Những điều KHÔNG ĐƯỢC làm

- ❌ Dùng role `premium` hoặc kiểm tra `if user.role == "admin"` — dùng permission.
- ❌ Dùng cookie cho refresh token.
- ❌ Lưu refresh token gốc trong DB, log, hay Redis.
- ❌ Dùng ID số nguyên cho user; tự tạo "x-user-id" header để xác thực.
- ❌ Bỏ qua kiểm tra `type` của token hoặc trạng thái user.
- ❌ Hard-code `JWT_SECRET_KEY` hay mật khẩu trong code/commit.
- ❌ Trả thông báo khác nhau cho "email không tồn tại" và "sai mật khẩu".
- ❌ Thêm cột `role`, `is_active`, `full_name` vào `auth.users`.
- ❌ Tự viết cách băm/mã hoá riêng.

## 12. Ngoài phạm vi MVP (ghi chú để khỏi thảo luận lại)

- Đăng nhập OAuth (Google/Apple/Facebook): bảng `auth.oauth_accounts` đã có; endpoint `POST /auth/oauth/{provider}` làm ở giai đoạn sau.
- Xác thực số điện thoại, 2FA/TOTP, gói trả phí (`premium`).
- Thu hồi tức thời access token (blacklist `jti`): chấp nhận tối đa 30 phút trễ ở MVP.
