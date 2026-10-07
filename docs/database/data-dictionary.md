# Từ điển dữ liệu — Smart Workout AI

> Tài liệu **tự sinh** từ `COMMENT ON` trong PostgreSQL bằng `database/postgresql/tools/data_dictionary.sql`. Không sửa tay — sửa mô tả trong `database/postgresql/schemas/*.sql` rồi sinh lại.

Quy ước cột **Khoá**: `PK` khoá chính, `UQ` thuộc ràng buộc unique, `FK → bảng` khoá ngoại. Các unique index có điều kiện (partial) và CHECK được liệt kê dưới mỗi bảng.

## Mục lục

- [Schema `auth`](#schema-auth) — 11 bảng
- [Schema `media`](#schema-media) — 3 bảng
- [Schema `catalog`](#schema-catalog) — 13 bảng
- [Schema `body`](#schema-body) — 7 bảng
- [Schema `training`](#schema-training) — 10 bảng
- [Schema `ai`](#schema-ai) — 6 bảng
- [Schema `analytics`](#schema-analytics) — 1 bảng
- [Views, materialized views & hàm](#views-materialized-views--hàm)


## Schema `auth`

Định danh & phân quyền: tài khoản, hồ sơ, RBAC, OAuth, thiết bị, phiên đăng nhập, nhật ký đăng nhập.

| Bảng | Mô tả |
|---|---|
| [`login_attempts`](#authlogin_attempts) | Nhật ký mọi lần đăng nhập (thành công/thất bại) phục vụ khoá tài khoản, giới hạn IP và điều tra bảo mật. Append-only, có thể xoá theo chính sách lưu trữ (vd: 180 ngày). |
| [`oauth_accounts`](#authoauth_accounts) | Tài khoản đăng nhập ngoài (OAuth/OIDC) được liên kết với user. |
| [`permissions`](#authpermissions) | Quyền nguyên tử dạng (resource, action). Chuỗi "resource:action" được ghép ở tầng ứng dụng, không lưu riêng (tránh dữ liệu dẫn xuất). |
| [`refresh_tokens`](#authrefresh_tokens) | Refresh token JWT. Chỉ lưu SHA-256 của token. Xoay vòng: mỗi lần refresh tạo token con (parent_token_id) cùng family_id; phát hiện dùng lại token cũ → thu hồi cả family. |
| [`role_permissions`](#authrole_permissions) | Bảng liên kết N-N: vai trò được cấp những quyền nào. |
| [`roles`](#authroles) | Vai trò (RBAC). Ví dụ: admin, content_editor, user. |
| [`user_devices`](#authuser_devices) | Thiết bị (bản cài ứng dụng/trình duyệt) mà user đăng nhập. Mỗi refresh token gắn với một thiết bị; push_token dùng gửi thông báo (vd: video AI phân tích xong). |
| [`user_profiles`](#authuser_profiles) | Hồ sơ hiển thị và tuỳ chọn cá nhân (1-1 với users). |
| [`user_roles`](#authuser_roles) | Bảng liên kết N-N: người dùng giữ vai trò nào (có thể có thời hạn). |
| [`users`](#authusers) | Tài khoản đăng nhập. Chỉ chứa thông tin định danh & xác thực; hồ sơ hiển thị ở user_profiles, dữ liệu thể chất ở body.user_body_profiles. |
| [`verification_tokens`](#authverification_tokens) | Token dùng một lần: xác thực email/SĐT, đặt lại mật khẩu. Chỉ lưu SHA-256. |

### `auth.users`

Tài khoản đăng nhập. Chỉ chứa thông tin định danh & xác thực; hồ sơ hiển thị ở user_profiles, dữ liệu thể chất ở body.user_body_profiles.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | PK | Khoá chính (UUID v4). |
| 2 | `email` | citext | NOT NULL |  |  | Email đăng nhập (citext, duy nhất trong các tài khoản chưa xoá). |
| 3 | `phone_number` | character varying(20) |  |  |  | Số điện thoại định dạng E.164 (tuỳ chọn, duy nhất). |
| 4 | `password_hash` | character varying(255) |  |  |  | Băm mật khẩu bcrypt/argon2. NULL nếu tài khoản chỉ đăng nhập qua OAuth. |
| 5 | `status` | auth.user_status | NOT NULL | 'pending_verification'::auth.user_status |  | Trạng thái tài khoản (pending_verification/active/locked/disabled). |
| 6 | `email_verified_at` | timestamp with time zone |  |  |  | Thời điểm xác thực email; NULL = chưa xác thực. |
| 7 | `phone_verified_at` | timestamp with time zone |  |  |  | Thời điểm xác thực số điện thoại. |
| 8 | `password_changed_at` | timestamp with time zone |  |  |  | Lần đổi mật khẩu gần nhất (dùng để vô hiệu token cũ). |
| 9 | `locked_until` | timestamp with time zone |  |  |  | Khoá tạm thời đến thời điểm này (chống brute-force). |
| 10 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 11 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất (trigger). |
| 12 | `deleted_at` | timestamp with time zone |  |  |  | Xoá mềm; NULL = còn hoạt động. |

**Ràng buộc:**

- `ck_users_email_format` — `CHECK ((email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'::citext))`
- `ck_users_password_hash_len` — `CHECK (((password_hash IS NULL) OR (length((password_hash)::text) >= 50)))`
- `ck_users_phone_format` — `CHECK (((phone_number IS NULL) OR ((phone_number)::text ~ '^\+?[0-9]{8,15}$'::text)))`
- `ck_users_phone_verified` — `CHECK (((phone_verified_at IS NULL) OR (phone_number IS NOT NULL)))`

**Index:**

- `ix_users_status` — `USING btree (status) WHERE (deleted_at IS NULL)`
- `uq_users_email_alive` — `UNIQUE USING btree (email) WHERE (deleted_at IS NULL)`
- `uq_users_phone_alive` — `UNIQUE USING btree (phone_number) WHERE ((deleted_at IS NULL) AND (phone_number IS NOT NULL))`

### `auth.user_profiles`

Hồ sơ hiển thị và tuỳ chọn cá nhân (1-1 với users).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `user_id` | uuid | NOT NULL |  | PK<br>FK → auth.users | PK đồng thời FK → auth.users. |
| 2 | `display_name` | character varying(50) | NOT NULL |  |  | Tên hiển thị trong ứng dụng. |
| 3 | `full_name` | character varying(100) |  |  |  | Họ và tên đầy đủ. |
| 4 | `avatar_media_id` | uuid |  |  | FK → media.media_files | Ảnh đại diện → media.media_files. |
| 5 | `locale` | character varying(10) | NOT NULL | 'vi-VN'::character varying |  | Ngôn ngữ giao diện (BCP-47, vd: vi-VN). |
| 6 | `timezone` | character varying(50) | NOT NULL | 'Asia/Ho_Chi_Minh'::character varying |  | Múi giờ IANA, dùng để chia ngày cho thống kê. |
| 7 | `unit_system` | auth.unit_system | NOT NULL | 'metric'::auth.unit_system |  | Hệ đơn vị hiển thị (metric/imperial). |
| 8 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 9 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_user_profiles_display_name` — `CHECK ((length(btrim((display_name)::text)) > 0))`
- `ck_user_profiles_locale` — `CHECK (((locale)::text ~ '^[a-z]{2}(-[A-Z]{2})?$'::text))`

**Index:**

- `ix_user_profiles_avatar_media_id` — `USING btree (avatar_media_id)`

### `auth.roles`

Vai trò (RBAC). Ví dụ: admin, content_editor, user.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | smallint | NOT NULL | IDENTITY | PK | Khoá chính. |
| 2 | `code` | character varying(50) | NOT NULL |  | UQ | Mã vai trò (khoá tự nhiên, snake_case). |
| 3 | `name` | character varying(100) | NOT NULL |  |  | Tên hiển thị. |
| 4 | `description` | text |  |  |  | Mô tả phạm vi vai trò. |
| 5 | `is_system` | boolean | NOT NULL | false |  | TRUE = vai trò hệ thống, không được xoá. |
| 6 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 7 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_roles_code_format` — `CHECK (((code)::text ~ '^[a-z][a-z0-9_]*$'::text))`

### `auth.permissions`

Quyền nguyên tử dạng (resource, action). Chuỗi "resource:action" được ghép ở tầng ứng dụng, không lưu riêng (tránh dữ liệu dẫn xuất).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | smallint | NOT NULL | IDENTITY | PK | Khoá chính. |
| 2 | `resource` | character varying(50) | NOT NULL |  | UQ | Tài nguyên (vd: exercise, user, workout). |
| 3 | `action` | character varying(30) | NOT NULL |  | UQ | Hành động (vd: read, create, update, delete, publish). |
| 4 | `description` | text |  |  |  | Mô tả quyền. |
| 5 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 6 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_permissions_action_format` — `CHECK (((action)::text ~ '^[a-z][a-z0-9_]*$'::text))`
- `ck_permissions_resource_format` — `CHECK (((resource)::text ~ '^[a-z][a-z0-9_]*$'::text))`
- `uq_permissions_resource_action` — `UNIQUE (resource, action)`

### `auth.role_permissions`

Bảng liên kết N-N: vai trò được cấp những quyền nào.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `role_id` | smallint | NOT NULL |  | PK<br>FK → auth.roles | FK → auth.roles. |
| 2 | `permission_id` | smallint | NOT NULL |  | PK<br>FK → auth.permissions | FK → auth.permissions. |
| 3 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm gán quyền. |

**Index:**

- `ix_role_permissions_permission_id` — `USING btree (permission_id)`

### `auth.user_roles`

Bảng liên kết N-N: người dùng giữ vai trò nào (có thể có thời hạn).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `user_id` | uuid | NOT NULL |  | PK<br>FK → auth.users | FK → auth.users. |
| 2 | `role_id` | smallint | NOT NULL |  | PK<br>FK → auth.roles | FK → auth.roles. |
| 3 | `granted_by` | uuid |  |  | FK → auth.users | Người cấp vai trò (FK → auth.users). |
| 4 | `granted_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cấp. |
| 5 | `expires_at` | timestamp with time zone |  |  |  | Hết hạn vai trò; NULL = vô thời hạn. |

**Ràng buộc:**

- `ck_user_roles_expiry` — `CHECK (((expires_at IS NULL) OR (expires_at > granted_at)))`

**Index:**

- `ix_user_roles_granted_by` — `USING btree (granted_by)`
- `ix_user_roles_role_id` — `USING btree (role_id)`

### `auth.oauth_accounts`

Tài khoản đăng nhập ngoài (OAuth/OIDC) được liên kết với user.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | PK | Khoá chính. |
| 2 | `user_id` | uuid | NOT NULL |  | UQ<br>FK → auth.users | FK → auth.users. |
| 3 | `provider` | auth.oauth_provider | NOT NULL |  | UQ<br>UQ | Nhà cung cấp (google/apple/facebook). |
| 4 | `provider_subject` | character varying(255) | NOT NULL |  | UQ | ID người dùng phía provider (claim "sub"). |
| 5 | `provider_email` | citext |  |  |  | Email do provider trả về tại thời điểm liên kết. |
| 6 | `linked_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm liên kết. |
| 7 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 8 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `uq_oauth_accounts_provider_subject` — `UNIQUE (provider, provider_subject)`
- `uq_oauth_accounts_user_provider` — `UNIQUE (user_id, provider)`

### `auth.user_devices`

Thiết bị (bản cài ứng dụng/trình duyệt) mà user đăng nhập. Mỗi refresh token gắn với một thiết bị; push_token dùng gửi thông báo (vd: video AI phân tích xong).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | PK | Khoá chính. |
| 2 | `user_id` | uuid | NOT NULL |  | FK → auth.users | FK → auth.users. |
| 3 | `platform` | auth.device_platform | NOT NULL |  |  | Nền tảng ios/android/web. |
| 4 | `device_name` | character varying(100) |  |  |  | Tên thiết bị (vd: iPhone 15 của An). |
| 5 | `os_version` | character varying(30) |  |  |  | Phiên bản hệ điều hành. |
| 6 | `app_version` | character varying(30) |  |  |  | Phiên bản ứng dụng. |
| 7 | `push_token` | character varying(512) |  |  |  | FCM/APNs token để gửi push notification. |
| 8 | `push_token_updated_at` | timestamp with time zone |  |  |  | Thời điểm cập nhật push_token. |
| 9 | `last_seen_at` | timestamp with time zone | NOT NULL | now() |  | Lần cuối thiết bị gọi API. |
| 10 | `revoked_at` | timestamp with time zone |  |  |  | Thời điểm thu hồi thiết bị (đăng xuất từ xa). |
| 11 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 12 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_user_devices_push_token` — `CHECK (((push_token IS NULL) = (push_token_updated_at IS NULL)))`

**Index:**

- `ix_user_devices_user_id` — `USING btree (user_id)`
- `uq_user_devices_push_token_active` — `UNIQUE USING btree (push_token) WHERE ((push_token IS NOT NULL) AND (revoked_at IS NULL))`

### `auth.refresh_tokens`

Refresh token JWT. Chỉ lưu SHA-256 của token. Xoay vòng: mỗi lần refresh tạo token con (parent_token_id) cùng family_id; phát hiện dùng lại token cũ → thu hồi cả family.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | PK | Khoá chính (dùng làm jti). |
| 2 | `device_id` | uuid | NOT NULL |  | FK → auth.user_devices | Thiết bị sở hữu token (FK → auth.user_devices); user suy ra qua thiết bị. |
| 3 | `family_id` | uuid | NOT NULL |  |  | Chuỗi xoay vòng: mọi token sinh ra từ một lần đăng nhập có chung family_id. |
| 4 | `parent_token_id` | uuid |  |  | FK → auth.refresh_tokens | Token trước đó trong chuỗi xoay vòng. |
| 5 | `token_hash` | character(64) | NOT NULL |  | UQ | SHA-256 (hex) của refresh token; không bao giờ lưu token gốc. |
| 6 | `issued_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm phát hành. |
| 7 | `expires_at` | timestamp with time zone | NOT NULL |  |  | Thời điểm hết hạn. |
| 8 | `revoked_at` | timestamp with time zone |  |  |  | Thời điểm thu hồi. |
| 9 | `revoke_reason` | auth.token_revoke_reason |  |  |  | Lý do thu hồi (bắt buộc khi revoked_at có giá trị). |
| 10 | `ip_address` | inet |  |  |  | IP client khi phát hành. |
| 11 | `user_agent` | character varying(500) |  |  |  | User-Agent khi phát hành. |

**Ràng buộc:**

- `ck_refresh_tokens_expiry` — `CHECK ((expires_at > issued_at))`
- `ck_refresh_tokens_hash_format` — `CHECK ((token_hash ~ '^[0-9a-f]{64}$'::text))`
- `ck_refresh_tokens_revoke` — `CHECK (((revoked_at IS NULL) = (revoke_reason IS NULL)))`

**Index:**

- `ix_refresh_tokens_device_id` — `USING btree (device_id)`
- `ix_refresh_tokens_expires_at` — `USING btree (expires_at) WHERE (revoked_at IS NULL)`
- `ix_refresh_tokens_family_id` — `USING btree (family_id)`
- `ix_refresh_tokens_parent_token_id` — `USING btree (parent_token_id)`

### `auth.verification_tokens`

Token dùng một lần: xác thực email/SĐT, đặt lại mật khẩu. Chỉ lưu SHA-256.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | PK | Khoá chính. |
| 2 | `user_id` | uuid | NOT NULL |  | FK → auth.users | FK → auth.users. |
| 3 | `purpose` | auth.token_purpose | NOT NULL |  |  | Mục đích token. |
| 4 | `token_hash` | character(64) | NOT NULL |  | UQ | SHA-256 (hex) của token. |
| 5 | `expires_at` | timestamp with time zone | NOT NULL |  |  | Thời điểm hết hạn. |
| 6 | `consumed_at` | timestamp with time zone |  |  |  | Thời điểm đã sử dụng; NULL = chưa dùng. |
| 7 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo. |

**Ràng buộc:**

- `ck_verification_tokens_consumed` — `CHECK (((consumed_at IS NULL) OR (consumed_at >= created_at)))`
- `ck_verification_tokens_expiry` — `CHECK ((expires_at > created_at))`
- `ck_verification_tokens_hash_format` — `CHECK ((token_hash ~ '^[0-9a-f]{64}$'::text))`

**Index:**

- `ix_verification_tokens_user_purpose` — `USING btree (user_id, purpose)`

### `auth.login_attempts`

Nhật ký mọi lần đăng nhập (thành công/thất bại) phục vụ khoá tài khoản, giới hạn IP và điều tra bảo mật. Append-only, có thể xoá theo chính sách lưu trữ (vd: 180 ngày).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | bigint | NOT NULL | IDENTITY | PK | Khoá chính. |
| 2 | `user_id` | uuid |  |  | FK → auth.users | User tương ứng nếu email tồn tại (FK → auth.users). |
| 3 | `email_attempted` | citext | NOT NULL |  |  | Email được nhập khi đăng nhập. |
| 4 | `ip_address` | inet |  |  |  | IP client. |
| 5 | `user_agent` | character varying(500) |  |  |  | User-Agent client. |
| 6 | `succeeded` | boolean | NOT NULL |  |  | TRUE = đăng nhập thành công. |
| 7 | `failure_reason` | auth.login_failure_reason |  |  |  | Lý do thất bại (NULL khi thành công). |
| 8 | `attempted_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm thử đăng nhập. |

**Ràng buộc:**

- `ck_login_attempts_reason` — `CHECK ((succeeded = (failure_reason IS NULL)))`

**Index:**

- `brin_login_attempts_attempted_at` — `USING brin (attempted_at)`
- `ix_login_attempts_email_time` — `USING btree (email_attempted, attempted_at DESC)`
- `ix_login_attempts_ip_time` — `USING btree (ip_address, attempted_at DESC)`
- `ix_login_attempts_user_time` — `USING btree (user_id, attempted_at DESC)`

## Schema `media`

Quản lý file trên Object Storage (S3/Firebase) và nhật ký ảnh tiến độ (Progress Gallery).

| Bảng | Mô tả |
|---|---|
| [`media_files`](#mediamedia_files) | Sổ đăng ký mọi file (ảnh, GIF, video, keypoint) trên Object Storage. Các bảng nghiệp vụ tham chiếu tới đây thay vì lưu URL. |
| [`photo_comparisons`](#mediaphoto_comparisons) | Cặp ảnh Before/After user đã lưu để xem lại/chia sẻ. Chủ sở hữu suy ra từ ảnh. |
| [`progress_photos`](#mediaprogress_photos) | Ảnh vóc dáng theo thời gian. Async worker nén ảnh, sinh thumbnail và đóng watermark (Ngày – Cân nặng – %Mỡ) rồi cập nhật processing_status. |

### `media.media_files`

Sổ đăng ký mọi file (ảnh, GIF, video, keypoint) trên Object Storage. Các bảng nghiệp vụ tham chiếu tới đây thay vì lưu URL.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | PK | Khoá chính. |
| 2 | `uploaded_by_user_id` | uuid |  |  | FK → auth.users | Người tải lên (FK → auth.users); NULL nếu do hệ thống sinh hoặc user đã bị xoá. |
| 3 | `storage_provider` | media.storage_provider | NOT NULL | 's3'::media.storage_provider | UQ | Nhà cung cấp lưu trữ (s3/firebase). |
| 4 | `bucket` | character varying(63) | NOT NULL |  | UQ | Tên bucket. |
| 5 | `object_key` | character varying(1024) | NOT NULL |  | UQ | Đường dẫn object trong bucket. |
| 6 | `original_filename` | character varying(255) |  |  |  | Tên file gốc phía client. |
| 7 | `mime_type` | character varying(100) | NOT NULL |  |  | MIME type (vd: image/jpeg, video/mp4). |
| 8 | `size_bytes` | bigint |  |  |  | Kích thước (byte); bắt buộc khi available. |
| 9 | `checksum_sha256` | character(64) |  |  |  | SHA-256 nội dung file; bắt buộc khi available (chống trùng/hỏng). |
| 10 | `width_px` | integer |  |  |  | Chiều rộng (ảnh/video). |
| 11 | `height_px` | integer |  |  |  | Chiều cao (ảnh/video). |
| 12 | `duration_ms` | integer |  |  |  | Thời lượng video/GIF (ms). |
| 13 | `status` | media.media_status | NOT NULL | 'pending_upload'::media.media_status |  | Trạng thái vòng đời file. |
| 14 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 15 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |
| 16 | `deleted_at` | timestamp with time zone |  |  |  | Xoá mềm; job dọn dẹp sẽ xoá object trên storage. |

**Ràng buộc:**

- `ck_media_files_available` — `CHECK (((status <> 'available'::media.media_status) OR ((size_bytes IS NOT NULL) AND (checksum_sha256 IS NOT NULL))))`
- `ck_media_files_checksum` — `CHECK (((checksum_sha256 IS NULL) OR (checksum_sha256 ~ '^[0-9a-f]{64}$'::text)))`
- `ck_media_files_dimensions` — `CHECK ((((width_px IS NULL) OR (width_px > 0)) AND ((height_px IS NULL) OR (height_px > 0))))`
- `ck_media_files_duration` — `CHECK (((duration_ms IS NULL) OR (duration_ms >= 0)))`
- `ck_media_files_mime_format` — `CHECK (((mime_type)::text ~ '^[a-z]+/[a-z0-9.+-]+$'::text))`
- `ck_media_files_size` — `CHECK (((size_bytes IS NULL) OR (size_bytes >= 0)))`
- `uq_media_files_object` — `UNIQUE (storage_provider, bucket, object_key)`

**Index:**

- `ix_media_files_pending` — `USING btree (created_at) WHERE (status = 'pending_upload'::media.media_status)`
- `ix_media_files_uploaded_by` — `USING btree (uploaded_by_user_id)`

### `media.progress_photos`

Ảnh vóc dáng theo thời gian. Async worker nén ảnh, sinh thumbnail và đóng watermark (Ngày – Cân nặng – %Mỡ) rồi cập nhật processing_status.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | PK | Khoá chính. |
| 2 | `user_id` | uuid | NOT NULL |  | FK → auth.users | Chủ ảnh (FK → auth.users). |
| 3 | `original_media_id` | uuid | NOT NULL |  | UQ<br>FK → media.media_files | Ảnh gốc (FK → media.media_files). |
| 4 | `watermarked_media_id` | uuid |  |  | FK → media.media_files | Ảnh đã đóng watermark chỉ số. |
| 5 | `thumbnail_media_id` | uuid |  |  | FK → media.media_files | Ảnh thu nhỏ cho lưới ảnh. |
| 6 | `angle` | media.photo_angle | NOT NULL |  |  | Góc chụp front/side/back. |
| 7 | `capture_source` | media.capture_source | NOT NULL | 'camera'::media.capture_source |  | camera/library. |
| 8 | `taken_at` | timestamp with time zone | NOT NULL |  |  | Thời điểm chụp (sắp xếp dòng thời gian, tra số đo tương ứng). |
| 9 | `processing_status` | util.job_status | NOT NULL | 'queued'::util.job_status |  | Trạng thái xử lý watermark. |
| 10 | `processing_error` | text |  |  |  | Lỗi xử lý (khi failed). |
| 11 | `note` | character varying(500) |  |  |  | Ghi chú. |
| 12 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 13 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |
| 14 | `deleted_at` | timestamp with time zone |  |  |  | Xoá mềm. |

**Ràng buộc:**

- `ck_progress_photos_completed` — `CHECK (((processing_status <> 'completed'::util.job_status) OR (watermarked_media_id IS NOT NULL)))`
- `ck_progress_photos_distinct_media` — `CHECK ((((watermarked_media_id IS NULL) OR (watermarked_media_id <> original_media_id)) AND ((thumbnail_media_id IS NULL) OR (thumbnail_media_id <> original_media_id))))`
- `ck_progress_photos_failed` — `CHECK (((processing_status <> 'failed'::util.job_status) OR (processing_error IS NOT NULL)))`

**Index:**

- `ix_progress_photos_thumbnail_media_id` — `USING btree (thumbnail_media_id)`
- `ix_progress_photos_user_taken` — `USING btree (user_id, taken_at DESC)`
- `ix_progress_photos_watermarked_media_id` — `USING btree (watermarked_media_id)`

### `media.photo_comparisons`

Cặp ảnh Before/After user đã lưu để xem lại/chia sẻ. Chủ sở hữu suy ra từ ảnh.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | PK | Khoá chính. |
| 2 | `before_photo_id` | uuid | NOT NULL |  | UQ<br>FK → media.progress_photos | Ảnh trước (FK → media.progress_photos). |
| 3 | `after_photo_id` | uuid | NOT NULL |  | UQ<br>FK → media.progress_photos | Ảnh sau (FK → media.progress_photos). |
| 4 | `title` | character varying(100) |  |  |  | Tiêu đề (vd: Tháng 1 vs Tháng 6). |
| 5 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |

**Ràng buộc:**

- `ck_photo_comparisons_distinct` — `CHECK ((before_photo_id <> after_photo_id))`
- `uq_photo_comparisons_pair` — `UNIQUE (before_photo_id, after_photo_id)`

**Index:**

- `ix_photo_comparisons_after_photo_id` — `USING btree (after_photo_id)`

**Trigger:**

- `trg_photo_comparisons_owner` → `fn_check_photo_comparison_owner()` — Đảm bảo hai ảnh trong một cặp so sánh thuộc cùng user.

## Schema `catalog`

Thư viện bài tập (Exercise Wiki): nhóm cơ, thiết bị, bài tập, hướng dẫn, lỗi sai thường gặp.

| Bảng | Mô tả |
|---|---|
| [`body_regions`](#catalogbody_regions) | Vùng cơ thể lớn (thân trên / thân dưới / core) để nhóm các nhóm cơ. |
| [`difficulty_levels`](#catalogdifficulty_levels) | Mức độ khó (dùng cho bài tập, giáo án và trình độ người tập). |
| [`equipment`](#catalogequipment) | Thiết bị phòng tập (tạ đơn, máy kéo cáp...). Bài tập không gắn thiết bị nào = bài tự thân. |
| [`equipment_aliases`](#catalogequipment_aliases) | Tên gọi khác của thiết bị: từ đồng nghĩa để tìm kiếm ("tạ tay" = Tạ đơn) và nhãn lớp YOLOv8 ("cable_crossover_machine") để ánh xạ kết quả nhận diện → thiết bị → bài tập. |
| [`equipment_categories`](#catalogequipment_categories) | Nhóm thiết bị (tạ tự do, máy, cáp, ghế & khung, cardio...). |
| [`exercise_alternatives`](#catalogexercise_alternatives) | Bài thay thế do biên tập viên chọn (quan hệ có hướng A → B). Gợi ý tự động theo nhóm cơ + thiết bị trống nằm ở hàm catalog.fn_suggest_alternatives(). |
| [`exercise_equipment`](#catalogexercise_equipment) | Thiết bị cần cho bài tập (N-N). Dùng cho lọc "thiết bị sẵn có", gợi ý bài thay thế và chức năng nhận diện thiết bị. |
| [`exercise_instructions`](#catalogexercise_instructions) | Các bước thực hiện bài tập theo thứ tự (mỗi bước một dòng, đạt 1NF). |
| [`exercise_media`](#catalogexercise_media) | Video/GIF/ảnh minh hoạ bài tập. Mỗi vai trò có tối đa một media chính. |
| [`exercise_mistakes`](#catalogexercise_mistakes) | Lỗi sai thường gặp của bài tập. Dùng chung cho trang Wiki (cảnh báo) và module AI (ai.posture_issues tham chiếu mã lỗi này). |
| [`exercise_muscles`](#catalogexercise_muscles) | Bài tập tác động nhóm cơ nào, vai trò và tỷ lệ kích hoạt (để phân bổ khối lượng tập cho mô hình phục hồi). |
| [`exercises`](#catalogexercises) | Bài tập trong thư viện. Nhóm cơ, thiết bị, các bước, lỗi sai, media được tách thành bảng con (1NF). |
| [`muscle_groups`](#catalogmuscle_groups) | Nhóm cơ phân cấp (vd: Lưng → Lưng xô). Nút lá có heatmap_region_key được vẽ trên mô hình cơ thể và được theo dõi phục hồi. |

### `catalog.difficulty_levels`

Mức độ khó (dùng cho bài tập, giáo án và trình độ người tập).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | smallint | NOT NULL | IDENTITY | PK | Khoá chính. |
| 2 | `code` | character varying(30) | NOT NULL |  | UQ | Mã (beginner/intermediate/advanced). |
| 3 | `name` | character varying(50) | NOT NULL |  |  | Tên hiển thị. |
| 4 | `rank` | smallint | NOT NULL |  | UQ | Thứ tự tăng dần độ khó, dùng để sắp xếp. |
| 5 | `description` | text |  |  |  | Mô tả. |
| 6 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 7 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_difficulty_levels_code_format` — `CHECK (((code)::text ~ '^[a-z][a-z0-9_]*$'::text))`
- `ck_difficulty_levels_rank` — `CHECK ((rank > 0))`

### `catalog.body_regions`

Vùng cơ thể lớn (thân trên / thân dưới / core) để nhóm các nhóm cơ.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | smallint | NOT NULL | IDENTITY | PK | Khoá chính. |
| 2 | `code` | character varying(30) | NOT NULL |  | UQ | Mã vùng. |
| 3 | `name` | character varying(50) | NOT NULL |  |  | Tên hiển thị. |
| 4 | `display_order` | smallint | NOT NULL | 0 |  | Thứ tự hiển thị. |
| 5 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 6 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_body_regions_code_format` — `CHECK (((code)::text ~ '^[a-z][a-z0-9_]*$'::text))`

### `catalog.muscle_groups`

Nhóm cơ phân cấp (vd: Lưng → Lưng xô). Nút lá có heatmap_region_key được vẽ trên mô hình cơ thể và được theo dõi phục hồi.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | smallint | NOT NULL | IDENTITY | PK | Khoá chính. |
| 2 | `code` | character varying(50) | NOT NULL |  | UQ | Mã nhóm cơ (vd: lats, chest). |
| 3 | `name` | character varying(100) | NOT NULL |  |  | Tên tiếng Việt (vd: Lưng xô). |
| 4 | `name_en` | character varying(100) |  |  |  | Tên tiếng Anh/giải phẫu (vd: Latissimus Dorsi). |
| 5 | `parent_id` | smallint |  |  | FK → catalog.muscle_groups | Nhóm cơ cha; NULL = nút gốc. |
| 6 | `body_region_id` | smallint |  |  | FK → catalog.body_regions | Vùng cơ thể; CHỈ có ở nút gốc (nút con suy ra qua cha). |
| 7 | `heatmap_region_key` | character varying(50) |  |  | UQ | ID vùng trên SVG mô hình cơ thể (Heatmap); NULL = không vẽ riêng. |
| 8 | `base_recovery_hours` | smallint | NOT NULL | 48 |  | Thời gian phục hồi tham chiếu (giờ) khi chưa đủ dữ liệu cá nhân hoá cho AI. |
| 9 | `display_order` | smallint | NOT NULL | 0 |  | Thứ tự hiển thị. |
| 10 | `description` | text |  |  |  | Mô tả chức năng nhóm cơ. |
| 11 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 12 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_muscle_groups_code_format` — `CHECK (((code)::text ~ '^[a-z][a-z0-9_]*$'::text))`
- `ck_muscle_groups_not_self_parent` — `CHECK (((parent_id IS NULL) OR (parent_id <> id)))`
- `ck_muscle_groups_recovery_hours` — `CHECK (((base_recovery_hours >= 12) AND (base_recovery_hours <= 168)))`
- `ck_muscle_groups_region_on_root` — `CHECK (((parent_id IS NULL) = (body_region_id IS NOT NULL)))`

**Index:**

- `ix_muscle_groups_body_region_id` — `USING btree (body_region_id)`
- `ix_muscle_groups_name_search` — `USING gin (util.search_norm((name)::text) gin_trgm_ops)`
- `ix_muscle_groups_parent_id` — `USING btree (parent_id)`

### `catalog.equipment_categories`

Nhóm thiết bị (tạ tự do, máy, cáp, ghế & khung, cardio...).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | smallint | NOT NULL | IDENTITY | PK | Khoá chính. |
| 2 | `code` | character varying(30) | NOT NULL |  | UQ | Mã nhóm. |
| 3 | `name` | character varying(100) | NOT NULL |  |  | Tên hiển thị. |
| 4 | `description` | text |  |  |  | Mô tả. |
| 5 | `display_order` | smallint | NOT NULL | 0 |  | Thứ tự hiển thị. |
| 6 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 7 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_equipment_categories_code_format` — `CHECK (((code)::text ~ '^[a-z][a-z0-9_]*$'::text))`

### `catalog.equipment`

Thiết bị phòng tập (tạ đơn, máy kéo cáp...). Bài tập không gắn thiết bị nào = bài tự thân.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | integer | NOT NULL | IDENTITY | PK | Khoá chính. |
| 2 | `code` | character varying(50) | NOT NULL |  | UQ | Mã thiết bị. |
| 3 | `name` | character varying(100) | NOT NULL |  |  | Tên tiếng Việt. |
| 4 | `name_en` | character varying(100) |  |  |  | Tên tiếng Anh. |
| 5 | `category_id` | smallint | NOT NULL |  | FK → catalog.equipment_categories | FK → catalog.equipment_categories. |
| 6 | `description` | text |  |  |  | Mô tả công dụng ("máy này dùng để làm gì?"). |
| 7 | `image_media_id` | uuid |  |  | FK → media.media_files | Ảnh minh hoạ (FK → media.media_files). |
| 8 | `created_by` | uuid |  |  | FK → auth.users | Người tạo (biên tập viên). |
| 9 | `updated_by` | uuid |  |  | FK → auth.users | Người cập nhật gần nhất. |
| 10 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 11 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |
| 12 | `deleted_at` | timestamp with time zone |  |  |  | Xoá mềm. |

**Ràng buộc:**

- `ck_equipment_code_format` — `CHECK (((code)::text ~ '^[a-z][a-z0-9_]*$'::text))`

**Index:**

- `ix_equipment_category_id` — `USING btree (category_id)`
- `ix_equipment_created_by` — `USING btree (created_by)`
- `ix_equipment_image_media_id` — `USING btree (image_media_id)`
- `ix_equipment_name_search` — `USING gin (util.search_norm((name)::text) gin_trgm_ops)`
- `ix_equipment_updated_by` — `USING btree (updated_by)`

### `catalog.equipment_aliases`

Tên gọi khác của thiết bị: từ đồng nghĩa để tìm kiếm ("tạ tay" = Tạ đơn) và nhãn lớp YOLOv8 ("cable_crossover_machine") để ánh xạ kết quả nhận diện → thiết bị → bài tập.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | integer | NOT NULL | IDENTITY | PK | Khoá chính. |
| 2 | `equipment_id` | integer | NOT NULL |  | UQ<br>FK → catalog.equipment | FK → catalog.equipment. |
| 3 | `alias` | character varying(100) | NOT NULL |  | UQ | Tên gọi khác (chữ thường). |
| 4 | `alias_type` | catalog.alias_type | NOT NULL |  | UQ | synonym = từ đồng nghĩa; ai_label = nhãn lớp model AI (duy nhất toàn bảng). |
| 5 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |

**Ràng buộc:**

- `ck_equipment_aliases_lowercase` — `CHECK (((alias)::text = lower((alias)::text)))`
- `uq_equipment_aliases_equipment_alias` — `UNIQUE (equipment_id, alias_type, alias)`

**Index:**

- `ix_equipment_aliases_alias_search` — `USING gin (util.search_norm((alias)::text) gin_trgm_ops)`
- `uq_equipment_aliases_ai_label` — `UNIQUE USING btree (alias) WHERE (alias_type = 'ai_label'::catalog.alias_type)`

### `catalog.exercises`

Bài tập trong thư viện. Nhóm cơ, thiết bị, các bước, lỗi sai, media được tách thành bảng con (1NF).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | integer | NOT NULL | IDENTITY | PK | Khoá chính. |
| 2 | `slug` | character varying(120) | NOT NULL |  | UQ | Định danh thân thiện URL (vd: dumbbell-row). |
| 3 | `name` | character varying(150) | NOT NULL |  |  | Tên tiếng Việt. |
| 4 | `name_en` | character varying(150) |  |  |  | Tên tiếng Anh. |
| 5 | `description` | text |  |  |  | Mô tả tổng quan. |
| 6 | `difficulty_level_id` | smallint | NOT NULL |  | FK → catalog.difficulty_levels | Mức độ khó (FK → catalog.difficulty_levels). |
| 7 | `category` | catalog.exercise_category | NOT NULL | 'strength'::catalog.exercise_category |  | Phân loại (strength/cardio/...). |
| 8 | `mechanic` | catalog.mechanic_type |  |  |  | compound/isolation; NULL với bài cardio/giãn cơ. |
| 9 | `force_type` | catalog.force_type |  |  |  | push/pull/static. |
| 10 | `is_unilateral` | boolean | NOT NULL | false |  | TRUE = tập từng bên (một tay/một chân). |
| 11 | `met_value` | numeric(4,1) |  |  |  | Chỉ số MET để ước tính calo tiêu hao = MET × kg × giờ. |
| 12 | `supports_ai_tracking` | boolean | NOT NULL | false |  | TRUE = có thuật toán AI chấm tư thế/đếm rep cho bài này. |
| 13 | `status` | catalog.content_status | NOT NULL | 'draft'::catalog.content_status |  | Trạng thái biên tập (chỉ published hiển thị cho user). |
| 14 | `published_at` | timestamp with time zone |  |  |  | Thời điểm xuất bản lần đầu. |
| 15 | `created_by` | uuid |  |  | FK → auth.users | Người tạo (biên tập viên). |
| 16 | `updated_by` | uuid |  |  | FK → auth.users | Người cập nhật gần nhất. |
| 17 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 18 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |
| 19 | `deleted_at` | timestamp with time zone |  |  |  | Xoá mềm (bài tập đã có lịch sử tập không được xoá cứng). |

**Ràng buộc:**

- `ck_exercises_met_value` — `CHECK (((met_value IS NULL) OR ((met_value >= 1.0) AND (met_value <= 25.0))))`
- `ck_exercises_published` — `CHECK (((status <> 'published'::catalog.content_status) OR (published_at IS NOT NULL)))`
- `ck_exercises_slug_format` — `CHECK (((slug)::text ~ '^[a-z0-9]+(-[a-z0-9]+)*$'::text))`

**Index:**

- `ix_exercises_created_by` — `USING btree (created_by)`
- `ix_exercises_difficulty_level_id` — `USING btree (difficulty_level_id)`
- `ix_exercises_name_en_search` — `USING gin (util.search_norm((name_en)::text) gin_trgm_ops)`
- `ix_exercises_name_search` — `USING gin (util.search_norm((name)::text) gin_trgm_ops)`
- `ix_exercises_published` — `USING btree (difficulty_level_id, name) WHERE ((status = 'published'::catalog.content_status) AND (deleted_at IS NULL))`
- `ix_exercises_updated_by` — `USING btree (updated_by)`

### `catalog.exercise_muscles`

Bài tập tác động nhóm cơ nào, vai trò và tỷ lệ kích hoạt (để phân bổ khối lượng tập cho mô hình phục hồi).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `exercise_id` | integer | NOT NULL |  | PK<br>FK → catalog.exercises | FK → catalog.exercises. |
| 2 | `muscle_group_id` | smallint | NOT NULL |  | PK<br>FK → catalog.muscle_groups | FK → catalog.muscle_groups (nên là nút lá). |
| 3 | `role` | catalog.muscle_role | NOT NULL |  |  | primary/secondary/stabilizer. |
| 4 | `activation_ratio` | numeric(3,2) | NOT NULL |  |  | Tỷ lệ kích hoạt (0–1]: volume của set × tỷ lệ này = tải lên nhóm cơ. |
| 5 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |

**Ràng buộc:**

- `ck_exercise_muscles_activation` — `CHECK (((activation_ratio > (0)::numeric) AND (activation_ratio <= (1)::numeric)))`

**Index:**

- `ix_exercise_muscles_muscle_role` — `USING btree (muscle_group_id, role)`

### `catalog.exercise_equipment`

Thiết bị cần cho bài tập (N-N). Dùng cho lọc "thiết bị sẵn có", gợi ý bài thay thế và chức năng nhận diện thiết bị.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `exercise_id` | integer | NOT NULL |  | PK<br>FK → catalog.exercises | FK → catalog.exercises. |
| 2 | `equipment_id` | integer | NOT NULL |  | PK<br>FK → catalog.equipment | FK → catalog.equipment. |
| 3 | `is_optional` | boolean | NOT NULL | false |  | TRUE = thiết bị tuỳ chọn (không bắt buộc để thực hiện). |
| 4 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |

**Index:**

- `ix_exercise_equipment_equipment_id` — `USING btree (equipment_id)`

### `catalog.exercise_instructions`

Các bước thực hiện bài tập theo thứ tự (mỗi bước một dòng, đạt 1NF).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `exercise_id` | integer | NOT NULL |  | PK<br>FK → catalog.exercises | FK → catalog.exercises. |
| 2 | `step_no` | smallint | NOT NULL |  | PK | Số thứ tự bước (bắt đầu từ 1). |
| 3 | `content` | text | NOT NULL |  |  | Nội dung bước. |
| 4 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 5 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_exercise_instructions_content` — `CHECK ((length(btrim(content)) > 0))`
- `ck_exercise_instructions_step_no` — `CHECK ((step_no > 0))`

### `catalog.exercise_mistakes`

Lỗi sai thường gặp của bài tập. Dùng chung cho trang Wiki (cảnh báo) và module AI (ai.posture_issues tham chiếu mã lỗi này).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | integer | NOT NULL | IDENTITY | PK | Khoá chính. |
| 2 | `exercise_id` | integer | NOT NULL |  | FK → catalog.exercises | FK → catalog.exercises. |
| 3 | `code` | character varying(60) | NOT NULL |  | UQ | Mã lỗi duy nhất, model AI trả về mã này (vd: SQUAT_BACK_ROUNDING). |
| 4 | `title` | character varying(150) | NOT NULL |  |  | Tiêu đề lỗi. |
| 5 | `description` | text |  |  |  | Mô tả lỗi và hậu quả. |
| 6 | `correction_cue` | text |  |  |  | Gợi ý sửa (hiển thị/đọc khi AI phát hiện). |
| 7 | `at_risk_joint` | catalog.joint_type |  |  |  | Khớp có nguy cơ chấn thương. |
| 8 | `ai_detectable` | boolean | NOT NULL | false |  | TRUE = AI có thể phát hiện tự động. |
| 9 | `display_order` | smallint | NOT NULL | 0 |  | Thứ tự hiển thị. |
| 10 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 11 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_exercise_mistakes_code_format` — `CHECK (((code)::text ~ '^[A-Z][A-Z0-9_]*$'::text))`

**Index:**

- `ix_exercise_mistakes_exercise_id` — `USING btree (exercise_id)`

### `catalog.exercise_media`

Video/GIF/ảnh minh hoạ bài tập. Mỗi vai trò có tối đa một media chính.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `exercise_id` | integer | NOT NULL |  | PK<br>FK → catalog.exercises | FK → catalog.exercises. |
| 2 | `media_id` | uuid | NOT NULL |  | PK<br>FK → media.media_files | FK → media.media_files. |
| 3 | `media_role` | catalog.media_role | NOT NULL |  |  | thumbnail/gif/video/image. |
| 4 | `is_primary` | boolean | NOT NULL | false |  | Media chính của vai trò đó. |
| 5 | `display_order` | smallint | NOT NULL | 0 |  | Thứ tự hiển thị. |
| 6 | `caption` | character varying(200) |  |  |  | Chú thích. |
| 7 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |

**Index:**

- `ix_exercise_media_media_id` — `USING btree (media_id)`
- `uq_exercise_media_primary_per_role` — `UNIQUE USING btree (exercise_id, media_role) WHERE is_primary`

### `catalog.exercise_alternatives`

Bài thay thế do biên tập viên chọn (quan hệ có hướng A → B). Gợi ý tự động theo nhóm cơ + thiết bị trống nằm ở hàm catalog.fn_suggest_alternatives().

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `exercise_id` | integer | NOT NULL |  | PK<br>FK → catalog.exercises | Bài gốc (FK → catalog.exercises). |
| 2 | `alternative_exercise_id` | integer | NOT NULL |  | PK<br>FK → catalog.exercises | Bài thay thế (FK → catalog.exercises). |
| 3 | `note` | character varying(255) |  |  |  | Lý do/ghi chú khi thay thế. |
| 4 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |

**Ràng buộc:**

- `ck_exercise_alternatives_not_self` — `CHECK ((exercise_id <> alternative_exercise_id))`

**Index:**

- `ix_exercise_alternatives_alternative_id` — `USING btree (alternative_exercise_id)`

## Schema `body`

Hồ sơ thể chất, chỉ số cơ thể theo thời gian và mục tiêu cá nhân.

| Bảng | Mô tả |
|---|---|
| [`activity_levels`](#bodyactivity_levels) | Mức độ vận động hằng ngày và hệ số nhân TDEE = BMR × multiplier. |
| [`body_circumferences`](#bodybody_circumferences) | Số đo vòng gắn với một lần đo (thay cho nhiều cột vòng eo/ngực... thưa dữ liệu). |
| [`body_measurements`](#bodybody_measurements) | Mỗi lần cập nhật chỉ số cơ thể (điểm dữ liệu trên biểu đồ xu hướng). Ảnh tiến độ lấy cân nặng/%mỡ từ đây theo thời điểm chụp. |
| [`body_sites`](#bodybody_sites) | Vị trí đo số đo vòng (eo, ngực, mông, bắp tay...). |
| [`fitness_goal_types`](#bodyfitness_goal_types) | Loại mục tiêu tập luyện (giảm mỡ, tăng cơ, duy trì...). |
| [`user_body_profiles`](#bodyuser_body_profiles) | Hồ sơ thể chất ít thay đổi: giới tính, ngày sinh, chiều cao, mức vận động, trình độ. Tuổi được tính từ ngày sinh (không lưu). |
| [`user_goals`](#bodyuser_goals) | Mục tiêu thể chất theo thời gian. Mỗi user tối đa một mục tiêu đang active. |

### `body.activity_levels`

Mức độ vận động hằng ngày và hệ số nhân TDEE = BMR × multiplier.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | smallint | NOT NULL | IDENTITY | PK | Khoá chính. |
| 2 | `code` | character varying(30) | NOT NULL |  | UQ | Mã (sedentary/light/moderate/active/very_active). |
| 3 | `name` | character varying(100) | NOT NULL |  |  | Tên hiển thị. |
| 4 | `description` | text |  |  |  | Mô tả (vd: 3–5 buổi/tuần). |
| 5 | `multiplier` | numeric(4,3) | NOT NULL |  |  | Hệ số hoạt động (1.2 – 1.9). |
| 6 | `display_order` | smallint | NOT NULL | 0 |  | Thứ tự hiển thị. |
| 7 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 8 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_activity_levels_code_format` — `CHECK (((code)::text ~ '^[a-z][a-z0-9_]*$'::text))`
- `ck_activity_levels_multiplier` — `CHECK (((multiplier >= 1.0) AND (multiplier <= 2.5)))`

### `body.fitness_goal_types`

Loại mục tiêu tập luyện (giảm mỡ, tăng cơ, duy trì...).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | smallint | NOT NULL | IDENTITY | PK | Khoá chính. |
| 2 | `code` | character varying(30) | NOT NULL |  | UQ | Mã mục tiêu. |
| 3 | `name` | character varying(100) | NOT NULL |  |  | Tên hiển thị. |
| 4 | `description` | text |  |  |  | Mô tả. |
| 5 | `display_order` | smallint | NOT NULL | 0 |  | Thứ tự hiển thị. |
| 6 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 7 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_fitness_goal_types_code_format` — `CHECK (((code)::text ~ '^[a-z][a-z0-9_]*$'::text))`

### `body.body_sites`

Vị trí đo số đo vòng (eo, ngực, mông, bắp tay...).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | smallint | NOT NULL | IDENTITY | PK | Khoá chính. |
| 2 | `code` | character varying(30) | NOT NULL |  | UQ | Mã vị trí. |
| 3 | `name` | character varying(100) | NOT NULL |  |  | Tên hiển thị. |
| 4 | `display_order` | smallint | NOT NULL | 0 |  | Thứ tự hiển thị. |
| 5 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 6 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_body_sites_code_format` — `CHECK (((code)::text ~ '^[a-z][a-z0-9_]*$'::text))`

### `body.user_body_profiles`

Hồ sơ thể chất ít thay đổi: giới tính, ngày sinh, chiều cao, mức vận động, trình độ. Tuổi được tính từ ngày sinh (không lưu).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `user_id` | uuid | NOT NULL |  | PK<br>FK → auth.users | PK đồng thời FK → auth.users. |
| 2 | `gender` | body.gender | NOT NULL | 'unspecified'::body.gender |  | Giới tính (cho công thức BMR). |
| 3 | `date_of_birth` | date |  |  |  | Ngày sinh (tuổi = age(ngày đo, ngày sinh)). |
| 4 | `height_cm` | numeric(5,1) |  |  |  | Chiều cao (cm). |
| 5 | `activity_level_id` | smallint |  |  | FK → body.activity_levels | Mức vận động hiện tại (FK → body.activity_levels). |
| 6 | `experience_level_id` | smallint |  |  | FK → catalog.difficulty_levels | Trình độ tập luyện (FK → catalog.difficulty_levels), dùng để gợi ý bài phù hợp. |
| 7 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 8 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_user_body_profiles_dob` — `CHECK (((date_of_birth IS NULL) OR (date_of_birth >= '1900-01-01'::date)))`
- `ck_user_body_profiles_height` — `CHECK (((height_cm IS NULL) OR ((height_cm >= (80)::numeric) AND (height_cm <= (250)::numeric))))`

**Index:**

- `ix_user_body_profiles_activity_level_id` — `USING btree (activity_level_id)`
- `ix_user_body_profiles_experience_level_id` — `USING btree (experience_level_id)`

### `body.body_measurements`

Mỗi lần cập nhật chỉ số cơ thể (điểm dữ liệu trên biểu đồ xu hướng). Ảnh tiến độ lấy cân nặng/%mỡ từ đây theo thời điểm chụp.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | PK | Khoá chính. |
| 2 | `user_id` | uuid | NOT NULL |  | UQ<br>FK → auth.users | FK → auth.users. |
| 3 | `measured_at` | timestamp with time zone | NOT NULL |  | UQ | Thời điểm đo. |
| 4 | `weight_kg` | numeric(5,2) | NOT NULL |  |  | Cân nặng (kg). |
| 5 | `body_fat_pct` | numeric(4,1) |  |  |  | Tỷ lệ mỡ cơ thể (%). |
| 6 | `muscle_mass_kg` | numeric(5,2) |  |  |  | Khối lượng cơ (kg), thường từ cân thông minh. |
| 7 | `source` | body.measurement_source | NOT NULL | 'manual'::body.measurement_source |  | Nguồn số đo. |
| 8 | `note` | character varying(500) |  |  |  | Ghi chú. |
| 9 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 10 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_body_measurements_body_fat` — `CHECK (((body_fat_pct IS NULL) OR ((body_fat_pct >= (2)::numeric) AND (body_fat_pct <= (70)::numeric))))`
- `ck_body_measurements_muscle_mass` — `CHECK (((muscle_mass_kg IS NULL) OR ((muscle_mass_kg > (0)::numeric) AND (muscle_mass_kg < weight_kg))))`
- `ck_body_measurements_weight` — `CHECK (((weight_kg >= (20)::numeric) AND (weight_kg <= (400)::numeric)))`
- `uq_body_measurements_user_time` — `UNIQUE (user_id, measured_at)`

### `body.body_circumferences`

Số đo vòng gắn với một lần đo (thay cho nhiều cột vòng eo/ngực... thưa dữ liệu).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `measurement_id` | uuid | NOT NULL |  | PK<br>FK → body.body_measurements | FK → body.body_measurements. |
| 2 | `body_site_id` | smallint | NOT NULL |  | PK<br>FK → body.body_sites | FK → body.body_sites. |
| 3 | `value_cm` | numeric(5,1) | NOT NULL |  |  | Số đo (cm). |
| 4 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |

**Ràng buộc:**

- `ck_body_circumferences_value` — `CHECK (((value_cm >= (5)::numeric) AND (value_cm <= (300)::numeric)))`

**Index:**

- `ix_body_circumferences_body_site_id` — `USING btree (body_site_id)`

### `body.user_goals`

Mục tiêu thể chất theo thời gian. Mỗi user tối đa một mục tiêu đang active.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | PK | Khoá chính. |
| 2 | `user_id` | uuid | NOT NULL |  | FK → auth.users | FK → auth.users. |
| 3 | `goal_type_id` | smallint | NOT NULL |  | FK → body.fitness_goal_types | FK → body.fitness_goal_types. |
| 4 | `target_weight_kg` | numeric(5,2) |  |  |  | Cân nặng mục tiêu (kg). |
| 5 | `target_body_fat_pct` | numeric(4,1) |  |  |  | %mỡ mục tiêu. |
| 6 | `start_date` | date | NOT NULL | CURRENT_DATE |  | Ngày bắt đầu. |
| 7 | `target_date` | date |  |  |  | Ngày dự kiến đạt. |
| 8 | `status` | body.goal_status | NOT NULL | 'active'::body.goal_status |  | active/achieved/abandoned. |
| 9 | `closed_at` | timestamp with time zone |  |  |  | Thời điểm kết thúc (đạt hoặc bỏ); NULL khi đang active. |
| 10 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 11 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_user_goals_closed` — `CHECK (((status = 'active'::body.goal_status) = (closed_at IS NULL)))`
- `ck_user_goals_dates` — `CHECK (((target_date IS NULL) OR (target_date > start_date)))`
- `ck_user_goals_target_fat` — `CHECK (((target_body_fat_pct IS NULL) OR ((target_body_fat_pct >= (2)::numeric) AND (target_body_fat_pct <= (70)::numeric))))`
- `ck_user_goals_target_weight` — `CHECK (((target_weight_kg IS NULL) OR ((target_weight_kg >= (20)::numeric) AND (target_weight_kg <= (400)::numeric))))`

**Index:**

- `ix_user_goals_goal_type_id` — `USING btree (goal_type_id)`
- `ix_user_goals_user_id` — `USING btree (user_id)`
- `uq_user_goals_one_active` — `UNIQUE USING btree (user_id) WHERE (status = 'active'::body.goal_status)`

## Schema `training`

Giáo án, lịch tập, buổi tập thực tế, set/rep/tempo và dự đoán phục hồi cơ.

| Bảng | Mô tả |
|---|---|
| [`exercise_sets`](#trainingexercise_sets) | Từng hiệp tập. Volume = reps × weight_kg được tính ở view (không lưu). reps là số đã được user xác nhận (có thể khác số AI đếm trong set_rep_events nếu user sửa). |
| [`muscle_soreness_reports`](#trainingmuscle_soreness_reports) | User tự báo mức đau mỏi cơ (DOMS). Là nhãn thực tế để huấn luyện/cá nhân hoá model dự đoán phục hồi. |
| [`recovery_predictions`](#trainingrecovery_predictions) | Kết quả model PyTorch sau mỗi buổi tập: mức mệt mỏi và thời điểm hồi phục hoàn toàn của từng nhóm cơ. User suy ra qua session (không lưu). Trạng thái Heatmap hiện tại tính ở training.v_muscle_recovery_status. |
| [`scheduled_workouts`](#trainingscheduled_workouts) | Lịch tập của user theo ngày, có thể gắn một buổi trong giáo án (của user hoặc giáo án mẫu). Khi xếp lịch nhóm cơ chưa hồi phục, app cảnh báo; nếu user vẫn xác nhận thì ghi recovery_warning_ack_at. |
| [`session_exercises`](#trainingsession_exercises) | Bài tập được thực hiện trong buổi. exercise_id là bài THỰC TẾ (có thể khác bài kê trong giáo án khi đổi sang bài thay thế), nên không phụ thuộc hàm vào plan_exercise_id. |
| [`set_rep_events`](#trainingset_rep_events) | Dữ liệu từng rep do máy trạng thái (FSM) trên thiết bị ghi nhận: thời lượng các pha (tempo) và biên độ góc khớp. Tempo trung bình/TUT tính ở training.v_set_tempo. |
| [`workout_plan_days`](#trainingworkout_plan_days) | Các buổi trong một chu kỳ giáo án (vd: Ngày 1 – Push, Ngày 2 – Pull). |
| [`workout_plan_exercises`](#trainingworkout_plan_exercises) | Bài tập được kê trong một buổi của giáo án (chỉ tiêu set/rep hoặc thời gian/tạ/tempo). Tempo tách thành 4 cột nguyên tử thay vì chuỗi "3-1-1-0" (1NF). |
| [`workout_plans`](#trainingworkout_plans) | Giáo án tập. owner_user_id NULL = giáo án mẫu của hệ thống (do biên tập viên tạo, mọi user dùng được). Số buổi/tuần suy ra từ số ngày trong giáo án. |
| [`workout_sessions`](#trainingworkout_sessions) | Buổi tập thực tế. Mỗi user chỉ có tối đa 1 buổi in_progress (bài thêm từ Wiki/quét thiết bị sẽ vào buổi này). Thời lượng, volume, calo tiêu hao xem training.v_session_summary. |

### `training.workout_plans`

Giáo án tập. owner_user_id NULL = giáo án mẫu của hệ thống (do biên tập viên tạo, mọi user dùng được). Số buổi/tuần suy ra từ số ngày trong giáo án.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | PK | Khoá chính. |
| 2 | `owner_user_id` | uuid |  |  | FK → auth.users | Chủ sở hữu (FK → auth.users); NULL = giáo án mẫu. |
| 3 | `source_plan_id` | uuid |  |  | FK → training.workout_plans | Giáo án gốc nếu được nhân bản từ mẫu. |
| 4 | `name` | character varying(150) | NOT NULL |  |  | Tên giáo án. |
| 5 | `description` | text |  |  |  | Mô tả. |
| 6 | `goal_type_id` | smallint |  |  | FK → body.fitness_goal_types | Mục tiêu phù hợp (FK → body.fitness_goal_types). |
| 7 | `difficulty_level_id` | smallint |  |  | FK → catalog.difficulty_levels | Độ khó (FK → catalog.difficulty_levels). |
| 8 | `duration_weeks` | smallint |  |  |  | Thời lượng chương trình (tuần). |
| 9 | `status` | training.plan_status | NOT NULL | 'draft'::training.plan_status |  | draft/active/archived. |
| 10 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 11 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |
| 12 | `deleted_at` | timestamp with time zone |  |  |  | Xoá mềm. |

**Ràng buộc:**

- `ck_workout_plans_duration` — `CHECK (((duration_weeks IS NULL) OR ((duration_weeks >= 1) AND (duration_weeks <= 104))))`
- `ck_workout_plans_not_self_source` — `CHECK (((source_plan_id IS NULL) OR (source_plan_id <> id)))`

**Index:**

- `ix_workout_plans_difficulty_level_id` — `USING btree (difficulty_level_id)`
- `ix_workout_plans_goal_type_id` — `USING btree (goal_type_id)`
- `ix_workout_plans_owner_user_id` — `USING btree (owner_user_id)`
- `ix_workout_plans_source_plan_id` — `USING btree (source_plan_id)`
- `ix_workout_plans_templates` — `USING btree (difficulty_level_id) WHERE ((owner_user_id IS NULL) AND (status = 'active'::training.plan_status) AND (deleted_at IS NULL))`

### `training.workout_plan_days`

Các buổi trong một chu kỳ giáo án (vd: Ngày 1 – Push, Ngày 2 – Pull).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | PK | Khoá chính. |
| 2 | `plan_id` | uuid | NOT NULL |  | UQ<br>FK → training.workout_plans | FK → training.workout_plans. |
| 3 | `day_no` | smallint | NOT NULL |  | UQ | Thứ tự buổi trong chu kỳ (unique trong giáo án, deferrable để sắp xếp lại). |
| 4 | `name` | character varying(100) | NOT NULL |  |  | Tên buổi. |
| 5 | `notes` | text |  |  |  | Ghi chú. |
| 6 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 7 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_workout_plan_days_day_no` — `CHECK (((day_no >= 1) AND (day_no <= 31)))`
- `uq_workout_plan_days_plan_day` — `UNIQUE (plan_id, day_no) DEFERRABLE INITIALLY DEFERRED`

### `training.workout_plan_exercises`

Bài tập được kê trong một buổi của giáo án (chỉ tiêu set/rep hoặc thời gian/tạ/tempo). Tempo tách thành 4 cột nguyên tử thay vì chuỗi "3-1-1-0" (1NF).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | PK | Khoá chính. |
| 2 | `plan_day_id` | uuid | NOT NULL |  | UQ<br>FK → training.workout_plan_days | FK → training.workout_plan_days. |
| 3 | `exercise_id` | integer | NOT NULL |  | FK → catalog.exercises | FK → catalog.exercises. |
| 4 | `order_no` | smallint | NOT NULL |  | UQ | Thứ tự trong buổi. |
| 5 | `target_sets` | smallint | NOT NULL |  |  | Số hiệp mục tiêu. |
| 6 | `target_reps_min` | smallint |  |  |  | Số rep tối thiểu mục tiêu. |
| 7 | `target_reps_max` | smallint |  |  |  | Số rep tối đa mục tiêu. |
| 8 | `target_duration_seconds` | smallint |  |  |  | Thời gian mục tiêu mỗi hiệp (giây) cho bài giữ tĩnh/cardio (vd: Plank 60s, chạy bộ 1200s). Phải có rep mục tiêu hoặc thời gian mục tiêu. |
| 9 | `target_weight_kg` | numeric(6,2) |  |  |  | Mức tạ mục tiêu (kg). |
| 10 | `target_rpe` | numeric(3,1) |  |  |  | RPE mục tiêu (1–10). |
| 11 | `rest_seconds` | smallint |  |  |  | Thời gian nghỉ giữa hiệp (giây). |
| 12 | `tempo_eccentric_s` | smallint |  |  |  | Tempo pha hạ/co dài (giây). |
| 13 | `tempo_pause_bottom_s` | smallint |  |  |  | Tempo dừng ở điểm thấp (giây). |
| 14 | `tempo_concentric_s` | smallint |  |  |  | Tempo pha đẩy/co ngắn (giây). |
| 15 | `tempo_pause_top_s` | smallint |  |  |  | Tempo dừng ở điểm cao (giây). |
| 16 | `notes` | character varying(500) |  |  |  | Ghi chú cho bài tập. |
| 17 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 18 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_workout_plan_exercises_duration` — `CHECK (((target_duration_seconds IS NULL) OR ((target_duration_seconds >= 1) AND (target_duration_seconds <= 7200))))`
- `ck_workout_plan_exercises_has_target` — `CHECK (((target_reps_min IS NOT NULL) OR (target_duration_seconds IS NOT NULL)))`
- `ck_workout_plan_exercises_order` — `CHECK ((order_no > 0))`
- `ck_workout_plan_exercises_reps` — `CHECK ((((target_reps_min IS NULL) OR ((target_reps_min >= 1) AND (target_reps_min <= 100))) AND ((target_reps_max IS NULL) OR ((target_reps_max >= 1) AND (target_reps_max <= 100))) AND ((target_reps_min IS NULL) OR (target_reps_max IS NULL) OR (target_reps_max >= target_reps_min))))`
- `ck_workout_plan_exercises_rest` — `CHECK (((rest_seconds IS NULL) OR ((rest_seconds >= 0) AND (rest_seconds <= 900))))`
- `ck_workout_plan_exercises_rpe` — `CHECK (((target_rpe IS NULL) OR ((target_rpe >= (1)::numeric) AND (target_rpe <= (10)::numeric))))`
- `ck_workout_plan_exercises_sets` — `CHECK (((target_sets >= 1) AND (target_sets <= 20)))`
- `ck_workout_plan_exercises_tempo_all_or_none` — `CHECK ((num_nulls(tempo_eccentric_s, tempo_pause_bottom_s, tempo_concentric_s, tempo_pause_top_s) = ANY (ARRAY[0, 4])))`
- `ck_workout_plan_exercises_tempo_range` — `CHECK ((((COALESCE((tempo_eccentric_s)::integer, 0) >= 0) AND (COALESCE((tempo_eccentric_s)::integer, 0) <= 20)) AND ((COALESCE((tempo_pause_bottom_s)::integer, 0) >= 0) AND (COALESCE((tempo_pause_bottom_s)::integer, 0) <= 20)) AND ((COALESCE((tempo_concentric_s)::integer, 0) >= 0) AND (COALESCE((tempo_concentric_s)::integer, 0) <= 20)) AND ((COALESCE((tempo_pause_top_s)::integer, 0) >= 0) AND (COALESCE((tempo_pause_top_s)::integer, 0) <= 20))))`
- `ck_workout_plan_exercises_weight` — `CHECK (((target_weight_kg IS NULL) OR ((target_weight_kg >= (0)::numeric) AND (target_weight_kg <= (1000)::numeric))))`
- `uq_workout_plan_exercises_order` — `UNIQUE (plan_day_id, order_no) DEFERRABLE INITIALLY DEFERRED`

**Index:**

- `ix_workout_plan_exercises_exercise_id` — `USING btree (exercise_id)`

### `training.scheduled_workouts`

Lịch tập của user theo ngày, có thể gắn một buổi trong giáo án (của user hoặc giáo án mẫu). Khi xếp lịch nhóm cơ chưa hồi phục, app cảnh báo; nếu user vẫn xác nhận thì ghi recovery_warning_ack_at.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | UQ<br>PK | Khoá chính. |
| 2 | `user_id` | uuid | NOT NULL |  | UQ<br>FK → auth.users | FK → auth.users. |
| 3 | `plan_day_id` | uuid |  |  | FK → training.workout_plan_days | Buổi giáo án áp dụng (FK → training.workout_plan_days); NULL = buổi tự do. |
| 4 | `scheduled_date` | date | NOT NULL |  |  | Ngày tập dự kiến (theo múi giờ user). |
| 5 | `title` | character varying(150) |  |  |  | Tiêu đề buổi tự do (hoặc ghi đè tên buổi giáo án). |
| 6 | `status` | training.schedule_status | NOT NULL | 'planned'::training.schedule_status |  | planned/skipped/cancelled. |
| 7 | `recovery_warning_ack_at` | timestamp with time zone |  |  |  | Thời điểm user xác nhận vẫn tập dù được cảnh báo nhóm cơ chưa hồi phục. |
| 8 | `notes` | character varying(500) |  |  |  | Ghi chú. |
| 9 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 10 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_scheduled_workouts_has_content` — `CHECK (((plan_day_id IS NOT NULL) OR (title IS NOT NULL)))`
- `uq_scheduled_workouts_id_user` — `UNIQUE (id, user_id)`

**Index:**

- `ix_scheduled_workouts_plan_day_id` — `USING btree (plan_day_id)`
- `ix_scheduled_workouts_user_date` — `USING btree (user_id, scheduled_date)`

**Trigger:**

- `trg_scheduled_workouts_plan_access` → `fn_check_schedule_plan_access()` — Đảm bảo scheduled_workouts chỉ tham chiếu buổi giáo án của chính user hoặc giáo án mẫu.

### `training.workout_sessions`

Buổi tập thực tế. Mỗi user chỉ có tối đa 1 buổi in_progress (bài thêm từ Wiki/quét thiết bị sẽ vào buổi này). Thời lượng, volume, calo tiêu hao xem training.v_session_summary.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | PK | Khoá chính. |
| 2 | `user_id` | uuid | NOT NULL |  | FK → training.scheduled_workouts<br>FK → auth.users | FK → auth.users. |
| 3 | `scheduled_workout_id` | uuid |  |  | UQ<br>FK → training.scheduled_workouts | Lịch tập được thực hiện (FK kép → scheduled_workouts(id, user_id)); NULL = buổi tập ngoài lịch. |
| 4 | `name` | character varying(150) |  |  |  | Tên buổi tập. |
| 5 | `started_at` | timestamp with time zone | NOT NULL | now() |  | Bắt đầu. |
| 6 | `ended_at` | timestamp with time zone |  |  |  | Kết thúc; NULL khi đang tập. |
| 7 | `status` | training.session_status | NOT NULL | 'in_progress'::training.session_status |  | in_progress/completed/abandoned. |
| 8 | `session_rpe` | numeric(3,1) |  |  |  | Cảm nhận gắng sức cả buổi (1–10). |
| 9 | `notes` | text |  |  |  | Ghi chú. |
| 10 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 11 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |
| 12 | `deleted_at` | timestamp with time zone |  |  |  | Xoá mềm. |

**Ràng buộc:**

- `ck_workout_sessions_ended` — `CHECK (((status = 'in_progress'::training.session_status) = (ended_at IS NULL)))`
- `ck_workout_sessions_rpe` — `CHECK (((session_rpe IS NULL) OR ((session_rpe >= (1)::numeric) AND (session_rpe <= (10)::numeric))))`
- `ck_workout_sessions_time` — `CHECK (((ended_at IS NULL) OR (ended_at >= started_at)))`

**Index:**

- `ix_workout_sessions_user_started` — `USING btree (user_id, started_at DESC)`
- `uq_workout_sessions_one_in_progress` — `UNIQUE USING btree (user_id) WHERE ((status = 'in_progress'::training.session_status) AND (deleted_at IS NULL))`

### `training.session_exercises`

Bài tập được thực hiện trong buổi. exercise_id là bài THỰC TẾ (có thể khác bài kê trong giáo án khi đổi sang bài thay thế), nên không phụ thuộc hàm vào plan_exercise_id.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | PK | Khoá chính. |
| 2 | `session_id` | uuid | NOT NULL |  | UQ<br>FK → training.workout_sessions | FK → training.workout_sessions. |
| 3 | `exercise_id` | integer | NOT NULL |  | FK → catalog.exercises | Bài thực tế (FK → catalog.exercises). |
| 4 | `plan_exercise_id` | uuid |  |  | FK → training.workout_plan_exercises | Chỉ tiêu giáo án mà bài này thực hiện (FK → training.workout_plan_exercises). |
| 5 | `order_no` | smallint | NOT NULL |  | UQ | Thứ tự trong buổi. |
| 6 | `added_via` | training.added_via | NOT NULL | 'manual'::training.added_via |  | Nguồn thêm bài (plan/manual/wiki/equipment_scan). |
| 7 | `notes` | character varying(500) |  |  |  | Ghi chú. |
| 8 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 9 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_session_exercises_order` — `CHECK ((order_no > 0))`
- `uq_session_exercises_order` — `UNIQUE (session_id, order_no) DEFERRABLE INITIALLY DEFERRED`

**Index:**

- `ix_session_exercises_exercise_id` — `USING btree (exercise_id)`
- `ix_session_exercises_plan_exercise_id` — `USING btree (plan_exercise_id)`

### `training.exercise_sets`

Từng hiệp tập. Volume = reps × weight_kg được tính ở view (không lưu). reps là số đã được user xác nhận (có thể khác số AI đếm trong set_rep_events nếu user sửa).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | bigint | NOT NULL | IDENTITY | PK | Khoá chính. |
| 2 | `session_exercise_id` | uuid | NOT NULL |  | UQ<br>FK → training.session_exercises | FK → training.session_exercises. |
| 3 | `set_no` | smallint | NOT NULL |  | UQ | Thứ tự hiệp trong bài. |
| 4 | `set_type` | training.set_type | NOT NULL | 'working'::training.set_type |  | warmup/working/drop/failure. |
| 5 | `reps` | smallint |  |  |  | Số rep đã xác nhận. |
| 6 | `weight_kg` | numeric(6,2) |  |  |  | Mức tạ (kg); NULL với bài tự thân. |
| 7 | `duration_seconds` | integer |  |  |  | Thời gian (giây) cho bài giữ tĩnh/cardio. |
| 8 | `distance_m` | numeric(8,2) |  |  |  | Quãng đường (m) cho cardio. |
| 9 | `rpe` | numeric(3,1) |  |  |  | RPE của hiệp (1–10, bước 0.5). RIR ≈ 10 − RPE nên không lưu riêng. |
| 10 | `rest_seconds` | smallint |  |  |  | Thời gian nghỉ sau hiệp (giây). |
| 11 | `source` | training.log_source | NOT NULL | 'manual'::training.log_source |  | Nguồn dữ liệu (manual/ai_realtime/ai_video). |
| 12 | `completed_at` | timestamp with time zone |  |  |  | Thời điểm hoàn thành hiệp; NULL = hiệp dự kiến chưa tập. |
| 13 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 14 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_exercise_sets_distance` — `CHECK (((distance_m IS NULL) OR (distance_m >= (0)::numeric)))`
- `ck_exercise_sets_duration` — `CHECK (((duration_seconds IS NULL) OR ((duration_seconds >= 0) AND (duration_seconds <= 86400))))`
- `ck_exercise_sets_has_metric` — `CHECK (((reps IS NOT NULL) OR (duration_seconds IS NOT NULL) OR (distance_m IS NOT NULL)))`
- `ck_exercise_sets_reps` — `CHECK (((reps IS NULL) OR ((reps >= 0) AND (reps <= 1000))))`
- `ck_exercise_sets_rest` — `CHECK (((rest_seconds IS NULL) OR ((rest_seconds >= 0) AND (rest_seconds <= 3600))))`
- `ck_exercise_sets_rpe` — `CHECK (((rpe IS NULL) OR (((rpe >= (1)::numeric) AND (rpe <= (10)::numeric)) AND ((rpe * (2)::numeric) = trunc((rpe * (2)::numeric))))))`
- `ck_exercise_sets_set_no` — `CHECK ((set_no > 0))`
- `ck_exercise_sets_weight` — `CHECK (((weight_kg IS NULL) OR ((weight_kg >= (0)::numeric) AND (weight_kg <= (1000)::numeric))))`
- `uq_exercise_sets_set_no` — `UNIQUE (session_exercise_id, set_no) DEFERRABLE INITIALLY DEFERRED`

**Index:**

- `ix_exercise_sets_completed` — `USING btree (completed_at) WHERE (completed_at IS NOT NULL)`

### `training.set_rep_events`

Dữ liệu từng rep do máy trạng thái (FSM) trên thiết bị ghi nhận: thời lượng các pha (tempo) và biên độ góc khớp. Tempo trung bình/TUT tính ở training.v_set_tempo.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `set_id` | bigint | NOT NULL |  | PK<br>FK → training.exercise_sets | FK → training.exercise_sets. |
| 2 | `rep_no` | smallint | NOT NULL |  | PK | Số thứ tự rep trong hiệp. |
| 3 | `start_offset_ms` | integer | NOT NULL |  |  | Thời điểm bắt đầu rep tính từ đầu hiệp (ms). |
| 4 | `eccentric_ms` | integer | NOT NULL |  |  | Thời lượng pha hạ (ms). |
| 5 | `pause_bottom_ms` | integer | NOT NULL | 0 |  | Thời gian dừng ở điểm thấp (ms). |
| 6 | `concentric_ms` | integer | NOT NULL |  |  | Thời lượng pha đẩy lên (ms). |
| 7 | `pause_top_ms` | integer | NOT NULL | 0 |  | Thời gian dừng ở điểm cao (ms). |
| 8 | `min_joint_angle_deg` | numeric(5,2) |  |  |  | Góc khớp nhỏ nhất trong rep (độ). |
| 9 | `max_joint_angle_deg` | numeric(5,2) |  |  |  | Góc khớp lớn nhất trong rep (độ). |
| 10 | `is_full_rom` | boolean | NOT NULL | true |  | TRUE = đạt đủ biên độ chuyển động theo ngưỡng. |
| 11 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |

**Ràng buộc:**

- `ck_set_rep_events_angles` — `CHECK ((((min_joint_angle_deg IS NULL) OR ((min_joint_angle_deg >= (0)::numeric) AND (min_joint_angle_deg <= (180)::numeric))) AND ((max_joint_angle_deg IS NULL) OR ((max_joint_angle_deg >= (0)::numeric) AND (max_joint_angle_deg <= (180)::numeric))) AND ((min_joint_angle_deg IS NULL) OR (max_joint_angle_deg IS NULL) OR (max_joint_angle_deg >= min_joint_angle_deg))))`
- `ck_set_rep_events_durations` — `CHECK (((start_offset_ms >= 0) AND (eccentric_ms >= 0) AND (pause_bottom_ms >= 0) AND (concentric_ms >= 0) AND (pause_top_ms >= 0)))`
- `ck_set_rep_events_rep_no` — `CHECK ((rep_no > 0))`

### `training.recovery_predictions`

Kết quả model PyTorch sau mỗi buổi tập: mức mệt mỏi và thời điểm hồi phục hoàn toàn của từng nhóm cơ. User suy ra qua session (không lưu). Trạng thái Heatmap hiện tại tính ở training.v_muscle_recovery_status.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `session_id` | uuid | NOT NULL |  | PK<br>FK → training.workout_sessions | Buổi tập kích hoạt dự đoán (FK → training.workout_sessions). |
| 2 | `muscle_group_id` | smallint | NOT NULL |  | PK<br>FK → catalog.muscle_groups | FK → catalog.muscle_groups. |
| 3 | `model_version` | character varying(50) | NOT NULL |  | PK | Phiên bản model (cho phép so sánh nhiều phiên bản). |
| 4 | `fatigue_score` | numeric(5,2) | NOT NULL |  |  | Mức mệt mỏi ngay sau buổi tập (0–100). |
| 5 | `recovered_at` | timestamp with time zone | NOT NULL |  |  | Thời điểm dự kiến hồi phục hoàn toàn. |
| 6 | `predicted_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm chạy dự đoán. |

**Ràng buộc:**

- `ck_recovery_predictions_fatigue` — `CHECK (((fatigue_score >= (0)::numeric) AND (fatigue_score <= (100)::numeric)))`

**Index:**

- `ix_recovery_predictions_muscle_group_id` — `USING btree (muscle_group_id)`

### `training.muscle_soreness_reports`

User tự báo mức đau mỏi cơ (DOMS). Là nhãn thực tế để huấn luyện/cá nhân hoá model dự đoán phục hồi.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | bigint | NOT NULL | IDENTITY | PK | Khoá chính. |
| 2 | `user_id` | uuid | NOT NULL |  | UQ<br>FK → auth.users | FK → auth.users. |
| 3 | `muscle_group_id` | smallint | NOT NULL |  | UQ<br>FK → catalog.muscle_groups | FK → catalog.muscle_groups. |
| 4 | `soreness_level` | smallint | NOT NULL |  |  | Mức đau mỏi 0 (không) – 10 (rất đau). |
| 5 | `reported_at` | timestamp with time zone | NOT NULL | now() | UQ | Thời điểm báo cáo. |
| 6 | `note` | character varying(255) |  |  |  | Ghi chú. |
| 7 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |

**Ràng buộc:**

- `ck_muscle_soreness_reports_level` — `CHECK (((soreness_level >= 0) AND (soreness_level <= 10)))`
- `uq_muscle_soreness_reports` — `UNIQUE (user_id, muscle_group_id, reported_at)`

**Index:**

- `ix_muscle_soreness_reports_muscle_group_id` — `USING btree (muscle_group_id)`

## Schema `ai`

Kết quả AI: phân tích tư thế (realtime/video), job xử lý video, nhận diện thiết bị.

| Bảng | Mô tả |
|---|---|
| [`bar_path_points`](#aibar_path_points) | Toạ độ thanh tạ theo frame (chuẩn hoá 0–1 theo khung hình) để vẽ biểu đồ quỹ đạo. |
| [`equipment_scan_predictions`](#aiequipment_scan_predictions) | Top-k dự đoán của model cho một lần quét (nhãn AI đã ánh xạ sang thiết bị qua catalog.equipment_aliases). Thứ hạng và kết quả top-1 suy ra từ confidence, không lưu riêng. |
| [`equipment_scans`](#aiequipment_scans) | Mỗi lần user quét thiết bị bằng camera. Phản hồi đúng/sai và nhãn sửa (corrected_equipment_id) dùng để fine-tune YOLOv8. |
| [`pose_analyses`](#aipose_analyses) | Kết quả phân tích tư thế cho một hiệp tập (realtime trên thiết bị hoặc video trên server). User/bài tập suy ra qua set → session_exercise → session. Keypoint thô từng frame lưu thành file trên Object Storage (keypoints_media_id) thay vì JSON trong DB. |
| [`posture_issues`](#aiposture_issues) | Các lỗi tư thế AI phát hiện (vd: lưng cong khi squat) kèm vị trí thời gian, dùng để tô đỏ khung xương và vẽ timeline cảnh báo. Mã lỗi tham chiếu catalog.exercise_mistakes của đúng bài tập (kiểm tra bằng trigger). |
| [`video_analysis_jobs`](#aivideo_analysis_jobs) | Job phân tích video (1B): backend tạo job trạng thái queued + đẩy message vào queue; AI worker chuyển processing → completed/failed, upload video kết quả, backend gửi push (notified_at). |

### `ai.pose_analyses`

Kết quả phân tích tư thế cho một hiệp tập (realtime trên thiết bị hoặc video trên server). User/bài tập suy ra qua set → session_exercise → session. Keypoint thô từng frame lưu thành file trên Object Storage (keypoints_media_id) thay vì JSON trong DB.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | PK | Khoá chính. |
| 2 | `set_id` | bigint | NOT NULL |  | FK → training.exercise_sets | Hiệp được phân tích (FK → training.exercise_sets). |
| 3 | `mode` | ai.analysis_mode | NOT NULL |  |  | realtime_edge/video_server. |
| 4 | `model_name` | character varying(50) | NOT NULL |  |  | Tên model (vd: mediapipe_blazepose, yolov8_pose). |
| 5 | `model_version` | character varying(50) | NOT NULL |  |  | Phiên bản model. |
| 6 | `overall_score` | numeric(5,2) |  |  |  | Điểm kỹ thuật tổng (0–100), vd: 85/100. |
| 7 | `correct_form_pct` | numeric(5,2) |  |  |  | Tỷ lệ % thời gian/frame đúng form. |
| 8 | `detected_rep_count` | smallint |  |  |  | Số rep AI phát hiện được. |
| 9 | `feedback_summary` | text |  |  |  | Nhận xét tổng hợp. |
| 10 | `keypoints_media_id` | uuid |  |  | FK → media.media_files | File keypoint thô (JSON/NPZ) trên storage, phục vụ huấn luyện lại. |
| 11 | `analyzed_at` | timestamp with time zone |  |  |  | Thời điểm có kết quả; NULL khi video đang chờ xử lý. |
| 12 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 13 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_pose_analyses_realtime_done` — `CHECK (((mode <> 'realtime_edge'::ai.analysis_mode) OR (analyzed_at IS NOT NULL)))`
- `ck_pose_analyses_rep_count` — `CHECK (((detected_rep_count IS NULL) OR (detected_rep_count >= 0)))`
- `ck_pose_analyses_scores` — `CHECK ((((overall_score IS NULL) OR ((overall_score >= (0)::numeric) AND (overall_score <= (100)::numeric))) AND ((correct_form_pct IS NULL) OR ((correct_form_pct >= (0)::numeric) AND (correct_form_pct <= (100)::numeric)))))`

**Index:**

- `ix_pose_analyses_keypoints_media_id` — `USING btree (keypoints_media_id)`
- `ix_pose_analyses_set_id` — `USING btree (set_id)`

### `ai.video_analysis_jobs`

Job phân tích video (1B): backend tạo job trạng thái queued + đẩy message vào queue; AI worker chuyển processing → completed/failed, upload video kết quả, backend gửi push (notified_at).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | PK | Khoá chính (dùng làm message id trong queue). |
| 2 | `pose_analysis_id` | uuid | NOT NULL |  | UQ<br>FK → ai.pose_analyses | Kết quả phân tích tương ứng (1-1, FK → ai.pose_analyses, mode phải là video_server). |
| 3 | `source_video_media_id` | uuid | NOT NULL |  | FK → media.media_files | Video gốc user tải lên (FK → media.media_files). |
| 4 | `result_video_media_id` | uuid |  |  | FK → media.media_files | Video đã vẽ khung xương/nhãn cảnh báo. |
| 5 | `status` | util.job_status | NOT NULL | 'queued'::util.job_status |  | queued/processing/completed/failed/cancelled. |
| 6 | `priority` | smallint | NOT NULL | 5 |  | Độ ưu tiên 1–10 (cao xử lý trước). |
| 7 | `attempt_count` | smallint | NOT NULL | 0 |  | Số lần đã thử xử lý. |
| 8 | `max_attempts` | smallint | NOT NULL | 3 |  | Số lần thử tối đa trước khi failed. |
| 9 | `queued_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm vào hàng đợi. |
| 10 | `started_at` | timestamp with time zone |  |  |  | Thời điểm worker bắt đầu xử lý. |
| 11 | `finished_at` | timestamp with time zone |  |  |  | Thời điểm kết thúc xử lý. |
| 12 | `worker_id` | character varying(100) |  |  |  | Định danh worker xử lý. |
| 13 | `error_message` | text |  |  |  | Thông báo lỗi khi failed. |
| 14 | `notified_at` | timestamp with time zone |  |  |  | Thời điểm đã gửi push notification cho user. |
| 15 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |
| 16 | `updated_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm cập nhật gần nhất. |

**Ràng buộc:**

- `ck_video_analysis_jobs_attempts` — `CHECK (((attempt_count >= 0) AND (max_attempts >= 1) AND (attempt_count <= max_attempts)))`
- `ck_video_analysis_jobs_completed` — `CHECK (((status <> 'completed'::util.job_status) OR ((result_video_media_id IS NOT NULL) AND (finished_at IS NOT NULL))))`
- `ck_video_analysis_jobs_distinct_media` — `CHECK (((result_video_media_id IS NULL) OR (result_video_media_id <> source_video_media_id)))`
- `ck_video_analysis_jobs_failed` — `CHECK (((status <> 'failed'::util.job_status) OR (error_message IS NOT NULL)))`
- `ck_video_analysis_jobs_priority` — `CHECK (((priority >= 1) AND (priority <= 10)))`
- `ck_video_analysis_jobs_times` — `CHECK ((((started_at IS NULL) OR (started_at >= queued_at)) AND ((finished_at IS NULL) OR ((started_at IS NOT NULL) AND (finished_at >= started_at)))))`

**Index:**

- `ix_video_analysis_jobs_queue` — `USING btree (priority DESC, queued_at) WHERE (status = 'queued'::util.job_status)`
- `ix_video_analysis_jobs_result_video` — `USING btree (result_video_media_id)`
- `ix_video_analysis_jobs_source_video` — `USING btree (source_video_media_id)`

**Trigger:**

- `trg_video_analysis_jobs_mode` → `fn_check_video_job_mode()` — Job video chỉ được gắn với pose_analysis ở chế độ video_server.

### `ai.posture_issues`

Các lỗi tư thế AI phát hiện (vd: lưng cong khi squat) kèm vị trí thời gian, dùng để tô đỏ khung xương và vẽ timeline cảnh báo. Mã lỗi tham chiếu catalog.exercise_mistakes của đúng bài tập (kiểm tra bằng trigger).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | bigint | NOT NULL | IDENTITY | PK | Khoá chính. |
| 2 | `pose_analysis_id` | uuid | NOT NULL |  | FK → ai.pose_analyses | FK → ai.pose_analyses. |
| 3 | `mistake_id` | integer | NOT NULL |  | FK → catalog.exercise_mistakes | Loại lỗi (FK → catalog.exercise_mistakes). |
| 4 | `rep_no` | smallint |  |  |  | Rep xảy ra lỗi (nếu xác định được). |
| 5 | `offset_ms` | integer | NOT NULL |  |  | Thời điểm lỗi tính từ đầu hiệp/video (ms). |
| 6 | `frame_index` | integer |  |  |  | Chỉ số frame trong video (chế độ video). |
| 7 | `severity` | ai.issue_severity | NOT NULL | 'warning'::ai.issue_severity |  | info/warning/critical. |
| 8 | `measured_angle_deg` | numeric(5,2) |  |  |  | Góc khớp đo được tại thời điểm lỗi (độ). |
| 9 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm tạo bản ghi. |

**Ràng buộc:**

- `ck_posture_issues_angle` — `CHECK (((measured_angle_deg IS NULL) OR ((measured_angle_deg >= (0)::numeric) AND (measured_angle_deg <= (360)::numeric))))`
- `ck_posture_issues_frame` — `CHECK (((frame_index IS NULL) OR (frame_index >= 0)))`
- `ck_posture_issues_offset` — `CHECK ((offset_ms >= 0))`
- `ck_posture_issues_rep_no` — `CHECK (((rep_no IS NULL) OR (rep_no > 0)))`

**Index:**

- `ix_posture_issues_mistake_id` — `USING btree (mistake_id)`
- `ix_posture_issues_pose_analysis_id` — `USING btree (pose_analysis_id, offset_ms)`

**Trigger:**

- `trg_posture_issues_exercise_match` → `fn_check_posture_issue_exercise()` — Đảm bảo mã lỗi tư thế thuộc đúng bài tập của hiệp đang phân tích.

### `ai.bar_path_points`

Toạ độ thanh tạ theo frame (chuẩn hoá 0–1 theo khung hình) để vẽ biểu đồ quỹ đạo.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `pose_analysis_id` | uuid | NOT NULL |  | PK<br>FK → ai.pose_analyses | FK → ai.pose_analyses. |
| 2 | `frame_index` | integer | NOT NULL |  | PK | Chỉ số frame. |
| 3 | `offset_ms` | integer | NOT NULL |  |  | Thời điểm frame trong video (ms). |
| 4 | `x_norm` | numeric(6,5) | NOT NULL |  |  | Toạ độ X chuẩn hoá (0 = trái, 1 = phải). |
| 5 | `y_norm` | numeric(6,5) | NOT NULL |  |  | Toạ độ Y chuẩn hoá (0 = trên, 1 = dưới). |

**Ràng buộc:**

- `ck_bar_path_points_coords` — `CHECK ((((x_norm >= (0)::numeric) AND (x_norm <= (1)::numeric)) AND ((y_norm >= (0)::numeric) AND (y_norm <= (1)::numeric))))`
- `ck_bar_path_points_frame` — `CHECK (((frame_index >= 0) AND (offset_ms >= 0)))`

### `ai.equipment_scans`

Mỗi lần user quét thiết bị bằng camera. Phản hồi đúng/sai và nhãn sửa (corrected_equipment_id) dùng để fine-tune YOLOv8.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | PK | Khoá chính. |
| 2 | `user_id` | uuid | NOT NULL |  | FK → auth.users | FK → auth.users. |
| 3 | `image_media_id` | uuid |  |  | FK → media.media_files | Ảnh đã quét (có thể không lưu vì quyền riêng tư). |
| 4 | `model_name` | character varying(50) | NOT NULL |  |  | Tên model (vd: yolov8_cls_gym). |
| 5 | `model_version` | character varying(50) | NOT NULL |  |  | Phiên bản model. |
| 6 | `latency_ms` | integer |  |  |  | Thời gian suy luận (ms). |
| 7 | `scanned_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm quét. |
| 8 | `feedback` | ai.scan_feedback |  |  |  | User xác nhận kết quả đúng/sai. |
| 9 | `feedback_at` | timestamp with time zone |  |  |  | Thời điểm phản hồi. |
| 10 | `corrected_equipment_id` | integer |  |  | FK → catalog.equipment | Thiết bị đúng do user chọn khi AI sai. |

**Ràng buộc:**

- `ck_equipment_scans_correction` — `CHECK (((corrected_equipment_id IS NULL) OR (feedback = 'incorrect'::ai.scan_feedback)))`
- `ck_equipment_scans_feedback` — `CHECK (((feedback IS NULL) = (feedback_at IS NULL)))`
- `ck_equipment_scans_latency` — `CHECK (((latency_ms IS NULL) OR (latency_ms >= 0)))`

**Index:**

- `ix_equipment_scans_corrected_equipment_id` — `USING btree (corrected_equipment_id)`
- `ix_equipment_scans_image_media_id` — `USING btree (image_media_id)`
- `ix_equipment_scans_user_time` — `USING btree (user_id, scanned_at DESC)`

### `ai.equipment_scan_predictions`

Top-k dự đoán của model cho một lần quét (nhãn AI đã ánh xạ sang thiết bị qua catalog.equipment_aliases). Thứ hạng và kết quả top-1 suy ra từ confidence, không lưu riêng.

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `scan_id` | uuid | NOT NULL |  | PK<br>FK → ai.equipment_scans | FK → ai.equipment_scans. |
| 2 | `equipment_id` | integer | NOT NULL |  | PK<br>FK → catalog.equipment | Thiết bị dự đoán (FK → catalog.equipment). |
| 3 | `confidence` | numeric(5,4) | NOT NULL |  |  | Độ tin cậy (0–1). |

**Ràng buộc:**

- `ck_equipment_scan_predictions_confidence` — `CHECK (((confidence >= (0)::numeric) AND (confidence <= (1)::numeric)))`

**Index:**

- `ix_equipment_scan_predictions_equipment_id` — `USING btree (equipment_id)`

## Schema `analytics`

Báo cáo xuất bản và materialized view tổng hợp phục vụ Dashboard.

| Bảng | Mô tả |
|---|---|
| [`report_exports`](#analyticsreport_exports) | Thẻ báo cáo (ảnh) đã xuất để lưu/chia sẻ mạng xã hội. Tuần bắt đầu thứ Hai, tháng bắt đầu ngày 1; period_end = period_start + kỳ (tính, không lưu). |

### `analytics.report_exports`

Thẻ báo cáo (ảnh) đã xuất để lưu/chia sẻ mạng xã hội. Tuần bắt đầu thứ Hai, tháng bắt đầu ngày 1; period_end = period_start + kỳ (tính, không lưu).

| # | Cột | Kiểu | Null | Mặc định | Khoá | Mô tả |
|---|---|---|---|---|---|---|
| 1 | `id` | uuid | NOT NULL | gen_random_uuid() | PK | Khoá chính. |
| 2 | `user_id` | uuid | NOT NULL |  | UQ<br>FK → auth.users | FK → auth.users. |
| 3 | `report_type` | analytics.report_type | NOT NULL |  | UQ | weekly_summary/monthly_summary. |
| 4 | `period_start` | date | NOT NULL |  | UQ | Ngày bắt đầu kỳ báo cáo. |
| 5 | `media_id` | uuid | NOT NULL |  | FK → media.media_files | Ảnh thẻ báo cáo (FK → media.media_files). |
| 6 | `created_at` | timestamp with time zone | NOT NULL | now() |  | Thời điểm xuất. |

**Ràng buộc:**

- `ck_report_exports_period_start` — `CHECK ((((report_type = 'weekly_summary'::analytics.report_type) AND (EXTRACT(isodow FROM period_start) = (1)::numeric)) OR ((report_type = 'monthly_summary'::analytics.report_type) AND (EXTRACT(day FROM period_start) = (1)::numeric))))`
- `uq_report_exports_period` — `UNIQUE (user_id, report_type, period_start)`

**Index:**

- `ix_report_exports_media_id` — `USING btree (media_id)`

## Views, materialized views & hàm

| Đối tượng | Loại | Mô tả |
|---|---|---|
| `media.v_progress_photo_cards` | view | Ảnh tiến độ kèm ngày chụp (theo múi giờ user) và cân nặng/%mỡ tại thời điểm chụp — dữ liệu để đóng watermark và hiển thị lưới ảnh/so sánh Before-After. |
| `catalog.v_exercise_cards` | view | Bài tập đã xuất bản kèm độ khó, nhóm cơ chính/phụ, thiết bị bắt buộc và thumbnail (chuỗi ghép chỉ để hiển thị). |
| `body.v_body_metrics` | view | Số đo cơ thể kèm tuổi, BMI (+ phân loại châu Á), LBM, BMR (Mifflin-St Jeor & Katch-McArdle), TDEE. Tính tại thời điểm truy vấn. |
| `body.v_latest_body_metrics` | view | Lần đo gần nhất của mỗi user cùng các chỉ số tính toán. |
| `body.v_weekly_weight_trend` | view | Cân nặng/%mỡ trung bình theo tuần (theo múi giờ user), chênh lệch so với tuần trước và cờ chững cân (plateau). |
| `training.v_muscle_recovery_status` | view | Heatmap phục hồi: với mỗi user × nhóm cơ, lấy dự đoán mới nhất, tính % hồi phục và số giờ còn lại tại thời điểm truy vấn. recovery_status: fatigued (đỏ) / recovering (vàng) / ready (xanh). Luôn lọc theo user_id khi truy vấn. |
| `training.v_session_muscle_load` | view | Khối lượng tập phân bổ cho từng nhóm cơ trong mỗi buổi (volume × activation_ratio). Đây là đặc trưng đầu vào của model PyTorch dự đoán phục hồi. |
| `training.v_session_summary` | view | Tổng hợp buổi tập: thời lượng, số bài, số hiệp hoàn thành, tổng rep, tổng volume (không tính khởi động), calo ước tính = MET × kg × giờ (cân nặng = lần đo gần nhất trước buổi tập). |
| `training.v_set_metrics` | view | Từng hiệp kèm volume (reps × kg) và 1RM ước tính (Epley). |
| `training.v_set_tempo` | view | Tempo trung bình mỗi pha, tổng thời gian chịu tải (TUT) và tỷ lệ rep đủ biên độ của từng hiệp do AI ghi nhận. |
| `training.v_weekly_adherence` | view | Tiến độ hoàn thành lịch tập theo tuần (thứ Hai đầu tuần): số buổi dự kiến, đã hoàn thành, bỏ qua và % tuân thủ. |
| `ai.v_equipment_scan_results` | view | Mỗi lần quét kèm thiết bị có confidence cao nhất, cờ đủ tin cậy (≥ 0.6) và thiết bị cuối cùng (ưu tiên nhãn user sửa). |
| `ai.v_form_score_trend` | view | Điểm kỹ thuật và % đúng form trung bình theo ngày cho từng bài tập của user. |
| `ai.v_pose_analysis_details` | view | Phân tích tư thế kèm hiệp/bài/buổi tập/user, trạng thái job video và số lỗi phát hiện. |
| `analytics.mv_daily_user_summary` | materialized view | Tổng hợp theo ngày (múi giờ user): số buổi, hiệp, rep, volume, phút tập, calo tiêu hao ước tính, cân nặng cuối ngày, % đúng form. Nguồn cho biểu đồ Tháng/3 Tháng. |
| `analytics.refresh_materialized_views(p_concurrently boolean)` | hàm | Làm mới toàn bộ materialized view trong schema analytics (mặc định CONCURRENTLY, không khoá đọc). |
| `catalog.fn_exercises_for_ai_label(p_ai_label text, p_limit integer)` | hàm | Ánh xạ nhãn lớp của model nhận diện thiết bị sang danh sách bài tập dùng thiết bị đó. |
| `catalog.fn_search_exercises(p_keyword text, p_muscle_group_ids smallint[], p_primary_only boolean, p_available_equipment_ids integer[], p_max_difficulty_rank smallint, p_limit integer, p_offset integer)` | hàm | Tìm & lọc bài tập theo từ khoá (không dấu), nhóm cơ chính/phụ, thiết bị sẵn có, độ khó; sắp xếp theo độ khó. |
| `catalog.fn_suggest_alternatives(p_exercise_id integer, p_unavailable_equipment_ids integer[], p_limit integer)` | hàm | Gợi ý bài thay thế cùng nhóm cơ chính, loại bài cần thiết bị đang bận; ưu tiên bài do biên tập viên chọn. |
| `util.immutable_unaccent(p_text text)` | hàm | Wrapper IMMUTABLE của unaccent() (dùng được trong index). |
| `util.search_norm(p_text text)` | hàm | Chuẩn hoá chuỗi để tìm kiếm: bỏ dấu tiếng Việt + chữ thường. Ví dụ: 'Lưng xô' → 'lung xo'. |
