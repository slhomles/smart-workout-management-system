-- =====================================================================
-- Smart Workout AI — 99: Database roles & privileges
-- Vai trò nhóm (NOLOGIN). Tài khoản đăng nhập thật do DevOps tạo rồi GRANT vào nhóm:
--   CREATE ROLE sw_backend LOGIN PASSWORD '...' IN ROLE sw_app_rw;
--   CREATE ROLE sw_bi      LOGIN PASSWORD '...' IN ROLE sw_readonly;
-- =====================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sw_app_rw') THEN
        CREATE ROLE sw_app_rw NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sw_readonly') THEN
        CREATE ROLE sw_readonly NOLOGIN;
    END IF;
END
$$;

COMMENT ON ROLE sw_app_rw IS 'Nhóm quyền cho Backend/AI worker: đọc/ghi dữ liệu (DML), không DDL.';
COMMENT ON ROLE sw_readonly IS 'Nhóm quyền chỉ đọc cho BI/báo cáo; không được đọc mật khẩu băm và token.';

-- ---------------------------------------------------------------------
-- sw_app_rw: DML trên mọi schema nghiệp vụ
-- ---------------------------------------------------------------------
GRANT USAGE ON SCHEMA util, auth, media, catalog, body, training, ai, analytics TO sw_app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA auth, media, catalog, body, training, ai, analytics TO sw_app_rw;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA auth, media, catalog, body, training, ai, analytics TO sw_app_rw;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA util, auth, media, catalog, body, training, ai, analytics TO sw_app_rw;

ALTER DEFAULT PRIVILEGES IN SCHEMA auth, media, catalog, body, training, ai, analytics
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sw_app_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth, media, catalog, body, training, ai, analytics
    GRANT USAGE, SELECT ON SEQUENCES TO sw_app_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA util, auth, media, catalog, body, training, ai, analytics
    GRANT EXECUTE ON FUNCTIONS TO sw_app_rw;

-- ---------------------------------------------------------------------
-- sw_readonly: SELECT trên dữ liệu nghiệp vụ, KHÔNG có bí mật xác thực
-- ---------------------------------------------------------------------
GRANT USAGE ON SCHEMA util, auth, media, catalog, body, training, ai, analytics TO sw_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA media, catalog, body, training, ai, analytics TO sw_readonly;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA util, catalog TO sw_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA media, catalog, body, training, ai, analytics
    GRANT SELECT ON TABLES TO sw_readonly;

-- auth: chỉ các bảng không chứa bí mật; users thì cấp theo cột (bỏ password_hash)
GRANT SELECT ON auth.user_profiles, auth.roles, auth.permissions, auth.role_permissions, auth.user_roles TO sw_readonly;
GRANT SELECT (id, email, phone_number, status, email_verified_at, phone_verified_at,
              password_changed_at, locked_until, created_at, updated_at, deleted_at)
    ON auth.users TO sw_readonly;
-- Không cấp: auth.refresh_tokens, auth.verification_tokens, auth.oauth_accounts,
--            auth.user_devices (push token), auth.login_attempts (IP/User-Agent).
