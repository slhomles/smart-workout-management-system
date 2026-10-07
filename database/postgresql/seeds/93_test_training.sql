-- =====================================================================
-- Smart Workout AI — TEST DATA (4/7): giáo án, lịch tập, buổi tập của persona viết tay
-- Không có dữ liệu AI: mọi hiệp source = 'manual', không có set_rep_events / recovery_predictions.
-- Lịch sử 6 tháng của power@ nằm ở 94_test_power_user.sql.
-- =====================================================================

DO $$
DECLARE
    v_week0     date := date_trunc('week', current_date)::date;   -- thứ Hai tuần hiện tại
    v_plan      uuid;
    v_sched     uuid;
    v_d         date;
    v_w         integer;
    v_off       integer;
    v_day       integer;
    v_weights   jsonb;
BEGIN
    -- =================================================================
    -- demo@ (03): giáo án clone từ mẫu PPL, 3 buổi/tuần (T2 Push, T4 Pull, T6 Legs)
    -- =================================================================
    v_plan := test_seed.clone_plan(test_seed.template(2), test_seed.uid(3), 'PPL của An', 'active', now() - interval '42 days');
    v_weights := '{"barbell-bench-press": 55, "incline-dumbbell-press": 20, "overhead-press": 32.5, "cable-chest-fly": 12.5,
                   "dumbbell-lateral-raise": 7, "cable-triceps-pushdown": 20, "barbell-row": 45, "seated-cable-row": 45,
                   "face-pull": 15, "barbell-curl": 22.5, "hammer-curl": 10, "barbell-back-squat": 70,
                   "romanian-deadlift": 60, "leg-press": 120, "lying-leg-curl": 35}';

    FOR v_w IN REVERSE 4..-1 LOOP                       -- 4 tuần trước → tuần sau
        FOREACH v_off IN ARRAY ARRAY[0, 2, 4] LOOP
            v_d   := v_week0 - 7 * v_w + v_off;
            v_day := v_off / 2 + 1;                      -- 0→Push, 2→Pull, 4→Legs
            IF v_d >= current_date THEN
                PERFORM test_seed.schedule(test_seed.uid(3), v_plan, v_day, v_d);
            ELSIF v_w = 3 AND v_off = 4 THEN
                PERFORM test_seed.schedule(test_seed.uid(3), v_plan, v_day, v_d, 'skipped', NULL, 'Bận việc đột xuất');
            ELSIF v_w = 2 AND v_off = 2 THEN
                PERFORM test_seed.schedule(test_seed.uid(3), v_plan, v_day, v_d, 'cancelled', NULL, 'Đổi lịch');
            ELSE
                v_sched := test_seed.schedule(test_seed.uid(3), v_plan, v_day, v_d);
                PERFORM test_seed.log_plan_session(test_seed.uid(3), v_sched,
                            test_seed.at_local(v_d, '18:30'), 60 + v_day * 5, v_weights,
                            1 + 0.025 * (4 - v_w), 7.5, 1);
            END IF;
        END LOOP;
    END LOOP;

    -- Tập bù Push ngày mai: user đã xác nhận cảnh báo nhóm cơ chưa hồi phục
    v_sched := test_seed.schedule(test_seed.uid(3), v_plan, 1, current_date + 1, 'planned', 'Tập bù Push', NULL);
    UPDATE training.scheduled_workouts SET recovery_warning_ack_at = now() WHERE id = v_sched;

    -- Buổi tập ngoài lịch: bài thêm từ Wiki và từ quét thiết bị
    PERFORM test_seed.log_session(test_seed.uid(3), 'Tập thêm tay & vai', test_seed.at_local(current_date - 1, '07:00'), 40,
        '[{"slug": "cable-lateral-raise", "via": "wiki",           "sets": [[15, 5, 8], [12, 5, 8.5], [12, 5, 9]]},
          {"slug": "cable-chest-fly",     "via": "equipment_scan", "sets": [[15, 10, 8], [13, 10, 8.5]]},
          {"slug": "hammer-curl",         "via": "manual",         "sets": [[12, 10, 8], [10, 10, 9, "failure"]]}]');

    -- =================================================================
    -- dung@ (05): xếp lịch TRỰC TIẾP từ giáo án mẫu Full Body (không clone)
    -- T3 = buổi A, T7 = buổi B; múi giờ Asia/Tokyo
    -- =================================================================
    v_weights := '{"goblet-squat": 12, "dumbbell-bench-press": 10, "lat-pulldown": 30, "dumbbell-shoulder-press": 6,
                   "leg-press": 60, "seated-cable-row": 30}';
    FOR v_w IN REVERSE 4..-1 LOOP
        FOREACH v_off IN ARRAY ARRAY[1, 5] LOOP
            v_d   := v_week0 - 7 * v_w + v_off;
            v_day := CASE v_off WHEN 1 THEN 1 ELSE 2 END;
            IF v_d >= current_date THEN
                PERFORM test_seed.schedule(test_seed.uid(5), test_seed.template(1), v_day, v_d);
            ELSIF v_w = 2 AND v_off = 5 THEN
                PERFORM test_seed.schedule(test_seed.uid(5), test_seed.template(1), v_day, v_d, 'skipped', NULL, 'Đi công tác');
            ELSE
                v_sched := test_seed.schedule(test_seed.uid(5), test_seed.template(1), v_day, v_d);
                PERFORM test_seed.log_plan_session(test_seed.uid(5), v_sched,
                            test_seed.at_local(v_d, '07:00', 'Asia/Tokyo'), 50, v_weights,
                            1 + 0.04 * (4 - v_w), 7.0, 1);
            END IF;
        END LOOP;
    END LOOP;

    -- =================================================================
    -- plateau@ (06): giáo án tự tạo (không clone) + giáo án cũ archived + nháp đã xoá
    -- =================================================================
    INSERT INTO training.workout_plans (owner_user_id, name, description, goal_type_id, difficulty_level_id, duration_weeks, status, created_at)
    SELECT test_seed.uid(6), 'Giáo án tự tạo của Hải', 'Tự soạn: 2 buổi/tuần + đi bộ dốc.', g.id, d.id, NULL, 'active', now() - interval '70 days'
    FROM body.fitness_goal_types g, catalog.difficulty_levels d WHERE g.code = 'lose_fat' AND d.code = 'beginner'
    RETURNING id INTO v_plan;
    INSERT INTO training.workout_plan_days (plan_id, day_no, name) VALUES (v_plan, 1, 'Thân trên'), (v_plan, 2, 'Thân dưới + cardio');
    INSERT INTO training.workout_plan_exercises (plan_day_id, exercise_id, order_no, target_sets, target_reps_min, target_reps_max,
                                                 target_duration_seconds, rest_seconds)
    SELECT d.id, test_seed.ex(v.slug), v.ord, v.sets, v.rmin, v.rmax, v.dur, 90
    FROM (VALUES
        (1, 1, 'machine-chest-press',     3, 10, 12, NULL::smallint),
        (1, 2, 'lat-pulldown',            3, 10, 12, NULL),
        (1, 3, 'dumbbell-shoulder-press', 3, 10, 12, NULL),
        (2, 1, 'leg-press',               3, 12, 15, NULL),
        (2, 2, 'lying-leg-curl',          3, 12, 12, NULL),
        (2, 3, 'incline-treadmill-walk',  1, NULL, NULL, 1200)
    ) AS v(day_no, ord, slug, sets, rmin, rmax, dur)
    JOIN training.workout_plan_days d ON d.plan_id = v_plan AND d.day_no = v.day_no;

    v_weights := '{"machine-chest-press": 40, "lat-pulldown": 40, "dumbbell-shoulder-press": 10, "leg-press": 100, "lying-leg-curl": 30}';
    FOR v_w IN REVERSE 4..1 LOOP
        v_d := v_week0 - 7 * v_w + 2;
        v_sched := test_seed.schedule(test_seed.uid(6), v_plan, (v_w % 2) + 1, v_d);
        PERFORM test_seed.log_plan_session(test_seed.uid(6), v_sched, test_seed.at_local(v_d, '19:00'), 55, v_weights, 1.0, 7.0, 2);
    END LOOP;
    PERFORM test_seed.schedule(test_seed.uid(6), v_plan, 1, current_date + 2);

    -- Buổi tập tự do (không gắn lịch): chạy bộ có quãng đường
    PERFORM test_seed.log_session(test_seed.uid(6), 'Tập tự do', test_seed.at_local(current_date - 3, '06:00'), 35,
        '[{"slug": "treadmill-run", "sets": [[null, null, null, "working", 1800, 4500]]}]');

    PERFORM test_seed.clone_plan(test_seed.template(1), test_seed.uid(6), 'Full Body (cũ)', 'archived', now() - interval '150 days');
    v_plan := test_seed.clone_plan(test_seed.template(6), test_seed.uid(6), 'Nháp – bỏ', 'draft', now() - interval '20 days');
    UPDATE training.workout_plans SET deleted_at = now() - interval '19 days' WHERE id = v_plan;

    -- =================================================================
    -- inprogress@ (07): buổi đang tập, buổi bỏ dở, buổi đã xoá mềm,
    -- hiệp drop/failure, hiệp theo thời gian & quãng đường
    -- =================================================================
    v_plan := test_seed.clone_plan(test_seed.template(5), test_seed.uid(7), 'Circuit của Khoa', 'active', now() - interval '30 days');

    v_sched := test_seed.schedule(test_seed.uid(7), v_plan, 1, current_date - 3);
    PERFORM test_seed.log_session(test_seed.uid(7), 'Circuit A', test_seed.at_local(current_date - 3, '17:30'), 55,
        '[{"slug": "goblet-squat",           "sets": [[15, 20, 7], [15, 20, 7.5], [12, 20, 8.5, "failure"]]},
          {"slug": "push-up",                "sets": [[15, null, 7], [12, null, 8], [10, null, 9, "failure"]]},
          {"slug": "kettlebell-swing",       "sets": [[15, 16, 7], [15, 16, 7.5], [15, 16, 8]]},
          {"slug": "mountain-climber",       "sets": [[null, null, null, "working", 40], [null, null, null, "working", 40], [null, null, null, "working", 35]]},
          {"slug": "incline-treadmill-walk", "sets": [[null, null, null, "working", 1200, 1600]]},
          {"slug": "dumbbell-lateral-raise", "via": "manual", "sets": [[12, 8, 8], [10, 6, 9, "drop"], [8, 4, 9.5, "drop"]]}]',
        v_sched, 'completed', 8.5);

    -- Bỏ dở hôm qua
    v_sched := test_seed.schedule(test_seed.uid(7), v_plan, 2, current_date - 1);
    PERFORM test_seed.log_session(test_seed.uid(7), 'Cardio dài & core', test_seed.at_local(current_date - 1, '18:00'), 15,
        '[{"slug": "stationary-bike", "sets": [[null, null, null, "working", 600, 4000]]}]',
        v_sched, 'abandoned', NULL, NULL, 'Đau đầu, dừng sớm');

    -- Nhập nhầm rồi xoá mềm
    PERFORM test_seed.log_session(test_seed.uid(7), 'Buổi nhập nhầm', test_seed.at_local(current_date - 5, '12:00'), 10,
        '[{"slug": "push-up", "sets": [[5, null, 5]]}]',
        NULL, 'completed', NULL, now() - interval '4 days');

    -- Đang tập (in_progress) — bắt đầu 40 phút trước, còn hiệp chưa làm
    v_sched := test_seed.schedule(test_seed.uid(7), v_plan, 3, current_date);
    PERFORM test_seed.log_session(test_seed.uid(7), 'Circuit B', date_trunc('minute', now() - interval '40 minutes'), 0,
        '[{"slug": "walking-lunge", "sets": [[12, 10, 7], [12, 10, 7.5], [12, 10, 8]]},
          {"slug": "dumbbell-row",  "sets": [[12, 20, 7], [12, 20, 7.5], [12, 20, null, "working", null, null, false]]},
          {"slug": "burpee",        "sets": [[10, null, null, "working", null, null, false], [10, null, null, "working", null, null, false]]},
          {"slug": "russian-twist", "via": "wiki", "sets": []}]',
        v_sched, 'in_progress');

    PERFORM test_seed.schedule(test_seed.uid(7), v_plan, 1, current_date + 2);
    PERFORM test_seed.schedule(test_seed.uid(7), v_plan, 2, current_date + 4, 'cancelled', NULL, 'Bận họp');

    -- =================================================================
    -- other@ (10): bodyweight tại nhà — hiệp không có mức tạ
    -- =================================================================
    v_plan := test_seed.clone_plan(test_seed.template(6), test_seed.uid(10), 'Tập tại nhà', 'active', now() - interval '28 days');
    FOREACH v_off IN ARRAY ARRAY[12, 9, 5, 2] LOOP
        v_day := (v_off % 3) + 1;
        v_sched := test_seed.schedule(test_seed.uid(10), v_plan, v_day, current_date - v_off);
        PERFORM test_seed.log_plan_session(test_seed.uid(10), v_sched, test_seed.at_local(current_date - v_off, '06:15'), 35, '{}', 1.0, 7.0, 2);
    END LOOP;
    PERFORM test_seed.schedule(test_seed.uid(10), v_plan, 1, current_date + 1);

    -- =================================================================
    -- locked@ (12), deleted@ (14): một buổi tập cũ
    -- =================================================================
    PERFORM test_seed.log_session(test_seed.uid(12), 'Tập thử', test_seed.at_local(current_date - 35, '19:00'), 45,
        '[{"slug": "machine-chest-press", "sets": [[12, 35, 7], [10, 35, 8]]}, {"slug": "lat-pulldown", "sets": [[12, 35, 7], [10, 35, 8]]}]');
    PERFORM test_seed.log_session(test_seed.uid(14), 'Chân', test_seed.at_local(current_date - 126, '17:00'), 40,
        '[{"slug": "goblet-squat", "sets": [[12, 8, 7], [12, 8, 7.5], [10, 8, 8]]}, {"slug": "glute-bridge", "sets": [[15, null, 7], [15, null, 7]]}]');

    -- =================================================================
    -- trainer@ (16): giáo án clone 5×5 đang active + giáo án nháp cho khách
    -- =================================================================
    v_plan := test_seed.clone_plan(test_seed.template(4), test_seed.uid(16), '5×5 của Coach Xuân', 'active', now() - interval '84 days');
    v_weights := '{"barbell-back-squat": 140, "barbell-bench-press": 100, "barbell-row": 90, "overhead-press": 65, "conventional-deadlift": 180}';
    FOREACH v_off IN ARRAY ARRAY[6, 4, 1] LOOP
        v_day := (v_off % 2) + 1;
        v_sched := test_seed.schedule(test_seed.uid(16), v_plan, v_day, current_date - v_off);
        PERFORM test_seed.log_plan_session(test_seed.uid(16), v_sched, test_seed.at_local(current_date - v_off, '05:30'), 70, v_weights, 1.0, 8.0, 0);
    END LOOP;
    PERFORM test_seed.clone_plan(test_seed.template(1), test_seed.uid(16), 'Giáo án cho khách mới (nháp)', 'draft', now() - interval '3 days');
END
$$;
