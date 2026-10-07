-- =====================================================================
-- Smart Workout AI — 01: Common functions & shared types (schema util)
-- =====================================================================

-- ---------------------------------------------------------------------
-- Shared enum types
-- ---------------------------------------------------------------------
CREATE TYPE util.job_status AS ENUM ('queued', 'processing', 'completed', 'failed', 'cancelled');
COMMENT ON TYPE util.job_status IS 'Trạng thái xử lý bất đồng bộ (video AI, watermark ảnh): queued → processing → completed | failed | cancelled.';

-- ---------------------------------------------------------------------
-- Trigger function: tự cập nhật cột updated_at
-- (được gắn cho mọi bảng có cột updated_at trong 90_triggers.sql)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION util.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
COMMENT ON FUNCTION util.set_updated_at() IS 'Trigger BEFORE UPDATE: gán updated_at = now().';

-- ---------------------------------------------------------------------
-- Chuẩn hoá chuỗi tìm kiếm tiếng Việt (bỏ dấu + chữ thường)
-- unaccent() là STABLE nên cần wrapper IMMUTABLE để dùng trong index biểu thức.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION util.immutable_unaccent(p_text text)
RETURNS text
LANGUAGE sql
IMMUTABLE PARALLEL SAFE STRICT
AS $$
    SELECT public.unaccent('public.unaccent'::regdictionary, p_text)
$$;
COMMENT ON FUNCTION util.immutable_unaccent(text) IS 'Wrapper IMMUTABLE của unaccent() (dùng được trong index).';

CREATE OR REPLACE FUNCTION util.search_norm(p_text text)
RETURNS text
LANGUAGE sql
IMMUTABLE PARALLEL SAFE STRICT
AS $$
    SELECT lower(util.immutable_unaccent(p_text))
$$;
COMMENT ON FUNCTION util.search_norm(text) IS 'Chuẩn hoá chuỗi để tìm kiếm: bỏ dấu tiếng Việt + chữ thường. Ví dụ: ''Lưng xô'' → ''lung xo''.';
