-- =====================================================================
-- Smart Workout AI — TEST DATA (3/7): hồ sơ thể chất, số đo, mục tiêu
-- power@ (persona 04) được sinh riêng ở 94_test_power_user.sql
-- newbie@ (08), pending@ (11), disabled@ (13), admin/editor: KHÔNG có hồ sơ thể chất
-- =====================================================================

-- ---------------------------------------------------------------------
-- body.user_body_profiles
-- ---------------------------------------------------------------------
INSERT INTO body.user_body_profiles (user_id, gender, date_of_birth, height_cm, activity_level_id, experience_level_id)
SELECT test_seed.uid(v.n), v.gender::body.gender, v.dob::date, v.height,
       (SELECT a.id FROM body.activity_levels a WHERE a.code = v.activity),
       (SELECT d.id FROM catalog.difficulty_levels d WHERE d.code = v.experience)
FROM (VALUES
    ( 3, 'male',        '2003-05-10', 172.0, 'moderate',    'beginner'),
    ( 4, 'male',        '1996-02-14', 178.0, 'active',      'advanced'),
    ( 5, 'female',      '1999-08-21', 160.0, 'light',       'intermediate'),
    ( 6, 'male',        '1991-11-03', 170.0, 'sedentary',   'beginner'),
    ( 7, 'male',        '2000-01-15', 175.0, 'moderate',    'intermediate'),
    -- unspecified@: thiếu ngày sinh, chiều cao, mức vận động → BMI/BMR/TDEE = NULL
    ( 9, 'unspecified', NULL,         NULL,  NULL,          NULL),
    -- other@: giới tính other → BMR dùng hằng số −78
    (10, 'other',       '1998-03-30', 168.0, 'moderate',    'beginner'),
    (12, 'male',        '1995-07-07', 176.0, 'light',       'beginner'),
    (14, 'female',      '2001-12-12', 162.0, 'light',       'beginner'),
    (15, 'female',      '2002-04-25', 158.0, 'light',       'beginner'),
    (16, 'male',        '1990-09-09', 180.0, 'very_active', 'advanced')
) AS v(n, gender, dob, height, activity, experience);

-- ---------------------------------------------------------------------
-- body.body_measurements — w = số tuần trước hiện tại
-- ---------------------------------------------------------------------
INSERT INTO body.body_measurements (user_id, measured_at, weight_kg, body_fat_pct, muscle_mass_kg, source, note, created_at, updated_at)
SELECT test_seed.uid(v.n), m.at, v.kg, v.fat, v.muscle, v.source::body.measurement_source, v.note, m.at, m.at
FROM (VALUES
    -- demo@: giảm cân đều 6 tuần
    ( 3, 6, 72.4, 20.0, NULL::numeric, 'manual',      NULL::text),
    ( 3, 5, 71.9, 19.7, NULL, 'manual',      NULL),
    ( 3, 4, 71.5, 19.4, NULL, 'manual',      NULL),
    ( 3, 3, 71.1, 19.1, NULL, 'manual',      NULL),
    ( 3, 2, 70.6, 18.8, NULL, 'manual',      NULL),
    ( 3, 1, 70.3, 18.6, NULL, 'manual',      NULL),
    ( 3, 0, 70.0, 18.4, 32.5, 'smart_scale', 'Cân sau khi ngủ dậy'),
    -- dung@: tăng cân (tăng cơ) 8 tuần
    ( 5, 8, 52.0, 24.0, NULL, 'manual', NULL),
    ( 5, 7, 52.2, 24.0, NULL, 'manual', NULL),
    ( 5, 6, 52.5, 23.9, NULL, 'manual', NULL),
    ( 5, 5, 52.8, 23.9, NULL, 'manual', NULL),
    ( 5, 4, 53.0, 23.8, NULL, 'manual', NULL),
    ( 5, 3, 53.3, 23.7, NULL, 'manual', NULL),
    ( 5, 2, 53.5, 23.7, NULL, 'manual', NULL),
    ( 5, 1, 53.8, 23.6, NULL, 'manual', NULL),
    ( 5, 0, 54.0, 23.5, NULL, 'manual', NULL),
    -- plateau@: giảm 4 tuần đầu rồi đứng cân 6 tuần → is_plateau
    ( 6, 10, 85.0, 27.0, NULL, 'manual', NULL),
    ( 6,  9, 84.6, 26.8, NULL, 'manual', NULL),
    ( 6,  8, 84.2, 26.6, NULL, 'manual', NULL),
    ( 6,  7, 83.8, 26.4, NULL, 'manual', NULL),
    ( 6,  6, 83.4, 26.3, NULL, 'manual', NULL),
    ( 6,  5, 83.5, 26.3, NULL, 'manual', NULL),
    ( 6,  4, 83.4, 26.3, NULL, 'manual', NULL),
    ( 6,  3, 83.4, 26.2, NULL, 'manual', NULL),
    ( 6,  2, 83.5, 26.3, NULL, 'manual', 'Cân không đổi dù ăn kiêng'),
    ( 6,  1, 83.4, 26.2, NULL, 'manual', NULL),
    ( 6,  0, 83.4, 26.2, NULL, 'manual', NULL),
    -- inprogress@
    ( 7, 3, 78.5, 17.5, NULL, 'manual', NULL),
    ( 7, 2, 78.2, 17.3, NULL, 'manual', NULL),
    ( 7, 1, 78.0, 17.2, NULL, 'manual', NULL),
    -- unspecified@: một lần đo, không có %mỡ
    ( 9, 0, 65.0, NULL, NULL, 'manual', NULL),
    -- other@
    (10, 3, 66.0, 21.0, NULL, 'manual', NULL),
    (10, 2, 65.8, 20.9, NULL, 'manual', NULL),
    (10, 1, 65.6, 20.8, NULL, 'manual', NULL),
    (10, 0, 65.4, 20.7, NULL, 'manual', NULL),
    -- locked@
    (12, 5, 80.0, 22.0, NULL, 'manual', NULL),
    -- deleted@ (tài khoản đã xoá mềm — dữ liệu không được trả về API)
    (14, 20, 55.0, 25.0, NULL, 'manual', NULL),
    (14, 18, 54.6, 24.8, NULL, 'manual', NULL),
    (14, 16, 54.2, 24.6, NULL, 'manual', NULL),
    -- oauth@
    (15, 2, 58.5, 27.0, NULL, 'manual', NULL),
    (15, 0, 58.2, 26.8, NULL, 'manual', NULL),
    -- trainer@: dữ liệu nhập từ thiết bị khác
    (16, 12, 82.0, 12.0, 41.5, 'imported', NULL),
    (16,  8, 82.3, 12.1, 41.6, 'imported', NULL),
    (16,  4, 82.6, 12.1, 41.8, 'imported', NULL),
    (16,  0, 82.8, 12.2, 42.0, 'imported', NULL)
) AS v(n, w, kg, fat, muscle, source, note)
CROSS JOIN LATERAL (SELECT date_trunc('minute', now() - v.w * interval '7 days' - interval '2 hours') AS at) AS m;

-- ---------------------------------------------------------------------
-- body.body_circumferences — lần đo đầu & cuối của demo@ và dung@
-- ---------------------------------------------------------------------
INSERT INTO body.body_circumferences (measurement_id, body_site_id, value_cm)
SELECT bm.id, s.id, v.cm
FROM (VALUES
    ( 3, 6, 'waist', 84.0), ( 3, 6, 'chest', 96.0), ( 3, 6, 'hips', 96.0),
    ( 3, 0, 'waist', 80.5), ( 3, 0, 'chest', 95.0), ( 3, 0, 'hips', 94.0), ( 3, 0, 'right_arm', 33.0), ( 3, 0, 'right_thigh', 55.5),
    ( 5, 8, 'waist', 66.0), ( 5, 8, 'hips', 90.0),  ( 5, 8, 'right_arm', 26.0), ( 5, 8, 'right_thigh', 52.0),
    ( 5, 0, 'waist', 65.5), ( 5, 0, 'hips', 91.5),  ( 5, 0, 'right_arm', 26.8), ( 5, 0, 'right_thigh', 53.5)
) AS v(n, w, site, cm)
JOIN body.body_sites s ON s.code = v.site
JOIN body.body_measurements bm
  ON bm.user_id = test_seed.uid(v.n)
 AND bm.measured_at = date_trunc('minute', now() - v.w * interval '7 days' - interval '2 hours');

-- ---------------------------------------------------------------------
-- body.user_goals
-- ---------------------------------------------------------------------
INSERT INTO body.user_goals (user_id, goal_type_id, target_weight_kg, target_body_fat_pct, start_date, target_date, status, closed_at)
SELECT test_seed.uid(v.n), g.id, v.target_kg, v.target_fat,
       current_date - v.start_days, current_date + v.target_days,
       v.status::body.goal_status,
       CASE WHEN v.status <> 'active' THEN now() - v.closed_days * interval '1 day' END
FROM (VALUES
    ( 3, 'lose_fat',      67.0, 15.0,  42,  90, 'active',    NULL::integer),
    ( 5, 'gain_muscle',   56.0, NULL,  56,  60, 'active',    NULL),
    ( 6, 'lose_fat',      75.0, 20.0, 150, -60, 'abandoned', 80),
    ( 6, 'lose_fat',      78.0, 22.0,  70, 120, 'active',    NULL),
    (10, 'maintain',      NULL, NULL,  28, 180, 'active',    NULL),
    (14, 'gain_muscle',   57.0, NULL, 140,  40, 'active',    NULL),
    (15, 'lose_fat',      55.0, 24.0,  14, 100, 'active',    NULL),
    (16, 'strength',      NULL, NULL,  84,  84, 'active',    NULL)
) AS v(n, goal, target_kg, target_fat, start_days, target_days, status, closed_days)
JOIN body.fitness_goal_types g ON g.code = v.goal;
