-- =====================================================================
-- Smart Workout AI — TEST DATA (2/7): media placeholder & ca biên của danh mục
-- File trên S3 CHƯA tồn tại: các bản ghi media chỉ để test API trả về media.
-- Quy ước key: catalog/exercises/<slug>/{thumbnail.jpg, demo.gif, tutorial.mp4, step-N.jpg}
--              catalog/equipment/<code>.jpg
-- =====================================================================

-- Biên tập viên là người tạo/cập nhật nội dung danh mục
UPDATE catalog.exercises SET created_by = test_seed.uid(2), updated_by = test_seed.uid(2);
UPDATE catalog.equipment SET created_by = test_seed.uid(2), updated_by = test_seed.uid(2);

-- ---------------------------------------------------------------------
-- Media bài tập: thumbnail + GIF chính cho mọi bài đã xuất bản
-- ---------------------------------------------------------------------
INSERT INTO catalog.exercise_media (exercise_id, media_id, media_role, is_primary, display_order)
SELECT e.id,
       test_seed.media(test_seed.uid(2), format('catalog/exercises/%s/thumbnail.jpg', e.slug), 'image/jpeg',
                       28000 + (e.id * 977) % 20000, 400, 300, NULL, 'available', now() - interval '200 days'),
       'thumbnail', true, 0
FROM catalog.exercises e
WHERE e.status = 'published' AND e.deleted_at IS NULL;

INSERT INTO catalog.exercise_media (exercise_id, media_id, media_role, is_primary, display_order)
SELECT e.id,
       test_seed.media(test_seed.uid(2), format('catalog/exercises/%s/demo.gif', e.slug), 'image/gif',
                       600000 + (e.id * 7919) % 600000, 480, 360, 3000 + (e.id * 131) % 2000, 'available', now() - interval '200 days'),
       'gif', true, 1
FROM catalog.exercises e
WHERE e.status = 'published' AND e.deleted_at IS NULL;

-- Video hướng dẫn cho 20 bài đa khớp tạ/máy
INSERT INTO catalog.exercise_media (exercise_id, media_id, media_role, is_primary, display_order, caption)
SELECT e.id,
       test_seed.media(test_seed.uid(2), format('catalog/exercises/%s/tutorial.mp4', e.slug), 'video/mp4',
                       8000000 + (e.id * 104729) % 6000000, 1280, 720, 40000 + (e.id * 997) % 30000, 'available', now() - interval '180 days'),
       'video', true, 2, 'Video hướng dẫn kỹ thuật'
FROM (
    SELECT e2.id, e2.slug
    FROM catalog.exercises e2
    WHERE e2.status = 'published' AND e2.deleted_at IS NULL
      AND e2.category = 'strength' AND e2.mechanic = 'compound'
    ORDER BY e2.id
    LIMIT 20
) AS e;

-- Một bài có nhiều ảnh minh hoạ không chính (test sắp xếp display_order)
INSERT INTO catalog.exercise_media (exercise_id, media_id, media_role, is_primary, display_order, caption)
SELECT test_seed.ex('barbell-back-squat'),
       test_seed.media(test_seed.uid(2), format('catalog/exercises/barbell-back-squat/step-%s.jpg', v.n), 'image/jpeg',
                       150000 + v.n * 1000, 1080, 1080, NULL, 'available', now() - interval '150 days'),
       'image', false, 2 + v.n, v.caption
FROM (VALUES (1, 'Tư thế bắt đầu'), (2, 'Điểm thấp nhất'), (3, 'Đứng lên hoàn thành')) AS v(n, caption);

-- Ảnh thiết bị
UPDATE catalog.equipment eq
SET image_media_id = test_seed.media(test_seed.uid(2), format('catalog/equipment/%s.jpg', eq.code), 'image/jpeg',
                                     60000 + (eq.id * 1543) % 40000, 800, 600, NULL, 'available', now() - interval '200 days')
WHERE eq.deleted_at IS NULL;

-- ---------------------------------------------------------------------
-- Ca biên: bài tập draft / archived / đã xoá mềm
-- ---------------------------------------------------------------------
INSERT INTO catalog.exercises (slug, name, name_en, description, difficulty_level_id, category, mechanic, force_type,
                               met_value, status, published_at, created_by, updated_by, created_at, updated_at, deleted_at)
SELECT v.slug, v.name, v.name_en, v.description, d.id, 'strength', 'compound', 'push', 4.0,
       v.status::catalog.content_status,
       CASE WHEN v.status <> 'draft' THEN now() - interval '150 days' END,
       test_seed.uid(2), test_seed.uid(2),
       now() - interval '160 days', now() - v.updated_days * interval '1 day',
       CASE WHEN v.deleted THEN now() - interval '5 days' END
FROM (VALUES
    ('test-draft-exercise',    '[TEST] Bài tập nháp',          'Test Draft Exercise',    'Bài đang biên tập, KHÔNG được hiển thị cho user.',                 'draft',     2, false),
    ('test-archived-exercise', '[TEST] Bài tập đã lưu trữ',    'Test Archived Exercise', 'Bài đã ngừng hiển thị nhưng còn trong lịch sử tập.',              'archived', 30, false),
    ('test-deleted-exercise',  '[TEST] Bài tập đã xoá mềm',    'Test Deleted Exercise',  'Bài đã xoá mềm (deleted_at), KHÔNG được trả về từ API tìm kiếm.', 'published', 5, true)
) AS v(slug, name, name_en, description, status, updated_days, deleted)
JOIN catalog.difficulty_levels d ON d.code = 'beginner';

INSERT INTO catalog.exercise_muscles (exercise_id, muscle_group_id, role, activation_ratio)
SELECT test_seed.ex(s.slug), test_seed.mg('chest'), 'primary', 1.00
FROM (VALUES ('test-draft-exercise'), ('test-archived-exercise'), ('test-deleted-exercise')) AS s(slug);

INSERT INTO catalog.exercise_instructions (exercise_id, step_no, content)
SELECT test_seed.ex(s.slug), n, format('Bước %s của bài test.', n)
FROM (VALUES ('test-draft-exercise'), ('test-archived-exercise'), ('test-deleted-exercise')) AS s(slug)
CROSS JOIN generate_series(1, 3) AS n;

-- Thiết bị đã ngừng dùng (xoá mềm) kèm nhãn AI → fn_exercises_for_ai_label phải trả rỗng
INSERT INTO catalog.equipment (code, name, name_en, category_id, description, created_by, updated_by, deleted_at)
SELECT 'test_retired_machine', '[TEST] Máy đã ngừng dùng', 'Retired Machine', c.id,
       'Thiết bị đã gỡ khỏi phòng tập (xoá mềm).', test_seed.uid(2), test_seed.uid(2), now() - interval '20 days'
FROM catalog.equipment_categories c WHERE c.code = 'machine';

INSERT INTO catalog.equipment_aliases (equipment_id, alias, alias_type)
VALUES (test_seed.eq('test_retired_machine'), 'test_retired_machine', 'ai_label');

INSERT INTO catalog.exercise_equipment (exercise_id, equipment_id, is_optional)
VALUES (test_seed.ex('test-deleted-exercise'), test_seed.eq('test_retired_machine'), false);

-- ---------------------------------------------------------------------
-- Ca biên: giáo án mẫu draft & archived
-- ---------------------------------------------------------------------
INSERT INTO training.workout_plans (id, owner_user_id, name, description, goal_type_id, difficulty_level_id, duration_weeks, status)
SELECT v.id::uuid, NULL, v.name, v.description, g.id, d.id, 4, v.status::training.plan_status
FROM (VALUES
    ('5eed1000-0000-4000-8000-000000000007', '[TEST] Giáo án mẫu nháp',        'Đang soạn, KHÔNG hiển thị cho user.',      'draft'),
    ('5eed1000-0000-4000-8000-000000000008', '[TEST] Giáo án mẫu ngừng áp dụng', 'Đã lưu trữ, KHÔNG hiển thị cho user mới.', 'archived')
) AS v(id, name, description, status)
JOIN body.fitness_goal_types g ON g.code = 'maintain'
JOIN catalog.difficulty_levels d ON d.code = 'beginner';

INSERT INTO training.workout_plan_days (plan_id, day_no, name)
VALUES (test_seed.template(7), 1, 'Ngày 1'), (test_seed.template(8), 1, 'Ngày 1');

INSERT INTO training.workout_plan_exercises (plan_day_id, exercise_id, order_no, target_sets, target_reps_min, target_reps_max)
SELECT d.id, test_seed.ex('push-up'), 1, 3, 10, 12
FROM training.workout_plan_days d
WHERE d.plan_id IN (test_seed.template(7), test_seed.template(8));
