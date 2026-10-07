-- =====================================================================
-- Smart Workout AI — 05: Body & weight tracking (schema body)
-- Chức năng 3 (Dashboard chỉ số cơ thể). BMI/BMR/TDEE KHÔNG lưu — tính ở view body.v_body_metrics.
-- =====================================================================

CREATE TYPE body.gender AS ENUM ('male', 'female', 'other', 'unspecified');
CREATE TYPE body.measurement_source AS ENUM ('manual', 'smart_scale', 'imported');
CREATE TYPE body.goal_status AS ENUM ('active', 'achieved', 'abandoned');

COMMENT ON TYPE body.gender IS 'Giới tính sinh học dùng cho công thức BMR (other/unspecified dùng hằng số trung bình).';
COMMENT ON TYPE body.measurement_source IS 'Nguồn số đo.';
COMMENT ON TYPE body.goal_status IS 'Trạng thái mục tiêu.';

-- ---------------------------------------------------------------------
-- Bảng tra cứu
-- ---------------------------------------------------------------------
CREATE TABLE body.activity_levels (
    id              smallint        GENERATED ALWAYS AS IDENTITY,
    code            varchar(30)     NOT NULL,
    name            varchar(100)    NOT NULL,
    description     text,
    multiplier      numeric(4,3)    NOT NULL,
    display_order   smallint        NOT NULL DEFAULT 0,
    created_at      timestamptz     NOT NULL DEFAULT now(),
    updated_at      timestamptz     NOT NULL DEFAULT now(),
    CONSTRAINT pk_activity_levels PRIMARY KEY (id),
    CONSTRAINT uq_activity_levels_code UNIQUE (code),
    CONSTRAINT ck_activity_levels_code_format CHECK (code ~ '^[a-z][a-z0-9_]*$'),
    CONSTRAINT ck_activity_levels_multiplier CHECK (multiplier BETWEEN 1.0 AND 2.5)
);
COMMENT ON TABLE  body.activity_levels IS 'Mức độ vận động hằng ngày và hệ số nhân TDEE = BMR × multiplier.';
COMMENT ON COLUMN body.activity_levels.id IS 'Khoá chính.';
COMMENT ON COLUMN body.activity_levels.code IS 'Mã (sedentary/light/moderate/active/very_active).';
COMMENT ON COLUMN body.activity_levels.name IS 'Tên hiển thị.';
COMMENT ON COLUMN body.activity_levels.description IS 'Mô tả (vd: 3–5 buổi/tuần).';
COMMENT ON COLUMN body.activity_levels.multiplier IS 'Hệ số hoạt động (1.2 – 1.9).';
COMMENT ON COLUMN body.activity_levels.display_order IS 'Thứ tự hiển thị.';
COMMENT ON COLUMN body.activity_levels.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN body.activity_levels.updated_at IS 'Thời điểm cập nhật gần nhất.';

CREATE TABLE body.fitness_goal_types (
    id              smallint        GENERATED ALWAYS AS IDENTITY,
    code            varchar(30)     NOT NULL,
    name            varchar(100)    NOT NULL,
    description     text,
    display_order   smallint        NOT NULL DEFAULT 0,
    created_at      timestamptz     NOT NULL DEFAULT now(),
    updated_at      timestamptz     NOT NULL DEFAULT now(),
    CONSTRAINT pk_fitness_goal_types PRIMARY KEY (id),
    CONSTRAINT uq_fitness_goal_types_code UNIQUE (code),
    CONSTRAINT ck_fitness_goal_types_code_format CHECK (code ~ '^[a-z][a-z0-9_]*$')
);
COMMENT ON TABLE  body.fitness_goal_types IS 'Loại mục tiêu tập luyện (giảm mỡ, tăng cơ, duy trì...).';
COMMENT ON COLUMN body.fitness_goal_types.id IS 'Khoá chính.';
COMMENT ON COLUMN body.fitness_goal_types.code IS 'Mã mục tiêu.';
COMMENT ON COLUMN body.fitness_goal_types.name IS 'Tên hiển thị.';
COMMENT ON COLUMN body.fitness_goal_types.description IS 'Mô tả.';
COMMENT ON COLUMN body.fitness_goal_types.display_order IS 'Thứ tự hiển thị.';
COMMENT ON COLUMN body.fitness_goal_types.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN body.fitness_goal_types.updated_at IS 'Thời điểm cập nhật gần nhất.';

CREATE TABLE body.body_sites (
    id              smallint        GENERATED ALWAYS AS IDENTITY,
    code            varchar(30)     NOT NULL,
    name            varchar(100)    NOT NULL,
    display_order   smallint        NOT NULL DEFAULT 0,
    created_at      timestamptz     NOT NULL DEFAULT now(),
    updated_at      timestamptz     NOT NULL DEFAULT now(),
    CONSTRAINT pk_body_sites PRIMARY KEY (id),
    CONSTRAINT uq_body_sites_code UNIQUE (code),
    CONSTRAINT ck_body_sites_code_format CHECK (code ~ '^[a-z][a-z0-9_]*$')
);
COMMENT ON TABLE  body.body_sites IS 'Vị trí đo số đo vòng (eo, ngực, mông, bắp tay...).';
COMMENT ON COLUMN body.body_sites.id IS 'Khoá chính.';
COMMENT ON COLUMN body.body_sites.code IS 'Mã vị trí.';
COMMENT ON COLUMN body.body_sites.name IS 'Tên hiển thị.';
COMMENT ON COLUMN body.body_sites.display_order IS 'Thứ tự hiển thị.';
COMMENT ON COLUMN body.body_sites.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN body.body_sites.updated_at IS 'Thời điểm cập nhật gần nhất.';

-- ---------------------------------------------------------------------
-- body.user_body_profiles — hồ sơ thể chất (1-1 với users)
-- Tách khỏi auth vì là dữ liệu sức khoẻ nhạy cảm (phân quyền riêng).
-- ---------------------------------------------------------------------
CREATE TABLE body.user_body_profiles (
    user_id             uuid            NOT NULL,
    gender              body.gender     NOT NULL DEFAULT 'unspecified',
    date_of_birth       date,
    height_cm           numeric(5,1),
    activity_level_id   smallint,
    experience_level_id smallint,
    created_at          timestamptz     NOT NULL DEFAULT now(),
    updated_at          timestamptz     NOT NULL DEFAULT now(),
    CONSTRAINT pk_user_body_profiles PRIMARY KEY (user_id),
    CONSTRAINT fk_user_body_profiles_user FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE CASCADE,
    CONSTRAINT fk_user_body_profiles_activity_level FOREIGN KEY (activity_level_id) REFERENCES body.activity_levels (id) ON DELETE RESTRICT,
    CONSTRAINT fk_user_body_profiles_experience_level FOREIGN KEY (experience_level_id) REFERENCES catalog.difficulty_levels (id) ON DELETE RESTRICT,
    CONSTRAINT ck_user_body_profiles_dob CHECK (date_of_birth IS NULL OR date_of_birth >= DATE '1900-01-01'),
    CONSTRAINT ck_user_body_profiles_height CHECK (height_cm IS NULL OR height_cm BETWEEN 80 AND 250)
);
CREATE INDEX ix_user_body_profiles_activity_level_id ON body.user_body_profiles (activity_level_id);
CREATE INDEX ix_user_body_profiles_experience_level_id ON body.user_body_profiles (experience_level_id);
COMMENT ON TABLE  body.user_body_profiles IS 'Hồ sơ thể chất ít thay đổi: giới tính, ngày sinh, chiều cao, mức vận động, trình độ. Tuổi được tính từ ngày sinh (không lưu).';
COMMENT ON COLUMN body.user_body_profiles.user_id IS 'PK đồng thời FK → auth.users.';
COMMENT ON COLUMN body.user_body_profiles.gender IS 'Giới tính (cho công thức BMR).';
COMMENT ON COLUMN body.user_body_profiles.date_of_birth IS 'Ngày sinh (tuổi = age(ngày đo, ngày sinh)).';
COMMENT ON COLUMN body.user_body_profiles.height_cm IS 'Chiều cao (cm).';
COMMENT ON COLUMN body.user_body_profiles.activity_level_id IS 'Mức vận động hiện tại (FK → body.activity_levels).';
COMMENT ON COLUMN body.user_body_profiles.experience_level_id IS 'Trình độ tập luyện (FK → catalog.difficulty_levels), dùng để gợi ý bài phù hợp.';
COMMENT ON COLUMN body.user_body_profiles.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN body.user_body_profiles.updated_at IS 'Thời điểm cập nhật gần nhất.';

-- ---------------------------------------------------------------------
-- body.body_measurements — chuỗi thời gian số đo cơ thể
-- ---------------------------------------------------------------------
CREATE TABLE body.body_measurements (
    id              uuid                    NOT NULL DEFAULT gen_random_uuid(),
    user_id         uuid                    NOT NULL,
    measured_at     timestamptz             NOT NULL,
    weight_kg       numeric(5,2)            NOT NULL,
    body_fat_pct    numeric(4,1),
    muscle_mass_kg  numeric(5,2),
    source          body.measurement_source NOT NULL DEFAULT 'manual',
    note            varchar(500),
    created_at      timestamptz             NOT NULL DEFAULT now(),
    updated_at      timestamptz             NOT NULL DEFAULT now(),
    CONSTRAINT pk_body_measurements PRIMARY KEY (id),
    CONSTRAINT fk_body_measurements_user FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE CASCADE,
    CONSTRAINT uq_body_measurements_user_time UNIQUE (user_id, measured_at),
    CONSTRAINT ck_body_measurements_weight CHECK (weight_kg BETWEEN 20 AND 400),
    CONSTRAINT ck_body_measurements_body_fat CHECK (body_fat_pct IS NULL OR body_fat_pct BETWEEN 2 AND 70),
    CONSTRAINT ck_body_measurements_muscle_mass CHECK (muscle_mass_kg IS NULL OR (muscle_mass_kg > 0 AND muscle_mass_kg < weight_kg))
);
COMMENT ON TABLE  body.body_measurements IS 'Mỗi lần cập nhật chỉ số cơ thể (điểm dữ liệu trên biểu đồ xu hướng). Ảnh tiến độ lấy cân nặng/%mỡ từ đây theo thời điểm chụp.';
COMMENT ON COLUMN body.body_measurements.id IS 'Khoá chính.';
COMMENT ON COLUMN body.body_measurements.user_id IS 'FK → auth.users.';
COMMENT ON COLUMN body.body_measurements.measured_at IS 'Thời điểm đo.';
COMMENT ON COLUMN body.body_measurements.weight_kg IS 'Cân nặng (kg).';
COMMENT ON COLUMN body.body_measurements.body_fat_pct IS 'Tỷ lệ mỡ cơ thể (%).';
COMMENT ON COLUMN body.body_measurements.muscle_mass_kg IS 'Khối lượng cơ (kg), thường từ cân thông minh.';
COMMENT ON COLUMN body.body_measurements.source IS 'Nguồn số đo.';
COMMENT ON COLUMN body.body_measurements.note IS 'Ghi chú.';
COMMENT ON COLUMN body.body_measurements.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN body.body_measurements.updated_at IS 'Thời điểm cập nhật gần nhất.';

CREATE TABLE body.body_circumferences (
    measurement_id  uuid            NOT NULL,
    body_site_id    smallint        NOT NULL,
    value_cm        numeric(5,1)    NOT NULL,
    created_at      timestamptz     NOT NULL DEFAULT now(),
    CONSTRAINT pk_body_circumferences PRIMARY KEY (measurement_id, body_site_id),
    CONSTRAINT fk_body_circumferences_measurement FOREIGN KEY (measurement_id) REFERENCES body.body_measurements (id) ON DELETE CASCADE,
    CONSTRAINT fk_body_circumferences_body_site FOREIGN KEY (body_site_id) REFERENCES body.body_sites (id) ON DELETE RESTRICT,
    CONSTRAINT ck_body_circumferences_value CHECK (value_cm BETWEEN 5 AND 300)
);
CREATE INDEX ix_body_circumferences_body_site_id ON body.body_circumferences (body_site_id);
COMMENT ON TABLE  body.body_circumferences IS 'Số đo vòng gắn với một lần đo (thay cho nhiều cột vòng eo/ngực... thưa dữ liệu).';
COMMENT ON COLUMN body.body_circumferences.measurement_id IS 'FK → body.body_measurements.';
COMMENT ON COLUMN body.body_circumferences.body_site_id IS 'FK → body.body_sites.';
COMMENT ON COLUMN body.body_circumferences.value_cm IS 'Số đo (cm).';
COMMENT ON COLUMN body.body_circumferences.created_at IS 'Thời điểm tạo bản ghi.';

-- ---------------------------------------------------------------------
-- body.user_goals — mục tiêu cá nhân (lịch sử; tối đa 1 mục tiêu active)
-- ---------------------------------------------------------------------
CREATE TABLE body.user_goals (
    id                  uuid                NOT NULL DEFAULT gen_random_uuid(),
    user_id             uuid                NOT NULL,
    goal_type_id        smallint            NOT NULL,
    target_weight_kg    numeric(5,2),
    target_body_fat_pct numeric(4,1),
    start_date          date                NOT NULL DEFAULT current_date,
    target_date         date,
    status              body.goal_status    NOT NULL DEFAULT 'active',
    closed_at           timestamptz,
    created_at          timestamptz         NOT NULL DEFAULT now(),
    updated_at          timestamptz         NOT NULL DEFAULT now(),
    CONSTRAINT pk_user_goals PRIMARY KEY (id),
    CONSTRAINT fk_user_goals_user FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE CASCADE,
    CONSTRAINT fk_user_goals_goal_type FOREIGN KEY (goal_type_id) REFERENCES body.fitness_goal_types (id) ON DELETE RESTRICT,
    CONSTRAINT ck_user_goals_target_weight CHECK (target_weight_kg IS NULL OR target_weight_kg BETWEEN 20 AND 400),
    CONSTRAINT ck_user_goals_target_fat CHECK (target_body_fat_pct IS NULL OR target_body_fat_pct BETWEEN 2 AND 70),
    CONSTRAINT ck_user_goals_dates CHECK (target_date IS NULL OR target_date > start_date),
    CONSTRAINT ck_user_goals_closed CHECK ((status = 'active') = (closed_at IS NULL))
);
CREATE INDEX ix_user_goals_user_id ON body.user_goals (user_id);
CREATE INDEX ix_user_goals_goal_type_id ON body.user_goals (goal_type_id);
CREATE UNIQUE INDEX uq_user_goals_one_active ON body.user_goals (user_id) WHERE status = 'active';
COMMENT ON TABLE  body.user_goals IS 'Mục tiêu thể chất theo thời gian. Mỗi user tối đa một mục tiêu đang active.';
COMMENT ON COLUMN body.user_goals.id IS 'Khoá chính.';
COMMENT ON COLUMN body.user_goals.user_id IS 'FK → auth.users.';
COMMENT ON COLUMN body.user_goals.goal_type_id IS 'FK → body.fitness_goal_types.';
COMMENT ON COLUMN body.user_goals.target_weight_kg IS 'Cân nặng mục tiêu (kg).';
COMMENT ON COLUMN body.user_goals.target_body_fat_pct IS '%mỡ mục tiêu.';
COMMENT ON COLUMN body.user_goals.start_date IS 'Ngày bắt đầu.';
COMMENT ON COLUMN body.user_goals.target_date IS 'Ngày dự kiến đạt.';
COMMENT ON COLUMN body.user_goals.status IS 'active/achieved/abandoned.';
COMMENT ON COLUMN body.user_goals.closed_at IS 'Thời điểm kết thúc (đạt hoặc bỏ); NULL khi đang active.';
COMMENT ON COLUMN body.user_goals.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN body.user_goals.updated_at IS 'Thời điểm cập nhật gần nhất.';
