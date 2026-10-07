-- =====================================================================
-- Smart Workout AI — Views: ai
-- =====================================================================

-- ---------------------------------------------------------------------
-- ai.v_pose_analysis_details — kết quả phân tích tư thế kèm ngữ cảnh buổi tập
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW ai.v_pose_analysis_details AS
SELECT
    pa.id                   AS pose_analysis_id,
    pa.mode,
    pa.model_name,
    pa.model_version,
    pa.overall_score,
    pa.correct_form_pct,
    pa.detected_rep_count,
    pa.analyzed_at,
    es.id                   AS set_id,
    es.set_no,
    es.reps                 AS confirmed_reps,
    es.weight_kg,
    se.exercise_id,
    e.name                  AS exercise_name,
    s.id                    AS session_id,
    s.user_id,
    j.status                AS video_job_status,
    j.result_video_media_id,
    (SELECT count(*) FROM ai.posture_issues pi WHERE pi.pose_analysis_id = pa.id)                           AS issue_count,
    (SELECT count(*) FROM ai.posture_issues pi WHERE pi.pose_analysis_id = pa.id AND pi.severity = 'critical') AS critical_issue_count
FROM ai.pose_analyses pa
JOIN training.exercise_sets es ON es.id = pa.set_id
JOIN training.session_exercises se ON se.id = es.session_exercise_id
JOIN training.workout_sessions s ON s.id = se.session_id
JOIN catalog.exercises e ON e.id = se.exercise_id
LEFT JOIN ai.video_analysis_jobs j ON j.pose_analysis_id = pa.id
WHERE s.deleted_at IS NULL;

COMMENT ON VIEW ai.v_pose_analysis_details IS 'Phân tích tư thế kèm hiệp/bài/buổi tập/user, trạng thái job video và số lỗi phát hiện.';

-- ---------------------------------------------------------------------
-- ai.v_form_score_trend — xu hướng điểm kỹ thuật theo ngày & bài tập (Dashboard)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW ai.v_form_score_trend AS
SELECT
    d.user_id,
    d.exercise_id,
    d.exercise_name,
    (d.analyzed_at AT TIME ZONE coalesce(up.timezone, 'Asia/Ho_Chi_Minh'))::date AS analysis_date,
    count(*)                            AS analysis_count,
    round(avg(d.overall_score), 1)      AS avg_score,
    round(avg(d.correct_form_pct), 1)   AS avg_correct_form_pct,
    sum(d.issue_count)                  AS total_issues
FROM ai.v_pose_analysis_details d
LEFT JOIN auth.user_profiles up ON up.user_id = d.user_id
WHERE d.analyzed_at IS NOT NULL
GROUP BY d.user_id, d.exercise_id, d.exercise_name, 4;

COMMENT ON VIEW ai.v_form_score_trend IS 'Điểm kỹ thuật và % đúng form trung bình theo ngày cho từng bài tập của user.';

-- ---------------------------------------------------------------------
-- ai.v_equipment_scan_results — kết quả nhận diện thiết bị (top-1 suy ra từ confidence)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW ai.v_equipment_scan_results AS
SELECT
    s.id                    AS scan_id,
    s.user_id,
    s.scanned_at,
    s.model_name,
    s.model_version,
    s.latency_ms,
    top1.equipment_id       AS predicted_equipment_id,
    eq.code                 AS predicted_equipment_code,
    eq.name                 AS predicted_equipment_name,
    top1.confidence,
    (top1.confidence >= 0.60) AS is_confident,
    s.feedback,
    s.corrected_equipment_id,
    coalesce(s.corrected_equipment_id, top1.equipment_id) AS resolved_equipment_id
FROM ai.equipment_scans s
LEFT JOIN LATERAL (
    SELECT p.equipment_id, p.confidence
    FROM ai.equipment_scan_predictions p
    WHERE p.scan_id = s.id
    ORDER BY p.confidence DESC, p.equipment_id
    LIMIT 1
) top1 ON true
LEFT JOIN catalog.equipment eq ON eq.id = top1.equipment_id;

COMMENT ON VIEW ai.v_equipment_scan_results IS 'Mỗi lần quét kèm thiết bị có confidence cao nhất, cờ đủ tin cậy (≥ 0.6) và thiết bị cuối cùng (ưu tiên nhãn user sửa).';
