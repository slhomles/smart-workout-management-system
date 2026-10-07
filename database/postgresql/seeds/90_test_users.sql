-- =====================================================================
-- Smart Workout AI — TEST DATA (1/7): hàm hỗ trợ + 16 persona (schema auth)
-- Chỉ chạy khi SW_SEED_TEST ≠ false. KHÔNG dùng cho production.
-- Danh sách persona & tình huống test: docs/database/test-dataset.md
-- Mật khẩu chung: Demo@123 — UUID cố định 5eed0000-0000-4000-8000-0000000000NN
-- =====================================================================

-- ---------------------------------------------------------------------
-- Schema tạm chứa hàm hỗ trợ seed (bị xoá ở 99_test_cleanup.sql)
-- ---------------------------------------------------------------------
CREATE SCHEMA test_seed;

-- UUID cố định của persona số n
CREATE FUNCTION test_seed.uid(p_n integer) RETURNS uuid LANGUAGE sql IMMUTABLE AS
$$ SELECT format('5eed0000-0000-4000-8000-%s', lpad(p_n::text, 12, '0'))::uuid $$;

-- UUID cố định của giáo án mẫu số n (khớp 05_plan_templates.sql)
CREATE FUNCTION test_seed.template(p_n integer) RETURNS uuid LANGUAGE sql IMMUTABLE AS
$$ SELECT format('5eed1000-0000-4000-8000-%s', lpad(p_n::text, 12, '0'))::uuid $$;

CREATE FUNCTION test_seed.ex(p_slug text) RETURNS integer LANGUAGE sql STABLE AS
$$ SELECT id FROM catalog.exercises WHERE slug = p_slug $$;

CREATE FUNCTION test_seed.mg(p_code text) RETURNS smallint LANGUAGE sql STABLE AS
$$ SELECT id FROM catalog.muscle_groups WHERE code = p_code $$;

CREATE FUNCTION test_seed.eq(p_code text) RETURNS integer LANGUAGE sql STABLE AS
$$ SELECT id FROM catalog.equipment WHERE code = p_code $$;

CREATE FUNCTION test_seed.token_hash(p_raw text) RETURNS char(64) LANGUAGE sql IMMUTABLE AS
$$ SELECT encode(public.digest(p_raw, 'sha256'), 'hex') $$;

-- Ngày + giờ địa phương → timestamptz
CREATE FUNCTION test_seed.at_local(p_date date, p_time time, p_tz text DEFAULT 'Asia/Ho_Chi_Minh')
RETURNS timestamptz LANGUAGE sql STABLE AS
$$ SELECT (p_date + p_time) AT TIME ZONE p_tz $$;

-- Ghi một file giả lên media.media_files (checksum giả = sha256(object_key))
CREATE FUNCTION test_seed.media(p_uploader uuid, p_key text, p_mime text, p_size bigint,
                                p_w integer DEFAULT NULL, p_h integer DEFAULT NULL, p_dur integer DEFAULT NULL,
                                p_status media.media_status DEFAULT 'available',
                                p_created timestamptz DEFAULT now())
RETURNS uuid LANGUAGE sql AS
$$
    INSERT INTO media.media_files (uploaded_by_user_id, storage_provider, bucket, object_key, original_filename, mime_type,
                                   size_bytes, checksum_sha256, width_px, height_px, duration_ms, status, created_at, updated_at)
    VALUES (p_uploader, 's3', 'smart-workout-media', p_key, regexp_replace(p_key, '^.*/', ''), p_mime,
            CASE WHEN p_status = 'pending_upload' THEN NULL ELSE p_size END,
            CASE WHEN p_status = 'pending_upload' THEN NULL ELSE encode(public.digest(p_key, 'sha256'), 'hex') END,
            p_w, p_h, p_dur, p_status, p_created, p_created)
    RETURNING id
$$;

-- Nhân bản giáo án mẫu cho một user (giữ source_plan_id)
CREATE FUNCTION test_seed.clone_plan(p_template uuid, p_owner uuid, p_name text,
                                     p_status training.plan_status DEFAULT 'active',
                                     p_created timestamptz DEFAULT now())
RETURNS uuid LANGUAGE plpgsql AS
$$
DECLARE
    v_plan uuid;
BEGIN
    INSERT INTO training.workout_plans (owner_user_id, source_plan_id, name, description, goal_type_id,
                                        difficulty_level_id, duration_weeks, status, created_at, updated_at)
    SELECT p_owner, t.id, p_name, t.description, t.goal_type_id, t.difficulty_level_id, t.duration_weeks, p_status, p_created, p_created
    FROM training.workout_plans t WHERE t.id = p_template
    RETURNING id INTO v_plan;

    INSERT INTO training.workout_plan_days (plan_id, day_no, name, notes, created_at, updated_at)
    SELECT v_plan, d.day_no, d.name, d.notes, p_created, p_created
    FROM training.workout_plan_days d WHERE d.plan_id = p_template;

    INSERT INTO training.workout_plan_exercises (plan_day_id, exercise_id, order_no, target_sets, target_reps_min, target_reps_max,
                                                 target_duration_seconds, target_weight_kg, target_rpe, rest_seconds,
                                                 tempo_eccentric_s, tempo_pause_bottom_s, tempo_concentric_s, tempo_pause_top_s,
                                                 notes, created_at, updated_at)
    SELECT nd.id, pe.exercise_id, pe.order_no, pe.target_sets, pe.target_reps_min, pe.target_reps_max,
           pe.target_duration_seconds, pe.target_weight_kg, pe.target_rpe, pe.rest_seconds,
           pe.tempo_eccentric_s, pe.tempo_pause_bottom_s, pe.tempo_concentric_s, pe.tempo_pause_top_s,
           pe.notes, p_created, p_created
    FROM training.workout_plan_exercises pe
    JOIN training.workout_plan_days od ON od.id = pe.plan_day_id AND od.plan_id = p_template
    JOIN training.workout_plan_days nd ON nd.plan_id = v_plan AND nd.day_no = od.day_no;

    RETURN v_plan;
END
$$;

-- Xếp lịch một buổi của giáo án (p_day_no) vào ngày p_date
CREATE FUNCTION test_seed.schedule(p_user uuid, p_plan uuid, p_day_no integer, p_date date,
                                   p_status training.schedule_status DEFAULT 'planned',
                                   p_title text DEFAULT NULL, p_notes text DEFAULT NULL)
RETURNS uuid LANGUAGE sql AS
$$
    INSERT INTO training.scheduled_workouts (user_id, plan_day_id, scheduled_date, title, status, notes)
    SELECT p_user, d.id, p_date, p_title, p_status, p_notes
    FROM (SELECT 1) AS one
    LEFT JOIN training.workout_plan_days d ON d.plan_id = p_plan AND d.day_no = p_day_no
    RETURNING id
$$;

-- Ghi một buổi tập từ đặc tả JSON (chỉ là ĐẦU VÀO của script seed, DB không lưu JSON):
--   [{"slug": "...", "via": "wiki", "rest": 90, "sets": [[reps, kg, rpe, "set_type", duration_s, distance_m, done], ...]}, ...]
-- Phần tử thiếu = NULL; set_type mặc định working; done mặc định true (false → completed_at NULL).
CREATE FUNCTION test_seed.log_session(p_user uuid, p_name text, p_start timestamptz, p_minutes integer, p_exercises jsonb,
                                      p_scheduled uuid DEFAULT NULL,
                                      p_status training.session_status DEFAULT 'completed',
                                      p_session_rpe numeric DEFAULT NULL,
                                      p_deleted_at timestamptz DEFAULT NULL,
                                      p_notes text DEFAULT NULL)
RETURNS uuid LANGUAGE plpgsql AS
$$
DECLARE
    v_session   uuid;
    v_plan_day  uuid;
    v_ex        integer;
    v_plan_ex   uuid;
    v_se        uuid;
    v_end       timestamptz;
    v_minute    integer := 6;
    r_ex        record;
    r_set       record;
BEGIN
    SELECT sw.plan_day_id INTO v_plan_day FROM training.scheduled_workouts sw WHERE sw.id = p_scheduled;
    v_end := CASE WHEN p_status = 'in_progress' THEN NULL ELSE p_start + p_minutes * interval '1 minute' END;

    INSERT INTO training.workout_sessions (user_id, scheduled_workout_id, name, started_at, ended_at, status,
                                           session_rpe, notes, created_at, updated_at, deleted_at)
    VALUES (p_user, p_scheduled, p_name, p_start, v_end, p_status, p_session_rpe, p_notes,
            p_start, coalesce(v_end, p_start), p_deleted_at)
    RETURNING id INTO v_session;

    FOR r_ex IN SELECT x.value AS spec, x.ordinality AS ord FROM jsonb_array_elements(p_exercises) WITH ORDINALITY AS x LOOP
        v_ex := test_seed.ex(r_ex.spec->>'slug');
        IF v_ex IS NULL THEN
            RAISE EXCEPTION 'test_seed.log_session: không có bài tập %', r_ex.spec->>'slug';
        END IF;
        v_plan_ex := NULL;
        SELECT pe.id INTO v_plan_ex
        FROM training.workout_plan_exercises pe
        WHERE pe.plan_day_id = v_plan_day AND pe.exercise_id = v_ex
        ORDER BY pe.order_no LIMIT 1;

        INSERT INTO training.session_exercises (session_id, exercise_id, plan_exercise_id, order_no, added_via, notes, created_at, updated_at)
        VALUES (v_session, v_ex, v_plan_ex, r_ex.ord,
                coalesce((r_ex.spec->>'via')::training.added_via,
                         CASE WHEN v_plan_ex IS NULL THEN 'manual' ELSE 'plan' END::training.added_via),
                r_ex.spec->>'note', p_start, p_start)
        RETURNING id INTO v_se;

        FOR r_set IN SELECT y.value AS s, y.ordinality AS n FROM jsonb_array_elements(r_ex.spec->'sets') WITH ORDINALITY AS y LOOP
            v_minute := v_minute + 3;
            INSERT INTO training.exercise_sets (session_exercise_id, set_no, set_type, reps, weight_kg, rpe,
                                                duration_seconds, distance_m, rest_seconds, source, completed_at,
                                                created_at, updated_at)
            VALUES (v_se, r_set.n,
                    coalesce(r_set.s->>3, 'working')::training.set_type,
                    (r_set.s->>0)::smallint,
                    (r_set.s->>1)::numeric,
                    (r_set.s->>2)::numeric,
                    (r_set.s->>4)::integer,
                    (r_set.s->>5)::numeric,
                    coalesce((r_ex.spec->>'rest')::smallint, 90),
                    'manual',
                    CASE WHEN coalesce((r_set.s->>6)::boolean, true)
                         THEN least(p_start + v_minute * interval '1 minute', coalesce(v_end, now()))
                    END,
                    p_start, p_start);
        END LOOP;
    END LOOP;
    RETURN v_session;
END
$$;

-- Ghi buổi tập theo đúng chỉ tiêu của buổi giáo án đã xếp lịch.
--   p_weights: {"slug": kg_cơ_sở, ...} (bài không có trong map = tự thân, weight NULL)
--   p_progress: hệ số nhân tạ (tăng dần theo tuần); p_rpe: RPE hiệp đầu (+0.5 mỗi 2 hiệp)
--   p_rep_drop: số rep giảm thêm ở hiệp cuối (mô phỏng mệt)
CREATE FUNCTION test_seed.log_plan_session(p_user uuid, p_scheduled uuid, p_start timestamptz, p_minutes integer,
                                           p_weights jsonb, p_progress numeric DEFAULT 1.0,
                                           p_rpe numeric DEFAULT 7.5, p_rep_drop integer DEFAULT 1)
RETURNS uuid LANGUAGE plpgsql AS
$$
DECLARE
    v_spec  jsonb;
    v_name  text;
BEGIN
    SELECT d.name INTO v_name
    FROM training.scheduled_workouts sw JOIN training.workout_plan_days d ON d.id = sw.plan_day_id
    WHERE sw.id = p_scheduled;

    SELECT jsonb_agg(
               jsonb_build_object(
                   'slug', e.slug,
                   'rest', pe.rest_seconds,
                   'sets', (SELECT jsonb_agg(jsonb_build_array(
                                CASE WHEN pe.target_reps_max IS NULL THEN NULL
                                     ELSE greatest(1, pe.target_reps_max
                                                      - CASE WHEN gs.n = pe.target_sets THEN p_rep_drop ELSE 0 END) END,
                                CASE WHEN p_weights ? e.slug
                                     THEN round((p_weights->>e.slug)::numeric * p_progress / 2.5) * 2.5 END,
                                CASE WHEN pe.target_reps_max IS NULL THEN NULL
                                     ELSE least(10, p_rpe + floor((gs.n - 1) / 2.0) * 0.5) END,
                                'working',
                                pe.target_duration_seconds) ORDER BY gs.n)
                            FROM generate_series(1, pe.target_sets) AS gs(n))
               ) ORDER BY pe.order_no)
    INTO v_spec
    FROM training.scheduled_workouts sw
    JOIN training.workout_plan_exercises pe ON pe.plan_day_id = sw.plan_day_id
    JOIN catalog.exercises e ON e.id = pe.exercise_id
    WHERE sw.id = p_scheduled;

    RETURN test_seed.log_session(p_user, v_name, p_start, p_minutes, v_spec, p_scheduled, 'completed', least(10, p_rpe + 0.5));
END
$$;

-- =====================================================================
-- auth.users — 16 persona
-- =====================================================================
INSERT INTO auth.users (id, email, phone_number, password_hash, status, email_verified_at, phone_verified_at,
                        password_changed_at, locked_until, created_at, updated_at, deleted_at)
SELECT test_seed.uid(v.n), v.email, v.phone,
       CASE WHEN v.has_password THEN crypt('Demo@123', gen_salt('bf', 10)) END,
       v.status::auth.user_status,
       CASE WHEN v.verified THEN now() - v.age_days * interval '1 day' + interval '10 minutes' END,
       CASE WHEN v.phone IS NOT NULL AND v.verified THEN now() - v.age_days * interval '1 day' + interval '1 hour' END,
       CASE WHEN v.has_password THEN now() - v.age_days * interval '1 day' END,
       CASE WHEN v.status = 'locked' THEN now() + interval '30 minutes' END,
       now() - v.age_days * interval '1 day',
       now() - least(v.age_days, 1) * interval '1 day',
       CASE WHEN v.deleted THEN now() - interval '10 days' END
FROM (VALUES
    ( 1, 'admin@smartworkout.local',       NULL,           true,  'active',               true,  365, false),
    ( 2, 'editor@smartworkout.local',      NULL,           true,  'active',               true,  300, false),
    ( 3, 'demo@smartworkout.local',        '+84901234567', true,  'active',               true,   60, false),
    ( 4, 'power@smartworkout.local',       '+84912345678', true,  'active',               true,  200, false),
    ( 5, 'dung@smartworkout.local',        NULL,           true,  'active',               true,   70, false),
    ( 6, 'plateau@smartworkout.local',     NULL,           true,  'active',               true,  160, false),
    ( 7, 'inprogress@smartworkout.local',  '+84933334444', true,  'active',               true,   45, false),
    ( 8, 'newbie@smartworkout.local',      NULL,           true,  'active',               true,  0.1, false),
    ( 9, 'unspecified@smartworkout.local', NULL,           true,  'active',               true,   20, false),
    (10, 'other@smartworkout.local',       NULL,           true,  'active',               true,   40, false),
    (11, 'pending@smartworkout.local',     NULL,           true,  'pending_verification', false,   1, false),
    (12, 'locked@smartworkout.local',      NULL,           true,  'locked',               true,   90, false),
    (13, 'disabled@smartworkout.local',    NULL,           true,  'disabled',             true,  120, false),
    (14, 'deleted@smartworkout.local',     NULL,           true,  'active',               true,  150, true),
    (15, 'oauth@smartworkout.local',       NULL,           false, 'active',               true,   30, false),
    (16, 'trainer@smartworkout.local',     '+84987654321', true,  'active',               true,  250, false)
) AS v(n, email, phone, has_password, status, verified, age_days, deleted);

-- ---------------------------------------------------------------------
-- auth.user_profiles (avatar gán ở 95_test_media_reports.sql)
-- ---------------------------------------------------------------------
INSERT INTO auth.user_profiles (user_id, display_name, full_name, locale, timezone, unit_system, created_at, updated_at)
SELECT test_seed.uid(v.n), v.display_name, v.full_name, v.locale, v.tz, v.units::auth.unit_system, u.created_at, u.created_at
FROM (VALUES
    ( 1, 'Admin',   'Quản trị hệ thống',  'vi-VN', 'Asia/Ho_Chi_Minh', 'metric'),
    ( 2, 'Editor',  'Biên tập viên',      'vi-VN', 'Asia/Ho_Chi_Minh', 'metric'),
    ( 3, 'An',      'Nguyễn Văn An',      'vi-VN', 'Asia/Ho_Chi_Minh', 'metric'),
    ( 4, 'Bình',    'Trần Thanh Bình',    'vi-VN', 'Asia/Ho_Chi_Minh', 'metric'),
    ( 5, 'Dung',    'Lê Thị Dung',        'vi-VN', 'Asia/Tokyo',       'metric'),
    ( 6, 'Hải',     'Phạm Minh Hải',      'vi-VN', 'Asia/Ho_Chi_Minh', 'metric'),
    ( 7, 'Khoa',    'Võ Đăng Khoa',       'vi-VN', 'Asia/Ho_Chi_Minh', 'metric'),
    ( 8, 'Mai',     'Đỗ Ngọc Mai',        'vi-VN', 'Asia/Ho_Chi_Minh', 'metric'),
    ( 9, 'Nam',     NULL,                 'vi-VN', 'Asia/Ho_Chi_Minh', 'metric'),
    (10, 'Phuong',  'Bùi Phương',         'en-US', 'Asia/Ho_Chi_Minh', 'imperial'),
    (11, 'Quang',   'Ngô Quang',          'vi-VN', 'Asia/Ho_Chi_Minh', 'metric'),
    (12, 'Sơn',     'Đặng Sơn',           'vi-VN', 'Asia/Ho_Chi_Minh', 'metric'),
    (13, 'Tâm',     'Huỳnh Tâm',          'vi-VN', 'Asia/Ho_Chi_Minh', 'metric'),
    (14, 'Uyên',    'Lý Uyên',            'vi-VN', 'Asia/Ho_Chi_Minh', 'metric'),
    (15, 'Vy',      'Trịnh Vy',           'vi-VN', 'Asia/Ho_Chi_Minh', 'metric'),
    (16, 'Coach Xuân', 'Phan Xuân',       'vi-VN', 'Asia/Ho_Chi_Minh', 'metric')
) AS v(n, display_name, full_name, locale, tz, units)
JOIN auth.users u ON u.id = test_seed.uid(v.n);

-- ---------------------------------------------------------------------
-- auth.user_roles — admin/editor được admin cấp; user tự đăng ký (granted_by NULL)
-- trainer@: content_editor ĐÃ HẾT HẠN
-- ---------------------------------------------------------------------
INSERT INTO auth.user_roles (user_id, role_id, granted_by, granted_at, expires_at)
SELECT test_seed.uid(v.n), r.id,
       CASE WHEN v.granted_by IS NOT NULL THEN test_seed.uid(v.granted_by) END,
       u.created_at + interval '5 minutes',
       CASE WHEN v.expired THEN now() - interval '10 days' END
FROM (VALUES
    ( 1, 'admin',          NULL, false),
    ( 2, 'content_editor', 1,    false),
    ( 3, 'user', NULL, false), ( 4, 'user', NULL, false), ( 5, 'user', NULL, false), ( 6, 'user', NULL, false),
    ( 7, 'user', NULL, false), ( 8, 'user', NULL, false), ( 9, 'user', NULL, false), (10, 'user', NULL, false),
    (11, 'user', NULL, false), (12, 'user', NULL, false), (13, 'user', NULL, false), (14, 'user', NULL, false),
    (15, 'user', NULL, false), (16, 'user', NULL, false),
    (16, 'content_editor', 1, true)
) AS v(n, role_code, granted_by, expired)
JOIN auth.roles r ON r.code = v.role_code
JOIN auth.users u ON u.id = test_seed.uid(v.n);

-- ---------------------------------------------------------------------
-- auth.oauth_accounts
-- ---------------------------------------------------------------------
INSERT INTO auth.oauth_accounts (user_id, provider, provider_subject, provider_email, linked_at)
VALUES
    (test_seed.uid(3),  'google', '109876543210000000003', 'nguyenvanan.demo@gmail.com', now() - interval '59 days'),
    (test_seed.uid(15), 'google', '109876543210000000015', 'trinhvy.demo@gmail.com',     now() - interval '30 days'),
    (test_seed.uid(15), 'apple',  '001234.abcdef0123456789.0015', 'vy-relay@privaterelay.appleid.com', now() - interval '12 days');

-- ---------------------------------------------------------------------
-- auth.user_devices
-- ---------------------------------------------------------------------
INSERT INTO auth.user_devices (user_id, platform, device_name, os_version, app_version, push_token, push_token_updated_at,
                               last_seen_at, revoked_at, created_at, updated_at)
SELECT test_seed.uid(v.n), v.platform::auth.device_platform, v.device_name, v.os, v.app,
       CASE WHEN v.push THEN 'fcm-test-' || v.n || '-' || v.k END,
       CASE WHEN v.push THEN now() - v.seen_days * interval '1 day' END,
       now() - v.seen_days * interval '1 day',
       CASE WHEN v.revoked THEN now() - interval '30 days' END,
       now() - v.created_days * interval '1 day',
       now() - v.seen_days * interval '1 day'
FROM (VALUES
    ( 1, 1, 'web',     'Chrome trên Windows',   '128',  '1.0.0', false,   0,  365, false),
    ( 2, 1, 'web',     'Edge trên Windows',     '128',  '1.0.0', false,   1,  300, false),
    ( 3, 1, 'android', 'Pixel 8 của An',        '15',   '1.0.0', true,    0,   60, false),
    ( 4, 1, 'ios',     'iPhone 15 Pro',         '18.0', '1.0.0', true,    0,  120, false),
    ( 4, 2, 'web',     'Safari trên macOS',     '18.0', '1.0.0', false,   3,   90, false),
    ( 4, 3, 'android', 'Galaxy S21 (máy cũ)',   '13',   '0.9.0', true,   40,  200, true),
    ( 5, 1, 'ios',     'iPhone 13 của Dung',    '17.6', '1.0.0', true,    1,   70, false),
    ( 7, 1, 'android', 'Redmi Note 12',         '14',   '1.0.0', true,    0,   45, false),
    (12, 1, 'android', 'Oppo A78',              '13',   '1.0.0', true,    2,   90, false),
    (13, 1, 'web',     'Firefox trên Ubuntu',   '130',  '1.0.0', false,  15,  120, false),
    (15, 1, 'ios',     'iPhone 14 của Vy',      '18.0', '1.0.0', true,    0,   30, false),
    (16, 1, 'android', 'Galaxy Tab S9',         '14',   '1.0.0', true,    1,  250, false)
) AS v(n, k, platform, device_name, os, app, push, seen_days, created_days, revoked);

-- ---------------------------------------------------------------------
-- auth.refresh_tokens — dùng device_name để tìm thiết bị
--   demo@:     chuỗi xoay vòng (rotated → active) + 1 phiên đã logout
--   power@:    token active trên iOS & web, token thiết bị cũ bị thu hồi device_revoked
--   dung@:     1 token hết hạn tự nhiên (chưa thu hồi) → test job dọn dẹp
--   locked@:   family bị thu hồi reuse_detected
--   disabled@: thu hồi admin_revoked
-- ---------------------------------------------------------------------
CREATE TEMP TABLE tmp_tokens (key text, device_name text, family text, parent_key text,
                              issued_days numeric, expires_days numeric, revoked_days numeric, reason text) ON COMMIT DROP;
INSERT INTO tmp_tokens VALUES
    ('demo-1',     'Pixel 8 của An',        'demo-a',   NULL,         8,  -1,    1,    'rotated'),
    ('demo-2',     'Pixel 8 của An',        'demo-a',   'demo-1',     1,  -6,    NULL, NULL),
    ('demo-old',   'Pixel 8 của An',        'demo-b',   NULL,        40,  33,   35,    'logout'),
    ('power-ios',  'iPhone 15 Pro',         'power-a',  NULL,         2,  -5,    NULL, NULL),
    ('power-web',  'Safari trên macOS',     'power-b',  NULL,         3,  -4,    NULL, NULL),
    ('power-old',  'Galaxy S21 (máy cũ)',   'power-c',  NULL,        45,  38,   30,    'device_revoked'),
    ('dung-1',     'iPhone 13 của Dung',    'dung-a',   NULL,         1,  -6,    NULL, NULL),
    ('dung-exp',   'iPhone 13 của Dung',    'dung-b',   NULL,        20,  13,    NULL, NULL),
    ('khoa-1',     'Redmi Note 12',         'khoa-a',   NULL,         0.5, -6.5, NULL, NULL),
    ('locked-1',   'Oppo A78',              'locked-a', NULL,         3,  -4,    0.02, 'rotated'),
    ('locked-2',   'Oppo A78',              'locked-a', 'locked-1',   0.5, -6.5, 0.01, 'reuse_detected'),
    ('disabled-1', 'Firefox trên Ubuntu',   'disab-a',  NULL,        16,  -1,   14,    'admin_revoked'),
    ('vy-1',       'iPhone 14 của Vy',      'vy-a',     NULL,         0.2, -6.8, NULL, NULL),
    ('admin-1',    'Chrome trên Windows',   'admin-a',  NULL,         0.1, -6.9, NULL, NULL),
    ('editor-1',   'Edge trên Windows',     'editor-a', NULL,         1,  -6,    NULL, NULL),
    ('trainer-1',  'Galaxy Tab S9',         'train-a',  NULL,         1,  -6,    NULL, NULL);

INSERT INTO auth.refresh_tokens (device_id, family_id, token_hash, issued_at, expires_at, revoked_at, revoke_reason, ip_address, user_agent)
SELECT d.id,
       ('5eed2000-0000-4000-8000-' || lpad(dense_rank() OVER (ORDER BY t.family)::text, 12, '0'))::uuid,
       test_seed.token_hash('seed-refresh-' || t.key),
       now() - t.issued_days * interval '1 day',
       now() - t.expires_days * interval '1 day',
       CASE WHEN t.revoked_days IS NOT NULL THEN now() - t.revoked_days * interval '1 day' END,
       t.reason::auth.token_revoke_reason,
       '113.161.10.20'::inet,
       'SmartWorkout/1.0 (' || d.platform || ')'
FROM tmp_tokens t
JOIN auth.user_devices d ON d.device_name = t.device_name;

UPDATE auth.refresh_tokens rt
SET parent_token_id = parent.id
FROM tmp_tokens t
JOIN auth.refresh_tokens parent ON parent.token_hash = test_seed.token_hash('seed-refresh-' || t.parent_key)
WHERE t.parent_key IS NOT NULL
  AND rt.token_hash = test_seed.token_hash('seed-refresh-' || t.key);

-- ---------------------------------------------------------------------
-- auth.verification_tokens
-- ---------------------------------------------------------------------
INSERT INTO auth.verification_tokens (user_id, purpose, token_hash, created_at, expires_at, consumed_at)
VALUES
    -- pending@: token xác thực email còn hạn + 1 token cũ đã hết hạn
    (test_seed.uid(11), 'email_verification', test_seed.token_hash('seed-verify-pending-valid'),   now() - interval '1 hour',  now() + interval '23 hours', NULL),
    (test_seed.uid(11), 'email_verification', test_seed.token_hash('seed-verify-pending-expired'), now() - interval '26 hours', now() - interval '2 hours', NULL),
    -- demo@: đã xác thực email từ lâu
    (test_seed.uid(3),  'email_verification', test_seed.token_hash('seed-verify-demo-used'),       now() - interval '60 days', now() - interval '59 days', now() - interval '60 days' + interval '10 minutes'),
    -- trainer@: reset mật khẩu còn hạn / hết hạn / đã dùng
    (test_seed.uid(16), 'password_reset',     test_seed.token_hash('seed-reset-trainer-valid'),    now() - interval '5 minutes', now() + interval '25 minutes', NULL),
    (test_seed.uid(16), 'password_reset',     test_seed.token_hash('seed-reset-trainer-expired'),  now() - interval '2 days',  now() - interval '2 days' + interval '30 minutes', NULL),
    (test_seed.uid(16), 'password_reset',     test_seed.token_hash('seed-reset-trainer-used'),     now() - interval '30 days', now() - interval '30 days' + interval '30 minutes', now() - interval '30 days' + interval '3 minutes');

-- ---------------------------------------------------------------------
-- auth.login_attempts
-- ---------------------------------------------------------------------
INSERT INTO auth.login_attempts (user_id, email_attempted, ip_address, user_agent, succeeded, failure_reason, attempted_at)
-- locked@: 5 lần sai liên tiếp trong 15 phút rồi bị khoá
SELECT test_seed.uid(12), 'locked@smartworkout.local', '14.161.20.30'::inet, 'SmartWorkout/1.0 (android)',
       false, 'invalid_credentials'::auth.login_failure_reason, now() - (16 - i * 3) * interval '1 minute'
FROM generate_series(1, 5) AS i
UNION ALL
SELECT test_seed.uid(12), 'locked@smartworkout.local', '14.161.20.30', 'SmartWorkout/1.0 (android)', false, 'account_locked', now() - interval '30 seconds'
UNION ALL
-- dò mật khẩu từ một IP với nhiều email không tồn tại
SELECT NULL, format('user%s@example.com', i), '185.220.101.4', 'python-requests/2.32', false, 'invalid_credentials',
       now() - interval '2 days' + i * interval '7 seconds'
FROM generate_series(1, 8) AS i
UNION ALL
-- power@: đăng nhập thành công hằng ngày 14 ngày gần nhất
SELECT test_seed.uid(4), 'power@smartworkout.local', '27.72.88.10', 'SmartWorkout/1.0 (ios)', true, NULL,
       now() - i * interval '1 day' + interval '7 hours'
FROM generate_series(1, 14) AS i
UNION ALL
SELECT * FROM (VALUES
    (test_seed.uid(3),  'demo@smartworkout.local',     '113.161.10.20'::inet, 'SmartWorkout/1.0 (android)', false, 'invalid_credentials'::auth.login_failure_reason, now() - interval '8 days 2 minutes'),
    (test_seed.uid(3),  'demo@smartworkout.local',     '113.161.10.20', 'SmartWorkout/1.0 (android)', true,  NULL,                  now() - interval '8 days'),
    (test_seed.uid(3),  'demo@smartworkout.local',     '113.161.10.20', 'SmartWorkout/1.0 (android)', true,  NULL,                  now() - interval '1 day'),
    (test_seed.uid(11), 'pending@smartworkout.local',  '42.115.3.9',    'SmartWorkout/1.0 (ios)',     false, 'email_not_verified',  now() - interval '50 minutes'),
    (test_seed.uid(13), 'disabled@smartworkout.local', '171.244.5.6',   'Mozilla/5.0 Firefox/130',    false, 'account_disabled',    now() - interval '3 days'),
    (test_seed.uid(15), 'oauth@smartworkout.local',    '1.53.40.2',     'SmartWorkout/1.0 (ios)',     false, 'oauth_error',         now() - interval '12 days'),
    (test_seed.uid(15), 'oauth@smartworkout.local',    '1.53.40.2',     'SmartWorkout/1.0 (ios)',     true,  NULL,                  now() - interval '12 days' + interval '1 minute'),
    (test_seed.uid(1),  'admin@smartworkout.local',    '10.0.0.5',      'Mozilla/5.0 Chrome/128',     true,  NULL,                  now() - interval '2 hours')
) AS v(user_id, email, ip, ua, ok, reason, at);
