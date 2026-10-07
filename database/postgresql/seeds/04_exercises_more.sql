-- =====================================================================
-- Smart Workout AI — Seed: Exercise Wiki (mở rộng)
-- Cardio, plyometric, giãn cơ/mobility, bài máy/tạ bổ sung, core.
-- Cùng cấu trúc với 03_exercises.sql.
-- =====================================================================

-- ---------------------------------------------------------------------
-- catalog.exercises
-- ---------------------------------------------------------------------
INSERT INTO catalog.exercises (slug, name, name_en, description, difficulty_level_id, category, mechanic, force_type,
                               is_unilateral, met_value, supports_ai_tracking, status, published_at)
SELECT v.slug, v.name, v.name_en, v.description, d.id, v.category::catalog.exercise_category,
       v.mechanic::catalog.mechanic_type, v.force::catalog.force_type, v.unilateral, v.met, false, 'published', now()
FROM (VALUES
    -- Cardio
    ('treadmill-run',               'Chạy bộ trên máy',             'Treadmill Run',                    'Chạy bộ trên máy với tốc độ ổn định hoặc biến tốc.',            'beginner',     'cardio',     NULL,        NULL,     false,  9.8),
    ('incline-treadmill-walk',      'Đi bộ dốc trên máy',           'Incline Treadmill Walk',           'Đi bộ trên máy chạy với độ dốc 8–15%, cường độ vừa, ít va chạm.', 'beginner',     'cardio',     NULL,        NULL,     false,  5.3),
    ('stationary-bike',             'Đạp xe tại chỗ',               'Stationary Bike',                  'Đạp xe cố định, phù hợp khởi động hoặc cardio dài.',            'beginner',     'cardio',     NULL,        NULL,     false,  7.0),
    ('rowing-machine',              'Chèo thuyền trên máy',         'Rowing Machine',                   'Cardio toàn thân trên máy chèo thuyền.',                        'intermediate', 'cardio',     NULL,        NULL,     false,  7.0),
    ('jump-rope',                   'Nhảy dây',                     'Jump Rope',                        'Nhảy dây liên tục, đốt nhiều năng lượng.',                      'beginner',     'cardio',     NULL,        NULL,     false, 11.8),
    -- Plyometric
    ('box-jump',                    'Bật nhảy lên bục',             'Box Jump',                         'Bật nhảy hai chân lên bục, phát triển sức bật.',                'intermediate', 'plyometric', 'compound',  'push',   false,  8.0),
    ('jump-squat',                  'Squat bật nhảy',               'Jump Squat',                       'Squat rồi bật nhảy thẳng lên, tiếp đất mềm.',                   'beginner',     'plyometric', 'compound',  'push',   false,  8.0),
    ('burpee',                      'Burpee',                       'Burpee',                           'Chống đẩy kết hợp bật nhảy, bài toàn thân cường độ cao.',       'intermediate', 'plyometric', 'compound',  'push',   false,  8.0),
    ('mountain-climber',            'Leo núi tại chỗ',              'Mountain Climber',                 'Tư thế chống đẩy, kéo gối luân phiên về ngực thật nhanh.',      'beginner',     'plyometric', 'compound',  'push',   false,  8.0),
    ('medicine-ball-slam',          'Đập bóng tạ',                  'Medicine Ball Slam',               'Nâng bóng tạ qua đầu rồi đập mạnh xuống sàn.',                  'beginner',     'plyometric', 'compound',  'pull',   false,  8.0),
    -- Giãn cơ & mobility
    ('standing-hamstring-stretch',  'Giãn đùi sau đứng',            'Standing Hamstring Stretch',       'Gập hông với chân duỗi thẳng để giãn đùi sau.',                 'beginner',     'stretching', NULL,        'static', false,  2.3),
    ('kneeling-hip-flexor-stretch', 'Giãn cơ gập hông',             'Kneeling Hip Flexor Stretch',      'Quỳ một gối, đẩy hông về trước để giãn cơ gập hông.',           'beginner',     'stretching', NULL,        'static', true,   2.3),
    ('doorway-chest-stretch',       'Giãn ngực ở khung cửa',        'Doorway Chest Stretch',            'Tì cẳng tay vào khung cửa, bước tới để giãn ngực.',             'beginner',     'stretching', NULL,        'static', false,  2.3),
    ('childs-pose',                 'Tư thế em bé',                 'Child''s Pose',                    'Quỳ ngồi trên gót, duỗi tay về trước để thả lỏng lưng.',        'beginner',     'stretching', NULL,        'static', false,  2.3),
    ('cat-cow',                     'Mèo – Bò',                     'Cat-Cow',                          'Luân phiên cong và võng lưng ở tư thế bò.',                     'beginner',     'mobility',   NULL,        NULL,     false,  2.5),
    ('worlds-greatest-stretch',     'World''s Greatest Stretch',    'World''s Greatest Stretch',        'Chuỗi động tác mở hông, giãn đùi sau và xoay ngực.',            'intermediate', 'mobility',   NULL,        NULL,     true,   3.0),
    -- Chân & mông
    ('smith-machine-squat',         'Squat máy Smith',              'Smith Machine Squat',              'Squat với thanh tạ chạy trên ray, ổn định hơn tạ tự do.',       'beginner',     'strength',   'compound',  'push',   false,  5.0),
    ('sumo-deadlift',               'Deadlift sumo',                'Sumo Deadlift',                    'Deadlift chân rộng, tay nắm trong gối.',                        'advanced',     'strength',   'compound',  'pull',   false,  6.0),
    ('kettlebell-swing',            'Vung tạ ấm',                   'Kettlebell Swing',                 'Đẩy hông bùng nổ để vung tạ ấm lên ngang ngực.',                'intermediate', 'strength',   'compound',  'pull',   false,  9.8),
    ('walking-lunge',               'Chùng chân bước đi',           'Walking Lunge',                    'Bước dài về trước và hạ gối sau, luân phiên hai chân.',         'beginner',     'strength',   'compound',  'push',   true,   4.0),
    ('step-up',                     'Bước lên bục',                 'Step-up',                          'Bước một chân lên bục và đẩy người đứng thẳng.',                'beginner',     'strength',   'compound',  'push',   true,   4.0),
    ('glute-bridge',                'Cầu mông',                     'Glute Bridge',                     'Nằm ngửa, đẩy hông lên bằng lực mông.',                         'beginner',     'strength',   'isolation', 'push',   false,  3.5),
    -- Lưng
    ('chin-up',                     'Hít xà tay ngửa',              'Chin-up',                          'Hít xà với tay ngửa rộng bằng vai, nhấn tay trước.',            'intermediate', 'strength',   'compound',  'pull',   false,  6.0),
    ('inverted-row',                'Kéo xà thấp',                  'Inverted Row',                     'Treo người dưới thanh thấp, kéo ngực lên thanh.',               'beginner',     'strength',   'compound',  'pull',   false,  4.0),
    ('dumbbell-shrug',              'Nhún vai tạ đơn',              'Dumbbell Shrug',                   'Nhún vai thẳng lên với tạ đơn hai bên.',                        'beginner',     'strength',   'isolation', 'pull',   false,  3.5),
    -- Ngực & tay sau
    ('close-grip-bench-press',      'Đẩy ngực tay hẹp',             'Close-Grip Bench Press',           'Đẩy ngực tay nắm hẹp bằng vai, nhấn tay sau.',                  'intermediate', 'strength',   'compound',  'push',   false,  5.0),
    ('skull-crusher',               'Skull Crusher',                'EZ-Bar Skull Crusher',             'Nằm ghế, hạ thanh EZ về trán rồi duỗi khuỷu.',                  'intermediate', 'strength',   'isolation', 'push',   false,  3.5),
    ('overhead-triceps-extension',  'Duỗi tay sau qua đầu',         'Overhead Dumbbell Triceps Extension', 'Cầm tạ đơn qua đầu, hạ sau gáy rồi duỗi thẳng tay.',       'beginner',     'strength',   'isolation', 'push',   false,  3.5),
    -- Tay trước
    ('preacher-curl',               'Cuốn tay ghế Preacher',        'Preacher Curl',                    'Tì cánh tay lên đệm nghiêng, cuốn thanh EZ.',                   'intermediate', 'strength',   'isolation', 'pull',   false,  3.5),
    -- Vai
    ('cable-lateral-raise',         'Dang cáp sang ngang',          'Cable Lateral Raise',              'Dang tay một bên với cáp thấp, giữ căng cơ suốt biên độ.',      'intermediate', 'strength',   'isolation', 'push',   true,   3.5),
    ('reverse-pec-deck',            'Ép vai sau trên máy',          'Reverse Pec Deck',                 'Ngồi úp mặt vào máy ép ngực, mở tay về sau.',                   'beginner',     'strength',   'isolation', 'pull',   false,  3.5),
    ('machine-shoulder-press',      'Đẩy vai máy',                  'Machine Shoulder Press',           'Đẩy vai trên máy, quỹ đạo cố định.',                            'beginner',     'strength',   'compound',  'push',   false,  4.5),
    -- Core
    ('crunch',                      'Gập bụng',                     'Crunch',                           'Nằm ngửa, cuộn vai khỏi sàn bằng lực cơ bụng.',                 'beginner',     'strength',   'isolation', 'pull',   false,  3.0),
    ('cable-crunch',                'Gập bụng với cáp',             'Cable Crunch',                     'Quỳ trước ròng rọc cao, gập thân kéo dây xuống.',               'intermediate', 'strength',   'isolation', 'pull',   false,  3.5),
    ('side-plank',                  'Plank nghiêng',                'Side Plank',                       'Chống một khuỷu tay, giữ thân thẳng nghiêng.',                  'beginner',     'strength',   'isolation', 'static', true,   3.0),
    ('dead-bug',                    'Dead Bug',                     'Dead Bug',                         'Nằm ngửa, duỗi tay chân đối diện, giữ lưng áp sàn.',            'beginner',     'strength',   'isolation', 'static', false,  3.0),
    ('russian-twist',               'Xoay người kiểu Nga',          'Russian Twist',                    'Ngồi nghiêng thân, xoay vai sang hai bên.',                     'beginner',     'strength',   'isolation', NULL,     false,  3.5),
    ('ab-wheel-rollout',            'Lăn bánh xe tập bụng',         'Ab Wheel Rollout',                 'Quỳ, lăn bánh xe về trước rồi kéo về bằng cơ bụng.',            'advanced',     'strength',   'isolation', NULL,     false,  4.0),
    -- Toàn thân
    ('farmers-walk',                'Đi bộ xách tạ',                'Farmer''s Walk',                   'Xách tạ nặng hai tay và đi bộ, tăng sức nắm và core.',          'beginner',     'strength',   'compound',  'static', false,  6.0)
) AS v(slug, name, name_en, description, difficulty, category, mechanic, force, unilateral, met)
JOIN catalog.difficulty_levels d ON d.code = v.difficulty;

-- ---------------------------------------------------------------------
-- catalog.exercise_muscles
-- ---------------------------------------------------------------------
INSERT INTO catalog.exercise_muscles (exercise_id, muscle_group_id, role, activation_ratio)
SELECT e.id, mg.id, v.role::catalog.muscle_role, v.ratio
FROM (VALUES
    ('treadmill-run', 'quads', 'primary', 0.60), ('treadmill-run', 'hamstrings', 'primary', 0.50),
    ('treadmill-run', 'calves', 'secondary', 0.50), ('treadmill-run', 'glutes', 'secondary', 0.40),
    ('incline-treadmill-walk', 'glutes', 'primary', 0.60), ('incline-treadmill-walk', 'calves', 'primary', 0.50),
    ('incline-treadmill-walk', 'hamstrings', 'secondary', 0.40),
    ('stationary-bike', 'quads', 'primary', 0.70), ('stationary-bike', 'glutes', 'secondary', 0.40), ('stationary-bike', 'calves', 'secondary', 0.30),
    ('rowing-machine', 'lats', 'primary', 0.60), ('rowing-machine', 'upper_back', 'primary', 0.50),
    ('rowing-machine', 'quads', 'secondary', 0.50), ('rowing-machine', 'biceps', 'secondary', 0.30), ('rowing-machine', 'hamstrings', 'secondary', 0.30),
    ('jump-rope', 'calves', 'primary', 0.80), ('jump-rope', 'quads', 'secondary', 0.30), ('jump-rope', 'forearms', 'secondary', 0.20),
    ('box-jump', 'quads', 'primary', 1.00), ('box-jump', 'glutes', 'primary', 0.80), ('box-jump', 'calves', 'secondary', 0.50), ('box-jump', 'hamstrings', 'secondary', 0.30),
    ('jump-squat', 'quads', 'primary', 1.00), ('jump-squat', 'glutes', 'primary', 0.70), ('jump-squat', 'calves', 'secondary', 0.40),
    ('burpee', 'chest', 'primary', 0.60), ('burpee', 'quads', 'primary', 0.60), ('burpee', 'abs', 'secondary', 0.40),
    ('burpee', 'triceps', 'secondary', 0.30), ('burpee', 'front_delts', 'secondary', 0.30),
    ('mountain-climber', 'abs', 'primary', 0.80), ('mountain-climber', 'front_delts', 'secondary', 0.40),
    ('mountain-climber', 'quads', 'secondary', 0.40), ('mountain-climber', 'obliques', 'secondary', 0.30),
    ('medicine-ball-slam', 'abs', 'primary', 0.80), ('medicine-ball-slam', 'lats', 'primary', 0.70),
    ('medicine-ball-slam', 'front_delts', 'secondary', 0.40), ('medicine-ball-slam', 'triceps', 'secondary', 0.30),
    ('standing-hamstring-stretch', 'hamstrings', 'primary', 1.00), ('standing-hamstring-stretch', 'calves', 'secondary', 0.30),
    ('kneeling-hip-flexor-stretch', 'quads', 'primary', 0.80), ('kneeling-hip-flexor-stretch', 'glutes', 'stabilizer', 0.20),
    ('doorway-chest-stretch', 'chest', 'primary', 1.00), ('doorway-chest-stretch', 'front_delts', 'secondary', 0.50),
    ('childs-pose', 'lower_back', 'primary', 0.70), ('childs-pose', 'lats', 'secondary', 0.50), ('childs-pose', 'glutes', 'secondary', 0.30),
    ('cat-cow', 'lower_back', 'primary', 0.80), ('cat-cow', 'abs', 'secondary', 0.40),
    ('worlds-greatest-stretch', 'hamstrings', 'primary', 0.60), ('worlds-greatest-stretch', 'quads', 'primary', 0.60),
    ('worlds-greatest-stretch', 'upper_back', 'secondary', 0.40), ('worlds-greatest-stretch', 'glutes', 'secondary', 0.40),
    ('smith-machine-squat', 'quads', 'primary', 1.00), ('smith-machine-squat', 'glutes', 'primary', 0.70), ('smith-machine-squat', 'hamstrings', 'secondary', 0.30),
    ('sumo-deadlift', 'glutes', 'primary', 0.90), ('sumo-deadlift', 'quads', 'primary', 0.70), ('sumo-deadlift', 'adductors', 'primary', 0.70),
    ('sumo-deadlift', 'hamstrings', 'secondary', 0.60), ('sumo-deadlift', 'lower_back', 'secondary', 0.60), ('sumo-deadlift', 'traps', 'secondary', 0.30),
    ('kettlebell-swing', 'glutes', 'primary', 1.00), ('kettlebell-swing', 'hamstrings', 'primary', 0.80),
    ('kettlebell-swing', 'lower_back', 'secondary', 0.50), ('kettlebell-swing', 'forearms', 'secondary', 0.30), ('kettlebell-swing', 'front_delts', 'stabilizer', 0.20),
    ('walking-lunge', 'quads', 'primary', 1.00), ('walking-lunge', 'glutes', 'primary', 0.80),
    ('walking-lunge', 'hamstrings', 'secondary', 0.30), ('walking-lunge', 'adductors', 'secondary', 0.30),
    ('step-up', 'quads', 'primary', 1.00), ('step-up', 'glutes', 'primary', 0.80), ('step-up', 'calves', 'stabilizer', 0.20),
    ('glute-bridge', 'glutes', 'primary', 1.00), ('glute-bridge', 'hamstrings', 'secondary', 0.50),
    ('chin-up', 'lats', 'primary', 1.00), ('chin-up', 'biceps', 'primary', 0.80), ('chin-up', 'upper_back', 'secondary', 0.40),
    ('inverted-row', 'upper_back', 'primary', 0.90), ('inverted-row', 'lats', 'primary', 0.80),
    ('inverted-row', 'biceps', 'secondary', 0.50), ('inverted-row', 'rear_delts', 'secondary', 0.40),
    ('dumbbell-shrug', 'traps', 'primary', 1.00), ('dumbbell-shrug', 'forearms', 'secondary', 0.30),
    ('close-grip-bench-press', 'triceps', 'primary', 1.00), ('close-grip-bench-press', 'chest', 'primary', 0.70), ('close-grip-bench-press', 'front_delts', 'secondary', 0.40),
    ('skull-crusher', 'triceps', 'primary', 1.00),
    ('overhead-triceps-extension', 'triceps', 'primary', 1.00), ('overhead-triceps-extension', 'abs', 'stabilizer', 0.20),
    ('preacher-curl', 'biceps', 'primary', 1.00), ('preacher-curl', 'forearms', 'secondary', 0.30),
    ('cable-lateral-raise', 'side_delts', 'primary', 1.00), ('cable-lateral-raise', 'traps', 'secondary', 0.20),
    ('reverse-pec-deck', 'rear_delts', 'primary', 1.00), ('reverse-pec-deck', 'upper_back', 'secondary', 0.50), ('reverse-pec-deck', 'traps', 'secondary', 0.30),
    ('machine-shoulder-press', 'front_delts', 'primary', 1.00), ('machine-shoulder-press', 'side_delts', 'secondary', 0.50), ('machine-shoulder-press', 'triceps', 'secondary', 0.50),
    ('crunch', 'abs', 'primary', 1.00), ('crunch', 'obliques', 'secondary', 0.30),
    ('cable-crunch', 'abs', 'primary', 1.00), ('cable-crunch', 'obliques', 'secondary', 0.40),
    ('side-plank', 'obliques', 'primary', 1.00), ('side-plank', 'abs', 'secondary', 0.40), ('side-plank', 'lower_back', 'stabilizer', 0.20),
    ('dead-bug', 'abs', 'primary', 1.00), ('dead-bug', 'obliques', 'secondary', 0.30),
    ('russian-twist', 'obliques', 'primary', 1.00), ('russian-twist', 'abs', 'secondary', 0.50),
    ('ab-wheel-rollout', 'abs', 'primary', 1.00), ('ab-wheel-rollout', 'lats', 'secondary', 0.40),
    ('ab-wheel-rollout', 'obliques', 'secondary', 0.30), ('ab-wheel-rollout', 'lower_back', 'stabilizer', 0.30),
    ('farmers-walk', 'forearms', 'primary', 1.00), ('farmers-walk', 'traps', 'primary', 0.80),
    ('farmers-walk', 'abs', 'secondary', 0.40), ('farmers-walk', 'quads', 'secondary', 0.30)
) AS v(slug, muscle_code, role, ratio)
JOIN catalog.exercises e ON e.slug = v.slug
JOIN catalog.muscle_groups mg ON mg.code = v.muscle_code;

-- ---------------------------------------------------------------------
-- catalog.exercise_equipment (bài không có dòng nào = bài tự thân)
-- ---------------------------------------------------------------------
INSERT INTO catalog.exercise_equipment (exercise_id, equipment_id, is_optional)
SELECT e.id, eq.id, v.optional
FROM (VALUES
    ('treadmill-run', 'treadmill', false),
    ('incline-treadmill-walk', 'treadmill', false),
    ('stationary-bike', 'stationary_bike', false),
    ('rowing-machine', 'rowing_machine', false),
    ('jump-rope', 'jump_rope', false),
    ('box-jump', 'plyo_box', false),
    ('medicine-ball-slam', 'medicine_ball', false),
    ('smith-machine-squat', 'smith_machine', false),
    ('sumo-deadlift', 'barbell', false),
    ('kettlebell-swing', 'kettlebell', false),
    ('walking-lunge', 'dumbbell', true),
    ('step-up', 'plyo_box', false), ('step-up', 'dumbbell', true),
    ('chin-up', 'pull_up_bar', false),
    ('inverted-row', 'smith_machine', false),
    ('dumbbell-shrug', 'dumbbell', false),
    ('close-grip-bench-press', 'barbell', false), ('close-grip-bench-press', 'flat_bench', false),
    ('skull-crusher', 'ez_bar', false), ('skull-crusher', 'flat_bench', false),
    ('overhead-triceps-extension', 'dumbbell', false),
    ('preacher-curl', 'ez_bar', false), ('preacher-curl', 'adjustable_bench', false),
    ('cable-lateral-raise', 'cable_crossover', false),
    ('reverse-pec-deck', 'pec_deck_machine', false),
    ('machine-shoulder-press', 'shoulder_press_machine', false),
    ('cable-crunch', 'cable_crossover', false),
    ('russian-twist', 'medicine_ball', true),
    ('ab-wheel-rollout', 'ab_wheel', false),
    ('farmers-walk', 'dumbbell', false), ('farmers-walk', 'kettlebell', true)
) AS v(slug, equipment_code, optional)
JOIN catalog.exercises e ON e.slug = v.slug
JOIN catalog.equipment eq ON eq.code = v.equipment_code;

-- ---------------------------------------------------------------------
-- catalog.exercise_instructions
-- ---------------------------------------------------------------------
INSERT INTO catalog.exercise_instructions (exercise_id, step_no, content)
SELECT e.id, v.step_no, v.content
FROM (VALUES
    ('treadmill-run', 1, 'Khởi động đi bộ 3–5 phút, đứng giữa băng chạy.'),
    ('treadmill-run', 2, 'Tăng tốc độ đến mức chạy nói chuyện được ngắt quãng, tay đánh tự nhiên.'),
    ('treadmill-run', 3, 'Tiếp đất bằng giữa bàn chân, giảm tốc dần 3 phút cuối.'),
    ('incline-treadmill-walk', 1, 'Chỉnh độ dốc 8–15% và tốc độ 4–5.5 km/h.'),
    ('incline-treadmill-walk', 2, 'Đi bộ thẳng người, không vịn tay vào máy.'),
    ('incline-treadmill-walk', 3, 'Duy trì nhịp tim vùng 2 trong suốt thời gian tập.'),
    ('stationary-bike', 1, 'Chỉnh yên để gối hơi chùng khi bàn đạp ở điểm thấp nhất.'),
    ('stationary-bike', 2, 'Đạp đều, giữ lưng thẳng, vai thả lỏng.'),
    ('stationary-bike', 3, 'Điều chỉnh kháng lực theo cường độ mục tiêu.'),
    ('rowing-machine', 1, 'Ngồi, cố định chân, nắm tay cầm, gối co sát ngực.'),
    ('rowing-machine', 2, 'Đạp chân trước, ngả thân nhẹ rồi kéo tay cầm về bụng.'),
    ('rowing-machine', 3, 'Duỗi tay, gập thân rồi co gối trở về theo thứ tự ngược lại.'),
    ('jump-rope', 1, 'Cầm dây hai bên hông, khuỷu tay sát thân.'),
    ('jump-rope', 2, 'Quay dây bằng cổ tay, bật nhẹ bằng mũi chân.'),
    ('jump-rope', 3, 'Giữ nhịp đều, tiếp đất mềm.'),
    ('box-jump', 1, 'Đứng cách bục khoảng nửa bước, chân rộng bằng hông.'),
    ('box-jump', 2, 'Hạ hông, vung tay và bật nhảy lên bục, tiếp đất hai chân mềm.'),
    ('box-jump', 3, 'Đứng thẳng trên bục rồi bước xuống, không nhảy lùi xuống.'),
    ('jump-squat', 1, 'Đứng chân rộng bằng vai, hạ người squat.'),
    ('jump-squat', 2, 'Bật nhảy thẳng lên, duỗi hông và gối hoàn toàn.'),
    ('jump-squat', 3, 'Tiếp đất mềm bằng giữa bàn chân và chuyển ngay vào squat tiếp theo.'),
    ('burpee', 1, 'Từ tư thế đứng, ngồi xổm đặt tay xuống sàn.'),
    ('burpee', 2, 'Bật chân về sau thành tư thế chống đẩy, hít đất một lần.'),
    ('burpee', 3, 'Thu chân về và bật nhảy lên, vỗ tay trên đầu.'),
    ('mountain-climber', 1, 'Vào tư thế chống đẩy, tay ngay dưới vai.'),
    ('mountain-climber', 2, 'Kéo gối phải về ngực rồi đổi chân thật nhanh.'),
    ('mountain-climber', 3, 'Giữ hông ngang vai trong suốt bài.'),
    ('medicine-ball-slam', 1, 'Cầm bóng tạ, đứng chân rộng bằng vai.'),
    ('medicine-ball-slam', 2, 'Nâng bóng qua đầu, kiễng nhẹ chân.'),
    ('medicine-ball-slam', 3, 'Gập thân đập bóng mạnh xuống sàn trước mặt, nhặt lại và lặp.'),
    ('standing-hamstring-stretch', 1, 'Đứng thẳng, đặt gót một chân lên bậc thấp.'),
    ('standing-hamstring-stretch', 2, 'Giữ lưng thẳng, gập hông về trước đến khi đùi sau căng.'),
    ('standing-hamstring-stretch', 3, 'Giữ 30 giây, đổi chân.'),
    ('kneeling-hip-flexor-stretch', 1, 'Quỳ một gối, chân trước tạo góc 90°.'),
    ('kneeling-hip-flexor-stretch', 2, 'Siết mông, đẩy hông về trước đến khi hông trước căng.'),
    ('kneeling-hip-flexor-stretch', 3, 'Giữ 30 giây, đổi bên.'),
    ('doorway-chest-stretch', 1, 'Đặt cẳng tay lên khung cửa, khuỷu ngang vai.'),
    ('doorway-chest-stretch', 2, 'Bước một chân qua cửa, ngực đẩy về trước.'),
    ('doorway-chest-stretch', 3, 'Giữ 30 giây, thở đều.'),
    ('childs-pose', 1, 'Quỳ, ngồi lên gót chân, gối rộng bằng hông.'),
    ('childs-pose', 2, 'Gập người về trước, duỗi tay xa nhất có thể.'),
    ('childs-pose', 3, 'Thả lỏng trán xuống sàn, thở sâu 30–60 giây.'),
    ('cat-cow', 1, 'Vào tư thế bò, tay dưới vai, gối dưới hông.'),
    ('cat-cow', 2, 'Hít vào võng lưng, ngẩng đầu (bò).'),
    ('cat-cow', 3, 'Thở ra cong lưng lên, cúi đầu (mèo), lặp chậm.'),
    ('worlds-greatest-stretch', 1, 'Bước dài thành tư thế lunge, tay cùng bên chân trước đặt xuống sàn.'),
    ('worlds-greatest-stretch', 2, 'Hạ khuỷu tay về phía mắt cá chân trước.'),
    ('worlds-greatest-stretch', 3, 'Xoay thân mở tay lên trần, rồi duỗi chân trước để giãn đùi sau.'),
    ('smith-machine-squat', 1, 'Đặt thanh lên lưng trên, chân hơi đặt trước thanh.'),
    ('smith-machine-squat', 2, 'Mở khoá, hạ người đến khi đùi song song sàn.'),
    ('smith-machine-squat', 3, 'Đẩy người đứng lên, khoá lại khi xong hiệp.'),
    ('sumo-deadlift', 1, 'Đứng chân rộng, mũi chân hướng ra ngoài, thanh sát ống chân.'),
    ('sumo-deadlift', 2, 'Nắm thanh trong gối, hạ hông, ngực mở.'),
    ('sumo-deadlift', 3, 'Đẩy gối ra ngoài, đạp sàn kéo tạ đến khi đứng thẳng.'),
    ('kettlebell-swing', 1, 'Đứng chân rộng hơn vai, tạ ấm trước mặt.'),
    ('kettlebell-swing', 2, 'Gập hông kéo tạ ra sau giữa hai đùi.'),
    ('kettlebell-swing', 3, 'Đẩy hông bùng nổ vung tạ lên ngang ngực, để tạ rơi tự nhiên về.'),
    ('walking-lunge', 1, 'Đứng thẳng, có thể cầm tạ đơn hai bên.'),
    ('walking-lunge', 2, 'Bước dài về trước, hạ gối sau gần chạm sàn.'),
    ('walking-lunge', 3, 'Đẩy chân trước đứng lên và bước tiếp chân kia.'),
    ('step-up', 1, 'Đặt cả bàn chân lên bục cao ngang gối.'),
    ('step-up', 2, 'Dồn lực chân trên bục đẩy người đứng thẳng.'),
    ('step-up', 3, 'Hạ xuống có kiểm soát, đổi chân sau đủ số lần.'),
    ('glute-bridge', 1, 'Nằm ngửa, gập gối, bàn chân đặt sát mông.'),
    ('glute-bridge', 2, 'Siết mông đẩy hông lên đến khi thân thẳng từ vai đến gối.'),
    ('glute-bridge', 3, 'Giữ 1 giây rồi hạ hông chậm.'),
    ('chin-up', 1, 'Treo người trên xà, tay ngửa rộng bằng vai.'),
    ('chin-up', 2, 'Kéo người lên đến khi cằm qua xà.'),
    ('chin-up', 3, 'Hạ người chậm đến khi tay gần duỗi thẳng.'),
    ('inverted-row', 1, 'Đặt thanh Smith ngang hông, nằm dưới thanh và nắm tay rộng hơn vai.'),
    ('inverted-row', 2, 'Giữ thân thẳng, kéo ngực chạm thanh.'),
    ('inverted-row', 3, 'Hạ người chậm đến khi tay duỗi.'),
    ('dumbbell-shrug', 1, 'Đứng thẳng, tạ đơn hai bên thân.'),
    ('dumbbell-shrug', 2, 'Nhún vai thẳng lên về phía tai.'),
    ('dumbbell-shrug', 3, 'Giữ 1 giây rồi hạ chậm.'),
    ('close-grip-bench-press', 1, 'Nằm ghế, nắm thanh rộng bằng vai.'),
    ('close-grip-bench-press', 2, 'Hạ tạ về ngực dưới, khuỷu tay sát thân.'),
    ('close-grip-bench-press', 3, 'Đẩy tạ lên đến khi duỗi tay.'),
    ('skull-crusher', 1, 'Nằm ghế, giữ thanh EZ thẳng trên vai.'),
    ('skull-crusher', 2, 'Gập khuỷu hạ thanh về phía trán, cánh tay cố định.'),
    ('skull-crusher', 3, 'Duỗi khuỷu đưa thanh về vị trí đầu.'),
    ('overhead-triceps-extension', 1, 'Ngồi hoặc đứng, hai tay giữ một tạ đơn qua đầu.'),
    ('overhead-triceps-extension', 2, 'Gập khuỷu hạ tạ sau gáy, khuỷu hướng lên trần.'),
    ('overhead-triceps-extension', 3, 'Duỗi tay đưa tạ lên lại.'),
    ('preacher-curl', 1, 'Ngồi, tì mặt sau cánh tay lên đệm nghiêng.'),
    ('preacher-curl', 2, 'Cuốn thanh EZ lên đến khi cẳng tay gần thẳng đứng.'),
    ('preacher-curl', 3, 'Hạ chậm đến khi tay gần duỗi, không khoá khuỷu.'),
    ('cable-lateral-raise', 1, 'Đứng nghiêng cạnh ròng rọc thấp, tay xa nắm tay cầm.'),
    ('cable-lateral-raise', 2, 'Dang tay sang ngang đến ngang vai.'),
    ('cable-lateral-raise', 3, 'Hạ chậm, đổi bên sau đủ số lần.'),
    ('reverse-pec-deck', 1, 'Ngồi úp mặt vào lưng ghế máy ép ngực, tay nắm tay cầm.'),
    ('reverse-pec-deck', 2, 'Mở tay về sau theo vòng cung, siết bả vai.'),
    ('reverse-pec-deck', 3, 'Đưa tay về chậm.'),
    ('machine-shoulder-press', 1, 'Chỉnh ghế để tay cầm ngang vai.'),
    ('machine-shoulder-press', 2, 'Đẩy tay cầm lên đến khi gần duỗi tay.'),
    ('machine-shoulder-press', 3, 'Hạ chậm về ngang vai.'),
    ('crunch', 1, 'Nằm ngửa, gập gối, tay đặt nhẹ sau đầu.'),
    ('crunch', 2, 'Cuộn vai khỏi sàn bằng cơ bụng, không kéo cổ.'),
    ('crunch', 3, 'Hạ chậm về vị trí đầu.'),
    ('cable-crunch', 1, 'Quỳ trước ròng rọc cao, cầm dây hai bên đầu.'),
    ('cable-crunch', 2, 'Gập thân kéo khuỷu về phía gối, hông cố định.'),
    ('cable-crunch', 3, 'Duỗi thân về chậm.'),
    ('side-plank', 1, 'Nằm nghiêng, chống khuỷu tay ngay dưới vai.'),
    ('side-plank', 2, 'Nâng hông lên thành đường thẳng từ đầu đến chân.'),
    ('side-plank', 3, 'Giữ trong thời gian mục tiêu rồi đổi bên.'),
    ('dead-bug', 1, 'Nằm ngửa, tay thẳng lên trần, gối co 90°.'),
    ('dead-bug', 2, 'Duỗi tay và chân đối diện ra xa, lưng dưới áp sàn.'),
    ('dead-bug', 3, 'Thu về và đổi bên.'),
    ('russian-twist', 1, 'Ngồi, ngả thân 45°, gót chân chạm sàn hoặc nhấc lên.'),
    ('russian-twist', 2, 'Xoay vai sang phải, chạm tay/bóng xuống sàn.'),
    ('russian-twist', 3, 'Xoay sang trái, lặp luân phiên.'),
    ('ab-wheel-rollout', 1, 'Quỳ, hai tay nắm con lăn dưới vai.'),
    ('ab-wheel-rollout', 2, 'Lăn về trước đến khi thân gần song song sàn, siết bụng.'),
    ('ab-wheel-rollout', 3, 'Kéo con lăn về bằng cơ bụng.'),
    ('farmers-walk', 1, 'Nhặt tạ nặng hai tay, đứng thẳng, vai hạ xuống.'),
    ('farmers-walk', 2, 'Đi bộ bước ngắn, giữ thân thẳng.'),
    ('farmers-walk', 3, 'Đi hết quãng đường mục tiêu rồi đặt tạ xuống có kiểm soát.')
) AS v(slug, step_no, content)
JOIN catalog.exercises e ON e.slug = v.slug;

-- ---------------------------------------------------------------------
-- catalog.exercise_mistakes
-- ---------------------------------------------------------------------
INSERT INTO catalog.exercise_mistakes (exercise_id, code, title, description, correction_cue, at_risk_joint, ai_detectable, display_order)
SELECT e.id, v.code, v.title, v.description, v.cue, v.joint::catalog.joint_type, false, v.ord
FROM (VALUES
    ('treadmill-run', 'RUN_HEEL_STRIKE', 'Tiếp đất bằng gót', 'Sải chân quá dài, tiếp đất bằng gót gây sốc lên gối.', 'Rút ngắn sải chân, tăng nhịp bước.', 'knee', 1),
    ('incline-treadmill-walk', 'INCLINE_WALK_HOLD_RAILS', 'Vịn tay vào máy', 'Vịn tay làm giảm cường độ và lệch tư thế.', 'Thả tay đánh tự nhiên, giảm độ dốc nếu cần.', NULL, 1),
    ('stationary-bike', 'BIKE_SEAT_TOO_LOW', 'Yên quá thấp', 'Gối gập nhiều gây áp lực khớp gối.', 'Nâng yên để gối hơi chùng ở điểm thấp.', 'knee', 1),
    ('rowing-machine', 'ROW_ARMS_FIRST', 'Kéo tay trước chân', 'Kéo bằng tay trước khi đạp chân, mất lực.', 'Thứ tự: chân → thân → tay.', 'spine', 1),
    ('jump-rope', 'JUMP_ROPE_HIGH_JUMP', 'Nhảy quá cao', 'Bật quá cao tốn sức và gây áp lực cổ chân.', 'Chỉ nhấc chân vừa đủ cho dây qua.', 'ankle', 1),
    ('box-jump', 'BOX_JUMP_STIFF_LANDING', 'Tiếp đất cứng', 'Tiếp đất gối thẳng, dồn lực vào khớp.', 'Tiếp đất mềm, gối và hông chùng.', 'knee', 1),
    ('box-jump', 'BOX_JUMP_JUMP_DOWN', 'Nhảy lùi xuống', 'Nhảy lùi khỏi bục tăng nguy cơ chấn thương gân gót.', 'Bước xuống từng chân.', 'ankle', 2),
    ('jump-squat', 'JUMP_SQUAT_KNEE_VALGUS', 'Gối chụm khi tiếp đất', 'Gối đổ vào trong khi tiếp đất.', 'Đẩy gối theo hướng mũi chân.', 'knee', 1),
    ('burpee', 'BURPEE_HIP_SAG', 'Võng hông khi chống đẩy', 'Hông rơi xuống ở tư thế chống đẩy.', 'Siết bụng giữ thân thẳng.', 'spine', 1),
    ('mountain-climber', 'CLIMBER_HIPS_HIGH', 'Hông nhô cao', 'Hông nâng cao làm giảm tác dụng lên bụng.', 'Giữ hông ngang vai.', NULL, 1),
    ('medicine-ball-slam', 'SLAM_ROUNDED_BACK', 'Cong lưng khi nhặt bóng', 'Cúi cong lưng để nhặt bóng.', 'Gập hông, squat xuống nhặt bóng.', 'spine', 1),
    ('standing-hamstring-stretch', 'HAMSTRING_STRETCH_ROUNDED', 'Cong lưng khi giãn', 'Cong lưng thay vì gập hông.', 'Giữ lưng thẳng, gập từ hông.', 'spine', 1),
    ('kneeling-hip-flexor-stretch', 'HIP_FLEXOR_ARCH', 'Ưỡn lưng dưới', 'Ưỡn lưng thay vì đẩy hông.', 'Siết mông, nghiêng khung chậu ra sau.', 'spine', 1),
    ('doorway-chest-stretch', 'CHEST_STRETCH_OVERSTRETCH', 'Giãn quá mức', 'Bước quá sâu gây áp lực khớp vai trước.', 'Giãn đến khi căng nhẹ, không đau.', 'shoulder', 1),
    ('childs-pose', 'CHILDS_POSE_KNEE_PAIN', 'Đau gối khi ngồi', 'Ngồi lên gót gây đau gối.', 'Kê gối/đệm dưới mông.', 'knee', 1),
    ('cat-cow', 'CAT_COW_TOO_FAST', 'Làm quá nhanh', 'Chuyển động nhanh mất tác dụng linh hoạt cột sống.', 'Thực hiện chậm theo nhịp thở.', 'spine', 1),
    ('worlds-greatest-stretch', 'WGS_KNEE_COLLAPSE', 'Gối trước đổ vào', 'Gối chân trước đổ vào trong khi xoay thân.', 'Giữ gối thẳng hướng mũi chân.', 'knee', 1),
    ('smith-machine-squat', 'SMITH_FEET_UNDER_BAR', 'Chân đặt ngay dưới thanh', 'Gối dồn quá xa về trước.', 'Đặt chân hơi trước thanh.', 'knee', 1),
    ('sumo-deadlift', 'SUMO_KNEES_CAVE', 'Gối chụm vào', 'Gối đổ vào trong khi kéo.', 'Đẩy gối ra theo hướng mũi chân.', 'knee', 1),
    ('sumo-deadlift', 'SUMO_HIPS_TOO_LOW', 'Hông quá thấp', 'Hạ hông quá thấp như squat, tạ rời sàn khó.', 'Hông cao hơn gối, vai trước thanh.', 'spine', 2),
    ('kettlebell-swing', 'KB_SWING_SQUAT', 'Squat thay vì gập hông', 'Gập gối quá nhiều biến thành squat.', 'Đẩy hông ra sau, gối chùng nhẹ.', 'spine', 1),
    ('kettlebell-swing', 'KB_SWING_ARM_LIFT', 'Nâng tạ bằng tay', 'Dùng vai kéo tạ lên.', 'Lực đến từ hông, tay chỉ dẫn hướng.', 'shoulder', 2),
    ('walking-lunge', 'LUNGE_KNEE_VALGUS', 'Gối trước đổ vào', 'Gối chân trước lệch vào trong.', 'Giữ gối thẳng hướng mũi chân.', 'knee', 1),
    ('step-up', 'STEP_UP_PUSH_OFF', 'Đạp chân sau', 'Đạp mạnh chân dưới sàn để lên bục.', 'Dồn lực chân trên bục.', NULL, 1),
    ('glute-bridge', 'BRIDGE_LUMBAR_ARCH', 'Ưỡn lưng dưới', 'Ưỡn lưng thay vì duỗi hông.', 'Siết bụng và mông, dừng khi thân thẳng.', 'spine', 1),
    ('chin-up', 'CHINUP_KIPPING', 'Đung đưa lấy đà', 'Dùng đà để lên xà.', 'Siết bụng, kéo bằng lưng và tay trước.', 'shoulder', 1),
    ('inverted-row', 'INVERTED_ROW_HIP_SAG', 'Võng hông', 'Hông rơi xuống khi kéo.', 'Siết mông giữ thân thẳng.', 'spine', 1),
    ('dumbbell-shrug', 'SHRUG_ROLLING', 'Xoay vai', 'Xoay vai tròn khi nhún.', 'Chỉ nhún thẳng lên xuống.', 'shoulder', 1),
    ('close-grip-bench-press', 'CGBP_TOO_NARROW', 'Tay quá hẹp', 'Nắm quá hẹp gây áp lực cổ tay.', 'Nắm rộng bằng vai.', 'wrist', 1),
    ('skull-crusher', 'SKULL_ELBOW_FLARE', 'Khuỷu tay mở', 'Khuỷu tay mở rộng khi hạ.', 'Giữ khuỷu hướng lên trần.', 'elbow', 1),
    ('overhead-triceps-extension', 'OHTE_ELBOW_FLARE', 'Khuỷu tay mở rộng', 'Khuỷu tách xa nhau khi hạ tạ.', 'Giữ khuỷu gần đầu.', 'elbow', 1),
    ('preacher-curl', 'PREACHER_HYPEREXTEND', 'Duỗi khuỷu quá mức', 'Thả rơi tạ khoá khuỷu ở điểm thấp.', 'Hạ chậm, dừng trước khi khoá khuỷu.', 'elbow', 1),
    ('cable-lateral-raise', 'CABLE_LR_TORSO_LEAN', 'Nghiêng người', 'Nghiêng thân để nâng tay.', 'Đứng thẳng, giảm tạ.', 'spine', 1),
    ('reverse-pec-deck', 'REVERSE_PEC_SHRUG', 'Nhún vai', 'Dùng cơ cầu vai kéo.', 'Hạ vai, mở tay bằng vai sau.', 'shoulder', 1),
    ('machine-shoulder-press', 'MACHINE_OHP_ARCH', 'Ưỡn lưng', 'Lưng rời đệm khi đẩy nặng.', 'Giữ lưng áp đệm.', 'spine', 1),
    ('crunch', 'CRUNCH_NECK_PULL', 'Kéo cổ', 'Dùng tay kéo đầu lên.', 'Tay chỉ đỡ nhẹ, cằm cách ngực một nắm tay.', 'neck', 1),
    ('cable-crunch', 'CABLE_CRUNCH_HIP_HINGE', 'Gập hông thay vì gập bụng', 'Ngồi xuống gót thay vì cuộn thân.', 'Giữ hông cố định, cuộn cột sống.', 'spine', 1),
    ('side-plank', 'SIDE_PLANK_HIP_DROP', 'Hông rơi xuống', 'Hông võng xuống sàn.', 'Đẩy hông lên thành đường thẳng.', 'spine', 1),
    ('dead-bug', 'DEAD_BUG_BACK_ARCH', 'Lưng rời sàn', 'Lưng dưới võng khi duỗi chân.', 'Giảm biên độ, giữ lưng áp sàn.', 'spine', 1),
    ('russian-twist', 'TWIST_ROUNDED_BACK', 'Gù lưng', 'Lưng gù khi xoay.', 'Ngồi thẳng lưng, xoay từ ngực.', 'spine', 1),
    ('ab-wheel-rollout', 'ROLLOUT_LUMBAR_SAG', 'Võng lưng dưới', 'Lưng dưới võng khi lăn xa.', 'Siết bụng, chỉ lăn trong tầm kiểm soát.', 'spine', 1),
    ('farmers-walk', 'FARMER_LEAN', 'Nghiêng người', 'Thân nghiêng hoặc gù khi đi.', 'Đứng thẳng, vai hạ, bước ngắn.', 'spine', 1)
) AS v(slug, code, title, description, cue, joint, ord)
JOIN catalog.exercises e ON e.slug = v.slug;

-- ---------------------------------------------------------------------
-- catalog.exercise_alternatives
-- ---------------------------------------------------------------------
INSERT INTO catalog.exercise_alternatives (exercise_id, alternative_exercise_id, note)
SELECT a.id, b.id, v.note
FROM (VALUES
    ('treadmill-run',              'stationary-bike',            'Ít va chạm khớp gối.'),
    ('treadmill-run',              'rowing-machine',             'Cardio toàn thân khi máy chạy bận.'),
    ('stationary-bike',            'treadmill-run',              'Khi xe đạp bận.'),
    ('rowing-machine',             'stationary-bike',            'Khi máy chèo bận.'),
    ('incline-treadmill-walk',     'stationary-bike',            'Cường độ tương đương.'),
    ('box-jump',                   'jump-squat',                 'Không cần bục.'),
    ('jump-squat',                 'box-jump',                   'Giảm va chạm khi tiếp đất.'),
    ('burpee',                     'mountain-climber',           'Cường độ thấp hơn.'),
    ('smith-machine-squat',        'barbell-back-squat',         'Tạ tự do, tăng ổn định cơ.'),
    ('smith-machine-squat',        'goblet-squat',               'Khi máy Smith bận.'),
    ('barbell-back-squat',         'smith-machine-squat',        'Quỹ đạo cố định, an toàn khi tập một mình.'),
    ('sumo-deadlift',              'conventional-deadlift',      'Biến thể chân hẹp.'),
    ('conventional-deadlift',      'sumo-deadlift',              'Giảm tải lưng dưới với người hông linh hoạt.'),
    ('kettlebell-swing',           'romanian-deadlift',          'Cùng chuyển động gập hông, tải nặng hơn.'),
    ('walking-lunge',              'bulgarian-split-squat',      'Tập tại chỗ.'),
    ('walking-lunge',              'step-up',                    'Ít đòi hỏi thăng bằng hơn.'),
    ('step-up',                    'walking-lunge',              'Không cần bục.'),
    ('glute-bridge',               'hip-thrust',                 'Tăng tải bằng tạ đòn.'),
    ('hip-thrust',                 'glute-bridge',               'Không cần thiết bị.'),
    ('chin-up',                    'pull-up',                    'Nhấn lưng xô nhiều hơn.'),
    ('chin-up',                    'lat-pulldown',               'Điều chỉnh được mức tạ.'),
    ('pull-up',                    'chin-up',                    'Tay ngửa dễ hơn cho người mới.'),
    ('inverted-row',               'seated-cable-row',           'Khi máy Smith bận.'),
    ('inverted-row',               'barbell-row',                'Tăng tải.'),
    ('close-grip-bench-press',     'cable-triceps-pushdown',     'Cô lập tay sau, ít tải vai.'),
    ('skull-crusher',              'overhead-triceps-extension', 'Dùng tạ đơn.'),
    ('skull-crusher',              'cable-triceps-pushdown',     'Ít áp lực khuỷu tay.'),
    ('overhead-triceps-extension', 'skull-crusher',              'Tăng tải bằng thanh EZ.'),
    ('preacher-curl',              'barbell-curl',               'Khi ghế preacher bận.'),
    ('preacher-curl',              'hammer-curl',                'Dùng tạ đơn.'),
    ('cable-lateral-raise',        'dumbbell-lateral-raise',     'Khi máy cáp bận.'),
    ('dumbbell-lateral-raise',     'cable-lateral-raise',        'Giữ căng cơ suốt biên độ.'),
    ('reverse-pec-deck',           'face-pull',                  'Dùng máy cáp.'),
    ('face-pull',                  'reverse-pec-deck',           'Khi máy cáp bận.'),
    ('machine-shoulder-press',     'dumbbell-shoulder-press',    'Tạ tự do.'),
    ('machine-shoulder-press',     'overhead-press',             'Tăng tải tối đa.'),
    ('crunch',                     'cable-crunch',               'Tăng tải bằng cáp.'),
    ('cable-crunch',               'crunch',                     'Không cần thiết bị.'),
    ('side-plank',                 'russian-twist',              'Tập cơ liên sườn có chuyển động.'),
    ('plank',                      'dead-bug',                   'Ít áp lực vai.'),
    ('ab-wheel-rollout',           'plank',                      'Dễ hơn cho người mới.'),
    ('ab-wheel-rollout',           'hanging-leg-raise',          'Khi không có con lăn.'),
    ('farmers-walk',               'dumbbell-shrug',             'Tập tại chỗ cho cơ cầu vai.')
) AS v(slug, alt_slug, note)
JOIN catalog.exercises a ON a.slug = v.slug
JOIN catalog.exercises b ON b.slug = v.alt_slug;
