-- =====================================================================
-- Smart Workout AI — Seed: Exercise Wiki
-- Bài tập + nhóm cơ + thiết bị + các bước + lỗi sai thường gặp + bài thay thế
-- =====================================================================

-- ---------------------------------------------------------------------
-- catalog.exercises
-- ---------------------------------------------------------------------
INSERT INTO catalog.exercises (slug, name, name_en, description, difficulty_level_id, category, mechanic, force_type,
                               is_unilateral, met_value, supports_ai_tracking, status, published_at)
SELECT v.slug, v.name, v.name_en, v.description, d.id, 'strength', v.mechanic::catalog.mechanic_type,
       v.force::catalog.force_type, v.unilateral, v.met, v.ai, 'published', now()
FROM (VALUES
    -- Chân
    ('barbell-back-squat',      'Squat với tạ đòn',             'Barbell Back Squat',       'Bài đa khớp nền tảng cho thân dưới, tạ đặt trên lưng trên.',                 'intermediate', 'compound',  'push',   false, 5.0, true),
    ('goblet-squat',            'Goblet Squat',                 'Goblet Squat',             'Squat ôm tạ trước ngực, dễ học, giữ lưng thẳng tốt.',                       'beginner',     'compound',  'push',   false, 5.0, true),
    ('leg-press',               'Đạp đùi máy',                  'Leg Press',                'Đạp tạ bằng máy, tải nặng cho đùi trước với ít áp lực cột sống.',            'beginner',     'compound',  'push',   false, 5.0, false),
    ('bulgarian-split-squat',   'Bulgarian Split Squat',        'Bulgarian Split Squat',    'Squat một chân, chân sau gác lên ghế.',                                     'intermediate', 'compound',  'push',   true,  5.0, true),
    ('leg-extension',           'Đá đùi máy',                   'Leg Extension',            'Bài cô lập đùi trước trên máy.',                                            'beginner',     'isolation', 'push',   false, 4.0, false),
    ('lying-leg-curl',          'Móc đùi máy',                  'Lying Leg Curl',           'Bài cô lập đùi sau trên máy.',                                              'beginner',     'isolation', 'pull',   false, 4.0, false),
    ('standing-calf-raise',     'Nhón bắp chân',                'Standing Calf Raise',      'Nhón gót tập bắp chân, có thể cầm thêm tạ đơn.',                            'beginner',     'isolation', 'push',   false, 3.5, false),
    ('conventional-deadlift',   'Deadlift',                     'Conventional Deadlift',    'Kéo tạ từ sàn, tác động toàn bộ chuỗi cơ sau.',                             'advanced',     'compound',  'pull',   false, 6.0, true),
    ('romanian-deadlift',       'Romanian Deadlift',            'Romanian Deadlift',        'Gập hông với gối hơi chùng, tập trung đùi sau và mông.',                    'intermediate', 'compound',  'pull',   false, 5.0, true),
    ('hip-thrust',              'Hip Thrust',                   'Barbell Hip Thrust',       'Đẩy hông với tạ đòn, lưng tựa ghế, cô lập mông.',                           'intermediate', 'compound',  'push',   false, 4.5, false),
    -- Ngực
    ('barbell-bench-press',     'Đẩy ngực với tạ đòn',          'Barbell Bench Press',      'Bài đẩy ngang cơ bản trên ghế phẳng.',                                      'intermediate', 'compound',  'push',   false, 5.0, true),
    ('dumbbell-bench-press',    'Đẩy ngực tạ đơn',              'Dumbbell Bench Press',     'Đẩy ngực với tạ đơn, biên độ rộng hơn tạ đòn.',                             'beginner',     'compound',  'push',   false, 5.0, true),
    ('incline-dumbbell-press',  'Đẩy ngực dốc lên tạ đơn',      'Incline Dumbbell Press',   'Đẩy tạ đơn trên ghế dốc 30–45°, ưu tiên ngực trên.',                         'intermediate', 'compound',  'push',   false, 5.0, false),
    ('machine-chest-press',     'Đẩy ngực máy',                 'Machine Chest Press',      'Đẩy ngực trên máy ngồi, quỹ đạo cố định an toàn.',                          'beginner',     'compound',  'push',   false, 4.5, false),
    ('push-up',                 'Hít đất',                      'Push-up',                  'Bài tự thân đẩy ngực, có thể tập mọi nơi.',                                 'beginner',     'compound',  'push',   false, 3.8, true),
    ('cable-chest-fly',         'Ép ngực với cáp',              'Cable Chest Fly',          'Ép ngực trên máy kéo cáp đôi, giữ căng cơ suốt biên độ.',                   'beginner',     'isolation', 'push',   false, 4.0, false),
    ('pec-deck-fly',            'Ép ngực máy',                  'Pec Deck Fly',             'Ép ngực trên máy bướm.',                                                    'beginner',     'isolation', 'push',   false, 4.0, false),
    ('chest-dip',               'Dips ngực',                    'Chest Dip',                'Chống đẩy trên xà kép, nghiêng người về trước.',                            'intermediate', 'compound',  'push',   false, 5.0, false),
    -- Lưng
    ('dumbbell-row',            'Chèo tạ đơn một tay',          'One-Arm Dumbbell Row',     'Kéo tạ đơn về hông, tay và gối tựa ghế.',                                   'beginner',     'compound',  'pull',   true,  4.5, true),
    ('barbell-row',             'Chèo tạ đòn',                  'Bent-Over Barbell Row',    'Cúi người kéo tạ đòn về bụng.',                                             'intermediate', 'compound',  'pull',   false, 5.0, true),
    ('lat-pulldown',            'Kéo xô máy',                   'Lat Pulldown',             'Kéo thanh cáp từ trên xuống trước ngực.',                                   'beginner',     'compound',  'pull',   false, 4.5, false),
    ('pull-up',                 'Hít xà đơn',                   'Pull-up',                  'Kéo người lên xà, tay sấp rộng hơn vai.',                                   'advanced',     'compound',  'pull',   false, 6.0, true),
    ('seated-cable-row',        'Kéo cáp ngồi',                 'Seated Cable Row',         'Kéo cáp ngang về bụng ở tư thế ngồi.',                                      'beginner',     'compound',  'pull',   false, 4.5, false),
    -- Vai
    ('overhead-press',          'Đẩy vai tạ đòn đứng',          'Overhead Press',           'Đẩy tạ đòn từ ngực lên qua đầu khi đứng.',                                  'intermediate', 'compound',  'push',   false, 5.0, true),
    ('dumbbell-shoulder-press', 'Đẩy vai tạ đơn',               'Dumbbell Shoulder Press',  'Đẩy tạ đơn qua đầu khi ngồi ghế dựa thẳng.',                                'beginner',     'compound',  'push',   false, 4.5, false),
    ('dumbbell-lateral-raise',  'Dang tạ đơn sang ngang',       'Dumbbell Lateral Raise',   'Dang tay sang ngang với tạ đơn, cô lập vai giữa.',                          'beginner',     'isolation', 'push',   false, 3.5, false),
    ('face-pull',               'Face Pull',                    'Cable Face Pull',          'Kéo dây cáp về mặt, tập vai sau và lưng trên.',                             'beginner',     'isolation', 'pull',   false, 3.5, false),
    -- Tay
    ('barbell-curl',            'Cuốn tạ đòn',                  'Barbell Curl',             'Cuốn tạ đòn tập tay trước.',                                                'beginner',     'isolation', 'pull',   false, 3.5, true),
    ('hammer-curl',             'Cuốn búa tạ đơn',              'Dumbbell Hammer Curl',     'Cuốn tạ đơn tay cầm trung tính.',                                           'beginner',     'isolation', 'pull',   false, 3.5, false),
    ('cable-triceps-pushdown',  'Kéo cáp tay sau',              'Cable Triceps Pushdown',   'Duỗi khuỷu tay đẩy cáp xuống, cô lập tay sau.',                             'beginner',     'isolation', 'push',   false, 3.5, false),
    -- Bụng
    ('plank',                   'Plank',                        'Plank',                    'Giữ thân thẳng trên cẳng tay và mũi chân.',                                 'beginner',     'isolation', 'static', false, 3.0, true),
    ('hanging-leg-raise',       'Treo xà nâng chân',            'Hanging Leg Raise',        'Treo người trên xà, nâng chân lên ngang hông hoặc cao hơn.',                'intermediate', 'isolation', 'pull',   false, 4.0, false)
) AS v(slug, name, name_en, description, difficulty, mechanic, force, unilateral, met, ai)
JOIN catalog.difficulty_levels d ON d.code = v.difficulty;

-- ---------------------------------------------------------------------
-- catalog.exercise_muscles
-- ---------------------------------------------------------------------
INSERT INTO catalog.exercise_muscles (exercise_id, muscle_group_id, role, activation_ratio)
SELECT e.id, mg.id, v.role::catalog.muscle_role, v.ratio
FROM (VALUES
    ('barbell-back-squat', 'quads', 'primary', 1.00), ('barbell-back-squat', 'glutes', 'primary', 0.80),
    ('barbell-back-squat', 'hamstrings', 'secondary', 0.40), ('barbell-back-squat', 'lower_back', 'stabilizer', 0.30),
    ('barbell-back-squat', 'abs', 'stabilizer', 0.20),
    ('goblet-squat', 'quads', 'primary', 1.00), ('goblet-squat', 'glutes', 'primary', 0.70), ('goblet-squat', 'abs', 'stabilizer', 0.30),
    ('leg-press', 'quads', 'primary', 1.00), ('leg-press', 'glutes', 'secondary', 0.50), ('leg-press', 'hamstrings', 'secondary', 0.30),
    ('bulgarian-split-squat', 'quads', 'primary', 1.00), ('bulgarian-split-squat', 'glutes', 'primary', 0.80),
    ('bulgarian-split-squat', 'hamstrings', 'secondary', 0.30), ('bulgarian-split-squat', 'adductors', 'secondary', 0.30),
    ('leg-extension', 'quads', 'primary', 1.00),
    ('lying-leg-curl', 'hamstrings', 'primary', 1.00), ('lying-leg-curl', 'calves', 'secondary', 0.20),
    ('standing-calf-raise', 'calves', 'primary', 1.00),
    ('conventional-deadlift', 'hamstrings', 'primary', 0.90), ('conventional-deadlift', 'glutes', 'primary', 0.90),
    ('conventional-deadlift', 'lower_back', 'primary', 0.80), ('conventional-deadlift', 'quads', 'secondary', 0.40),
    ('conventional-deadlift', 'traps', 'secondary', 0.40), ('conventional-deadlift', 'forearms', 'secondary', 0.30),
    ('romanian-deadlift', 'hamstrings', 'primary', 1.00), ('romanian-deadlift', 'glutes', 'primary', 0.70),
    ('romanian-deadlift', 'lower_back', 'secondary', 0.50), ('romanian-deadlift', 'forearms', 'stabilizer', 0.20),
    ('hip-thrust', 'glutes', 'primary', 1.00), ('hip-thrust', 'hamstrings', 'secondary', 0.40), ('hip-thrust', 'quads', 'secondary', 0.20),
    ('barbell-bench-press', 'chest', 'primary', 1.00), ('barbell-bench-press', 'triceps', 'secondary', 0.50), ('barbell-bench-press', 'front_delts', 'secondary', 0.50),
    ('dumbbell-bench-press', 'chest', 'primary', 1.00), ('dumbbell-bench-press', 'triceps', 'secondary', 0.50), ('dumbbell-bench-press', 'front_delts', 'secondary', 0.50),
    ('incline-dumbbell-press', 'chest', 'primary', 1.00), ('incline-dumbbell-press', 'front_delts', 'secondary', 0.60), ('incline-dumbbell-press', 'triceps', 'secondary', 0.40),
    ('machine-chest-press', 'chest', 'primary', 1.00), ('machine-chest-press', 'triceps', 'secondary', 0.40), ('machine-chest-press', 'front_delts', 'secondary', 0.40),
    ('push-up', 'chest', 'primary', 1.00), ('push-up', 'triceps', 'secondary', 0.50), ('push-up', 'front_delts', 'secondary', 0.40), ('push-up', 'abs', 'stabilizer', 0.30),
    ('cable-chest-fly', 'chest', 'primary', 1.00), ('cable-chest-fly', 'front_delts', 'secondary', 0.30),
    ('pec-deck-fly', 'chest', 'primary', 1.00), ('pec-deck-fly', 'front_delts', 'secondary', 0.20),
    ('chest-dip', 'chest', 'primary', 0.90), ('chest-dip', 'triceps', 'primary', 0.80), ('chest-dip', 'front_delts', 'secondary', 0.40),
    ('dumbbell-row', 'lats', 'primary', 1.00), ('dumbbell-row', 'upper_back', 'secondary', 0.60),
    ('dumbbell-row', 'rear_delts', 'secondary', 0.40), ('dumbbell-row', 'biceps', 'secondary', 0.40),
    ('barbell-row', 'lats', 'primary', 1.00), ('barbell-row', 'upper_back', 'primary', 0.80), ('barbell-row', 'rear_delts', 'secondary', 0.40),
    ('barbell-row', 'biceps', 'secondary', 0.40), ('barbell-row', 'lower_back', 'stabilizer', 0.40),
    ('lat-pulldown', 'lats', 'primary', 1.00), ('lat-pulldown', 'biceps', 'secondary', 0.50), ('lat-pulldown', 'upper_back', 'secondary', 0.40),
    ('pull-up', 'lats', 'primary', 1.00), ('pull-up', 'biceps', 'secondary', 0.60), ('pull-up', 'upper_back', 'secondary', 0.50), ('pull-up', 'forearms', 'secondary', 0.30),
    ('seated-cable-row', 'lats', 'primary', 0.90), ('seated-cable-row', 'upper_back', 'primary', 0.90),
    ('seated-cable-row', 'biceps', 'secondary', 0.40), ('seated-cable-row', 'rear_delts', 'secondary', 0.30),
    ('overhead-press', 'front_delts', 'primary', 1.00), ('overhead-press', 'side_delts', 'secondary', 0.50),
    ('overhead-press', 'triceps', 'secondary', 0.60), ('overhead-press', 'abs', 'stabilizer', 0.30),
    ('dumbbell-shoulder-press', 'front_delts', 'primary', 1.00), ('dumbbell-shoulder-press', 'side_delts', 'secondary', 0.50), ('dumbbell-shoulder-press', 'triceps', 'secondary', 0.50),
    ('dumbbell-lateral-raise', 'side_delts', 'primary', 1.00), ('dumbbell-lateral-raise', 'traps', 'secondary', 0.20),
    ('face-pull', 'rear_delts', 'primary', 1.00), ('face-pull', 'traps', 'secondary', 0.50), ('face-pull', 'upper_back', 'secondary', 0.50),
    ('barbell-curl', 'biceps', 'primary', 1.00), ('barbell-curl', 'forearms', 'secondary', 0.40),
    ('hammer-curl', 'biceps', 'primary', 0.80), ('hammer-curl', 'forearms', 'primary', 0.70),
    ('cable-triceps-pushdown', 'triceps', 'primary', 1.00),
    ('plank', 'abs', 'primary', 1.00), ('plank', 'obliques', 'secondary', 0.50), ('plank', 'lower_back', 'stabilizer', 0.30),
    ('hanging-leg-raise', 'abs', 'primary', 1.00), ('hanging-leg-raise', 'obliques', 'secondary', 0.40), ('hanging-leg-raise', 'forearms', 'stabilizer', 0.30)
) AS v(slug, muscle_code, role, ratio)
JOIN catalog.exercises e ON e.slug = v.slug
JOIN catalog.muscle_groups mg ON mg.code = v.muscle_code;

-- ---------------------------------------------------------------------
-- catalog.exercise_equipment (bài không có dòng nào = bài tự thân)
-- ---------------------------------------------------------------------
INSERT INTO catalog.exercise_equipment (exercise_id, equipment_id, is_optional)
SELECT e.id, eq.id, v.optional
FROM (VALUES
    ('barbell-back-squat', 'barbell', false), ('barbell-back-squat', 'power_rack', false),
    ('goblet-squat', 'dumbbell', false),
    ('leg-press', 'leg_press_machine', false),
    ('bulgarian-split-squat', 'flat_bench', false), ('bulgarian-split-squat', 'dumbbell', true),
    ('leg-extension', 'leg_extension_machine', false),
    ('lying-leg-curl', 'leg_curl_machine', false),
    ('standing-calf-raise', 'dumbbell', true),
    ('conventional-deadlift', 'barbell', false),
    ('romanian-deadlift', 'barbell', false),
    ('hip-thrust', 'barbell', false), ('hip-thrust', 'flat_bench', false),
    ('barbell-bench-press', 'barbell', false), ('barbell-bench-press', 'flat_bench', false), ('barbell-bench-press', 'power_rack', true),
    ('dumbbell-bench-press', 'dumbbell', false), ('dumbbell-bench-press', 'flat_bench', false),
    ('incline-dumbbell-press', 'dumbbell', false), ('incline-dumbbell-press', 'adjustable_bench', false),
    ('machine-chest-press', 'chest_press_machine', false),
    ('cable-chest-fly', 'cable_crossover', false),
    ('pec-deck-fly', 'pec_deck_machine', false),
    ('chest-dip', 'dip_station', false),
    ('dumbbell-row', 'dumbbell', false), ('dumbbell-row', 'flat_bench', false),
    ('barbell-row', 'barbell', false),
    ('lat-pulldown', 'lat_pulldown_machine', false),
    ('pull-up', 'pull_up_bar', false),
    ('seated-cable-row', 'seated_row_machine', false),
    ('overhead-press', 'barbell', false), ('overhead-press', 'power_rack', true),
    ('dumbbell-shoulder-press', 'dumbbell', false), ('dumbbell-shoulder-press', 'adjustable_bench', false),
    ('dumbbell-lateral-raise', 'dumbbell', false),
    ('face-pull', 'cable_crossover', false),
    ('barbell-curl', 'barbell', false), ('barbell-curl', 'ez_bar', true),
    ('hammer-curl', 'dumbbell', false),
    ('cable-triceps-pushdown', 'cable_crossover', false),
    ('hanging-leg-raise', 'pull_up_bar', false)
) AS v(slug, equipment_code, optional)
JOIN catalog.exercises e ON e.slug = v.slug
JOIN catalog.equipment eq ON eq.code = v.equipment_code;

-- ---------------------------------------------------------------------
-- catalog.exercise_instructions
-- ---------------------------------------------------------------------
INSERT INTO catalog.exercise_instructions (exercise_id, step_no, content)
SELECT e.id, v.step_no, v.content
FROM (VALUES
    ('barbell-back-squat', 1, 'Đặt tạ trên phần cơ cầu vai, hai tay nắm thanh rộng hơn vai, chân rộng bằng vai.'),
    ('barbell-back-squat', 2, 'Hít sâu, siết bụng, đẩy hông ra sau và gập gối hạ người xuống.'),
    ('barbell-back-squat', 3, 'Hạ đến khi đùi song song sàn hoặc thấp hơn, gối hướng theo mũi chân, lưng giữ thẳng.'),
    ('barbell-back-squat', 4, 'Dồn lực qua cả bàn chân đẩy người đứng lên, thở ra khi qua điểm khó.'),
    ('goblet-squat', 1, 'Ôm một quả tạ đơn dựng đứng sát ngực, khuỷu tay hướng xuống.'),
    ('goblet-squat', 2, 'Đẩy hông ra sau, hạ người giữa hai gối, ngực mở và lưng thẳng.'),
    ('goblet-squat', 3, 'Đẩy gót chân đứng dậy về tư thế ban đầu.'),
    ('leg-press', 1, 'Ngồi tựa lưng sát đệm, đặt chân rộng bằng vai giữa bàn đạp.'),
    ('leg-press', 2, 'Mở khoá an toàn, gập gối hạ bàn đạp đến khi gối gần 90°.'),
    ('leg-press', 3, 'Đẩy bàn đạp lên, không khoá cứng gối ở điểm cao.'),
    ('bulgarian-split-squat', 1, 'Đứng trước ghế khoảng một bước dài, gác mu bàn chân sau lên ghế.'),
    ('bulgarian-split-squat', 2, 'Hạ người thẳng xuống đến khi đùi trước song song sàn.'),
    ('bulgarian-split-squat', 3, 'Đẩy chân trước đứng lên, hoàn thành đủ số lần rồi đổi chân.'),
    ('leg-extension', 1, 'Ngồi trên máy, đệm chân đặt ngay trên cổ chân, gối thẳng trục máy.'),
    ('leg-extension', 2, 'Duỗi gối nâng tạ đến khi chân gần thẳng, siết đùi trước 1 giây.'),
    ('leg-extension', 3, 'Hạ tạ chậm có kiểm soát.'),
    ('lying-leg-curl', 1, 'Nằm sấp trên máy, đệm chân đặt trên gót sau cổ chân.'),
    ('lying-leg-curl', 2, 'Gập gối kéo đệm về phía mông, hông áp sát ghế.'),
    ('lying-leg-curl', 3, 'Hạ chậm về vị trí ban đầu.'),
    ('standing-calf-raise', 1, 'Đứng mũi chân trên bậc, gót chân thả tự do.'),
    ('standing-calf-raise', 2, 'Nhón gót lên cao nhất có thể, giữ 1 giây.'),
    ('standing-calf-raise', 3, 'Hạ gót xuống thấp hơn bậc để giãn bắp chân.'),
    ('conventional-deadlift', 1, 'Đứng giữa bàn chân dưới thanh tạ, chân rộng bằng hông.'),
    ('conventional-deadlift', 2, 'Gập hông nắm thanh ngoài ống chân, hạ hông, ưỡn ngực, lưng thẳng.'),
    ('conventional-deadlift', 3, 'Đạp sàn kéo tạ lên sát ống chân, duỗi hông và gối cùng lúc.'),
    ('conventional-deadlift', 4, 'Đứng thẳng hoàn toàn rồi đẩy hông ra sau hạ tạ theo đường cũ.'),
    ('romanian-deadlift', 1, 'Cầm tạ đòn đứng thẳng, gối hơi chùng.'),
    ('romanian-deadlift', 2, 'Đẩy hông ra sau, hạ tạ sát đùi đến giữa ống chân, lưng giữ thẳng.'),
    ('romanian-deadlift', 3, 'Siết mông đẩy hông về trước để đứng lên.'),
    ('hip-thrust', 1, 'Ngồi dưới sàn, lưng trên tựa mép ghế, tạ đòn đặt trên hông (có đệm).'),
    ('hip-thrust', 2, 'Đạp gót đẩy hông lên đến khi thân và đùi thành một đường thẳng.'),
    ('hip-thrust', 3, 'Siết mông 1 giây rồi hạ hông chậm.'),
    ('barbell-bench-press', 1, 'Nằm trên ghế, mắt ngay dưới thanh tạ, nắm tay rộng hơn vai.'),
    ('barbell-bench-press', 2, 'Siết bả vai về sau, chân đạp chắc sàn, nhấc tạ ra khỏi giá.'),
    ('barbell-bench-press', 3, 'Hạ tạ có kiểm soát chạm giữa ngực, khuỷu tay khoảng 45–70° so với thân.'),
    ('barbell-bench-press', 4, 'Đẩy tạ lên theo đường hơi chéo về phía mặt đến khi duỗi tay.'),
    ('dumbbell-bench-press', 1, 'Nằm trên ghế phẳng, hai tạ đơn ngang ngực.'),
    ('dumbbell-bench-press', 2, 'Đẩy tạ lên trên ngực, hai tạ gần chạm nhau.'),
    ('dumbbell-bench-press', 3, 'Hạ chậm đến khi cảm thấy ngực giãn.'),
    ('incline-dumbbell-press', 1, 'Chỉnh ghế dốc 30–45°, nằm tựa lưng, tạ ngang vai.'),
    ('incline-dumbbell-press', 2, 'Đẩy tạ lên thẳng trên ngực trên.'),
    ('incline-dumbbell-press', 3, 'Hạ chậm về ngang vai.'),
    ('machine-chest-press', 1, 'Chỉnh ghế để tay cầm ngang giữa ngực.'),
    ('machine-chest-press', 2, 'Đẩy tay cầm về trước đến khi gần duỗi thẳng tay.'),
    ('machine-chest-press', 3, 'Thả về chậm, giữ bả vai áp vào lưng ghế.'),
    ('push-up', 1, 'Chống tay rộng hơn vai, thân thẳng từ đầu đến gót.'),
    ('push-up', 2, 'Gập khuỷu hạ ngực gần chạm sàn, khuỷu tay khoảng 45° so với thân.'),
    ('push-up', 3, 'Đẩy người lên, giữ hông không võng.'),
    ('cable-chest-fly', 1, 'Chỉnh ròng rọc ngang vai, mỗi tay nắm một tay cáp, bước lên trước một bước.'),
    ('cable-chest-fly', 2, 'Khuỷu hơi chùng, ép hai tay về trước ngực theo vòng cung.'),
    ('cable-chest-fly', 3, 'Mở tay chậm về sau đến khi ngực giãn.'),
    ('pec-deck-fly', 1, 'Ngồi tựa lưng, cẳng tay/tay cầm ngang vai.'),
    ('pec-deck-fly', 2, 'Ép hai tay vào giữa, siết ngực 1 giây.'),
    ('pec-deck-fly', 3, 'Mở tay chậm về vị trí đầu.'),
    ('chest-dip', 1, 'Chống thẳng tay trên xà kép, nghiêng thân về trước.'),
    ('chest-dip', 2, 'Gập khuỷu hạ người đến khi vai thấp hơn khuỷu một chút.'),
    ('chest-dip', 3, 'Đẩy người lên lại.'),
    ('dumbbell-row', 1, 'Tì gối và tay cùng bên lên ghế, lưng song song sàn, tay kia cầm tạ.'),
    ('dumbbell-row', 2, 'Kéo tạ về phía hông, khuỷu tay sát thân, siết bả vai.'),
    ('dumbbell-row', 3, 'Hạ tạ chậm đến khi tay duỗi, giữ lưng không xoay.'),
    ('barbell-row', 1, 'Cầm tạ đòn, gập hông khoảng 45°, lưng thẳng, gối hơi chùng.'),
    ('barbell-row', 2, 'Kéo tạ về rốn, khuỷu tay đi sát thân.'),
    ('barbell-row', 3, 'Hạ tạ có kiểm soát, không giật người.'),
    ('lat-pulldown', 1, 'Ngồi, kẹp đùi dưới đệm, nắm thanh rộng hơn vai.'),
    ('lat-pulldown', 2, 'Ưỡn ngực, kéo thanh xuống chạm ngực trên, khuỷu tay hướng xuống sàn.'),
    ('lat-pulldown', 3, 'Thả thanh lên chậm đến khi tay duỗi.'),
    ('pull-up', 1, 'Treo người trên xà, tay sấp rộng hơn vai.'),
    ('pull-up', 2, 'Kéo người lên đến khi cằm qua xà, siết lưng xô.'),
    ('pull-up', 3, 'Hạ người chậm đến khi tay gần duỗi thẳng.'),
    ('seated-cable-row', 1, 'Ngồi, chân đặt trên bàn đạp, gối hơi chùng, lưng thẳng.'),
    ('seated-cable-row', 2, 'Kéo tay cầm về bụng, siết bả vai.'),
    ('seated-cable-row', 3, 'Duỗi tay về trước chậm, không gập lưng.'),
    ('overhead-press', 1, 'Đặt tạ trên vai trước, nắm tay rộng hơn vai, siết bụng và mông.'),
    ('overhead-press', 2, 'Đẩy tạ thẳng lên qua đầu, đưa đầu ra trước khi tạ qua mặt.'),
    ('overhead-press', 3, 'Hạ tạ về vai có kiểm soát.'),
    ('dumbbell-shoulder-press', 1, 'Ngồi ghế dựa thẳng, tạ đơn ngang vai.'),
    ('dumbbell-shoulder-press', 2, 'Đẩy tạ lên qua đầu đến khi gần duỗi tay.'),
    ('dumbbell-shoulder-press', 3, 'Hạ tạ về ngang vai.'),
    ('dumbbell-lateral-raise', 1, 'Đứng thẳng, hai tay cầm tạ đơn hai bên thân.'),
    ('dumbbell-lateral-raise', 2, 'Dang tay sang ngang đến ngang vai, khuỷu hơi chùng.'),
    ('dumbbell-lateral-raise', 3, 'Hạ tạ chậm.'),
    ('face-pull', 1, 'Lắp dây thừng ở ròng rọc cao, nắm hai đầu dây.'),
    ('face-pull', 2, 'Kéo dây về phía mặt, tách hai tay sang hai bên tai.'),
    ('face-pull', 3, 'Duỗi tay về trước chậm.'),
    ('barbell-curl', 1, 'Đứng thẳng, cầm tạ đòn tay ngửa rộng bằng vai.'),
    ('barbell-curl', 2, 'Cuốn tạ lên ngực, giữ khuỷu tay cố định bên thân.'),
    ('barbell-curl', 3, 'Hạ tạ chậm đến khi tay duỗi.'),
    ('hammer-curl', 1, 'Cầm tạ đơn hai bên, lòng bàn tay hướng vào nhau.'),
    ('hammer-curl', 2, 'Cuốn tạ lên vai, giữ tay cầm trung tính.'),
    ('hammer-curl', 3, 'Hạ tạ chậm.'),
    ('cable-triceps-pushdown', 1, 'Đứng trước ròng rọc cao, nắm thanh/dây, khuỷu tay sát thân.'),
    ('cable-triceps-pushdown', 2, 'Duỗi khuỷu đẩy cáp xuống đến khi tay thẳng.'),
    ('cable-triceps-pushdown', 3, 'Thả về chậm đến khi cẳng tay ngang sàn.'),
    ('plank', 1, 'Chống khuỷu tay ngay dưới vai, duỗi thẳng chân.'),
    ('plank', 2, 'Siết bụng và mông, giữ thân thành một đường thẳng.'),
    ('plank', 3, 'Giữ tư thế trong thời gian mục tiêu, thở đều.'),
    ('hanging-leg-raise', 1, 'Treo người trên xà, vai kéo xuống ổn định.'),
    ('hanging-leg-raise', 2, 'Nâng chân lên ngang hông hoặc cao hơn, không đung đưa.'),
    ('hanging-leg-raise', 3, 'Hạ chân chậm có kiểm soát.')
) AS v(slug, step_no, content)
JOIN catalog.exercises e ON e.slug = v.slug;

-- ---------------------------------------------------------------------
-- catalog.exercise_mistakes — mã lỗi dùng chung Wiki & AI
-- ---------------------------------------------------------------------
INSERT INTO catalog.exercise_mistakes (exercise_id, code, title, description, correction_cue, at_risk_joint, ai_detectable, display_order)
SELECT e.id, v.code, v.title, v.description, v.cue, v.joint::catalog.joint_type, v.ai, v.ord
FROM (VALUES
    ('barbell-back-squat', 'SQUAT_BACK_ROUNDING', 'Cong lưng dưới', 'Lưng dưới bị cong (butt wink) ở đáy squat, tăng áp lực lên đĩa đệm.', 'Siết bụng, giữ ngực mở, giảm độ sâu nếu chưa đủ linh hoạt hông.', 'spine', true, 1),
    ('barbell-back-squat', 'SQUAT_KNEE_VALGUS', 'Gối chụm vào trong', 'Gối đổ vào trong khi đứng lên.', 'Đẩy gối hướng theo mũi chân, siết mông.', 'knee', true, 2),
    ('barbell-back-squat', 'SQUAT_HEEL_LIFT', 'Nhấc gót chân', 'Trọng tâm dồn lên mũi chân, gót rời sàn.', 'Dồn lực qua cả bàn chân, cải thiện linh hoạt cổ chân.', 'ankle', true, 3),
    ('barbell-back-squat', 'SQUAT_SHALLOW_DEPTH', 'Xuống chưa đủ sâu', 'Đùi chưa song song sàn.', 'Hạ thêm đến khi hông ngang hoặc thấp hơn gối.', NULL, true, 4),
    ('goblet-squat', 'GOBLET_TORSO_LEAN', 'Đổ người về trước', 'Thân nghiêng quá nhiều, tạ rời khỏi ngực.', 'Giữ tạ sát ngực, khuỷu tay chỉ xuống.', 'spine', true, 1),
    ('goblet-squat', 'GOBLET_KNEE_VALGUS', 'Gối chụm vào trong', 'Gối đổ vào trong khi lên.', 'Đẩy gối ra theo hướng mũi chân.', 'knee', true, 2),
    ('leg-extension', 'LEG_EXT_SWING', 'Đá tạ bằng quán tính', 'Đá chân nhanh, tạ văng lên rồi rơi tự do.', 'Nâng có kiểm soát, giữ 1 giây ở điểm cao, hạ chậm.', 'knee', false, 1),
    ('lying-leg-curl', 'LEG_CURL_HIP_LIFT', 'Nhấc hông khỏi ghế', 'Hông nhổm lên để kéo tạ nặng.', 'Ép hông xuống đệm, giảm tạ.', 'spine', false, 1),
    ('standing-calf-raise', 'CALF_RAISE_BOUNCE', 'Nảy ở điểm thấp', 'Nhún nảy nhanh, không dùng hết biên độ.', 'Dừng 1 giây ở điểm thấp và điểm cao.', 'ankle', false, 1),
    ('machine-chest-press', 'MACHINE_PRESS_SHOULDER_ROLL', 'Vai đổ về trước', 'Vai rời đệm, cuộn về trước khi đẩy.', 'Ép bả vai vào lưng ghế suốt hiệp.', 'shoulder', false, 1),
    ('pec-deck-fly', 'PEC_DECK_OVERSTRETCH', 'Mở tay quá sâu', 'Mở tay ra sau quá xa gây áp lực khớp vai trước.', 'Dừng khi tay ngang thân.', 'shoulder', false, 1),
    ('leg-press', 'LEG_PRESS_LOCKOUT', 'Khoá cứng gối', 'Duỗi thẳng gối hoàn toàn ở điểm cao.', 'Dừng khi gối còn hơi chùng.', 'knee', false, 1),
    ('leg-press', 'LEG_PRESS_HIP_LIFT', 'Hông rời ghế', 'Hạ quá sâu khiến hông và lưng dưới cuộn khỏi đệm.', 'Giảm biên độ, giữ hông áp đệm.', 'spine', false, 2),
    ('bulgarian-split-squat', 'BSS_KNEE_VALGUS', 'Gối trước đổ vào trong', 'Gối chân trước lệch vào trong.', 'Giữ gối thẳng hướng mũi chân.', 'knee', true, 1),
    ('conventional-deadlift', 'DEADLIFT_BACK_ROUNDING', 'Cong lưng khi kéo', 'Lưng cong khi tạ rời sàn, nguy cơ chấn thương cột sống cao.', 'Ưỡn ngực, siết lưng xô, kéo vai về sau trước khi kéo.', 'spine', true, 1),
    ('conventional-deadlift', 'DEADLIFT_BAR_DRIFT', 'Tạ xa người', 'Thanh tạ rời xa ống chân/đùi.', 'Kéo tạ sát người theo đường thẳng đứng.', 'spine', true, 2),
    ('conventional-deadlift', 'DEADLIFT_HIPS_RISE_FIRST', 'Hông lên trước', 'Hông bật lên trước vai, biến thành stiff-leg.', 'Đẩy sàn bằng chân, hông và vai lên cùng nhịp.', 'spine', true, 3),
    ('romanian-deadlift', 'RDL_BACK_ROUNDING', 'Cong lưng', 'Lưng cong khi hạ tạ quá thấp.', 'Chỉ hạ đến khi cảm thấy đùi sau căng, giữ lưng thẳng.', 'spine', true, 1),
    ('romanian-deadlift', 'RDL_KNEE_BEND', 'Gập gối quá nhiều', 'Gập gối biến bài thành deadlift thường.', 'Giữ góc gối cố định, chủ yếu gập hông.', NULL, true, 2),
    ('hip-thrust', 'HIP_THRUST_HYPEREXTENSION', 'Ưỡn lưng quá mức', 'Ưỡn lưng dưới thay vì duỗi hông ở điểm cao.', 'Hóp cằm, siết bụng, dừng khi thân thẳng.', 'spine', false, 1),
    ('barbell-bench-press', 'BENCH_ELBOW_FLARE', 'Khuỷu tay mở 90°', 'Khuỷu tay vuông góc thân, tăng áp lực khớp vai.', 'Giữ khuỷu tay khoảng 45–70° so với thân.', 'shoulder', true, 1),
    ('barbell-bench-press', 'BENCH_BAR_BOUNCE', 'Nảy tạ trên ngực', 'Thả rơi tạ rồi dùng ngực bật lên.', 'Hạ có kiểm soát, chạm nhẹ rồi đẩy.', NULL, true, 2),
    ('barbell-bench-press', 'BENCH_HIPS_OFF_BENCH', 'Nhấc mông khỏi ghế', 'Mông rời ghế khi đẩy nặng.', 'Giữ mông chạm ghế, dùng lực chân đạp sàn.', 'spine', true, 3),
    ('dumbbell-bench-press', 'DB_BENCH_UNEVEN', 'Hai tay lệch nhau', 'Một bên tạ lên nhanh/cao hơn bên kia.', 'Đẩy hai tạ cùng nhịp, giảm tạ nếu cần.', 'shoulder', true, 1),
    ('incline-dumbbell-press', 'INCLINE_ARCH_BACK', 'Ưỡn lưng quá nhiều', 'Ưỡn lưng làm mất góc dốc.', 'Giữ lưng áp ghế, giảm tạ.', 'spine', false, 1),
    ('push-up', 'PUSHUP_HIP_SAG', 'Võng hông', 'Hông rơi xuống, lưng dưới võng.', 'Siết bụng và mông, giữ thân thẳng.', 'spine', true, 1),
    ('push-up', 'PUSHUP_PARTIAL_ROM', 'Biên độ ngắn', 'Không hạ ngực đủ thấp.', 'Hạ đến khi ngực cách sàn một nắm tay.', NULL, true, 2),
    ('cable-chest-fly', 'FLY_ARMS_BENT', 'Gập khuỷu quá nhiều', 'Biến bài ép thành bài đẩy.', 'Giữ góc khuỷu cố định, hơi chùng.', 'elbow', false, 1),
    ('chest-dip', 'DIP_TOO_DEEP', 'Hạ quá sâu', 'Vai hạ quá thấp gây áp lực khớp vai trước.', 'Dừng khi vai thấp hơn khuỷu một chút.', 'shoulder', false, 1),
    ('dumbbell-row', 'DB_ROW_TORSO_ROTATION', 'Xoay thân khi kéo', 'Xoay vai/hông để kéo tạ nặng.', 'Giữ vai song song sàn, giảm tạ.', 'spine', true, 1),
    ('dumbbell-row', 'DB_ROW_ROUNDED_BACK', 'Cong lưng', 'Lưng cong khi cúi người.', 'Ưỡn ngực, giữ lưng thẳng.', 'spine', true, 2),
    ('barbell-row', 'BB_ROW_BODY_ENGLISH', 'Giật người kéo tạ', 'Dùng quán tính thân trên để kéo.', 'Giữ góc thân cố định, giảm tạ.', 'spine', true, 1),
    ('barbell-row', 'BB_ROW_ROUNDED_BACK', 'Cong lưng', 'Lưng cong khi cúi.', 'Siết bụng, giữ lưng thẳng.', 'spine', true, 2),
    ('lat-pulldown', 'PULLDOWN_LEAN_BACK', 'Ngả người quá nhiều', 'Ngả ra sau dùng trọng lượng cơ thể kéo.', 'Chỉ ngả nhẹ khoảng 10–15°.', 'spine', false, 1),
    ('pull-up', 'PULLUP_KIPPING', 'Đung đưa lấy đà', 'Dùng đà chân/hông để lên xà.', 'Siết bụng, kéo bằng lưng xô.', 'shoulder', true, 1),
    ('pull-up', 'PULLUP_PARTIAL_ROM', 'Biên độ ngắn', 'Cằm chưa qua xà hoặc không duỗi tay ở dưới.', 'Lên đến cằm qua xà, xuống gần duỗi tay.', NULL, true, 2),
    ('seated-cable-row', 'CABLE_ROW_ROCKING', 'Lắc lưng', 'Gập/ngả thân để kéo.', 'Giữ thân thẳng đứng cố định.', 'spine', false, 1),
    ('overhead-press', 'OHP_LUMBAR_ARCH', 'Ưỡn lưng dưới', 'Ưỡn lưng dưới khi đẩy tạ qua đầu.', 'Siết mông và bụng, giữ xương sườn hạ xuống.', 'spine', true, 1),
    ('overhead-press', 'OHP_BAR_FORWARD', 'Tạ lệch trước', 'Thanh tạ đi về phía trước mặt.', 'Đưa đầu ra trước khi tạ qua mặt, tạ thẳng trên giữa bàn chân.', 'shoulder', true, 2),
    ('dumbbell-shoulder-press', 'DB_PRESS_ELBOW_DROP', 'Khuỷu hạ quá thấp', 'Hạ tạ quá sâu dưới vai.', 'Dừng khi tạ ngang tai.', 'shoulder', false, 1),
    ('dumbbell-lateral-raise', 'LATERAL_RAISE_SHRUG', 'Nhún vai', 'Dùng cơ cầu vai nâng tạ.', 'Hạ vai xuống, nâng bằng khuỷu tay.', 'shoulder', false, 1),
    ('face-pull', 'FACE_PULL_LOW_ELBOWS', 'Khuỷu tay thấp', 'Khuỷu hạ thấp biến thành bài chèo.', 'Giữ khuỷu ngang hoặc cao hơn vai.', 'shoulder', false, 1),
    ('barbell-curl', 'CURL_ELBOW_DRIFT', 'Khuỷu tay di chuyển', 'Khuỷu tay đưa ra trước khi cuốn.', 'Giữ khuỷu tay cố định sát thân.', 'elbow', true, 1),
    ('barbell-curl', 'CURL_BODY_SWING', 'Đung đưa thân', 'Dùng hông đẩy tạ lên.', 'Đứng thẳng, giảm tạ.', 'spine', true, 2),
    ('hammer-curl', 'HAMMER_CURL_SWING', 'Đung đưa thân', 'Lấy đà để cuốn tạ.', 'Giữ thân cố định.', 'spine', false, 1),
    ('cable-triceps-pushdown', 'PUSHDOWN_ELBOW_FLARE', 'Khuỷu tay mở rộng', 'Khuỷu rời khỏi thân khi đẩy.', 'Kẹp khuỷu sát thân.', 'elbow', false, 1),
    ('plank', 'PLANK_HIP_SAG', 'Võng hông', 'Hông rơi xuống thấp hơn đường thẳng thân.', 'Siết bụng, nâng hông lên ngang vai.', 'spine', true, 1),
    ('plank', 'PLANK_HIP_PIKE', 'Đẩy hông quá cao', 'Hông nhô cao làm giảm tác dụng lên bụng.', 'Hạ hông về ngang vai.', NULL, true, 2),
    ('hanging-leg-raise', 'HLR_SWINGING', 'Đung đưa người', 'Người đung đưa lấy đà.', 'Dừng ở mỗi điểm, siết bụng.', 'shoulder', false, 1)
) AS v(slug, code, title, description, cue, joint, ai, ord)
JOIN catalog.exercises e ON e.slug = v.slug;

-- ---------------------------------------------------------------------
-- catalog.exercise_alternatives — bài thay thế do biên tập viên chọn
-- ---------------------------------------------------------------------
INSERT INTO catalog.exercise_alternatives (exercise_id, alternative_exercise_id, note)
SELECT a.id, b.id, v.note
FROM (VALUES
    ('dumbbell-row',          'barbell-row',            'Cùng nhóm lưng xô khi hết tạ đơn.'),
    ('dumbbell-row',          'seated-cable-row',       'Dùng máy cáp khi khu tạ tự do đông.'),
    ('barbell-row',           'dumbbell-row',           'Giảm tải cột sống, tập từng bên.'),
    ('barbell-row',           'seated-cable-row',       'Quỹ đạo ổn định hơn.'),
    ('lat-pulldown',          'pull-up',                'Khi đủ sức kéo trọng lượng cơ thể.'),
    ('pull-up',               'lat-pulldown',           'Điều chỉnh được mức tạ.'),
    ('barbell-bench-press',   'dumbbell-bench-press',   'Khi không có giá/người hỗ trợ.'),
    ('barbell-bench-press',   'machine-chest-press',    'An toàn khi tập một mình.'),
    ('barbell-bench-press',   'push-up',                'Không cần thiết bị.'),
    ('dumbbell-bench-press',  'barbell-bench-press',    'Tăng tải tối đa.'),
    ('cable-chest-fly',       'pec-deck-fly',           'Khi máy cáp đang bận.'),
    ('pec-deck-fly',          'cable-chest-fly',        'Khi máy ép ngực đang bận.'),
    ('barbell-back-squat',    'goblet-squat',           'Cho người mới hoặc khi khung squat bận.'),
    ('barbell-back-squat',    'leg-press',              'Giảm tải cột sống.'),
    ('barbell-back-squat',    'bulgarian-split-squat',  'Tập từng chân, ít tạ.'),
    ('leg-press',             'goblet-squat',           'Khi máy đạp đùi bận.'),
    ('conventional-deadlift', 'romanian-deadlift',      'Nhẹ hơn cho lưng dưới, nhấn đùi sau.'),
    ('romanian-deadlift',     'hip-thrust',             'Nhấn mạnh mông, ít tải lưng.'),
    ('overhead-press',        'dumbbell-shoulder-press', 'Ngồi tựa, ổn định hơn.'),
    ('dumbbell-shoulder-press', 'overhead-press',       'Tăng tải và sức mạnh tổng thể.'),
    ('barbell-curl',          'hammer-curl',            'Giảm áp lực cổ tay.'),
    ('chest-dip',             'cable-triceps-pushdown', 'Khi vai nhạy cảm.')
) AS v(slug, alt_slug, note)
JOIN catalog.exercises a ON a.slug = v.slug
JOIN catalog.exercises b ON b.slug = v.alt_slug;
