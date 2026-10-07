-- =====================================================================
-- Smart Workout AI — 08: Progress Gallery (schema media)
-- Chức năng 4 (Nhật ký ảnh, watermark tự động, so sánh Before/After)
-- Cân nặng/%mỡ in trên ảnh KHÔNG lưu ở đây — lấy từ body.body_measurements
-- theo lần đo gần nhất trước thời điểm chụp (view media.v_progress_photo_cards).
-- =====================================================================

CREATE TYPE media.photo_angle AS ENUM ('front', 'side', 'back');
CREATE TYPE media.capture_source AS ENUM ('camera', 'library');

COMMENT ON TYPE media.photo_angle IS 'Góc chụp ảnh vóc dáng.';
COMMENT ON TYPE media.capture_source IS 'Ảnh chụp trực tiếp hay tải từ thư viện máy.';

CREATE TABLE media.progress_photos (
    id                      uuid                    NOT NULL DEFAULT gen_random_uuid(),
    user_id                 uuid                    NOT NULL,
    original_media_id       uuid                    NOT NULL,
    watermarked_media_id    uuid,
    thumbnail_media_id      uuid,
    angle                   media.photo_angle       NOT NULL,
    capture_source          media.capture_source    NOT NULL DEFAULT 'camera',
    taken_at                timestamptz             NOT NULL,
    processing_status       util.job_status         NOT NULL DEFAULT 'queued',
    processing_error        text,
    note                    varchar(500),
    created_at              timestamptz             NOT NULL DEFAULT now(),
    updated_at              timestamptz             NOT NULL DEFAULT now(),
    deleted_at              timestamptz,
    CONSTRAINT pk_progress_photos PRIMARY KEY (id),
    CONSTRAINT fk_progress_photos_user FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE CASCADE,
    CONSTRAINT fk_progress_photos_original_media FOREIGN KEY (original_media_id) REFERENCES media.media_files (id) ON DELETE RESTRICT,
    CONSTRAINT fk_progress_photos_watermarked_media FOREIGN KEY (watermarked_media_id) REFERENCES media.media_files (id) ON DELETE SET NULL,
    CONSTRAINT fk_progress_photos_thumbnail_media FOREIGN KEY (thumbnail_media_id) REFERENCES media.media_files (id) ON DELETE SET NULL,
    CONSTRAINT uq_progress_photos_original_media UNIQUE (original_media_id),
    CONSTRAINT ck_progress_photos_completed CHECK (processing_status <> 'completed' OR watermarked_media_id IS NOT NULL),
    CONSTRAINT ck_progress_photos_failed CHECK (processing_status <> 'failed' OR processing_error IS NOT NULL),
    CONSTRAINT ck_progress_photos_distinct_media CHECK (
        (watermarked_media_id IS NULL OR watermarked_media_id <> original_media_id)
        AND (thumbnail_media_id IS NULL OR thumbnail_media_id <> original_media_id))
);
CREATE INDEX ix_progress_photos_user_taken ON media.progress_photos (user_id, taken_at DESC);
CREATE INDEX ix_progress_photos_watermarked_media_id ON media.progress_photos (watermarked_media_id);
CREATE INDEX ix_progress_photos_thumbnail_media_id ON media.progress_photos (thumbnail_media_id);
COMMENT ON TABLE  media.progress_photos IS 'Ảnh vóc dáng theo thời gian. Async worker nén ảnh, sinh thumbnail và đóng watermark (Ngày – Cân nặng – %Mỡ) rồi cập nhật processing_status.';
COMMENT ON COLUMN media.progress_photos.id IS 'Khoá chính.';
COMMENT ON COLUMN media.progress_photos.user_id IS 'Chủ ảnh (FK → auth.users).';
COMMENT ON COLUMN media.progress_photos.original_media_id IS 'Ảnh gốc (FK → media.media_files).';
COMMENT ON COLUMN media.progress_photos.watermarked_media_id IS 'Ảnh đã đóng watermark chỉ số.';
COMMENT ON COLUMN media.progress_photos.thumbnail_media_id IS 'Ảnh thu nhỏ cho lưới ảnh.';
COMMENT ON COLUMN media.progress_photos.angle IS 'Góc chụp front/side/back.';
COMMENT ON COLUMN media.progress_photos.capture_source IS 'camera/library.';
COMMENT ON COLUMN media.progress_photos.taken_at IS 'Thời điểm chụp (sắp xếp dòng thời gian, tra số đo tương ứng).';
COMMENT ON COLUMN media.progress_photos.processing_status IS 'Trạng thái xử lý watermark.';
COMMENT ON COLUMN media.progress_photos.processing_error IS 'Lỗi xử lý (khi failed).';
COMMENT ON COLUMN media.progress_photos.note IS 'Ghi chú.';
COMMENT ON COLUMN media.progress_photos.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN media.progress_photos.updated_at IS 'Thời điểm cập nhật gần nhất.';
COMMENT ON COLUMN media.progress_photos.deleted_at IS 'Xoá mềm.';

-- ---------------------------------------------------------------------
-- media.photo_comparisons — cặp ảnh Before/After đã lưu
-- Không lưu user_id (suy ra từ ảnh); trigger đảm bảo 2 ảnh cùng một chủ.
-- ---------------------------------------------------------------------
CREATE TABLE media.photo_comparisons (
    id              uuid            NOT NULL DEFAULT gen_random_uuid(),
    before_photo_id uuid            NOT NULL,
    after_photo_id  uuid            NOT NULL,
    title           varchar(100),
    created_at      timestamptz     NOT NULL DEFAULT now(),
    CONSTRAINT pk_photo_comparisons PRIMARY KEY (id),
    CONSTRAINT fk_photo_comparisons_before FOREIGN KEY (before_photo_id) REFERENCES media.progress_photos (id) ON DELETE CASCADE,
    CONSTRAINT fk_photo_comparisons_after FOREIGN KEY (after_photo_id) REFERENCES media.progress_photos (id) ON DELETE CASCADE,
    CONSTRAINT uq_photo_comparisons_pair UNIQUE (before_photo_id, after_photo_id),
    CONSTRAINT ck_photo_comparisons_distinct CHECK (before_photo_id <> after_photo_id)
);
CREATE INDEX ix_photo_comparisons_after_photo_id ON media.photo_comparisons (after_photo_id);
COMMENT ON TABLE  media.photo_comparisons IS 'Cặp ảnh Before/After user đã lưu để xem lại/chia sẻ. Chủ sở hữu suy ra từ ảnh.';
COMMENT ON COLUMN media.photo_comparisons.id IS 'Khoá chính.';
COMMENT ON COLUMN media.photo_comparisons.before_photo_id IS 'Ảnh trước (FK → media.progress_photos).';
COMMENT ON COLUMN media.photo_comparisons.after_photo_id IS 'Ảnh sau (FK → media.progress_photos).';
COMMENT ON COLUMN media.photo_comparisons.title IS 'Tiêu đề (vd: Tháng 1 vs Tháng 6).';
COMMENT ON COLUMN media.photo_comparisons.created_at IS 'Thời điểm tạo bản ghi.';

CREATE OR REPLACE FUNCTION media.fn_check_photo_comparison_owner()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_owner_count integer;
BEGIN
    SELECT count(DISTINCT p.user_id) INTO v_owner_count
    FROM media.progress_photos p
    WHERE p.id IN (NEW.before_photo_id, NEW.after_photo_id);
    IF v_owner_count > 1 THEN
        RAISE EXCEPTION 'Hai ảnh so sánh phải thuộc cùng một người dùng'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;
COMMENT ON FUNCTION media.fn_check_photo_comparison_owner() IS 'Đảm bảo hai ảnh trong một cặp so sánh thuộc cùng user.';

CREATE TRIGGER trg_photo_comparisons_owner
    BEFORE INSERT OR UPDATE ON media.photo_comparisons
    FOR EACH ROW EXECUTE FUNCTION media.fn_check_photo_comparison_owner();
