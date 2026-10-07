-- =====================================================================
-- Smart Workout AI — Kiểm tra dữ liệu seed (chạy tay, KHÔNG nằm trong init)
--   psql -U smart_workout -d smart_workout_db -f tools/verify_seed.sql
-- Mỗi dòng: PASS / FAIL / SKIP (SKIP = dữ liệu test không được nạp, SW_SEED_TEST=false)
-- Kết quả mong đợi: không có dòng FAIL.
-- =====================================================================
\pset pager off

WITH
flag AS (
    SELECT EXISTS (SELECT 1 FROM auth.users WHERE email = 'demo@smartworkout.local') AS test_on
),
u AS (
    SELECT split_part(email, '@', 1) AS k, id FROM auth.users WHERE email LIKE '%@smartworkout.local'
),
pub AS (
    SELECT e.id, e.slug FROM catalog.exercises e WHERE e.status = 'published' AND e.deleted_at IS NULL
),
checks (grp, name, ok, detail) AS (
    -- ================= MASTER DATA (luôn kiểm tra) =================
    SELECT 'master', 'Có ≥ 70 bài tập đã xuất bản',
           (SELECT count(*) FROM pub) >= 70,
           (SELECT count(*) FROM pub)::text || ' bài'
    UNION ALL
    SELECT 'master', 'Mọi bài published có ≥ 1 nhóm cơ primary',
           NOT EXISTS (SELECT 1 FROM pub WHERE NOT EXISTS (SELECT 1 FROM catalog.exercise_muscles m WHERE m.exercise_id = pub.id AND m.role = 'primary')),
           NULL
    UNION ALL
    SELECT 'master', 'Mọi bài published có ≥ 3 bước hướng dẫn',
           NOT EXISTS (SELECT 1 FROM pub WHERE (SELECT count(*) FROM catalog.exercise_instructions i WHERE i.exercise_id = pub.id) < 3),
           NULL
    UNION ALL
    SELECT 'master', 'Mọi bài published có ≥ 1 lỗi sai thường gặp',
           NOT EXISTS (SELECT 1 FROM pub WHERE NOT EXISTS (SELECT 1 FROM catalog.exercise_mistakes m WHERE m.exercise_id = pub.id)),
           (SELECT 'thiếu: ' || string_agg(pub.slug, ', ') FROM pub
            WHERE NOT EXISTS (SELECT 1 FROM catalog.exercise_mistakes m WHERE m.exercise_id = pub.id))
    UNION ALL
    SELECT 'master', 'Mọi thiết bị đang dùng có nhãn AI',
           NOT EXISTS (SELECT 1 FROM catalog.equipment eq WHERE eq.deleted_at IS NULL
                       AND NOT EXISTS (SELECT 1 FROM catalog.equipment_aliases a WHERE a.equipment_id = eq.id AND a.alias_type = 'ai_label')),
           (SELECT count(*) FROM catalog.equipment WHERE deleted_at IS NULL)::text || ' thiết bị'
    UNION ALL
    SELECT 'master', 'Đúng 6 giáo án mẫu active',
           (SELECT count(*) FROM training.workout_plans WHERE owner_user_id IS NULL AND status = 'active' AND deleted_at IS NULL) = 6,
           NULL
    UNION ALL
    SELECT 'master', 'Mọi buổi của giáo án mẫu có bài tập',
           NOT EXISTS (SELECT 1 FROM training.workout_plan_days d JOIN training.workout_plans p ON p.id = d.plan_id
                       WHERE p.owner_user_id IS NULL
                         AND NOT EXISTS (SELECT 1 FROM training.workout_plan_exercises pe WHERE pe.plan_day_id = d.id)),
           NULL
    UNION ALL
    SELECT 'master', 'Giáo án "Bodyweight tại nhà" không cần thiết bị bắt buộc',
           NOT EXISTS (SELECT 1 FROM training.workout_plan_days d
                       JOIN training.workout_plan_exercises pe ON pe.plan_day_id = d.id
                       JOIN catalog.exercise_equipment ee ON ee.exercise_id = pe.exercise_id AND NOT ee.is_optional
                       WHERE d.plan_id = '5eed1000-0000-4000-8000-000000000006'),
           NULL
    UNION ALL
    SELECT 'master', 'Giáo án mẫu chỉ dùng bài published',
           NOT EXISTS (SELECT 1 FROM training.workout_plan_exercises pe
                       JOIN training.workout_plan_days d ON d.id = pe.plan_day_id
                       JOIN training.workout_plans p ON p.id = d.plan_id AND p.owner_user_id IS NULL AND p.status = 'active'
                       WHERE pe.exercise_id NOT IN (SELECT id FROM pub)),
           NULL
    UNION ALL
    SELECT 'master', 'Không có dữ liệu AI (bảng ai.*, recovery_predictions, set_rep_events)',
           (SELECT count(*) FROM ai.pose_analyses) + (SELECT count(*) FROM ai.video_analysis_jobs) + (SELECT count(*) FROM ai.posture_issues)
         + (SELECT count(*) FROM ai.bar_path_points) + (SELECT count(*) FROM ai.equipment_scans) + (SELECT count(*) FROM ai.equipment_scan_predictions)
         + (SELECT count(*) FROM training.recovery_predictions) + (SELECT count(*) FROM training.set_rep_events) = 0,
           NULL
    UNION ALL
    SELECT 'master', 'Khi tắt dữ liệu test: không có user/media nào',
           (SELECT test_on FROM flag) OR ((SELECT count(*) FROM auth.users) = 0 AND (SELECT count(*) FROM media.media_files) = 0),
           CASE WHEN (SELECT test_on FROM flag) THEN 'dữ liệu test đang bật' END

    -- ================= TEST DATA =================
    UNION ALL
    SELECT 'test', '16 persona với đúng trạng thái',
           (SELECT count(*) FROM (VALUES
                ('admin', 'active', false), ('editor', 'active', false), ('demo', 'active', false), ('power', 'active', false),
                ('dung', 'active', false), ('plateau', 'active', false), ('inprogress', 'active', false), ('newbie', 'active', false),
                ('unspecified', 'active', false), ('other', 'active', false), ('pending', 'pending_verification', false),
                ('locked', 'locked', false), ('disabled', 'disabled', false), ('deleted', 'active', true),
                ('oauth', 'active', false), ('trainer', 'active', false)) AS x(k, st, del)
            JOIN auth.users au ON au.email = x.k || '@smartworkout.local'
                              AND au.status::text = x.st AND (au.deleted_at IS NOT NULL) = x.del) = 16,
           NULL
    UNION ALL
    SELECT 'test', 'UUID persona cố định 5eed0000-…-0000000000NN',
           (SELECT count(*) FROM auth.users WHERE id::text LIKE '5eed0000-0000-4000-8000-0000000000__') = 16, NULL
    UNION ALL
    SELECT 'test', 'Mọi bài published có thumbnail & GIF chính',
           NOT EXISTS (SELECT 1 FROM pub WHERE (SELECT count(*) FROM catalog.exercise_media em
                                                WHERE em.exercise_id = pub.id AND em.is_primary AND em.media_role IN ('thumbnail', 'gif')) < 2),
           NULL
    UNION ALL
    SELECT 'test', 'Có bài draft, archived, đã xoá mềm và thiết bị đã xoá mềm',
           EXISTS (SELECT 1 FROM catalog.exercises WHERE status = 'draft')
           AND EXISTS (SELECT 1 FROM catalog.exercises WHERE status = 'archived')
           AND EXISTS (SELECT 1 FROM catalog.exercises WHERE deleted_at IS NOT NULL)
           AND EXISTS (SELECT 1 FROM catalog.equipment WHERE deleted_at IS NOT NULL),
           NULL
    UNION ALL
    SELECT 'test', 'Nhãn AI của thiết bị đã xoá không trả về bài tập',
           NOT EXISTS (SELECT 1 FROM catalog.fn_exercises_for_ai_label('test_retired_machine')), NULL
    UNION ALL
    SELECT 'test', 'Mọi hiệp tập có source = manual',
           NOT EXISTS (SELECT 1 FROM training.exercise_sets WHERE source <> 'manual'), NULL
    UNION ALL
    SELECT 'test', 'power@: ≥ 80 buổi completed, ≥ 24 lần cân, ≥ 25 báo cáo tuần',
           (SELECT count(*) FROM training.workout_sessions s WHERE s.user_id = (SELECT id FROM u WHERE k = 'power') AND s.status = 'completed') >= 80
           AND (SELECT count(*) FROM body.body_measurements m WHERE m.user_id = (SELECT id FROM u WHERE k = 'power')) >= 24
           AND (SELECT count(*) FROM analytics.report_exports r WHERE r.user_id = (SELECT id FROM u WHERE k = 'power') AND r.report_type = 'weekly_summary') >= 25,
           (SELECT count(*) FROM training.workout_sessions s WHERE s.user_id = (SELECT id FROM u WHERE k = 'power') AND s.status = 'completed')::text || ' buổi'
    UNION ALL
    SELECT 'test', 'power@: có dữ liệu trong mv_daily_user_summary',
           (SELECT count(*) FROM analytics.mv_daily_user_summary WHERE user_id = (SELECT id FROM u WHERE k = 'power')) >= 80, NULL
    UNION ALL
    SELECT 'test', 'demo@: giáo án clone từ mẫu PPL',
           EXISTS (SELECT 1 FROM training.workout_plans WHERE owner_user_id = (SELECT id FROM u WHERE k = 'demo')
                   AND source_plan_id = '5eed1000-0000-4000-8000-000000000002'), NULL
    UNION ALL
    SELECT 'test', 'demo@: có lịch tương lai đã xác nhận cảnh báo phục hồi',
           EXISTS (SELECT 1 FROM training.scheduled_workouts WHERE user_id = (SELECT id FROM u WHERE k = 'demo')
                   AND scheduled_date > current_date AND recovery_warning_ack_at IS NOT NULL), NULL
    UNION ALL
    SELECT 'test', 'dung@: xếp lịch trực tiếp từ giáo án mẫu',
           EXISTS (SELECT 1 FROM training.scheduled_workouts sw
                   JOIN training.workout_plan_days d ON d.id = sw.plan_day_id
                   JOIN training.workout_plans p ON p.id = d.plan_id AND p.owner_user_id IS NULL
                   WHERE sw.user_id = (SELECT id FROM u WHERE k = 'dung')), NULL
    UNION ALL
    SELECT 'test', 'dung@: BMR nữ = 10·kg + 6.25·cm − 5·tuổi − 161',
           (SELECT v.bmr_kcal = round(10 * v.weight_kg + 6.25 * v.height_cm - 5 * v.age_years - 161)
            FROM body.v_latest_body_metrics v WHERE v.user_id = (SELECT id FROM u WHERE k = 'dung')),
           (SELECT v.bmr_kcal::text FROM body.v_latest_body_metrics v WHERE v.user_id = (SELECT id FROM u WHERE k = 'dung'))
    UNION ALL
    SELECT 'test', 'other@: BMR dùng hằng số −78',
           (SELECT v.bmr_kcal = round(10 * v.weight_kg + 6.25 * v.height_cm - 5 * v.age_years - 78)
            FROM body.v_latest_body_metrics v WHERE v.user_id = (SELECT id FROM u WHERE k = 'other')), NULL
    UNION ALL
    SELECT 'test', 'unspecified@: BMI, BMR, TDEE = NULL',
           (SELECT v.bmi IS NULL AND v.bmr_kcal IS NULL AND v.tdee_kcal IS NULL
            FROM body.v_latest_body_metrics v WHERE v.user_id = (SELECT id FROM u WHERE k = 'unspecified')), NULL
    UNION ALL
    SELECT 'test', 'plateau@: tuần gần nhất is_plateau = true',
           (SELECT t.is_plateau FROM body.v_weekly_weight_trend t
            WHERE t.user_id = (SELECT id FROM u WHERE k = 'plateau') ORDER BY t.week_start DESC LIMIT 1), NULL
    UNION ALL
    SELECT 'test', 'plateau@: có 1 goal abandoned và 1 goal active',
           (SELECT count(*) FILTER (WHERE status = 'abandoned') = 1 AND count(*) FILTER (WHERE status = 'active') = 1
            FROM body.user_goals WHERE user_id = (SELECT id FROM u WHERE k = 'plateau')), NULL
    UNION ALL
    SELECT 'test', 'inprogress@: đúng 1 buổi in_progress, có buổi abandoned & buổi xoá mềm',
           (SELECT count(*) FILTER (WHERE status = 'in_progress' AND deleted_at IS NULL) = 1
               AND count(*) FILTER (WHERE status = 'abandoned') >= 1
               AND count(*) FILTER (WHERE deleted_at IS NOT NULL) >= 1
            FROM training.workout_sessions WHERE user_id = (SELECT id FROM u WHERE k = 'inprogress')), NULL
    UNION ALL
    SELECT 'test', 'inprogress@: có hiệp chưa làm, drop, failure, theo thời gian & quãng đường',
           (SELECT bool_or(es.completed_at IS NULL) AND bool_or(es.set_type = 'drop') AND bool_or(es.set_type = 'failure')
                   AND bool_or(es.duration_seconds IS NOT NULL) AND bool_or(es.distance_m IS NOT NULL)
            FROM training.exercise_sets es
            JOIN training.session_exercises se ON se.id = es.session_exercise_id
            JOIN training.workout_sessions s ON s.id = se.session_id
            WHERE s.user_id = (SELECT id FROM u WHERE k = 'inprogress')), NULL
    UNION ALL
    SELECT 'test', 'newbie@: không có hồ sơ thể chất, số đo, buổi tập',
           NOT EXISTS (SELECT 1 FROM body.user_body_profiles WHERE user_id = (SELECT id FROM u WHERE k = 'newbie'))
           AND NOT EXISTS (SELECT 1 FROM body.body_measurements WHERE user_id = (SELECT id FROM u WHERE k = 'newbie'))
           AND NOT EXISTS (SELECT 1 FROM training.workout_sessions WHERE user_id = (SELECT id FROM u WHERE k = 'newbie')), NULL
    UNION ALL
    SELECT 'test', 'oauth@: không có mật khẩu, liên kết Google + Apple',
           (SELECT password_hash IS NULL FROM auth.users WHERE email = 'oauth@smartworkout.local')
           AND (SELECT count(*) FROM auth.oauth_accounts WHERE user_id = (SELECT id FROM u WHERE k = 'oauth')) = 2, NULL
    UNION ALL
    SELECT 'test', 'trainer@: vai trò content_editor đã hết hạn',
           EXISTS (SELECT 1 FROM auth.user_roles ur JOIN auth.roles r ON r.id = ur.role_id
                   WHERE ur.user_id = (SELECT id FROM u WHERE k = 'trainer') AND r.code = 'content_editor' AND ur.expires_at < now()), NULL
    UNION ALL
    SELECT 'test', 'trainer@: token reset mật khẩu còn hạn / hết hạn / đã dùng',
           (SELECT count(*) FILTER (WHERE consumed_at IS NULL AND expires_at > now()) = 1
               AND count(*) FILTER (WHERE consumed_at IS NULL AND expires_at <= now()) = 1
               AND count(*) FILTER (WHERE consumed_at IS NOT NULL) = 1
            FROM auth.verification_tokens WHERE user_id = (SELECT id FROM u WHERE k = 'trainer') AND purpose = 'password_reset'), NULL
    UNION ALL
    SELECT 'test', 'pending@: chưa xác thực email, có token xác thực còn hạn',
           (SELECT email_verified_at IS NULL FROM auth.users WHERE email = 'pending@smartworkout.local')
           AND EXISTS (SELECT 1 FROM auth.verification_tokens WHERE user_id = (SELECT id FROM u WHERE k = 'pending')
                       AND purpose = 'email_verification' AND consumed_at IS NULL AND expires_at > now()), NULL
    UNION ALL
    SELECT 'test', 'locked@: locked_until ở tương lai, ≥ 5 lần sai trong 30 phút, family reuse_detected',
           (SELECT locked_until > now() FROM auth.users WHERE email = 'locked@smartworkout.local')
           AND (SELECT count(*) FROM auth.login_attempts WHERE user_id = (SELECT id FROM u WHERE k = 'locked')
                AND NOT succeeded AND attempted_at > now() - interval '30 minutes') >= 5
           AND EXISTS (SELECT 1 FROM auth.refresh_tokens WHERE revoke_reason = 'reuse_detected'), NULL
    UNION ALL
    SELECT 'test', 'demo@: chuỗi refresh token xoay vòng (token con trỏ về token cha)',
           EXISTS (SELECT 1 FROM auth.refresh_tokens c JOIN auth.refresh_tokens p ON p.id = c.parent_token_id
                   JOIN auth.user_devices d ON d.id = c.device_id
                   WHERE d.user_id = (SELECT id FROM u WHERE k = 'demo') AND c.revoked_at IS NULL
                     AND p.revoke_reason = 'rotated' AND p.family_id = c.family_id), NULL
    UNION ALL
    SELECT 'test', 'Ảnh tiến độ phủ đủ queued / processing / completed / failed',
           (SELECT count(DISTINCT processing_status) FROM media.progress_photos) = 4, NULL
    UNION ALL
    SELECT 'test', 'Có upload treo > 24h (cần dọn) và upload mới (không dọn)',
           EXISTS (SELECT 1 FROM media.media_files WHERE status = 'pending_upload' AND created_at < now() - interval '24 hours')
           AND EXISTS (SELECT 1 FROM media.media_files WHERE status = 'pending_upload' AND created_at > now() - interval '1 hour'), NULL
    UNION ALL
    SELECT 'test', 'Có lần đăng nhập từ email không tồn tại (user_id NULL)',
           (SELECT count(*) FROM auth.login_attempts WHERE user_id IS NULL) >= 8, NULL
)
SELECT c.grp,
       CASE WHEN c.grp = 'test' AND NOT f.test_on THEN 'SKIP'
            WHEN c.ok THEN 'PASS'
            ELSE 'FAIL' END AS result,
       c.name,
       c.detail
FROM checks c CROSS JOIN flag f
ORDER BY c.grp, c.name;
