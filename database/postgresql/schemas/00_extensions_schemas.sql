-- =====================================================================
-- Smart Workout AI — 00: Extensions, schemas & database defaults
-- Target: PostgreSQL 16
-- =====================================================================

-- ---------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS citext;    -- email không phân biệt hoa/thường
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- tìm kiếm mờ (trigram) cho tên bài tập/thiết bị
CREATE EXTENSION IF NOT EXISTS unaccent;  -- tìm kiếm tiếng Việt không dấu
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- crypt()/gen_salt() cho seed dev, digest()

-- ---------------------------------------------------------------------
-- Database defaults: lưu & so sánh thời gian theo UTC
-- ---------------------------------------------------------------------
DO $$
BEGIN
    EXECUTE format('ALTER DATABASE %I SET timezone TO %L', current_database(), 'UTC');
END
$$;

-- ---------------------------------------------------------------------
-- Schemas (bounded contexts)
-- ---------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS util;
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS media;
CREATE SCHEMA IF NOT EXISTS catalog;
CREATE SCHEMA IF NOT EXISTS body;
CREATE SCHEMA IF NOT EXISTS training;
CREATE SCHEMA IF NOT EXISTS ai;
CREATE SCHEMA IF NOT EXISTS analytics;

COMMENT ON SCHEMA util      IS 'Hàm, kiểu dữ liệu và tiện ích dùng chung cho mọi schema.';
COMMENT ON SCHEMA auth      IS 'Định danh & phân quyền: tài khoản, hồ sơ, RBAC, OAuth, thiết bị, phiên đăng nhập, nhật ký đăng nhập.';
COMMENT ON SCHEMA media     IS 'Quản lý file trên Object Storage (S3/Firebase) và nhật ký ảnh tiến độ (Progress Gallery).';
COMMENT ON SCHEMA catalog   IS 'Thư viện bài tập (Exercise Wiki): nhóm cơ, thiết bị, bài tập, hướng dẫn, lỗi sai thường gặp.';
COMMENT ON SCHEMA body      IS 'Hồ sơ thể chất, chỉ số cơ thể theo thời gian và mục tiêu cá nhân.';
COMMENT ON SCHEMA training  IS 'Giáo án, lịch tập, buổi tập thực tế, set/rep/tempo và dự đoán phục hồi cơ.';
COMMENT ON SCHEMA ai        IS 'Kết quả AI: phân tích tư thế (realtime/video), job xử lý video, nhận diện thiết bị.';
COMMENT ON SCHEMA analytics IS 'Báo cáo xuất bản và materialized view tổng hợp phục vụ Dashboard.';
