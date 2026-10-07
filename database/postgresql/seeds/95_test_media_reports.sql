-- =====================================================================
-- Smart Workout AI — TEST DATA (6/7): avatar, ảnh tiến độ, báo cáo, báo đau cơ,
-- và các file ở trạng thái đặc biệt (test job dọn dẹp)
-- (power@ đã có ảnh & báo cáo riêng ở 94_test_power_user.sql)
-- =====================================================================

DO $$
DECLARE
    v_demo_first  uuid;
    v_demo_last   uuid;
    v_old_avatar  uuid;
BEGIN
    -- -----------------------------------------------------------------
    -- Avatar
    -- -----------------------------------------------------------------
    UPDATE auth.user_profiles p
    SET avatar_media_id = test_seed.media(p.user_id, format('users/%s/avatar.jpg', p.user_id), 'image/jpeg',
                                          85000, 512, 512, NULL, 'available', now() - interval '20 days')
    WHERE p.user_id IN (test_seed.uid(3), test_seed.uid(4), test_seed.uid(5), test_seed.uid(15), test_seed.uid(16));

    -- -----------------------------------------------------------------
    -- demo@: trước/sau 6 tuần, 1 ảnh đang xử lý, 1 ảnh đã xoá mềm
    -- -----------------------------------------------------------------
    INSERT INTO media.progress_photos (user_id, original_media_id, watermarked_media_id, thumbnail_media_id, angle, capture_source,
                                       taken_at, processing_status, created_at, updated_at)
    VALUES (test_seed.uid(3),
            test_seed.media(test_seed.uid(3), 'users/demo/progress/w00-front.jpg', 'image/jpeg', 2350000, 3024, 4032, NULL, 'available', now() - interval '42 days'),
            test_seed.media(NULL,             'users/demo/progress/w00-front.wm.jpg', 'image/jpeg', 980000, 1512, 2016, NULL, 'available', now() - interval '42 days'),
            test_seed.media(NULL,             'users/demo/progress/w00-front.thumb.jpg', 'image/jpeg', 42000, 300, 400, NULL, 'available', now() - interval '42 days'),
            'front', 'camera', date_trunc('hour', now() - interval '42 days'), 'completed', now() - interval '42 days', now() - interval '42 days')
    RETURNING id INTO v_demo_first;

    INSERT INTO media.progress_photos (user_id, original_media_id, watermarked_media_id, thumbnail_media_id, angle, capture_source,
                                       taken_at, processing_status, created_at, updated_at)
    VALUES (test_seed.uid(3),
            test_seed.media(test_seed.uid(3), 'users/demo/progress/w06-front.jpg', 'image/jpeg', 2410000, 3024, 4032, NULL, 'available', now() - interval '1 hour'),
            test_seed.media(NULL,             'users/demo/progress/w06-front.wm.jpg', 'image/jpeg', 1010000, 1512, 2016, NULL, 'available', now() - interval '58 minutes'),
            test_seed.media(NULL,             'users/demo/progress/w06-front.thumb.jpg', 'image/jpeg', 43000, 300, 400, NULL, 'available', now() - interval '58 minutes'),
            'front', 'camera', date_trunc('minute', now() - interval '1 hour'), 'completed', now() - interval '1 hour', now() - interval '58 minutes')
    RETURNING id INTO v_demo_last;

    INSERT INTO media.photo_comparisons (before_photo_id, after_photo_id, title)
    VALUES (v_demo_first, v_demo_last, '6 tuần giảm mỡ');

    INSERT INTO media.progress_photos (user_id, original_media_id, angle, capture_source, taken_at, processing_status)
    VALUES (test_seed.uid(3),
            test_seed.media(test_seed.uid(3), 'users/demo/progress/w06-side.jpg', 'image/jpeg', 2280000, 3024, 4032),
            'side', 'library', date_trunc('minute', now() - interval '50 minutes'), 'processing');

    INSERT INTO media.progress_photos (user_id, original_media_id, watermarked_media_id, angle, capture_source, taken_at,
                                       processing_status, note, deleted_at)
    VALUES (test_seed.uid(3),
            test_seed.media(test_seed.uid(3), 'users/demo/progress/w03-front.jpg', 'image/jpeg', 2300000, 3024, 4032, NULL, 'available', now() - interval '21 days'),
            test_seed.media(NULL,             'users/demo/progress/w03-front.wm.jpg', 'image/jpeg', 990000, 1512, 2016, NULL, 'available', now() - interval '21 days'),
            'front', 'camera', date_trunc('hour', now() - interval '21 days'), 'completed', 'Ảnh mờ, đã xoá', now() - interval '20 days');

    -- -----------------------------------------------------------------
    -- dung@: completed / failed / queued
    -- -----------------------------------------------------------------
    INSERT INTO media.progress_photos (user_id, original_media_id, watermarked_media_id, thumbnail_media_id, angle, capture_source,
                                       taken_at, processing_status)
    VALUES (test_seed.uid(5),
            test_seed.media(test_seed.uid(5), 'users/dung/progress/w00-front.jpg', 'image/jpeg', 2100000, 3024, 4032, NULL, 'available', now() - interval '56 days'),
            test_seed.media(NULL,             'users/dung/progress/w00-front.wm.jpg', 'image/jpeg', 900000, 1512, 2016, NULL, 'available', now() - interval '56 days'),
            test_seed.media(NULL,             'users/dung/progress/w00-front.thumb.jpg', 'image/jpeg', 40000, 300, 400, NULL, 'available', now() - interval '56 days'),
            'front', 'camera', date_trunc('hour', now() - interval '56 days'), 'completed');

    INSERT INTO media.progress_photos (user_id, original_media_id, angle, capture_source, taken_at, processing_status, processing_error)
    VALUES (test_seed.uid(5),
            test_seed.media(test_seed.uid(5), 'users/dung/progress/w04-back.heic', 'image/heic', 1800000, 3024, 4032, NULL, 'available', now() - interval '28 days'),
            'back', 'library', date_trunc('hour', now() - interval '28 days'), 'failed', 'Không giải mã được ảnh HEIC (thiếu codec)');

    INSERT INTO media.progress_photos (user_id, original_media_id, angle, capture_source, taken_at, processing_status)
    VALUES (test_seed.uid(5),
            test_seed.media(test_seed.uid(5), 'users/dung/progress/w08-front.jpg', 'image/jpeg', 2150000, 3024, 4032),
            'front', 'camera', date_trunc('minute', now() - interval '30 minutes'), 'queued');

    -- plateau@ và deleted@ (tài khoản đã xoá mềm)
    INSERT INTO media.progress_photos (user_id, original_media_id, watermarked_media_id, thumbnail_media_id, angle, capture_source,
                                       taken_at, processing_status)
    VALUES (test_seed.uid(6),
            test_seed.media(test_seed.uid(6), 'users/plateau/progress/side.jpg', 'image/jpeg', 2000000, 3024, 4032, NULL, 'available', now() - interval '30 days'),
            test_seed.media(NULL,             'users/plateau/progress/side.wm.jpg', 'image/jpeg', 880000, 1512, 2016, NULL, 'available', now() - interval '30 days'),
            test_seed.media(NULL,             'users/plateau/progress/side.thumb.jpg', 'image/jpeg', 39000, 300, 400, NULL, 'available', now() - interval '30 days'),
            'side', 'camera', date_trunc('hour', now() - interval '30 days'), 'completed'),
           (test_seed.uid(14),
            test_seed.media(test_seed.uid(14), 'users/deleted/progress/front.jpg', 'image/jpeg', 1900000, 3024, 4032, NULL, 'available', now() - interval '130 days'),
            test_seed.media(NULL,              'users/deleted/progress/front.wm.jpg', 'image/jpeg', 850000, 1512, 2016, NULL, 'available', now() - interval '130 days'),
            NULL,
            'front', 'camera', date_trunc('hour', now() - interval '130 days'), 'completed');

    -- -----------------------------------------------------------------
    -- Báo cáo đã xuất
    -- -----------------------------------------------------------------
    INSERT INTO analytics.report_exports (user_id, report_type, period_start, media_id, created_at)
    VALUES (test_seed.uid(3), 'weekly_summary', date_trunc('week', current_date - 7)::date,
            test_seed.media(NULL, 'users/demo/reports/weekly-last.png', 'image/png', 350000, 1080, 1920), now() - interval '1 day'),
           (test_seed.uid(5), 'monthly_summary', (date_trunc('month', current_date) - interval '1 month')::date,
            test_seed.media(NULL, 'users/dung/reports/monthly-last.png', 'image/png', 410000, 1080, 1920), now() - interval '3 days');

    -- -----------------------------------------------------------------
    -- Báo đau mỏi cơ (user tự nhập)
    -- -----------------------------------------------------------------
    INSERT INTO training.muscle_soreness_reports (user_id, muscle_group_id, soreness_level, reported_at, note)
    VALUES (test_seed.uid(3), test_seed.mg('chest'),   6, date_trunc('minute', now() - interval '8 hours'), 'Ê ngực khi giơ tay'),
           (test_seed.uid(3), test_seed.mg('triceps'), 4, date_trunc('minute', now() - interval '8 hours'), NULL),
           (test_seed.uid(5), test_seed.mg('glutes'),  5, date_trunc('minute', now() - interval '1 day'),   NULL),
           (test_seed.uid(7), test_seed.mg('quads'),   7, date_trunc('minute', now() - interval '2 days'),  'Đau đùi sau buổi circuit');

    -- -----------------------------------------------------------------
    -- File ở trạng thái đặc biệt (không gắn với bản ghi nghiệp vụ nào)
    -- -----------------------------------------------------------------
    -- Upload treo > 24h (job dọn dẹp PHẢI xoá) và upload vừa tạo (KHÔNG được xoá)
    PERFORM test_seed.media(test_seed.uid(3), 'users/demo/uploads/tmp-stale.jpg', 'image/jpeg', 0, NULL, NULL, NULL, 'pending_upload', now() - interval '2 days');
    PERFORM test_seed.media(test_seed.uid(7), 'users/khoa/uploads/tmp-fresh.mp4', 'video/mp4', 0, NULL, NULL, NULL, 'pending_upload', now() - interval '5 minutes');
    -- Upload lỗi và file bị chặn kiểm duyệt
    PERFORM test_seed.media(test_seed.uid(7), 'users/khoa/uploads/broken.jpg', 'image/jpeg', 1200, NULL, NULL, NULL, 'failed', now() - interval '6 days');
    PERFORM test_seed.media(test_seed.uid(12), 'users/locked/uploads/flagged.jpg', 'image/jpeg', 640000, 1080, 1080, NULL, 'quarantined', now() - interval '40 days');
    -- Avatar cũ đã thay, xoá mềm
    v_old_avatar := test_seed.media(test_seed.uid(3), 'users/demo/avatar-old.jpg', 'image/jpeg', 80000, 512, 512, NULL, 'available', now() - interval '55 days');
    UPDATE media.media_files SET deleted_at = now() - interval '20 days' WHERE id = v_old_avatar;
END
$$;
