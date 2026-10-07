-- =====================================================================
-- Smart Workout AI — 03: Media files registry (schema media)
-- File thực nằm trên Object Storage (S3/Firebase); DB chỉ lưu metadata.
-- =====================================================================

CREATE TYPE media.storage_provider AS ENUM ('s3', 'firebase');
CREATE TYPE media.media_status AS ENUM ('pending_upload', 'available', 'failed', 'quarantined');

COMMENT ON TYPE media.storage_provider IS 'Nơi lưu trữ object.';
COMMENT ON TYPE media.media_status IS 'Vòng đời file: pending_upload (đã cấp presigned URL) → available | failed | quarantined (bị chặn kiểm duyệt).';

-- ---------------------------------------------------------------------
-- media.media_files
-- URL KHÔNG được lưu: URL = f(storage_provider, bucket, object_key, CDN) sinh ở tầng ứng dụng.
-- Loại media (ảnh/video) suy ra từ mime_type.
-- ---------------------------------------------------------------------
CREATE TABLE media.media_files (
    id                  uuid                    NOT NULL DEFAULT gen_random_uuid(),
    uploaded_by_user_id uuid,
    storage_provider    media.storage_provider  NOT NULL DEFAULT 's3',
    bucket              varchar(63)             NOT NULL,
    object_key          varchar(1024)           NOT NULL,
    original_filename   varchar(255),
    mime_type           varchar(100)            NOT NULL,
    size_bytes          bigint,
    checksum_sha256     char(64),
    width_px            integer,
    height_px           integer,
    duration_ms         integer,
    status              media.media_status      NOT NULL DEFAULT 'pending_upload',
    created_at          timestamptz             NOT NULL DEFAULT now(),
    updated_at          timestamptz             NOT NULL DEFAULT now(),
    deleted_at          timestamptz,
    CONSTRAINT pk_media_files PRIMARY KEY (id),
    CONSTRAINT fk_media_files_uploaded_by FOREIGN KEY (uploaded_by_user_id) REFERENCES auth.users (id) ON DELETE SET NULL,
    CONSTRAINT uq_media_files_object UNIQUE (storage_provider, bucket, object_key),
    CONSTRAINT ck_media_files_mime_format CHECK (mime_type ~ '^[a-z]+/[a-z0-9.+-]+$'),
    CONSTRAINT ck_media_files_size CHECK (size_bytes IS NULL OR size_bytes >= 0),
    CONSTRAINT ck_media_files_checksum CHECK (checksum_sha256 IS NULL OR checksum_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_media_files_dimensions CHECK ((width_px IS NULL OR width_px > 0) AND (height_px IS NULL OR height_px > 0)),
    CONSTRAINT ck_media_files_duration CHECK (duration_ms IS NULL OR duration_ms >= 0),
    CONSTRAINT ck_media_files_available CHECK (status <> 'available' OR (size_bytes IS NOT NULL AND checksum_sha256 IS NOT NULL))
);
CREATE INDEX ix_media_files_uploaded_by ON media.media_files (uploaded_by_user_id);
CREATE INDEX ix_media_files_pending ON media.media_files (created_at) WHERE status = 'pending_upload';

COMMENT ON TABLE  media.media_files IS 'Sổ đăng ký mọi file (ảnh, GIF, video, keypoint) trên Object Storage. Các bảng nghiệp vụ tham chiếu tới đây thay vì lưu URL.';
COMMENT ON COLUMN media.media_files.id IS 'Khoá chính.';
COMMENT ON COLUMN media.media_files.uploaded_by_user_id IS 'Người tải lên (FK → auth.users); NULL nếu do hệ thống sinh hoặc user đã bị xoá.';
COMMENT ON COLUMN media.media_files.storage_provider IS 'Nhà cung cấp lưu trữ (s3/firebase).';
COMMENT ON COLUMN media.media_files.bucket IS 'Tên bucket.';
COMMENT ON COLUMN media.media_files.object_key IS 'Đường dẫn object trong bucket.';
COMMENT ON COLUMN media.media_files.original_filename IS 'Tên file gốc phía client.';
COMMENT ON COLUMN media.media_files.mime_type IS 'MIME type (vd: image/jpeg, video/mp4).';
COMMENT ON COLUMN media.media_files.size_bytes IS 'Kích thước (byte); bắt buộc khi available.';
COMMENT ON COLUMN media.media_files.checksum_sha256 IS 'SHA-256 nội dung file; bắt buộc khi available (chống trùng/hỏng).';
COMMENT ON COLUMN media.media_files.width_px IS 'Chiều rộng (ảnh/video).';
COMMENT ON COLUMN media.media_files.height_px IS 'Chiều cao (ảnh/video).';
COMMENT ON COLUMN media.media_files.duration_ms IS 'Thời lượng video/GIF (ms).';
COMMENT ON COLUMN media.media_files.status IS 'Trạng thái vòng đời file.';
COMMENT ON COLUMN media.media_files.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN media.media_files.updated_at IS 'Thời điểm cập nhật gần nhất.';
COMMENT ON COLUMN media.media_files.deleted_at IS 'Xoá mềm; job dọn dẹp sẽ xoá object trên storage.';

-- FK trì hoãn từ 02_auth.sql (auth được tạo trước media)
ALTER TABLE auth.user_profiles
    ADD CONSTRAINT fk_user_profiles_avatar_media FOREIGN KEY (avatar_media_id)
        REFERENCES media.media_files (id) ON DELETE SET NULL;
