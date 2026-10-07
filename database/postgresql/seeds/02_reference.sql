-- =====================================================================
-- Smart Workout AI — Seed: reference data
-- Độ khó, vùng cơ thể, nhóm cơ, thiết bị (+ alias/nhãn AI), mức vận động, mục tiêu, vị trí đo
-- =====================================================================

-- ---------------------------------------------------------------------
-- catalog.difficulty_levels
-- ---------------------------------------------------------------------
INSERT INTO catalog.difficulty_levels (code, name, rank, description) VALUES
    ('beginner',     'Cơ bản',    1, 'Phù hợp người mới, kỹ thuật đơn giản, rủi ro thấp.'),
    ('intermediate', 'Trung cấp', 2, 'Cần nền tảng kỹ thuật và sức mạnh cơ bản.'),
    ('advanced',     'Nâng cao',  3, 'Kỹ thuật phức tạp hoặc tải nặng, cần kinh nghiệm.');

-- ---------------------------------------------------------------------
-- catalog.body_regions
-- ---------------------------------------------------------------------
INSERT INTO catalog.body_regions (code, name, display_order) VALUES
    ('upper_body', 'Thân trên', 1),
    ('core',       'Thân giữa (Core)', 2),
    ('lower_body', 'Thân dưới', 3);

-- ---------------------------------------------------------------------
-- catalog.muscle_groups — nút gốc (có body_region) rồi nút con
-- ---------------------------------------------------------------------
INSERT INTO catalog.muscle_groups (code, name, name_en, body_region_id, heatmap_region_key, base_recovery_hours, display_order)
SELECT v.code, v.name, v.name_en, br.id, v.heatmap, v.hours, v.ord
FROM (VALUES
    ('chest',     'Ngực',  'Pectoralis Major', 'upper_body', 'chest', 60, 1),
    ('back',      'Lưng',  'Back',             'upper_body', NULL,    48, 2),
    ('shoulders', 'Vai',   'Deltoids',         'upper_body', NULL,    48, 3),
    ('arms',      'Tay',   'Arms',             'upper_body', NULL,    48, 4),
    ('core',      'Bụng',  'Core',             'core',       NULL,    36, 5),
    ('legs',      'Chân',  'Legs',             'lower_body', NULL,    72, 6)
) AS v(code, name, name_en, region, heatmap, hours, ord)
JOIN catalog.body_regions br ON br.code = v.region;

INSERT INTO catalog.muscle_groups (code, name, name_en, parent_id, heatmap_region_key, base_recovery_hours, display_order)
SELECT v.code, v.name, v.name_en, p.id, v.heatmap, v.hours, v.ord
FROM (VALUES
    ('lats',        'Lưng xô',          'Latissimus Dorsi',        'back',      'lats',        60, 1),
    ('traps',       'Cơ cầu vai',       'Trapezius',               'back',      'traps',       48, 2),
    ('upper_back',  'Lưng giữa',        'Rhomboids',               'back',      'upper_back',  48, 3),
    ('lower_back',  'Lưng dưới',        'Erector Spinae',          'back',      'lower_back',  72, 4),
    ('front_delts', 'Vai trước',        'Anterior Deltoid',        'shoulders', 'front_delts', 48, 1),
    ('side_delts',  'Vai giữa',         'Lateral Deltoid',         'shoulders', 'side_delts',  48, 2),
    ('rear_delts',  'Vai sau',          'Posterior Deltoid',       'shoulders', 'rear_delts',  48, 3),
    ('biceps',      'Tay trước',        'Biceps Brachii',          'arms',      'biceps',      48, 1),
    ('triceps',     'Tay sau',          'Triceps Brachii',         'arms',      'triceps',     48, 2),
    ('forearms',    'Cẳng tay',         'Forearms',                'arms',      'forearms',    36, 3),
    ('abs',         'Cơ bụng',          'Rectus Abdominis',        'core',      'abs',         36, 1),
    ('obliques',    'Cơ liên sườn',     'Obliques',                'core',      'obliques',    36, 2),
    ('quads',       'Đùi trước',        'Quadriceps',              'legs',      'quads',       72, 1),
    ('hamstrings',  'Đùi sau',          'Hamstrings',              'legs',      'hamstrings',  72, 2),
    ('glutes',      'Mông',             'Gluteus Maximus',         'legs',      'glutes',      72, 3),
    ('calves',      'Bắp chân',         'Calves',                  'legs',      'calves',      36, 4),
    ('adductors',   'Đùi trong',        'Adductors',               'legs',      'adductors',   48, 5)
) AS v(code, name, name_en, parent_code, heatmap, hours, ord)
JOIN catalog.muscle_groups p ON p.code = v.parent_code;

-- ---------------------------------------------------------------------
-- catalog.equipment_categories
-- ---------------------------------------------------------------------
INSERT INTO catalog.equipment_categories (code, name, description, display_order) VALUES
    ('free_weight', 'Tạ tự do',          'Tạ đòn, tạ đơn, tạ ấm.',                       1),
    ('machine',     'Máy tập',           'Máy có quỹ đạo cố định.',                      2),
    ('cable',       'Hệ thống cáp',      'Máy kéo cáp, ròng rọc.',                       3),
    ('bench_rack',  'Ghế & khung',       'Ghế tập, khung squat.',                        4),
    ('bodyweight',  'Dụng cụ tự thân',   'Xà đơn, xà kép.',                              5),
    ('cardio',      'Cardio',            'Máy chạy bộ, xe đạp, máy chèo thuyền.',        6),
    ('accessory',   'Phụ kiện',          'Dây kháng lực, thảm...',                       7);

-- ---------------------------------------------------------------------
-- catalog.equipment
-- ---------------------------------------------------------------------
INSERT INTO catalog.equipment (code, name, name_en, category_id, description)
SELECT v.code, v.name, v.name_en, c.id, v.description
FROM (VALUES
    ('barbell',                'Tạ đòn',                  'Barbell',                 'free_weight', 'Thanh đòn dài lắp bánh tạ, dùng cho các bài đa khớp tải nặng.'),
    ('ez_bar',                 'Thanh đòn EZ',            'EZ Curl Bar',             'free_weight', 'Thanh đòn uốn cong giảm áp lực cổ tay khi cuốn tay.'),
    ('dumbbell',               'Tạ đơn',                  'Dumbbell',                'free_weight', 'Tạ cầm một tay, cho phép tập từng bên.'),
    ('kettlebell',             'Tạ ấm',                   'Kettlebell',              'free_weight', 'Tạ hình quả chuông có tay cầm.'),
    ('flat_bench',             'Ghế phẳng',               'Flat Bench',              'bench_rack',  'Ghế tập nằm phẳng.'),
    ('adjustable_bench',       'Ghế điều chỉnh',          'Adjustable Bench',        'bench_rack',  'Ghế chỉnh được góc dốc lên/xuống.'),
    ('power_rack',             'Khung squat',             'Power Rack',              'bench_rack',  'Khung có thanh chắn an toàn cho squat, đẩy ngực.'),
    ('smith_machine',          'Máy Smith',               'Smith Machine',           'machine',     'Thanh đòn chạy trên ray cố định.'),
    ('cable_crossover',        'Máy kéo cáp đôi',         'Cable Crossover Machine', 'cable',       'Hai tháp cáp điều chỉnh độ cao, tập ép ngực, kéo cáp, face pull...'),
    ('lat_pulldown_machine',   'Máy kéo xô',              'Lat Pulldown Machine',    'cable',       'Máy kéo cáp từ trên xuống cho cơ lưng xô.'),
    ('seated_row_machine',     'Máy kéo cáp ngồi',        'Seated Cable Row',        'cable',       'Máy kéo cáp ngang khi ngồi cho lưng giữa.'),
    ('leg_press_machine',      'Máy đạp đùi',             'Leg Press Machine',       'machine',     'Máy đạp tạ bằng chân ở tư thế ngồi/nằm.'),
    ('leg_extension_machine',  'Máy đá đùi',              'Leg Extension Machine',   'machine',     'Máy duỗi gối cô lập đùi trước.'),
    ('leg_curl_machine',       'Máy móc đùi',             'Leg Curl Machine',        'machine',     'Máy gập gối cô lập đùi sau.'),
    ('chest_press_machine',    'Máy đẩy ngực',            'Chest Press Machine',     'machine',     'Máy đẩy ngực tư thế ngồi.'),
    ('pec_deck_machine',       'Máy ép ngực',             'Pec Deck Machine',        'machine',     'Máy ép ngực (butterfly).'),
    ('shoulder_press_machine', 'Máy đẩy vai',             'Shoulder Press Machine',  'machine',     'Máy đẩy vai tư thế ngồi.'),
    ('pull_up_bar',            'Xà đơn',                  'Pull-up Bar',             'bodyweight',  'Thanh xà treo người.'),
    ('dip_station',            'Xà kép',                  'Dip Station',             'bodyweight',  'Hai thanh song song cho bài dips.'),
    ('treadmill',              'Máy chạy bộ',             'Treadmill',               'cardio',      'Máy chạy bộ điện.'),
    ('stationary_bike',        'Xe đạp tập',              'Stationary Bike',         'cardio',      'Xe đạp cố định.'),
    ('rowing_machine',         'Máy chèo thuyền',         'Rowing Machine',          'cardio',      'Máy mô phỏng chèo thuyền.'),
    ('resistance_band',        'Dây kháng lực',           'Resistance Band',         'accessory',   'Dây đàn hồi tạo lực cản.'),
    ('jump_rope',              'Dây nhảy',                'Jump Rope',               'accessory',   'Dây nhảy cho bài cardio cường độ cao.'),
    ('plyo_box',               'Bục nhảy',                'Plyo Box',                'accessory',   'Bục gỗ/xốp cho bài bật nhảy và step-up.'),
    ('medicine_ball',          'Bóng tạ',                 'Medicine Ball',           'free_weight', 'Bóng có trọng lượng cho bài core và bật ném.'),
    ('ab_wheel',               'Con lăn tập bụng',        'Ab Wheel',                'accessory',   'Bánh xe lăn tập cơ bụng.')
) AS v(code, name, name_en, category_code, description)
JOIN catalog.equipment_categories c ON c.code = v.category_code;

-- ---------------------------------------------------------------------
-- catalog.equipment_aliases — nhãn lớp YOLOv8 (ai_label) + từ đồng nghĩa (synonym)
-- ---------------------------------------------------------------------
INSERT INTO catalog.equipment_aliases (equipment_id, alias, alias_type)
SELECT e.id, v.alias, v.alias_type::catalog.alias_type
FROM (VALUES
    ('barbell',                'barbell',                  'ai_label'),
    ('barbell',                'tạ đòn dài',               'synonym'),
    ('barbell',                'thanh đòn',                'synonym'),
    ('ez_bar',                 'ez_curl_bar',              'ai_label'),
    ('dumbbell',               'dumbbell',                 'ai_label'),
    ('dumbbell',               'tạ tay',                   'synonym'),
    ('kettlebell',             'kettlebell',               'ai_label'),
    ('flat_bench',             'flat_bench',               'ai_label'),
    ('adjustable_bench',       'adjustable_bench',         'ai_label'),
    ('adjustable_bench',       'ghế dốc',                  'synonym'),
    ('power_rack',             'power_rack',               'ai_label'),
    ('power_rack',             'squat rack',               'synonym'),
    ('smith_machine',          'smith_machine',            'ai_label'),
    ('cable_crossover',        'cable_crossover_machine',  'ai_label'),
    ('cable_crossover',        'máy cáp',                  'synonym'),
    ('cable_crossover',        'tạ cáp',                   'synonym'),
    ('lat_pulldown_machine',   'lat_pulldown_machine',     'ai_label'),
    ('lat_pulldown_machine',   'máy kéo lưng',             'synonym'),
    ('seated_row_machine',     'seated_cable_row_machine', 'ai_label'),
    ('leg_press_machine',      'leg_press_machine',        'ai_label'),
    ('leg_extension_machine',  'leg_extension_machine',    'ai_label'),
    ('leg_curl_machine',       'leg_curl_machine',         'ai_label'),
    ('chest_press_machine',    'chest_press_machine',      'ai_label'),
    ('pec_deck_machine',       'pec_deck_machine',         'ai_label'),
    ('pec_deck_machine',       'máy bướm',                 'synonym'),
    ('shoulder_press_machine', 'shoulder_press_machine',   'ai_label'),
    ('pull_up_bar',            'pull_up_bar',              'ai_label'),
    ('dip_station',            'dip_station',              'ai_label'),
    ('treadmill',              'treadmill',                'ai_label'),
    ('stationary_bike',        'stationary_bike',          'ai_label'),
    ('rowing_machine',         'rowing_machine',           'ai_label'),
    ('resistance_band',        'resistance_band',          'ai_label'),
    ('resistance_band',        'dây đàn hồi',              'synonym'),
    ('jump_rope',              'jump_rope',                'ai_label'),
    ('plyo_box',               'plyo_box',                 'ai_label'),
    ('plyo_box',               'hộp nhảy',                 'synonym'),
    ('medicine_ball',          'medicine_ball',            'ai_label'),
    ('ab_wheel',               'ab_wheel',                 'ai_label'),
    ('ab_wheel',               'bánh xe tập bụng',         'synonym')
) AS v(equipment_code, alias, alias_type)
JOIN catalog.equipment e ON e.code = v.equipment_code;

-- ---------------------------------------------------------------------
-- body.activity_levels — hệ số TDEE chuẩn (Harris-Benedict / Mifflin)
-- ---------------------------------------------------------------------
INSERT INTO body.activity_levels (code, name, description, multiplier, display_order) VALUES
    ('sedentary',   'Ít vận động',          'Làm việc văn phòng, hầu như không tập.',  1.200, 1),
    ('light',       'Vận động nhẹ',         'Tập 1–3 buổi/tuần.',                       1.375, 2),
    ('moderate',    'Vận động vừa',         'Tập 3–5 buổi/tuần.',                       1.550, 3),
    ('active',      'Vận động nhiều',       'Tập 6–7 buổi/tuần.',                       1.725, 4),
    ('very_active', 'Vận động rất nhiều',   'Tập 2 buổi/ngày hoặc lao động nặng.',      1.900, 5);

-- ---------------------------------------------------------------------
-- body.fitness_goal_types
-- ---------------------------------------------------------------------
INSERT INTO body.fitness_goal_types (code, name, description, display_order) VALUES
    ('lose_fat',      'Giảm mỡ',                'Giảm tỷ lệ mỡ, giữ khối cơ.',              1),
    ('gain_muscle',   'Tăng cơ',                'Tăng khối lượng cơ (bulking).',             2),
    ('recomposition', 'Tái cấu trúc cơ thể',    'Đồng thời giảm mỡ và tăng cơ.',             3),
    ('strength',      'Tăng sức mạnh',          'Tối đa hoá sức mạnh các bài chính.',        4),
    ('maintain',      'Duy trì',                'Giữ vóc dáng và sức khoẻ hiện tại.',        5);

-- ---------------------------------------------------------------------
-- body.body_sites
-- ---------------------------------------------------------------------
INSERT INTO body.body_sites (code, name, display_order) VALUES
    ('neck',        'Cổ',               1),
    ('shoulders',   'Vai',              2),
    ('chest',       'Ngực',             3),
    ('waist',       'Eo',               4),
    ('hips',        'Mông',             5),
    ('left_arm',    'Bắp tay trái',     6),
    ('right_arm',   'Bắp tay phải',     7),
    ('left_thigh',  'Đùi trái',         8),
    ('right_thigh', 'Đùi phải',         9),
    ('left_calf',   'Bắp chân trái',    10),
    ('right_calf',  'Bắp chân phải',    11);
