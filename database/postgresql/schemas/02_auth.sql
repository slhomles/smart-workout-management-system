-- =====================================================================
-- Smart Workout AI — 02: Identity & Access Management (schema auth)
-- Tài khoản, hồ sơ, RBAC, OAuth, thiết bị, refresh token, xác thực, nhật ký đăng nhập
-- =====================================================================

-- ---------------------------------------------------------------------
-- Enum types
-- ---------------------------------------------------------------------
CREATE TYPE auth.user_status AS ENUM ('pending_verification', 'active', 'locked', 'disabled');
CREATE TYPE auth.unit_system AS ENUM ('metric', 'imperial');
CREATE TYPE auth.oauth_provider AS ENUM ('google', 'apple', 'facebook');
CREATE TYPE auth.device_platform AS ENUM ('ios', 'android', 'web');
CREATE TYPE auth.token_purpose AS ENUM ('email_verification', 'phone_verification', 'password_reset');
CREATE TYPE auth.token_revoke_reason AS ENUM ('logout', 'rotated', 'reuse_detected', 'password_changed', 'admin_revoked', 'device_revoked');
CREATE TYPE auth.login_failure_reason AS ENUM ('invalid_credentials', 'account_locked', 'account_disabled', 'email_not_verified', 'oauth_error');

COMMENT ON TYPE auth.user_status IS 'Trạng thái tài khoản.';
COMMENT ON TYPE auth.unit_system IS 'Hệ đơn vị hiển thị (DB luôn lưu theo SI).';
COMMENT ON TYPE auth.oauth_provider IS 'Nhà cung cấp đăng nhập ngoài.';
COMMENT ON TYPE auth.device_platform IS 'Nền tảng thiết bị/ứng dụng.';
COMMENT ON TYPE auth.token_purpose IS 'Mục đích của token xác thực một lần.';
COMMENT ON TYPE auth.token_revoke_reason IS 'Lý do thu hồi refresh token.';
COMMENT ON TYPE auth.login_failure_reason IS 'Lý do đăng nhập thất bại.';

-- ---------------------------------------------------------------------
-- auth.users — tài khoản đăng nhập
-- ---------------------------------------------------------------------
CREATE TABLE auth.users (
    id                  uuid                NOT NULL DEFAULT gen_random_uuid(),
    email               citext              NOT NULL,
    phone_number        varchar(20),
    password_hash       varchar(255),
    status              auth.user_status    NOT NULL DEFAULT 'pending_verification',
    email_verified_at   timestamptz,
    phone_verified_at   timestamptz,
    password_changed_at timestamptz,
    locked_until        timestamptz,
    created_at          timestamptz         NOT NULL DEFAULT now(),
    updated_at          timestamptz         NOT NULL DEFAULT now(),
    deleted_at          timestamptz,
    CONSTRAINT pk_users PRIMARY KEY (id),
    CONSTRAINT ck_users_email_format CHECK (email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
    CONSTRAINT ck_users_phone_format CHECK (phone_number IS NULL OR phone_number ~ '^\+?[0-9]{8,15}$'),
    CONSTRAINT ck_users_password_hash_len CHECK (password_hash IS NULL OR length(password_hash) >= 50),
    CONSTRAINT ck_users_phone_verified CHECK (phone_verified_at IS NULL OR phone_number IS NOT NULL)
);
CREATE UNIQUE INDEX uq_users_email_alive ON auth.users (email) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX uq_users_phone_alive ON auth.users (phone_number) WHERE deleted_at IS NULL AND phone_number IS NOT NULL;
CREATE INDEX ix_users_status ON auth.users (status) WHERE deleted_at IS NULL;

COMMENT ON TABLE  auth.users IS 'Tài khoản đăng nhập. Chỉ chứa thông tin định danh & xác thực; hồ sơ hiển thị ở user_profiles, dữ liệu thể chất ở body.user_body_profiles.';
COMMENT ON COLUMN auth.users.id IS 'Khoá chính (UUID v4).';
COMMENT ON COLUMN auth.users.email IS 'Email đăng nhập (citext, duy nhất trong các tài khoản chưa xoá).';
COMMENT ON COLUMN auth.users.phone_number IS 'Số điện thoại định dạng E.164 (tuỳ chọn, duy nhất).';
COMMENT ON COLUMN auth.users.password_hash IS 'Băm mật khẩu bcrypt/argon2. NULL nếu tài khoản chỉ đăng nhập qua OAuth.';
COMMENT ON COLUMN auth.users.status IS 'Trạng thái tài khoản (pending_verification/active/locked/disabled).';
COMMENT ON COLUMN auth.users.email_verified_at IS 'Thời điểm xác thực email; NULL = chưa xác thực.';
COMMENT ON COLUMN auth.users.phone_verified_at IS 'Thời điểm xác thực số điện thoại.';
COMMENT ON COLUMN auth.users.password_changed_at IS 'Lần đổi mật khẩu gần nhất (dùng để vô hiệu token cũ).';
COMMENT ON COLUMN auth.users.locked_until IS 'Khoá tạm thời đến thời điểm này (chống brute-force).';
COMMENT ON COLUMN auth.users.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN auth.users.updated_at IS 'Thời điểm cập nhật gần nhất (trigger).';
COMMENT ON COLUMN auth.users.deleted_at IS 'Xoá mềm; NULL = còn hoạt động.';

-- ---------------------------------------------------------------------
-- auth.user_profiles — hồ sơ hiển thị & tuỳ chọn (1-1 với users)
-- ---------------------------------------------------------------------
CREATE TABLE auth.user_profiles (
    user_id         uuid                NOT NULL,
    display_name    varchar(50)         NOT NULL,
    full_name       varchar(100),
    avatar_media_id uuid,
    locale          varchar(10)         NOT NULL DEFAULT 'vi-VN',
    timezone        varchar(50)         NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
    unit_system     auth.unit_system    NOT NULL DEFAULT 'metric',
    created_at      timestamptz         NOT NULL DEFAULT now(),
    updated_at      timestamptz         NOT NULL DEFAULT now(),
    CONSTRAINT pk_user_profiles PRIMARY KEY (user_id),
    CONSTRAINT fk_user_profiles_user FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE CASCADE,
    CONSTRAINT ck_user_profiles_display_name CHECK (length(btrim(display_name)) > 0),
    CONSTRAINT ck_user_profiles_locale CHECK (locale ~ '^[a-z]{2}(-[A-Z]{2})?$')
);
-- FK avatar_media_id → media.media_files được thêm trong 03_media.sql
CREATE INDEX ix_user_profiles_avatar_media_id ON auth.user_profiles (avatar_media_id);

COMMENT ON TABLE  auth.user_profiles IS 'Hồ sơ hiển thị và tuỳ chọn cá nhân (1-1 với users).';
COMMENT ON COLUMN auth.user_profiles.user_id IS 'PK đồng thời FK → auth.users.';
COMMENT ON COLUMN auth.user_profiles.display_name IS 'Tên hiển thị trong ứng dụng.';
COMMENT ON COLUMN auth.user_profiles.full_name IS 'Họ và tên đầy đủ.';
COMMENT ON COLUMN auth.user_profiles.avatar_media_id IS 'Ảnh đại diện → media.media_files.';
COMMENT ON COLUMN auth.user_profiles.locale IS 'Ngôn ngữ giao diện (BCP-47, vd: vi-VN).';
COMMENT ON COLUMN auth.user_profiles.timezone IS 'Múi giờ IANA, dùng để chia ngày cho thống kê.';
COMMENT ON COLUMN auth.user_profiles.unit_system IS 'Hệ đơn vị hiển thị (metric/imperial).';
COMMENT ON COLUMN auth.user_profiles.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN auth.user_profiles.updated_at IS 'Thời điểm cập nhật gần nhất.';

-- ---------------------------------------------------------------------
-- RBAC: roles, permissions, role_permissions, user_roles
-- ---------------------------------------------------------------------
CREATE TABLE auth.roles (
    id          smallint        GENERATED ALWAYS AS IDENTITY,
    code        varchar(50)     NOT NULL,
    name        varchar(100)    NOT NULL,
    description text,
    is_system   boolean         NOT NULL DEFAULT false,
    created_at  timestamptz     NOT NULL DEFAULT now(),
    updated_at  timestamptz     NOT NULL DEFAULT now(),
    CONSTRAINT pk_roles PRIMARY KEY (id),
    CONSTRAINT uq_roles_code UNIQUE (code),
    CONSTRAINT ck_roles_code_format CHECK (code ~ '^[a-z][a-z0-9_]*$')
);
COMMENT ON TABLE  auth.roles IS 'Vai trò (RBAC). Ví dụ: admin, content_editor, user.';
COMMENT ON COLUMN auth.roles.id IS 'Khoá chính.';
COMMENT ON COLUMN auth.roles.code IS 'Mã vai trò (khoá tự nhiên, snake_case).';
COMMENT ON COLUMN auth.roles.name IS 'Tên hiển thị.';
COMMENT ON COLUMN auth.roles.description IS 'Mô tả phạm vi vai trò.';
COMMENT ON COLUMN auth.roles.is_system IS 'TRUE = vai trò hệ thống, không được xoá.';
COMMENT ON COLUMN auth.roles.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN auth.roles.updated_at IS 'Thời điểm cập nhật gần nhất.';

CREATE TABLE auth.permissions (
    id          smallint        GENERATED ALWAYS AS IDENTITY,
    resource    varchar(50)     NOT NULL,
    action      varchar(30)     NOT NULL,
    description text,
    created_at  timestamptz     NOT NULL DEFAULT now(),
    updated_at  timestamptz     NOT NULL DEFAULT now(),
    CONSTRAINT pk_permissions PRIMARY KEY (id),
    CONSTRAINT uq_permissions_resource_action UNIQUE (resource, action),
    CONSTRAINT ck_permissions_resource_format CHECK (resource ~ '^[a-z][a-z0-9_]*$'),
    CONSTRAINT ck_permissions_action_format CHECK (action ~ '^[a-z][a-z0-9_]*$')
);
COMMENT ON TABLE  auth.permissions IS 'Quyền nguyên tử dạng (resource, action). Chuỗi "resource:action" được ghép ở tầng ứng dụng, không lưu riêng (tránh dữ liệu dẫn xuất).';
COMMENT ON COLUMN auth.permissions.id IS 'Khoá chính.';
COMMENT ON COLUMN auth.permissions.resource IS 'Tài nguyên (vd: exercise, user, workout).';
COMMENT ON COLUMN auth.permissions.action IS 'Hành động (vd: read, create, update, delete, publish).';
COMMENT ON COLUMN auth.permissions.description IS 'Mô tả quyền.';
COMMENT ON COLUMN auth.permissions.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN auth.permissions.updated_at IS 'Thời điểm cập nhật gần nhất.';

CREATE TABLE auth.role_permissions (
    role_id         smallint    NOT NULL,
    permission_id   smallint    NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_role_permissions PRIMARY KEY (role_id, permission_id),
    CONSTRAINT fk_role_permissions_role FOREIGN KEY (role_id) REFERENCES auth.roles (id) ON DELETE CASCADE,
    CONSTRAINT fk_role_permissions_permission FOREIGN KEY (permission_id) REFERENCES auth.permissions (id) ON DELETE CASCADE
);
CREATE INDEX ix_role_permissions_permission_id ON auth.role_permissions (permission_id);
COMMENT ON TABLE  auth.role_permissions IS 'Bảng liên kết N-N: vai trò được cấp những quyền nào.';
COMMENT ON COLUMN auth.role_permissions.role_id IS 'FK → auth.roles.';
COMMENT ON COLUMN auth.role_permissions.permission_id IS 'FK → auth.permissions.';
COMMENT ON COLUMN auth.role_permissions.created_at IS 'Thời điểm gán quyền.';

CREATE TABLE auth.user_roles (
    user_id     uuid        NOT NULL,
    role_id     smallint    NOT NULL,
    granted_by  uuid,
    granted_at  timestamptz NOT NULL DEFAULT now(),
    expires_at  timestamptz,
    CONSTRAINT pk_user_roles PRIMARY KEY (user_id, role_id),
    CONSTRAINT fk_user_roles_user FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE CASCADE,
    CONSTRAINT fk_user_roles_role FOREIGN KEY (role_id) REFERENCES auth.roles (id) ON DELETE RESTRICT,
    CONSTRAINT fk_user_roles_granted_by FOREIGN KEY (granted_by) REFERENCES auth.users (id) ON DELETE SET NULL,
    CONSTRAINT ck_user_roles_expiry CHECK (expires_at IS NULL OR expires_at > granted_at)
);
CREATE INDEX ix_user_roles_role_id ON auth.user_roles (role_id);
CREATE INDEX ix_user_roles_granted_by ON auth.user_roles (granted_by);
COMMENT ON TABLE  auth.user_roles IS 'Bảng liên kết N-N: người dùng giữ vai trò nào (có thể có thời hạn).';
COMMENT ON COLUMN auth.user_roles.user_id IS 'FK → auth.users.';
COMMENT ON COLUMN auth.user_roles.role_id IS 'FK → auth.roles.';
COMMENT ON COLUMN auth.user_roles.granted_by IS 'Người cấp vai trò (FK → auth.users).';
COMMENT ON COLUMN auth.user_roles.granted_at IS 'Thời điểm cấp.';
COMMENT ON COLUMN auth.user_roles.expires_at IS 'Hết hạn vai trò; NULL = vô thời hạn.';

-- ---------------------------------------------------------------------
-- auth.oauth_accounts — liên kết đăng nhập Google/Apple/Facebook
-- ---------------------------------------------------------------------
CREATE TABLE auth.oauth_accounts (
    id                  uuid                NOT NULL DEFAULT gen_random_uuid(),
    user_id             uuid                NOT NULL,
    provider            auth.oauth_provider NOT NULL,
    provider_subject    varchar(255)        NOT NULL,
    provider_email      citext,
    linked_at           timestamptz         NOT NULL DEFAULT now(),
    created_at          timestamptz         NOT NULL DEFAULT now(),
    updated_at          timestamptz         NOT NULL DEFAULT now(),
    CONSTRAINT pk_oauth_accounts PRIMARY KEY (id),
    CONSTRAINT fk_oauth_accounts_user FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE CASCADE,
    CONSTRAINT uq_oauth_accounts_provider_subject UNIQUE (provider, provider_subject),
    CONSTRAINT uq_oauth_accounts_user_provider UNIQUE (user_id, provider)
);
COMMENT ON TABLE  auth.oauth_accounts IS 'Tài khoản đăng nhập ngoài (OAuth/OIDC) được liên kết với user.';
COMMENT ON COLUMN auth.oauth_accounts.id IS 'Khoá chính.';
COMMENT ON COLUMN auth.oauth_accounts.user_id IS 'FK → auth.users.';
COMMENT ON COLUMN auth.oauth_accounts.provider IS 'Nhà cung cấp (google/apple/facebook).';
COMMENT ON COLUMN auth.oauth_accounts.provider_subject IS 'ID người dùng phía provider (claim "sub").';
COMMENT ON COLUMN auth.oauth_accounts.provider_email IS 'Email do provider trả về tại thời điểm liên kết.';
COMMENT ON COLUMN auth.oauth_accounts.linked_at IS 'Thời điểm liên kết.';
COMMENT ON COLUMN auth.oauth_accounts.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN auth.oauth_accounts.updated_at IS 'Thời điểm cập nhật gần nhất.';

-- ---------------------------------------------------------------------
-- auth.user_devices — thiết bị/phiên cài đặt ứng dụng của user
-- ---------------------------------------------------------------------
CREATE TABLE auth.user_devices (
    id                      uuid                    NOT NULL DEFAULT gen_random_uuid(),
    user_id                 uuid                    NOT NULL,
    platform                auth.device_platform    NOT NULL,
    device_name             varchar(100),
    os_version              varchar(30),
    app_version             varchar(30),
    push_token              varchar(512),
    push_token_updated_at   timestamptz,
    last_seen_at            timestamptz             NOT NULL DEFAULT now(),
    revoked_at              timestamptz,
    created_at              timestamptz             NOT NULL DEFAULT now(),
    updated_at              timestamptz             NOT NULL DEFAULT now(),
    CONSTRAINT pk_user_devices PRIMARY KEY (id),
    CONSTRAINT fk_user_devices_user FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE CASCADE,
    CONSTRAINT ck_user_devices_push_token CHECK ((push_token IS NULL) = (push_token_updated_at IS NULL))
);
CREATE INDEX ix_user_devices_user_id ON auth.user_devices (user_id);
CREATE UNIQUE INDEX uq_user_devices_push_token_active ON auth.user_devices (push_token)
    WHERE push_token IS NOT NULL AND revoked_at IS NULL;
COMMENT ON TABLE  auth.user_devices IS 'Thiết bị (bản cài ứng dụng/trình duyệt) mà user đăng nhập. Mỗi refresh token gắn với một thiết bị; push_token dùng gửi thông báo (vd: video AI phân tích xong).';
COMMENT ON COLUMN auth.user_devices.id IS 'Khoá chính.';
COMMENT ON COLUMN auth.user_devices.user_id IS 'FK → auth.users.';
COMMENT ON COLUMN auth.user_devices.platform IS 'Nền tảng ios/android/web.';
COMMENT ON COLUMN auth.user_devices.device_name IS 'Tên thiết bị (vd: iPhone 15 của An).';
COMMENT ON COLUMN auth.user_devices.os_version IS 'Phiên bản hệ điều hành.';
COMMENT ON COLUMN auth.user_devices.app_version IS 'Phiên bản ứng dụng.';
COMMENT ON COLUMN auth.user_devices.push_token IS 'FCM/APNs token để gửi push notification.';
COMMENT ON COLUMN auth.user_devices.push_token_updated_at IS 'Thời điểm cập nhật push_token.';
COMMENT ON COLUMN auth.user_devices.last_seen_at IS 'Lần cuối thiết bị gọi API.';
COMMENT ON COLUMN auth.user_devices.revoked_at IS 'Thời điểm thu hồi thiết bị (đăng xuất từ xa).';
COMMENT ON COLUMN auth.user_devices.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN auth.user_devices.updated_at IS 'Thời điểm cập nhật gần nhất.';

-- ---------------------------------------------------------------------
-- auth.refresh_tokens — refresh token có xoay vòng (rotation)
-- Không lưu user_id: user được suy ra qua device_id (tránh phụ thuộc bắc cầu).
-- ---------------------------------------------------------------------
CREATE TABLE auth.refresh_tokens (
    id              uuid                        NOT NULL DEFAULT gen_random_uuid(),
    device_id       uuid                        NOT NULL,
    family_id       uuid                        NOT NULL,
    parent_token_id uuid,
    token_hash      char(64)                    NOT NULL,
    issued_at       timestamptz                 NOT NULL DEFAULT now(),
    expires_at      timestamptz                 NOT NULL,
    revoked_at      timestamptz,
    revoke_reason   auth.token_revoke_reason,
    ip_address      inet,
    user_agent      varchar(500),
    CONSTRAINT pk_refresh_tokens PRIMARY KEY (id),
    CONSTRAINT fk_refresh_tokens_device FOREIGN KEY (device_id) REFERENCES auth.user_devices (id) ON DELETE CASCADE,
    CONSTRAINT fk_refresh_tokens_parent FOREIGN KEY (parent_token_id) REFERENCES auth.refresh_tokens (id) ON DELETE SET NULL,
    CONSTRAINT uq_refresh_tokens_token_hash UNIQUE (token_hash),
    CONSTRAINT ck_refresh_tokens_hash_format CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_refresh_tokens_expiry CHECK (expires_at > issued_at),
    CONSTRAINT ck_refresh_tokens_revoke CHECK ((revoked_at IS NULL) = (revoke_reason IS NULL))
);
CREATE INDEX ix_refresh_tokens_device_id ON auth.refresh_tokens (device_id);
CREATE INDEX ix_refresh_tokens_family_id ON auth.refresh_tokens (family_id);
CREATE INDEX ix_refresh_tokens_parent_token_id ON auth.refresh_tokens (parent_token_id);
CREATE INDEX ix_refresh_tokens_expires_at ON auth.refresh_tokens (expires_at) WHERE revoked_at IS NULL;
COMMENT ON TABLE  auth.refresh_tokens IS 'Refresh token JWT. Chỉ lưu SHA-256 của token. Xoay vòng: mỗi lần refresh tạo token con (parent_token_id) cùng family_id; phát hiện dùng lại token cũ → thu hồi cả family.';
COMMENT ON COLUMN auth.refresh_tokens.id IS 'Khoá chính (dùng làm jti).';
COMMENT ON COLUMN auth.refresh_tokens.device_id IS 'Thiết bị sở hữu token (FK → auth.user_devices); user suy ra qua thiết bị.';
COMMENT ON COLUMN auth.refresh_tokens.family_id IS 'Chuỗi xoay vòng: mọi token sinh ra từ một lần đăng nhập có chung family_id.';
COMMENT ON COLUMN auth.refresh_tokens.parent_token_id IS 'Token trước đó trong chuỗi xoay vòng.';
COMMENT ON COLUMN auth.refresh_tokens.token_hash IS 'SHA-256 (hex) của refresh token; không bao giờ lưu token gốc.';
COMMENT ON COLUMN auth.refresh_tokens.issued_at IS 'Thời điểm phát hành.';
COMMENT ON COLUMN auth.refresh_tokens.expires_at IS 'Thời điểm hết hạn.';
COMMENT ON COLUMN auth.refresh_tokens.revoked_at IS 'Thời điểm thu hồi.';
COMMENT ON COLUMN auth.refresh_tokens.revoke_reason IS 'Lý do thu hồi (bắt buộc khi revoked_at có giá trị).';
COMMENT ON COLUMN auth.refresh_tokens.ip_address IS 'IP client khi phát hành.';
COMMENT ON COLUMN auth.refresh_tokens.user_agent IS 'User-Agent khi phát hành.';

-- ---------------------------------------------------------------------
-- auth.verification_tokens — token một lần (xác thực email, đặt lại mật khẩu)
-- ---------------------------------------------------------------------
CREATE TABLE auth.verification_tokens (
    id          uuid                NOT NULL DEFAULT gen_random_uuid(),
    user_id     uuid                NOT NULL,
    purpose     auth.token_purpose  NOT NULL,
    token_hash  char(64)            NOT NULL,
    expires_at  timestamptz         NOT NULL,
    consumed_at timestamptz,
    created_at  timestamptz         NOT NULL DEFAULT now(),
    CONSTRAINT pk_verification_tokens PRIMARY KEY (id),
    CONSTRAINT fk_verification_tokens_user FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE CASCADE,
    CONSTRAINT uq_verification_tokens_token_hash UNIQUE (token_hash),
    CONSTRAINT ck_verification_tokens_hash_format CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_verification_tokens_expiry CHECK (expires_at > created_at),
    CONSTRAINT ck_verification_tokens_consumed CHECK (consumed_at IS NULL OR consumed_at >= created_at)
);
CREATE INDEX ix_verification_tokens_user_purpose ON auth.verification_tokens (user_id, purpose);
COMMENT ON TABLE  auth.verification_tokens IS 'Token dùng một lần: xác thực email/SĐT, đặt lại mật khẩu. Chỉ lưu SHA-256.';
COMMENT ON COLUMN auth.verification_tokens.id IS 'Khoá chính.';
COMMENT ON COLUMN auth.verification_tokens.user_id IS 'FK → auth.users.';
COMMENT ON COLUMN auth.verification_tokens.purpose IS 'Mục đích token.';
COMMENT ON COLUMN auth.verification_tokens.token_hash IS 'SHA-256 (hex) của token.';
COMMENT ON COLUMN auth.verification_tokens.expires_at IS 'Thời điểm hết hạn.';
COMMENT ON COLUMN auth.verification_tokens.consumed_at IS 'Thời điểm đã sử dụng; NULL = chưa dùng.';
COMMENT ON COLUMN auth.verification_tokens.created_at IS 'Thời điểm tạo.';

-- ---------------------------------------------------------------------
-- auth.login_attempts — nhật ký đăng nhập (append-only)
-- Số lần sai liên tiếp / lần đăng nhập cuối được TÍNH từ bảng này, không lưu ở users.
-- ---------------------------------------------------------------------
CREATE TABLE auth.login_attempts (
    id              bigint                      GENERATED ALWAYS AS IDENTITY,
    user_id         uuid,
    email_attempted citext                      NOT NULL,
    ip_address      inet,
    user_agent      varchar(500),
    succeeded       boolean                     NOT NULL,
    failure_reason  auth.login_failure_reason,
    attempted_at    timestamptz                 NOT NULL DEFAULT now(),
    CONSTRAINT pk_login_attempts PRIMARY KEY (id),
    CONSTRAINT fk_login_attempts_user FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE SET NULL,
    CONSTRAINT ck_login_attempts_reason CHECK (succeeded = (failure_reason IS NULL))
);
CREATE INDEX ix_login_attempts_user_time ON auth.login_attempts (user_id, attempted_at DESC);
CREATE INDEX ix_login_attempts_email_time ON auth.login_attempts (email_attempted, attempted_at DESC);
CREATE INDEX ix_login_attempts_ip_time ON auth.login_attempts (ip_address, attempted_at DESC);
CREATE INDEX brin_login_attempts_attempted_at ON auth.login_attempts USING brin (attempted_at);
COMMENT ON TABLE  auth.login_attempts IS 'Nhật ký mọi lần đăng nhập (thành công/thất bại) phục vụ khoá tài khoản, giới hạn IP và điều tra bảo mật. Append-only, có thể xoá theo chính sách lưu trữ (vd: 180 ngày).';
COMMENT ON COLUMN auth.login_attempts.id IS 'Khoá chính.';
COMMENT ON COLUMN auth.login_attempts.user_id IS 'User tương ứng nếu email tồn tại (FK → auth.users).';
COMMENT ON COLUMN auth.login_attempts.email_attempted IS 'Email được nhập khi đăng nhập.';
COMMENT ON COLUMN auth.login_attempts.ip_address IS 'IP client.';
COMMENT ON COLUMN auth.login_attempts.user_agent IS 'User-Agent client.';
COMMENT ON COLUMN auth.login_attempts.succeeded IS 'TRUE = đăng nhập thành công.';
COMMENT ON COLUMN auth.login_attempts.failure_reason IS 'Lý do thất bại (NULL khi thành công).';
COMMENT ON COLUMN auth.login_attempts.attempted_at IS 'Thời điểm thử đăng nhập.';
