-- =====================================================================
-- Smart Workout AI — Seed: Giáo án mẫu (owner_user_id NULL)
-- UUID cố định 5eed1000-0000-4000-8000-0000000000NN để client/test tham chiếu.
-- =====================================================================

-- ---------------------------------------------------------------------
-- training.workout_plans
-- ---------------------------------------------------------------------
INSERT INTO training.workout_plans (id, owner_user_id, name, description, goal_type_id, difficulty_level_id, duration_weeks, status)
SELECT v.id::uuid, NULL, v.name, v.description, g.id, d.id, v.weeks, 'active'
FROM (VALUES
    ('5eed1000-0000-4000-8000-000000000001', 'Full Body cho người mới',
     'Hai buổi toàn thân luân phiên, 2–3 buổi/tuần. Dùng tạ đơn, máy và trọng lượng cơ thể; ưu tiên học kỹ thuật.',
     'recomposition', 'beginner', 8),
    ('5eed1000-0000-4000-8000-000000000002', 'Push / Pull / Legs',
     'Chia nhóm cơ theo kiểu đẩy – kéo – chân, 3 hoặc 6 buổi/tuần, tập trung tăng cơ.',
     'gain_muscle', 'intermediate', 12),
    ('5eed1000-0000-4000-8000-000000000003', 'Upper / Lower 4 buổi',
     'Thân trên/thân dưới, mỗi nhóm cơ 2 lần/tuần: một buổi thiên sức mạnh, một buổi thiên phì đại.',
     'gain_muscle', 'intermediate', 10),
    ('5eed1000-0000-4000-8000-000000000004', 'Sức mạnh 5×5',
     'Hai buổi A/B luân phiên với các bài đa khớp 5 hiệp × 5 rep, tăng tạ đều mỗi buổi.',
     'strength', 'intermediate', 12),
    ('5eed1000-0000-4000-8000-000000000005', 'Giảm mỡ – Circuit + Cardio',
     'Circuit nghỉ ngắn kết hợp cardio vùng 2, 3 buổi/tuần.',
     'lose_fat', 'beginner', 8),
    ('5eed1000-0000-4000-8000-000000000006', 'Bodyweight tại nhà',
     'Không cần thiết bị: thân trên & core, thân dưới, cardio & mobility.',
     'maintain', 'beginner', 6)
) AS v(id, name, description, goal_code, difficulty, weeks)
JOIN body.fitness_goal_types g ON g.code = v.goal_code
JOIN catalog.difficulty_levels d ON d.code = v.difficulty;

-- ---------------------------------------------------------------------
-- training.workout_plan_days
-- ---------------------------------------------------------------------
INSERT INTO training.workout_plan_days (plan_id, day_no, name)
SELECT v.plan_id::uuid, v.day_no, v.name
FROM (VALUES
    ('5eed1000-0000-4000-8000-000000000001', 1, 'Toàn thân A'),
    ('5eed1000-0000-4000-8000-000000000001', 2, 'Toàn thân B'),
    ('5eed1000-0000-4000-8000-000000000002', 1, 'Push – Ngực/Vai/Tay sau'),
    ('5eed1000-0000-4000-8000-000000000002', 2, 'Pull – Lưng/Tay trước'),
    ('5eed1000-0000-4000-8000-000000000002', 3, 'Legs – Chân/Mông'),
    ('5eed1000-0000-4000-8000-000000000003', 1, 'Upper A – Sức mạnh'),
    ('5eed1000-0000-4000-8000-000000000003', 2, 'Lower A – Sức mạnh'),
    ('5eed1000-0000-4000-8000-000000000003', 3, 'Upper B – Phì đại'),
    ('5eed1000-0000-4000-8000-000000000003', 4, 'Lower B – Phì đại'),
    ('5eed1000-0000-4000-8000-000000000004', 1, 'Buổi A'),
    ('5eed1000-0000-4000-8000-000000000004', 2, 'Buổi B'),
    ('5eed1000-0000-4000-8000-000000000005', 1, 'Circuit A'),
    ('5eed1000-0000-4000-8000-000000000005', 2, 'Cardio dài & core'),
    ('5eed1000-0000-4000-8000-000000000005', 3, 'Circuit B'),
    ('5eed1000-0000-4000-8000-000000000006', 1, 'Thân trên & core'),
    ('5eed1000-0000-4000-8000-000000000006', 2, 'Thân dưới'),
    ('5eed1000-0000-4000-8000-000000000006', 3, 'Cardio & mobility')
) AS v(plan_id, day_no, name);

-- ---------------------------------------------------------------------
-- training.workout_plan_exercises
-- Cột: plan, day, order, slug, sets, reps_min, reps_max, duration_s, weight, rpe, rest_s, tempo (e, pb, c, pt)
-- ---------------------------------------------------------------------
INSERT INTO training.workout_plan_exercises (plan_day_id, exercise_id, order_no, target_sets, target_reps_min, target_reps_max,
                                             target_duration_seconds, target_weight_kg, target_rpe, rest_seconds,
                                             tempo_eccentric_s, tempo_pause_bottom_s, tempo_concentric_s, tempo_pause_top_s)
SELECT pd.id, e.id, v.ord, v.sets, v.rmin, v.rmax, v.dur, v.kg, v.rpe, v.rest, v.te, v.tpb, v.tc, v.tpt
FROM (VALUES
    -- 01 Full Body cho người mới
    ('5eed1000-0000-4000-8000-000000000001', 1, 1, 'goblet-squat',            3, 10, 12, NULL::smallint, NULL::numeric, 7.0, 90,  NULL::smallint, NULL::smallint, NULL::smallint, NULL::smallint),
    ('5eed1000-0000-4000-8000-000000000001', 1, 2, 'dumbbell-bench-press',    3, 10, 12, NULL, NULL, 7.0, 90,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000001', 1, 3, 'lat-pulldown',            3, 10, 12, NULL, NULL, 7.0, 90,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000001', 1, 4, 'dumbbell-shoulder-press', 2, 10, 12, NULL, NULL, 7.0, 90,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000001', 1, 5, 'plank',                   3, NULL, NULL, 30, NULL, NULL, 60, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000001', 2, 1, 'leg-press',               3, 10, 12, NULL, NULL, 7.0, 90,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000001', 2, 2, 'push-up',                 3, 8,  12, NULL, NULL, 7.0, 90,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000001', 2, 3, 'seated-cable-row',        3, 10, 12, NULL, NULL, 7.0, 90,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000001', 2, 4, 'glute-bridge',            3, 12, 15, NULL, NULL, 7.0, 60,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000001', 2, 5, 'dead-bug',                3, 10, 12, NULL, NULL, NULL, 60, NULL, NULL, NULL, NULL),
    -- 02 Push / Pull / Legs
    ('5eed1000-0000-4000-8000-000000000002', 1, 1, 'barbell-bench-press',     4, 6,  8,  NULL, NULL, 8.0, 150, 3, 1, 1, 0),
    ('5eed1000-0000-4000-8000-000000000002', 1, 2, 'incline-dumbbell-press',  3, 8,  10, NULL, NULL, 8.0, 120, 2, 0, 1, 0),
    ('5eed1000-0000-4000-8000-000000000002', 1, 3, 'overhead-press',          3, 8,  10, NULL, NULL, 8.0, 120, 2, 0, 1, 0),
    ('5eed1000-0000-4000-8000-000000000002', 1, 4, 'cable-chest-fly',         3, 12, 15, NULL, NULL, 8.5, 60,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000002', 1, 5, 'dumbbell-lateral-raise',  3, 12, 15, NULL, NULL, 8.5, 60,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000002', 1, 6, 'cable-triceps-pushdown',  3, 10, 12, NULL, NULL, 8.5, 60,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000002', 2, 1, 'pull-up',                 4, 6,  8,  NULL, NULL, 8.0, 120, 2, 0, 1, 1),
    ('5eed1000-0000-4000-8000-000000000002', 2, 2, 'barbell-row',             3, 8,  10, NULL, NULL, 8.0, 120, 2, 0, 1, 1),
    ('5eed1000-0000-4000-8000-000000000002', 2, 3, 'seated-cable-row',        3, 10, 12, NULL, NULL, 8.0, 90,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000002', 2, 4, 'face-pull',               3, 12, 15, NULL, NULL, 8.0, 60,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000002', 2, 5, 'barbell-curl',            3, 10, 12, NULL, NULL, 8.5, 60,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000002', 2, 6, 'hammer-curl',             2, 10, 12, NULL, NULL, 8.5, 60,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000002', 3, 1, 'barbell-back-squat',      4, 6,  8,  NULL, NULL, 8.0, 180, 3, 1, 1, 0),
    ('5eed1000-0000-4000-8000-000000000002', 3, 2, 'romanian-deadlift',       3, 8,  10, NULL, NULL, 8.0, 120, 3, 0, 1, 0),
    ('5eed1000-0000-4000-8000-000000000002', 3, 3, 'leg-press',               3, 10, 12, NULL, NULL, 8.0, 90,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000002', 3, 4, 'lying-leg-curl',          3, 10, 12, NULL, NULL, 8.5, 60,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000002', 3, 5, 'standing-calf-raise',     4, 12, 15, NULL, NULL, 8.5, 60,  NULL, NULL, NULL, NULL),
    -- 03 Upper / Lower 4 buổi
    ('5eed1000-0000-4000-8000-000000000003', 1, 1, 'barbell-bench-press',     4, 5,  6,  NULL, NULL, 8.5, 180, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 1, 2, 'barbell-row',             4, 6,  8,  NULL, NULL, 8.0, 150, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 1, 3, 'overhead-press',          3, 6,  8,  NULL, NULL, 8.0, 150, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 1, 4, 'lat-pulldown',            3, 8,  10, NULL, NULL, 8.0, 90,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 1, 5, 'skull-crusher',           3, 10, 12, NULL, NULL, 8.5, 60,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 1, 6, 'barbell-curl',            3, 10, 12, NULL, NULL, 8.5, 60,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 2, 1, 'barbell-back-squat',      4, 5,  6,  NULL, NULL, 8.5, 180, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 2, 2, 'romanian-deadlift',       3, 8,  10, NULL, NULL, 8.0, 120, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 2, 3, 'walking-lunge',           3, 10, 12, NULL, NULL, 8.0, 90,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 2, 4, 'leg-extension',           3, 12, 15, NULL, NULL, 8.5, 60,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 2, 5, 'standing-calf-raise',     4, 12, 15, NULL, NULL, 8.5, 60,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 3, 1, 'incline-dumbbell-press',  4, 8,  10, NULL, NULL, 8.0, 120, 3, 0, 1, 0),
    ('5eed1000-0000-4000-8000-000000000003', 3, 2, 'chin-up',                 4, 6,  10, NULL, NULL, 8.0, 120, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 3, 3, 'machine-shoulder-press',  3, 10, 12, NULL, NULL, 8.0, 90,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 3, 4, 'seated-cable-row',        3, 10, 12, NULL, NULL, 8.0, 90,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 3, 5, 'cable-lateral-raise',     3, 12, 15, NULL, NULL, 8.5, 60,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 3, 6, 'overhead-triceps-extension', 3, 10, 12, NULL, NULL, 8.5, 60, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 4, 1, 'conventional-deadlift',   3, 4,  6,  NULL, NULL, 8.5, 180, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 4, 2, 'leg-press',               4, 10, 12, NULL, NULL, 8.0, 90,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 4, 3, 'hip-thrust',              3, 8,  10, NULL, NULL, 8.0, 90,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 4, 4, 'lying-leg-curl',          3, 10, 12, NULL, NULL, 8.5, 60,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000003', 4, 5, 'hanging-leg-raise',       3, 10, 15, NULL, NULL, 8.0, 60,  NULL, NULL, NULL, NULL),
    -- 04 Sức mạnh 5×5
    ('5eed1000-0000-4000-8000-000000000004', 1, 1, 'barbell-back-squat',      5, 5,  5,  NULL, NULL, 8.0, 180, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000004', 1, 2, 'barbell-bench-press',     5, 5,  5,  NULL, NULL, 8.0, 180, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000004', 1, 3, 'barbell-row',             5, 5,  5,  NULL, NULL, 8.0, 150, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000004', 2, 1, 'barbell-back-squat',      5, 5,  5,  NULL, NULL, 8.0, 180, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000004', 2, 2, 'overhead-press',          5, 5,  5,  NULL, NULL, 8.0, 180, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000004', 2, 3, 'conventional-deadlift',   1, 5,  5,  NULL, NULL, 8.5, 180, NULL, NULL, NULL, NULL),
    -- 05 Giảm mỡ – Circuit + Cardio
    ('5eed1000-0000-4000-8000-000000000005', 1, 1, 'goblet-squat',            3, 15, 15, NULL, NULL, 7.0, 30,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000005', 1, 2, 'push-up',                 3, 10, 15, NULL, NULL, 7.0, 30,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000005', 1, 3, 'kettlebell-swing',        3, 15, 15, NULL, NULL, 7.5, 30,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000005', 1, 4, 'mountain-climber',        3, NULL, NULL, 40, NULL, NULL, 30, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000005', 1, 5, 'incline-treadmill-walk',  1, NULL, NULL, 1200, NULL, NULL, 0, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000005', 2, 1, 'stationary-bike',         1, NULL, NULL, 1800, NULL, NULL, 0, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000005', 2, 2, 'plank',                   3, NULL, NULL, 45, NULL, NULL, 45, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000005', 2, 3, 'side-plank',              2, NULL, NULL, 30, NULL, NULL, 30, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000005', 3, 1, 'walking-lunge',           3, 12, 14, NULL, NULL, 7.0, 30,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000005', 3, 2, 'dumbbell-row',            3, 12, 15, NULL, NULL, 7.0, 30,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000005', 3, 3, 'burpee',                  3, 10, 10, NULL, NULL, 8.0, 45,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000005', 3, 4, 'russian-twist',           3, 20, 20, NULL, NULL, 7.0, 30,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000005', 3, 5, 'rowing-machine',          1, NULL, NULL, 900, NULL, NULL, 0, NULL, NULL, NULL, NULL),
    -- 06 Bodyweight tại nhà (không thiết bị bắt buộc)
    ('5eed1000-0000-4000-8000-000000000006', 1, 1, 'push-up',                 4, 8,  15, NULL, NULL, 8.0, 60,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000006', 1, 2, 'plank',                   3, NULL, NULL, 45, NULL, NULL, 45, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000006', 1, 3, 'crunch',                  3, 15, 20, NULL, NULL, 7.0, 45,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000006', 1, 4, 'dead-bug',                3, 10, 12, NULL, NULL, NULL, 45, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000006', 1, 5, 'side-plank',              2, NULL, NULL, 30, NULL, NULL, 30, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000006', 2, 1, 'jump-squat',              3, 10, 12, NULL, NULL, 7.5, 60,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000006', 2, 2, 'walking-lunge',           3, 10, 12, NULL, NULL, 7.5, 60,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000006', 2, 3, 'glute-bridge',            3, 15, 20, NULL, NULL, 7.5, 45,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000006', 2, 4, 'standing-calf-raise',     3, 15, 20, NULL, NULL, 7.5, 45,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000006', 3, 1, 'burpee',                  4, 8,  12, NULL, NULL, 8.0, 60,  NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000006', 3, 2, 'mountain-climber',        3, NULL, NULL, 30, NULL, NULL, 30, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000006', 3, 3, 'worlds-greatest-stretch', 2, 5,  6,  NULL, NULL, NULL, 30, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000006', 3, 4, 'cat-cow',                 2, 10, 10, NULL, NULL, NULL, 15, NULL, NULL, NULL, NULL),
    ('5eed1000-0000-4000-8000-000000000006', 3, 5, 'childs-pose',             1, NULL, NULL, 60, NULL, NULL, 0, NULL, NULL, NULL, NULL)
) AS v(plan_id, day_no, ord, slug, sets, rmin, rmax, dur, kg, rpe, rest, te, tpb, tc, tpt)
JOIN training.workout_plan_days pd ON pd.plan_id = v.plan_id::uuid AND pd.day_no = v.day_no
JOIN catalog.exercises e ON e.slug = v.slug;
