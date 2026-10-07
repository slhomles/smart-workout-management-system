-- =====================================================================
-- Smart Workout AI — 09: Analytics & reports (schema analytics)
-- Chức năng 3 bước 5 ("Xuất báo cáo tuần"). Materialized view nằm ở views/06_materialized.sql.
-- =====================================================================

CREATE TYPE analytics.report_type AS ENUM ('weekly_summary', 'monthly_summary');
COMMENT ON TYPE analytics.report_type IS 'Loại báo cáo. Kỳ báo cáo (tuần/tháng) quyết định ngày kết thúc nên period_end không được lưu.';

CREATE TABLE analytics.report_exports (
    id              uuid                    NOT NULL DEFAULT gen_random_uuid(),
    user_id         uuid                    NOT NULL,
    report_type     analytics.report_type   NOT NULL,
    period_start    date                    NOT NULL,
    media_id        uuid                    NOT NULL,
    created_at      timestamptz             NOT NULL DEFAULT now(),
    CONSTRAINT pk_report_exports PRIMARY KEY (id),
    CONSTRAINT fk_report_exports_user FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE CASCADE,
    CONSTRAINT fk_report_exports_media FOREIGN KEY (media_id) REFERENCES media.media_files (id) ON DELETE RESTRICT,
    CONSTRAINT uq_report_exports_period UNIQUE (user_id, report_type, period_start),
    CONSTRAINT ck_report_exports_period_start CHECK (
        (report_type = 'weekly_summary' AND extract(isodow FROM period_start) = 1)
        OR (report_type = 'monthly_summary' AND extract(day FROM period_start) = 1))
);
CREATE INDEX ix_report_exports_media_id ON analytics.report_exports (media_id);
COMMENT ON TABLE  analytics.report_exports IS 'Thẻ báo cáo (ảnh) đã xuất để lưu/chia sẻ mạng xã hội. Tuần bắt đầu thứ Hai, tháng bắt đầu ngày 1; period_end = period_start + kỳ (tính, không lưu).';
COMMENT ON COLUMN analytics.report_exports.id IS 'Khoá chính.';
COMMENT ON COLUMN analytics.report_exports.user_id IS 'FK → auth.users.';
COMMENT ON COLUMN analytics.report_exports.report_type IS 'weekly_summary/monthly_summary.';
COMMENT ON COLUMN analytics.report_exports.period_start IS 'Ngày bắt đầu kỳ báo cáo.';
COMMENT ON COLUMN analytics.report_exports.media_id IS 'Ảnh thẻ báo cáo (FK → media.media_files).';
COMMENT ON COLUMN analytics.report_exports.created_at IS 'Thời điểm xuất.';
