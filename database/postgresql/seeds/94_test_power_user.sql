-- =====================================================================
-- Smart Workout AI — TEST DATA (5/7): power@ (persona 04) — lịch sử ~6 tháng
-- Phục vụ test phân trang, biểu đồ Tháng/3 Tháng, materialized view, báo cáo tuần.
-- Upper/Lower 4 buổi/tuần (T2, T3, T5, T6), tăng tạ dần, deload mỗi 6 tuần,
-- ~6% buổi bỏ qua, ~2% huỷ. setseed() cố định → mỗi lần init cho cùng kết quả.
-- =====================================================================

DO $$
DECLARE
    v_user      uuid := test_seed.uid(4);
    v_week0     date := date_trunc('week', current_date)::date;
    v_offsets   integer[] := ARRAY[0, 1, 3, 4];
    v_weights   jsonb := '{"barbell-bench-press": 80, "barbell-row": 70, "overhead-press": 50, "lat-pulldown": 65,
                           "skull-crusher": 30, "barbell-curl": 35, "barbell-back-squat": 110, "romanian-deadlift": 100,
                           "walking-lunge": 20, "leg-extension": 55, "incline-dumbbell-press": 30,
                           "machine-shoulder-press": 50, "seated-cable-row": 65, "cable-lateral-raise": 7.5,
                           "overhead-triceps-extension": 22.5, "conventional-deadlift": 140, "leg-press": 200,
                           "hip-thrust": 120, "lying-leg-curl": 50}';
    v_plan      uuid;
    v_sched     uuid;
    v_d         date;
    v_w         integer;
    v_i         integer;
    v_r         double precision;
    v_progress  numeric;
    v_kg        numeric;
    v_measure   uuid;
    v_photo_first uuid;
    v_photo_last  uuid;
    v_photo     uuid;
    v_m         integer;
    v_taken     timestamptz;
BEGIN
    PERFORM setseed(0.2026);

    -- -----------------------------------------------------------------
    -- Giáo án: PPL cũ (archived) → Upper/Lower hiện tại
    -- -----------------------------------------------------------------
    PERFORM test_seed.clone_plan(test_seed.template(2), v_user, 'PPL (giai đoạn trước)', 'archived', now() - interval '200 days');
    v_plan := test_seed.clone_plan(test_seed.template(3), v_user, 'Upper/Lower của Bình', 'active', now() - interval '185 days');

    -- -----------------------------------------------------------------
    -- Lịch tập & buổi tập: 25 tuần trước → tuần sau
    -- -----------------------------------------------------------------
    FOR v_w IN REVERSE 25..-1 LOOP
        v_progress := 0.85 + 0.15 * (25 - greatest(v_w, 0)) / 25.0;
        IF v_w IN (19, 13, 7) THEN
            v_progress := v_progress * 0.9;                       -- tuần deload
        END IF;

        FOR v_i IN 1..4 LOOP
            v_d := v_week0 - 7 * v_w + v_offsets[v_i];
            IF v_d >= current_date THEN
                IF v_d <= current_date + 10 THEN
                    PERFORM test_seed.schedule(v_user, v_plan, v_i, v_d);
                END IF;
                CONTINUE;
            END IF;

            v_r := random();
            IF v_r < 0.06 THEN
                PERFORM test_seed.schedule(v_user, v_plan, v_i, v_d, 'skipped', NULL, 'Bỏ buổi');
            ELSIF v_r < 0.08 THEN
                PERFORM test_seed.schedule(v_user, v_plan, v_i, v_d, 'cancelled', NULL, 'Phòng tập đóng cửa');
            ELSE
                v_sched := test_seed.schedule(v_user, v_plan, v_i, v_d);
                PERFORM test_seed.log_plan_session(
                    v_user, v_sched,
                    test_seed.at_local(v_d, '18:00') + floor(random() * 60)::integer * interval '1 minute',
                    55 + floor(random() * 25)::integer,
                    v_weights, v_progress,
                    CASE WHEN random() < 0.5 THEN 7.5 ELSE 8.0 END,
                    floor(random() * 3)::integer);
            END IF;
        END LOOP;
    END LOOP;

    -- -----------------------------------------------------------------
    -- Số đo hằng tuần: tăng cơ 76 → 80 kg (15 tuần), sau đó duy trì
    -- -----------------------------------------------------------------
    FOR v_w IN REVERSE 25..0 LOOP
        v_kg := CASE WHEN v_w >= 10 THEN 76.0 + (25 - v_w) * 4.0 / 15.0
                     ELSE 80.0 + round((random() * 0.6 - 0.3)::numeric, 1) END;
        INSERT INTO body.body_measurements (user_id, measured_at, weight_kg, body_fat_pct, muscle_mass_kg, source, created_at, updated_at)
        VALUES (v_user,
                date_trunc('minute', now() - v_w * interval '7 days' - interval '3 hours'),
                round(v_kg, 1),
                round(18.0 - (25 - v_w) * 0.1, 1),
                round(35.0 + (25 - v_w) * 0.12, 1),
                'smart_scale',
                date_trunc('minute', now() - v_w * interval '7 days' - interval '3 hours'),
                date_trunc('minute', now() - v_w * interval '7 days' - interval '3 hours'))
        RETURNING id INTO v_measure;

        IF v_w % 4 = 0 THEN                                        -- số đo vòng mỗi 4 tuần
            INSERT INTO body.body_circumferences (measurement_id, body_site_id, value_cm)
            SELECT v_measure, s.id, round(v.base + v.step * (25 - v_w), 1)
            FROM (VALUES ('waist', 82.0, -0.08), ('chest', 98.0, 0.20), ('right_arm', 35.0, 0.10), ('right_thigh', 57.0, 0.12))
                 AS v(site, base, step)
            JOIN body.body_sites s ON s.code = v.site;
        END IF;
    END LOOP;

    -- -----------------------------------------------------------------
    -- Mục tiêu: tăng cơ (đã đạt) → sức mạnh (đang theo)
    -- -----------------------------------------------------------------
    INSERT INTO body.user_goals (user_id, goal_type_id, target_weight_kg, target_body_fat_pct, start_date, target_date, status, closed_at)
    SELECT v_user, g.id, 80.0, 16.0, current_date - 182, current_date - 40, 'achieved', now() - interval '60 days'
    FROM body.fitness_goal_types g WHERE g.code = 'gain_muscle';
    INSERT INTO body.user_goals (user_id, goal_type_id, start_date, target_date, status)
    SELECT v_user, g.id, current_date - 59, current_date + 120, 'active'
    FROM body.fitness_goal_types g WHERE g.code = 'strength';

    -- -----------------------------------------------------------------
    -- Báo đau mỏi cơ (user tự nhập — không phải dữ liệu AI)
    -- -----------------------------------------------------------------
    INSERT INTO training.muscle_soreness_reports (user_id, muscle_group_id, soreness_level, reported_at, note)
    SELECT v_user, test_seed.mg(v.muscle), v.level, date_trunc('minute', now() - v.days * interval '1 day'), v.note
    FROM (VALUES ('quads', 7, 120, 'Sau tuần tăng tạ squat'), ('hamstrings', 6, 119, NULL), ('chest', 4, 60, NULL),
                 ('lower_back', 5, 33, 'Deadlift nặng'), ('quads', 3, 10, NULL), ('lats', 4, 2, NULL)) AS v(muscle, level, days, note);

    -- -----------------------------------------------------------------
    -- Ảnh tiến độ mỗi 4 tuần (mặt trước; mặt bên ở các tháng chẵn)
    -- -----------------------------------------------------------------
    FOR v_m IN REVERSE 6..0 LOOP
        v_taken := date_trunc('hour', now() - v_m * interval '28 days' - interval '1 hour');
        INSERT INTO media.progress_photos (user_id, original_media_id, watermarked_media_id, thumbnail_media_id,
                                           angle, capture_source, taken_at, processing_status, created_at, updated_at)
        VALUES (v_user,
                test_seed.media(v_user, format('users/%s/progress/m%s-front.jpg', v_user, v_m), 'image/jpeg', 2300000 + v_m * 10000, 3024, 4032, NULL, 'available', v_taken),
                test_seed.media(NULL,   format('users/%s/progress/m%s-front.wm.jpg', v_user, v_m), 'image/jpeg', 950000 + v_m * 5000, 1512, 2016, NULL, 'available', v_taken + interval '2 minutes'),
                test_seed.media(NULL,   format('users/%s/progress/m%s-front.thumb.jpg', v_user, v_m), 'image/jpeg', 42000, 300, 400, NULL, 'available', v_taken + interval '2 minutes'),
                'front', 'camera', v_taken, 'completed', v_taken, v_taken + interval '2 minutes')
        RETURNING id INTO v_photo;
        IF v_m = 6 THEN v_photo_first := v_photo; END IF;
        IF v_m = 0 THEN v_photo_last := v_photo; END IF;

        IF v_m % 2 = 0 THEN
            INSERT INTO media.progress_photos (user_id, original_media_id, watermarked_media_id, thumbnail_media_id,
                                               angle, capture_source, taken_at, processing_status, created_at, updated_at)
            VALUES (v_user,
                    test_seed.media(v_user, format('users/%s/progress/m%s-side.jpg', v_user, v_m), 'image/jpeg', 2200000, 3024, 4032, NULL, 'available', v_taken),
                    test_seed.media(NULL,   format('users/%s/progress/m%s-side.wm.jpg', v_user, v_m), 'image/jpeg', 900000, 1512, 2016, NULL, 'available', v_taken + interval '2 minutes'),
                    test_seed.media(NULL,   format('users/%s/progress/m%s-side.thumb.jpg', v_user, v_m), 'image/jpeg', 40000, 300, 400, NULL, 'available', v_taken + interval '2 minutes'),
                    'side', 'camera', v_taken + interval '1 minute', 'completed', v_taken, v_taken + interval '2 minutes');
        END IF;
    END LOOP;

    INSERT INTO media.photo_comparisons (before_photo_id, after_photo_id, title)
    VALUES (v_photo_first, v_photo_last, '6 tháng tăng cơ');

    -- -----------------------------------------------------------------
    -- Báo cáo đã xuất: 25 báo cáo tuần + 5 báo cáo tháng
    -- -----------------------------------------------------------------
    INSERT INTO analytics.report_exports (user_id, report_type, period_start, media_id, created_at)
    SELECT v_user, 'weekly_summary', p.period_start,
           test_seed.media(NULL, format('users/%s/reports/weekly-%s.png', v_user, p.period_start), 'image/png', 340000, 1080, 1920,
                           NULL, 'available', least(p.period_start + 7 + time '09:00', now())),
           least(p.period_start + 7 + time '09:00', now())
    FROM (SELECT v_week0 - 7 * w AS period_start FROM generate_series(1, 25) AS w) AS p;

    INSERT INTO analytics.report_exports (user_id, report_type, period_start, media_id, created_at)
    SELECT v_user, 'monthly_summary', p.period_start,
           test_seed.media(NULL, format('users/%s/reports/monthly-%s.png', v_user, p.period_start), 'image/png', 420000, 1080, 1920,
                           NULL, 'available', least((p.period_start + interval '1 month')::date + time '09:00', now())),
           least((p.period_start + interval '1 month')::date + time '09:00', now())
    FROM (SELECT (date_trunc('month', current_date) - k * interval '1 month')::date AS period_start
          FROM generate_series(1, 5) AS k) AS p;
END
$$;
