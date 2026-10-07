-- =====================================================================
-- Smart Workout AI — Materialized views: analytics
-- Phi chuẩn hoá CÓ KIỂM SOÁT chỉ cho tầng đọc (Dashboard), nằm ngoài lõi 3NF.
-- Làm mới định kỳ bằng analytics.refresh_materialized_views() (scheduler của backend);
-- số liệu "hôm nay" nên lấy trực tiếp từ views hoặc cache Redis.
-- =====================================================================

CREATE MATERIALIZED VIEW analytics.mv_daily_user_summary AS
WITH tz AS (
    SELECT u.id AS user_id, coalesce(up.timezone, 'Asia/Ho_Chi_Minh') AS tz
    FROM auth.users u
    LEFT JOIN auth.user_profiles up ON up.user_id = u.id
    WHERE u.deleted_at IS NULL
),
training_daily AS (
    SELECT
        ss.user_id,
        (ss.started_at AT TIME ZONE tz.tz)::date    AS activity_date,
        count(*)                                    AS sessions_completed,
        sum(ss.completed_set_count)                 AS completed_sets,
        sum(ss.total_reps)                          AS total_reps,
        sum(ss.total_volume_kg)                     AS total_volume_kg,
        sum(ss.duration_minutes)                    AS active_minutes,
        sum(ss.est_calories_kcal)                   AS est_calories_burned_kcal
    FROM training.v_session_summary ss
    JOIN tz ON tz.user_id = ss.user_id
    WHERE ss.status = 'completed'
    GROUP BY ss.user_id, 2
),
body_daily AS (
    SELECT DISTINCT ON (m.user_id, (m.measured_at AT TIME ZONE tz.tz)::date)
        m.user_id,
        (m.measured_at AT TIME ZONE tz.tz)::date AS activity_date,
        m.weight_kg,
        m.body_fat_pct
    FROM body.body_measurements m
    JOIN tz ON tz.user_id = m.user_id
    ORDER BY m.user_id, (m.measured_at AT TIME ZONE tz.tz)::date, m.measured_at DESC
),
form_daily AS (
    SELECT
        f.user_id,
        f.analysis_date                 AS activity_date,
        round(avg(f.avg_correct_form_pct), 1) AS avg_correct_form_pct
    FROM ai.v_form_score_trend f
    GROUP BY f.user_id, f.analysis_date
),
keys AS (
    SELECT user_id, activity_date FROM training_daily
    UNION
    SELECT user_id, activity_date FROM body_daily
    UNION
    SELECT user_id, activity_date FROM form_daily
)
SELECT
    k.user_id,
    k.activity_date,
    coalesce(t.sessions_completed, 0)       AS sessions_completed,
    coalesce(t.completed_sets, 0)           AS completed_sets,
    coalesce(t.total_reps, 0)               AS total_reps,
    coalesce(t.total_volume_kg, 0)          AS total_volume_kg,
    coalesce(t.active_minutes, 0)           AS active_minutes,
    t.est_calories_burned_kcal,
    b.weight_kg,
    b.body_fat_pct,
    f.avg_correct_form_pct
FROM keys k
LEFT JOIN training_daily t ON t.user_id = k.user_id AND t.activity_date = k.activity_date
LEFT JOIN body_daily b ON b.user_id = k.user_id AND b.activity_date = k.activity_date
LEFT JOIN form_daily f ON f.user_id = k.user_id AND f.activity_date = k.activity_date
WITH DATA;

CREATE UNIQUE INDEX uq_mv_daily_user_summary ON analytics.mv_daily_user_summary (user_id, activity_date);

COMMENT ON MATERIALIZED VIEW analytics.mv_daily_user_summary IS 'Tổng hợp theo ngày (múi giờ user): số buổi, hiệp, rep, volume, phút tập, calo tiêu hao ước tính, cân nặng cuối ngày, % đúng form. Nguồn cho biểu đồ Tháng/3 Tháng.';

-- ---------------------------------------------------------------------
-- Làm mới mọi materialized view của schema analytics.
-- SECURITY DEFINER để role ứng dụng (không sở hữu MV) vẫn gọi được.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION analytics.refresh_materialized_views(p_concurrently boolean DEFAULT true)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    r record;
BEGIN
    FOR r IN
        SELECT schemaname, matviewname
        FROM pg_matviews
        WHERE schemaname = 'analytics'
        ORDER BY matviewname
    LOOP
        IF p_concurrently THEN
            EXECUTE format('REFRESH MATERIALIZED VIEW CONCURRENTLY %I.%I', r.schemaname, r.matviewname);
        ELSE
            EXECUTE format('REFRESH MATERIALIZED VIEW %I.%I', r.schemaname, r.matviewname);
        END IF;
    END LOOP;
END
$$;

COMMENT ON FUNCTION analytics.refresh_materialized_views(boolean) IS 'Làm mới toàn bộ materialized view trong schema analytics (mặc định CONCURRENTLY, không khoá đọc).';

-- Hàm SECURITY DEFINER: chỉ role ứng dụng được gọi
REVOKE ALL ON FUNCTION analytics.refresh_materialized_views(boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION analytics.refresh_materialized_views(boolean) TO sw_app_rw;
