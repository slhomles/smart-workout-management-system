-- =====================================================================
-- Smart Workout AI — Seed: RBAC (roles, permissions, role_permissions)
-- =====================================================================

INSERT INTO auth.roles (code, name, description, is_system) VALUES
    ('admin',          'Quản trị viên',       'Toàn quyền hệ thống: người dùng, phân quyền, nội dung, giám sát AI.', true),
    ('content_editor', 'Biên tập nội dung',   'Quản lý thư viện bài tập, thiết bị, nhóm cơ và giáo án mẫu.',          true),
    ('user',           'Người dùng',          'Người tập: quản lý dữ liệu cá nhân và sử dụng tính năng AI.',            true);

INSERT INTO auth.permissions (resource, action, description) VALUES
    -- Nội dung thư viện
    ('exercise',          'read',         'Xem bài tập đã xuất bản'),
    ('exercise',          'create',       'Tạo bài tập'),
    ('exercise',          'update',       'Sửa bài tập'),
    ('exercise',          'delete',       'Xoá (archive) bài tập'),
    ('exercise',          'publish',      'Xuất bản bài tập'),
    ('equipment',         'read',         'Xem thiết bị'),
    ('equipment',         'manage',       'Tạo/sửa/xoá thiết bị và alias nhận diện'),
    ('muscle_group',      'read',         'Xem nhóm cơ'),
    ('muscle_group',      'manage',       'Tạo/sửa nhóm cơ'),
    ('plan_template',     'read',         'Xem giáo án mẫu'),
    ('plan_template',     'manage',       'Tạo/sửa/xuất bản giáo án mẫu'),
    ('media',             'upload',       'Tải file lên Object Storage'),
    ('media',             'moderate',     'Kiểm duyệt/chặn file vi phạm'),
    -- Dữ liệu cá nhân
    ('workout',           'manage_own',   'Quản lý giáo án, lịch tập, buổi tập của chính mình'),
    ('body_metric',       'manage_own',   'Quản lý chỉ số cơ thể và mục tiêu của chính mình'),
    ('progress_photo',    'manage_own',   'Quản lý ảnh tiến độ của chính mình'),
    ('report',            'export_own',   'Xuất báo cáo tuần/tháng của chính mình'),
    ('ai',                'use',          'Dùng phân tích tư thế, đếm rep, nhận diện thiết bị'),
    -- Quản trị
    ('user',              'read',         'Xem danh sách & thông tin người dùng'),
    ('user',              'update',       'Sửa thông tin người dùng'),
    ('user',              'lock',         'Khoá/mở khoá tài khoản'),
    ('user',              'delete',       'Xoá tài khoản'),
    ('role',              'assign',       'Gán/thu hồi vai trò'),
    ('ai_job',            'read',         'Xem hàng đợi job AI'),
    ('ai_job',            'retry',        'Chạy lại job AI lỗi'),
    ('system_report',     'read',         'Xem báo cáo thống kê toàn hệ thống');

-- admin: mọi quyền
INSERT INTO auth.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM auth.roles r
CROSS JOIN auth.permissions p
WHERE r.code = 'admin';

-- content_editor
INSERT INTO auth.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM auth.roles r
JOIN auth.permissions p ON (p.resource, p.action) IN (
    ('exercise', 'read'), ('exercise', 'create'), ('exercise', 'update'), ('exercise', 'delete'), ('exercise', 'publish'),
    ('equipment', 'read'), ('equipment', 'manage'),
    ('muscle_group', 'read'), ('muscle_group', 'manage'),
    ('plan_template', 'read'), ('plan_template', 'manage'),
    ('media', 'upload'))
WHERE r.code = 'content_editor';

-- user
INSERT INTO auth.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM auth.roles r
JOIN auth.permissions p ON (p.resource, p.action) IN (
    ('exercise', 'read'), ('equipment', 'read'), ('muscle_group', 'read'), ('plan_template', 'read'),
    ('media', 'upload'),
    ('workout', 'manage_own'), ('body_metric', 'manage_own'), ('progress_photo', 'manage_own'),
    ('report', 'export_own'), ('ai', 'use'))
WHERE r.code = 'user';
