-- =====================================================================
-- Smart Workout AI — Views: media (Progress Gallery)
-- =====================================================================

-- ---------------------------------------------------------------------
-- media.v_progress_photo_cards — lưới ảnh tiến độ: Ngày chụp – Cân nặng – %Mỡ
-- Số đo = lần đo gần nhất của user tại hoặc trước thời điểm chụp.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW media.v_progress_photo_cards AS
SELECT
    p.id                    AS photo_id,
    p.user_id,
    p.angle,
    p.capture_source,
    p.taken_at,
    (p.taken_at AT TIME ZONE coalesce(up.timezone, 'Asia/Ho_Chi_Minh'))::date AS taken_date,
    p.original_media_id,
    p.watermarked_media_id,
    p.thumbnail_media_id,
    p.processing_status,
    bm.measurement_id,
    bm.measured_at,
    bm.weight_kg,
    bm.body_fat_pct
FROM media.progress_photos p
LEFT JOIN auth.user_profiles up ON up.user_id = p.user_id
LEFT JOIN LATERAL (
    SELECT m.id AS measurement_id, m.measured_at, m.weight_kg, m.body_fat_pct
    FROM body.body_measurements m
    WHERE m.user_id = p.user_id
      AND m.measured_at <= p.taken_at
    ORDER BY m.measured_at DESC
    LIMIT 1
) bm ON true
WHERE p.deleted_at IS NULL;

COMMENT ON VIEW media.v_progress_photo_cards IS 'Ảnh tiến độ kèm ngày chụp (theo múi giờ user) và cân nặng/%mỡ tại thời điểm chụp — dữ liệu để đóng watermark và hiển thị lưới ảnh/so sánh Before-After.';
