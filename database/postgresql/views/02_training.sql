-- =====================================================================
-- Smart Workout AI — Views: training
-- Volume, 1RM ước tính, thời lượng, calo tiêu hao, tải theo nhóm cơ, tempo,
-- trạng thái phục hồi (Heatmap) và mức tuân thủ lịch tập.
-- =====================================================================

-- ---------------------------------------------------------------------
-- training.v_set_metrics — chỉ số từng hiệp
--   volume_kg  = reps × weight_kg
--   est_1rm_kg = Epley: weight × (1 + reps/30), chỉ tính khi 1 ≤ reps ≤ 12
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW training.v_set_metrics AS
SELECT
    es.id                   AS set_id,
    es.session_exercise_id,
    se.session_id,
    s.user_id,
    se.exercise_id,
    es.set_no,
    es.set_type,
    es.reps,
    es.weight_kg,
    es.duration_seconds,
    es.rpe,
    es.source,
    es.completed_at,
    (es.reps * es.weight_kg)::numeric(10,2) AS volume_kg,
    CASE WHEN es.reps BETWEEN 1 AND 12 AND es.weight_kg > 0
         THEN round(es.weight_kg * (1 + es.reps / 30.0), 1)
    END                     AS est_1rm_kg
FROM training.exercise_sets es
JOIN training.session_exercises se ON se.id = es.session_exercise_id
JOIN training.workout_sessions s ON s.id = se.session_id
WHERE s.deleted_at IS NULL;

COMMENT ON VIEW training.v_set_metrics IS 'Từng hiệp kèm volume (reps × kg) và 1RM ước tính (Epley).';

-- ---------------------------------------------------------------------
-- training.v_session_summary — tổng hợp buổi tập (Workout_Log)
--   Calo ước tính = MET trung bình (theo số hiệp) × cân nặng gần nhất × số giờ
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW training.v_session_summary AS
SELECT
    s.id                AS session_id,
    s.user_id,
    s.scheduled_workout_id,
    s.name,
    s.status,
    s.started_at,
    s.ended_at,
    round((extract(epoch FROM (s.ended_at - s.started_at)) / 60.0)::numeric, 1) AS duration_minutes,
    agg.exercise_count,
    agg.completed_set_count,
    agg.total_reps,
    agg.total_volume_kg,
    agg.avg_met,
    bw.weight_kg        AS body_weight_kg,
    round((agg.avg_met * bw.weight_kg * extract(epoch FROM (s.ended_at - s.started_at)) / 3600.0)::numeric, 0) AS est_calories_kcal
FROM training.workout_sessions s
LEFT JOIN LATERAL (
    SELECT
        count(DISTINCT se.id)                                                       AS exercise_count,
        count(es.id) FILTER (WHERE es.completed_at IS NOT NULL)                     AS completed_set_count,
        coalesce(sum(es.reps) FILTER (WHERE es.completed_at IS NOT NULL), 0)        AS total_reps,
        coalesce(sum(es.reps * es.weight_kg)
                 FILTER (WHERE es.completed_at IS NOT NULL AND es.set_type <> 'warmup'), 0)::numeric(12,2) AS total_volume_kg,
        round(avg(coalesce(e.met_value, 5.0)) FILTER (WHERE es.completed_at IS NOT NULL), 2) AS avg_met
    FROM training.session_exercises se
    JOIN catalog.exercises e ON e.id = se.exercise_id
    LEFT JOIN training.exercise_sets es ON es.session_exercise_id = se.id
    WHERE se.session_id = s.id
) agg ON true
LEFT JOIN LATERAL (
    SELECT bm.weight_kg
    FROM body.body_measurements bm
    WHERE bm.user_id = s.user_id
    ORDER BY (bm.measured_at > s.started_at), abs(extract(epoch FROM (bm.measured_at - s.started_at)))
    LIMIT 1
) bw ON true
WHERE s.deleted_at IS NULL;

COMMENT ON VIEW training.v_session_summary IS 'Tổng hợp buổi tập: thời lượng, số bài, số hiệp hoàn thành, tổng rep, tổng volume (không tính khởi động), calo ước tính = MET × kg × giờ (cân nặng = lần đo gần nhất trước buổi tập).';

-- ---------------------------------------------------------------------
-- training.v_session_muscle_load — tải tập theo nhóm cơ (đầu vào model phục hồi)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW training.v_session_muscle_load AS
SELECT
    se.session_id,
    s.user_id,
    s.ended_at,
    em.muscle_group_id,
    count(es.id)                                                                AS direct_sets,
    round(sum(em.activation_ratio), 2)                                          AS effective_sets,
    coalesce(sum(es.reps), 0)                                                   AS total_reps,
    round(sum(coalesce(es.reps, 0) * coalesce(es.weight_kg, 0) * em.activation_ratio), 1) AS weighted_volume_kg,
    round(avg(es.rpe), 1)                                                       AS avg_rpe
FROM training.exercise_sets es
JOIN training.session_exercises se ON se.id = es.session_exercise_id
JOIN training.workout_sessions s ON s.id = se.session_id
JOIN catalog.exercise_muscles em ON em.exercise_id = se.exercise_id
WHERE es.completed_at IS NOT NULL
  AND es.set_type <> 'warmup'
  AND s.deleted_at IS NULL
GROUP BY se.session_id, s.user_id, s.ended_at, em.muscle_group_id;

COMMENT ON VIEW training.v_session_muscle_load IS 'Khối lượng tập phân bổ cho từng nhóm cơ trong mỗi buổi (volume × activation_ratio). Đây là đặc trưng đầu vào của model PyTorch dự đoán phục hồi.';

-- ---------------------------------------------------------------------
-- training.v_set_tempo — tempo trung bình & thời gian chịu tải (TUT) của hiệp AI
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW training.v_set_tempo AS
SELECT
    r.set_id,
    count(*)                                AS rep_count,
    round(avg(r.eccentric_ms))::integer     AS avg_eccentric_ms,
    round(avg(r.pause_bottom_ms))::integer  AS avg_pause_bottom_ms,
    round(avg(r.concentric_ms))::integer    AS avg_concentric_ms,
    round(avg(r.pause_top_ms))::integer     AS avg_pause_top_ms,
    sum(r.eccentric_ms + r.pause_bottom_ms + r.concentric_ms + r.pause_top_ms) AS time_under_tension_ms,
    round(100.0 * count(*) FILTER (WHERE r.is_full_rom) / count(*), 1) AS full_rom_pct
FROM training.set_rep_events r
GROUP BY r.set_id;

COMMENT ON VIEW training.v_set_tempo IS 'Tempo trung bình mỗi pha, tổng thời gian chịu tải (TUT) và tỷ lệ rep đủ biên độ của từng hiệp do AI ghi nhận.';

-- ---------------------------------------------------------------------
-- training.v_muscle_recovery_status — trạng thái phục hồi hiện tại (Heatmap)
--   recovery_pct = thời gian đã nghỉ / tổng thời gian cần nghỉ
--   recovery_status: fatigued (đỏ, < 50%), recovering (vàng, 50–99%), ready (xanh)
-- Chỉ gồm nhóm cơ có heatmap_region_key.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW training.v_muscle_recovery_status AS
WITH latest AS (
    SELECT DISTINCT ON (s.user_id, rp.muscle_group_id)
        s.user_id,
        rp.muscle_group_id,
        rp.session_id,
        coalesce(s.ended_at, s.started_at) AS trained_at,
        rp.fatigue_score,
        rp.recovered_at,
        rp.model_version
    FROM training.recovery_predictions rp
    JOIN training.workout_sessions s ON s.id = rp.session_id AND s.deleted_at IS NULL
    ORDER BY s.user_id, rp.muscle_group_id, coalesce(s.ended_at, s.started_at) DESC, rp.predicted_at DESC
),
calc AS (
    SELECT
        u.id                    AS user_id,
        mg.id                   AS muscle_group_id,
        mg.code                 AS muscle_code,
        mg.name                 AS muscle_name,
        mg.heatmap_region_key,
        l.session_id            AS last_session_id,
        l.trained_at            AS last_trained_at,
        l.fatigue_score,
        l.recovered_at,
        l.model_version,
        CASE
            WHEN l.recovered_at IS NULL OR now() >= l.recovered_at THEN 100
            ELSE greatest(0, round((100 * extract(epoch FROM (now() - l.trained_at))
                                   / nullif(extract(epoch FROM (l.recovered_at - l.trained_at)), 0))::numeric))
        END                     AS recovery_pct
    FROM auth.users u
    CROSS JOIN catalog.muscle_groups mg
    LEFT JOIN latest l ON l.user_id = u.id AND l.muscle_group_id = mg.id
    WHERE u.deleted_at IS NULL
      AND mg.heatmap_region_key IS NOT NULL
)
SELECT
    st.*,
    round((greatest(0, extract(epoch FROM (st.recovered_at - now())) / 3600.0))::numeric, 1) AS remaining_hours,
    CASE
        WHEN st.recovery_pct >= 100 THEN 'ready'
        WHEN st.recovery_pct >= 50  THEN 'recovering'
        ELSE 'fatigued'
    END AS recovery_status
FROM calc st;

COMMENT ON VIEW training.v_muscle_recovery_status IS 'Heatmap phục hồi: với mỗi user × nhóm cơ, lấy dự đoán mới nhất, tính % hồi phục và số giờ còn lại tại thời điểm truy vấn. recovery_status: fatigued (đỏ) / recovering (vàng) / ready (xanh). Luôn lọc theo user_id khi truy vấn.';

-- ---------------------------------------------------------------------
-- training.v_weekly_adherence — mức tuân thủ lịch tập theo tuần
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW training.v_weekly_adherence AS
SELECT
    sw.user_id,
    date_trunc('week', sw.scheduled_date)::date                                 AS week_start,
    count(*) FILTER (WHERE sw.status <> 'cancelled')                            AS planned_count,
    count(ws.id) FILTER (WHERE ws.status = 'completed')                         AS completed_count,
    count(*) FILTER (WHERE sw.status = 'skipped')                               AS skipped_count,
    round(100.0 * count(ws.id) FILTER (WHERE ws.status = 'completed')
          / nullif(count(*) FILTER (WHERE sw.status <> 'cancelled'), 0), 1)     AS adherence_pct
FROM training.scheduled_workouts sw
LEFT JOIN training.workout_sessions ws ON ws.scheduled_workout_id = sw.id AND ws.deleted_at IS NULL
GROUP BY sw.user_id, 2;

COMMENT ON VIEW training.v_weekly_adherence IS 'Tiến độ hoàn thành lịch tập theo tuần (thứ Hai đầu tuần): số buổi dự kiến, đã hoàn thành, bỏ qua và % tuân thủ.';
