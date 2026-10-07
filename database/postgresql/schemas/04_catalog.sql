-- =====================================================================
-- Smart Workout AI — 04: Exercise Wiki (schema catalog)
-- Chức năng 1 (Thư viện bài tập), dùng chung cho chức năng 2, 5, 6, 7
-- =====================================================================

CREATE TYPE catalog.content_status AS ENUM ('draft', 'published', 'archived');
CREATE TYPE catalog.muscle_role AS ENUM ('primary', 'secondary', 'stabilizer');
CREATE TYPE catalog.mechanic_type AS ENUM ('compound', 'isolation');
CREATE TYPE catalog.force_type AS ENUM ('push', 'pull', 'static');
CREATE TYPE catalog.exercise_category AS ENUM ('strength', 'cardio', 'stretching', 'plyometric', 'mobility');
CREATE TYPE catalog.media_role AS ENUM ('thumbnail', 'gif', 'video', 'image');
CREATE TYPE catalog.alias_type AS ENUM ('synonym', 'ai_label');
CREATE TYPE catalog.joint_type AS ENUM ('neck', 'shoulder', 'elbow', 'wrist', 'spine', 'hip', 'knee', 'ankle');

COMMENT ON TYPE catalog.content_status IS 'Trạng thái nội dung biên tập.';
COMMENT ON TYPE catalog.muscle_role IS 'Vai trò nhóm cơ trong bài tập: chính / phụ / ổn định.';
COMMENT ON TYPE catalog.mechanic_type IS 'Bài đa khớp (compound) hay đơn khớp (isolation).';
COMMENT ON TYPE catalog.force_type IS 'Kiểu lực: đẩy / kéo / giữ tĩnh.';
COMMENT ON TYPE catalog.exercise_category IS 'Phân loại bài tập.';
COMMENT ON TYPE catalog.media_role IS 'Vai trò media minh hoạ bài tập.';
COMMENT ON TYPE catalog.alias_type IS 'Loại tên gọi khác của thiết bị: từ đồng nghĩa (tìm kiếm) hay nhãn lớp của model AI.';
COMMENT ON TYPE catalog.joint_type IS 'Khớp có nguy cơ chấn thương.';

-- ---------------------------------------------------------------------
-- Bảng tra cứu
-- ---------------------------------------------------------------------
CREATE TABLE catalog.difficulty_levels (
    id          smallint        GENERATED ALWAYS AS IDENTITY,
    code        varchar(30)     NOT NULL,
    name        varchar(50)     NOT NULL,
    rank        smallint        NOT NULL,
    description text,
    created_at  timestamptz     NOT NULL DEFAULT now(),
    updated_at  timestamptz     NOT NULL DEFAULT now(),
    CONSTRAINT pk_difficulty_levels PRIMARY KEY (id),
    CONSTRAINT uq_difficulty_levels_code UNIQUE (code),
    CONSTRAINT uq_difficulty_levels_rank UNIQUE (rank),
    CONSTRAINT ck_difficulty_levels_code_format CHECK (code ~ '^[a-z][a-z0-9_]*$'),
    CONSTRAINT ck_difficulty_levels_rank CHECK (rank > 0)
);
COMMENT ON TABLE  catalog.difficulty_levels IS 'Mức độ khó (dùng cho bài tập, giáo án và trình độ người tập).';
COMMENT ON COLUMN catalog.difficulty_levels.id IS 'Khoá chính.';
COMMENT ON COLUMN catalog.difficulty_levels.code IS 'Mã (beginner/intermediate/advanced).';
COMMENT ON COLUMN catalog.difficulty_levels.name IS 'Tên hiển thị.';
COMMENT ON COLUMN catalog.difficulty_levels.rank IS 'Thứ tự tăng dần độ khó, dùng để sắp xếp.';
COMMENT ON COLUMN catalog.difficulty_levels.description IS 'Mô tả.';
COMMENT ON COLUMN catalog.difficulty_levels.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN catalog.difficulty_levels.updated_at IS 'Thời điểm cập nhật gần nhất.';

CREATE TABLE catalog.body_regions (
    id              smallint        GENERATED ALWAYS AS IDENTITY,
    code            varchar(30)     NOT NULL,
    name            varchar(50)     NOT NULL,
    display_order   smallint        NOT NULL DEFAULT 0,
    created_at      timestamptz     NOT NULL DEFAULT now(),
    updated_at      timestamptz     NOT NULL DEFAULT now(),
    CONSTRAINT pk_body_regions PRIMARY KEY (id),
    CONSTRAINT uq_body_regions_code UNIQUE (code),
    CONSTRAINT ck_body_regions_code_format CHECK (code ~ '^[a-z][a-z0-9_]*$')
);
COMMENT ON TABLE  catalog.body_regions IS 'Vùng cơ thể lớn (thân trên / thân dưới / core) để nhóm các nhóm cơ.';
COMMENT ON COLUMN catalog.body_regions.id IS 'Khoá chính.';
COMMENT ON COLUMN catalog.body_regions.code IS 'Mã vùng.';
COMMENT ON COLUMN catalog.body_regions.name IS 'Tên hiển thị.';
COMMENT ON COLUMN catalog.body_regions.display_order IS 'Thứ tự hiển thị.';
COMMENT ON COLUMN catalog.body_regions.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN catalog.body_regions.updated_at IS 'Thời điểm cập nhật gần nhất.';

-- ---------------------------------------------------------------------
-- catalog.muscle_groups — nhóm cơ phân cấp (cha → con)
-- body_region_id chỉ đặt ở nút gốc; nút con kế thừa qua parent_id
-- (nếu lưu ở cả nút con sẽ tạo phụ thuộc bắc cầu parent_id → body_region_id).
-- ---------------------------------------------------------------------
CREATE TABLE catalog.muscle_groups (
    id                  smallint        GENERATED ALWAYS AS IDENTITY,
    code                varchar(50)     NOT NULL,
    name                varchar(100)    NOT NULL,
    name_en             varchar(100),
    parent_id           smallint,
    body_region_id      smallint,
    heatmap_region_key  varchar(50),
    base_recovery_hours smallint        NOT NULL DEFAULT 48,
    display_order       smallint        NOT NULL DEFAULT 0,
    description         text,
    created_at          timestamptz     NOT NULL DEFAULT now(),
    updated_at          timestamptz     NOT NULL DEFAULT now(),
    CONSTRAINT pk_muscle_groups PRIMARY KEY (id),
    CONSTRAINT uq_muscle_groups_code UNIQUE (code),
    CONSTRAINT uq_muscle_groups_heatmap_region_key UNIQUE (heatmap_region_key),
    CONSTRAINT fk_muscle_groups_parent FOREIGN KEY (parent_id) REFERENCES catalog.muscle_groups (id) ON DELETE RESTRICT,
    CONSTRAINT fk_muscle_groups_body_region FOREIGN KEY (body_region_id) REFERENCES catalog.body_regions (id) ON DELETE RESTRICT,
    CONSTRAINT ck_muscle_groups_code_format CHECK (code ~ '^[a-z][a-z0-9_]*$'),
    CONSTRAINT ck_muscle_groups_not_self_parent CHECK (parent_id IS NULL OR parent_id <> id),
    CONSTRAINT ck_muscle_groups_region_on_root CHECK ((parent_id IS NULL) = (body_region_id IS NOT NULL)),
    CONSTRAINT ck_muscle_groups_recovery_hours CHECK (base_recovery_hours BETWEEN 12 AND 168)
);
CREATE INDEX ix_muscle_groups_parent_id ON catalog.muscle_groups (parent_id);
CREATE INDEX ix_muscle_groups_body_region_id ON catalog.muscle_groups (body_region_id);
CREATE INDEX ix_muscle_groups_name_search ON catalog.muscle_groups USING gin (util.search_norm(name) gin_trgm_ops);

COMMENT ON TABLE  catalog.muscle_groups IS 'Nhóm cơ phân cấp (vd: Lưng → Lưng xô). Nút lá có heatmap_region_key được vẽ trên mô hình cơ thể và được theo dõi phục hồi.';
COMMENT ON COLUMN catalog.muscle_groups.id IS 'Khoá chính.';
COMMENT ON COLUMN catalog.muscle_groups.code IS 'Mã nhóm cơ (vd: lats, chest).';
COMMENT ON COLUMN catalog.muscle_groups.name IS 'Tên tiếng Việt (vd: Lưng xô).';
COMMENT ON COLUMN catalog.muscle_groups.name_en IS 'Tên tiếng Anh/giải phẫu (vd: Latissimus Dorsi).';
COMMENT ON COLUMN catalog.muscle_groups.parent_id IS 'Nhóm cơ cha; NULL = nút gốc.';
COMMENT ON COLUMN catalog.muscle_groups.body_region_id IS 'Vùng cơ thể; CHỈ có ở nút gốc (nút con suy ra qua cha).';
COMMENT ON COLUMN catalog.muscle_groups.heatmap_region_key IS 'ID vùng trên SVG mô hình cơ thể (Heatmap); NULL = không vẽ riêng.';
COMMENT ON COLUMN catalog.muscle_groups.base_recovery_hours IS 'Thời gian phục hồi tham chiếu (giờ) khi chưa đủ dữ liệu cá nhân hoá cho AI.';
COMMENT ON COLUMN catalog.muscle_groups.display_order IS 'Thứ tự hiển thị.';
COMMENT ON COLUMN catalog.muscle_groups.description IS 'Mô tả chức năng nhóm cơ.';
COMMENT ON COLUMN catalog.muscle_groups.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN catalog.muscle_groups.updated_at IS 'Thời điểm cập nhật gần nhất.';

-- ---------------------------------------------------------------------
-- Thiết bị
-- ---------------------------------------------------------------------
CREATE TABLE catalog.equipment_categories (
    id              smallint        GENERATED ALWAYS AS IDENTITY,
    code            varchar(30)     NOT NULL,
    name            varchar(100)    NOT NULL,
    description     text,
    display_order   smallint        NOT NULL DEFAULT 0,
    created_at      timestamptz     NOT NULL DEFAULT now(),
    updated_at      timestamptz     NOT NULL DEFAULT now(),
    CONSTRAINT pk_equipment_categories PRIMARY KEY (id),
    CONSTRAINT uq_equipment_categories_code UNIQUE (code),
    CONSTRAINT ck_equipment_categories_code_format CHECK (code ~ '^[a-z][a-z0-9_]*$')
);
COMMENT ON TABLE  catalog.equipment_categories IS 'Nhóm thiết bị (tạ tự do, máy, cáp, ghế & khung, cardio...).';
COMMENT ON COLUMN catalog.equipment_categories.id IS 'Khoá chính.';
COMMENT ON COLUMN catalog.equipment_categories.code IS 'Mã nhóm.';
COMMENT ON COLUMN catalog.equipment_categories.name IS 'Tên hiển thị.';
COMMENT ON COLUMN catalog.equipment_categories.description IS 'Mô tả.';
COMMENT ON COLUMN catalog.equipment_categories.display_order IS 'Thứ tự hiển thị.';
COMMENT ON COLUMN catalog.equipment_categories.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN catalog.equipment_categories.updated_at IS 'Thời điểm cập nhật gần nhất.';

CREATE TABLE catalog.equipment (
    id              integer         GENERATED ALWAYS AS IDENTITY,
    code            varchar(50)     NOT NULL,
    name            varchar(100)    NOT NULL,
    name_en         varchar(100),
    category_id     smallint        NOT NULL,
    description     text,
    image_media_id  uuid,
    created_by      uuid,
    updated_by      uuid,
    created_at      timestamptz     NOT NULL DEFAULT now(),
    updated_at      timestamptz     NOT NULL DEFAULT now(),
    deleted_at      timestamptz,
    CONSTRAINT pk_equipment PRIMARY KEY (id),
    CONSTRAINT uq_equipment_code UNIQUE (code),
    CONSTRAINT fk_equipment_category FOREIGN KEY (category_id) REFERENCES catalog.equipment_categories (id) ON DELETE RESTRICT,
    CONSTRAINT fk_equipment_image_media FOREIGN KEY (image_media_id) REFERENCES media.media_files (id) ON DELETE SET NULL,
    CONSTRAINT fk_equipment_created_by FOREIGN KEY (created_by) REFERENCES auth.users (id) ON DELETE SET NULL,
    CONSTRAINT fk_equipment_updated_by FOREIGN KEY (updated_by) REFERENCES auth.users (id) ON DELETE SET NULL,
    CONSTRAINT ck_equipment_code_format CHECK (code ~ '^[a-z][a-z0-9_]*$')
);
CREATE INDEX ix_equipment_category_id ON catalog.equipment (category_id);
CREATE INDEX ix_equipment_image_media_id ON catalog.equipment (image_media_id);
CREATE INDEX ix_equipment_created_by ON catalog.equipment (created_by);
CREATE INDEX ix_equipment_updated_by ON catalog.equipment (updated_by);
CREATE INDEX ix_equipment_name_search ON catalog.equipment USING gin (util.search_norm(name) gin_trgm_ops);

COMMENT ON TABLE  catalog.equipment IS 'Thiết bị phòng tập (tạ đơn, máy kéo cáp...). Bài tập không gắn thiết bị nào = bài tự thân.';
COMMENT ON COLUMN catalog.equipment.id IS 'Khoá chính.';
COMMENT ON COLUMN catalog.equipment.code IS 'Mã thiết bị.';
COMMENT ON COLUMN catalog.equipment.name IS 'Tên tiếng Việt.';
COMMENT ON COLUMN catalog.equipment.name_en IS 'Tên tiếng Anh.';
COMMENT ON COLUMN catalog.equipment.category_id IS 'FK → catalog.equipment_categories.';
COMMENT ON COLUMN catalog.equipment.description IS 'Mô tả công dụng ("máy này dùng để làm gì?").';
COMMENT ON COLUMN catalog.equipment.image_media_id IS 'Ảnh minh hoạ (FK → media.media_files).';
COMMENT ON COLUMN catalog.equipment.created_by IS 'Người tạo (biên tập viên).';
COMMENT ON COLUMN catalog.equipment.updated_by IS 'Người cập nhật gần nhất.';
COMMENT ON COLUMN catalog.equipment.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN catalog.equipment.updated_at IS 'Thời điểm cập nhật gần nhất.';
COMMENT ON COLUMN catalog.equipment.deleted_at IS 'Xoá mềm.';

CREATE TABLE catalog.equipment_aliases (
    id              integer             GENERATED ALWAYS AS IDENTITY,
    equipment_id    integer             NOT NULL,
    alias           varchar(100)        NOT NULL,
    alias_type      catalog.alias_type  NOT NULL,
    created_at      timestamptz         NOT NULL DEFAULT now(),
    CONSTRAINT pk_equipment_aliases PRIMARY KEY (id),
    CONSTRAINT fk_equipment_aliases_equipment FOREIGN KEY (equipment_id) REFERENCES catalog.equipment (id) ON DELETE CASCADE,
    CONSTRAINT uq_equipment_aliases_equipment_alias UNIQUE (equipment_id, alias_type, alias),
    CONSTRAINT ck_equipment_aliases_lowercase CHECK (alias = lower(alias))
);
-- Một nhãn AI chỉ được ánh xạ tới đúng một thiết bị
CREATE UNIQUE INDEX uq_equipment_aliases_ai_label ON catalog.equipment_aliases (alias) WHERE alias_type = 'ai_label';
CREATE INDEX ix_equipment_aliases_alias_search ON catalog.equipment_aliases USING gin (util.search_norm(alias) gin_trgm_ops);

COMMENT ON TABLE  catalog.equipment_aliases IS 'Tên gọi khác của thiết bị: từ đồng nghĩa để tìm kiếm ("tạ tay" = Tạ đơn) và nhãn lớp YOLOv8 ("cable_crossover_machine") để ánh xạ kết quả nhận diện → thiết bị → bài tập.';
COMMENT ON COLUMN catalog.equipment_aliases.id IS 'Khoá chính.';
COMMENT ON COLUMN catalog.equipment_aliases.equipment_id IS 'FK → catalog.equipment.';
COMMENT ON COLUMN catalog.equipment_aliases.alias IS 'Tên gọi khác (chữ thường).';
COMMENT ON COLUMN catalog.equipment_aliases.alias_type IS 'synonym = từ đồng nghĩa; ai_label = nhãn lớp model AI (duy nhất toàn bảng).';
COMMENT ON COLUMN catalog.equipment_aliases.created_at IS 'Thời điểm tạo bản ghi.';

-- ---------------------------------------------------------------------
-- catalog.exercises — bài tập
-- ---------------------------------------------------------------------
CREATE TABLE catalog.exercises (
    id                      integer                     GENERATED ALWAYS AS IDENTITY,
    slug                    varchar(120)                NOT NULL,
    name                    varchar(150)                NOT NULL,
    name_en                 varchar(150),
    description             text,
    difficulty_level_id     smallint                    NOT NULL,
    category                catalog.exercise_category   NOT NULL DEFAULT 'strength',
    mechanic                catalog.mechanic_type,
    force_type              catalog.force_type,
    is_unilateral           boolean                     NOT NULL DEFAULT false,
    met_value               numeric(4,1),
    supports_ai_tracking    boolean                     NOT NULL DEFAULT false,
    status                  catalog.content_status      NOT NULL DEFAULT 'draft',
    published_at            timestamptz,
    created_by              uuid,
    updated_by              uuid,
    created_at              timestamptz                 NOT NULL DEFAULT now(),
    updated_at              timestamptz                 NOT NULL DEFAULT now(),
    deleted_at              timestamptz,
    CONSTRAINT pk_exercises PRIMARY KEY (id),
    CONSTRAINT uq_exercises_slug UNIQUE (slug),
    CONSTRAINT fk_exercises_difficulty_level FOREIGN KEY (difficulty_level_id) REFERENCES catalog.difficulty_levels (id) ON DELETE RESTRICT,
    CONSTRAINT fk_exercises_created_by FOREIGN KEY (created_by) REFERENCES auth.users (id) ON DELETE SET NULL,
    CONSTRAINT fk_exercises_updated_by FOREIGN KEY (updated_by) REFERENCES auth.users (id) ON DELETE SET NULL,
    CONSTRAINT ck_exercises_slug_format CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    CONSTRAINT ck_exercises_met_value CHECK (met_value IS NULL OR met_value BETWEEN 1.0 AND 25.0),
    CONSTRAINT ck_exercises_published CHECK (status <> 'published' OR published_at IS NOT NULL)
);
CREATE INDEX ix_exercises_difficulty_level_id ON catalog.exercises (difficulty_level_id);
CREATE INDEX ix_exercises_created_by ON catalog.exercises (created_by);
CREATE INDEX ix_exercises_updated_by ON catalog.exercises (updated_by);
CREATE INDEX ix_exercises_published ON catalog.exercises (difficulty_level_id, name) WHERE status = 'published' AND deleted_at IS NULL;
CREATE INDEX ix_exercises_name_search ON catalog.exercises USING gin (util.search_norm(name) gin_trgm_ops);
CREATE INDEX ix_exercises_name_en_search ON catalog.exercises USING gin (util.search_norm(name_en) gin_trgm_ops);

COMMENT ON TABLE  catalog.exercises IS 'Bài tập trong thư viện. Nhóm cơ, thiết bị, các bước, lỗi sai, media được tách thành bảng con (1NF).';
COMMENT ON COLUMN catalog.exercises.id IS 'Khoá chính.';
COMMENT ON COLUMN catalog.exercises.slug IS 'Định danh thân thiện URL (vd: dumbbell-row).';
COMMENT ON COLUMN catalog.exercises.name IS 'Tên tiếng Việt.';
COMMENT ON COLUMN catalog.exercises.name_en IS 'Tên tiếng Anh.';
COMMENT ON COLUMN catalog.exercises.description IS 'Mô tả tổng quan.';
COMMENT ON COLUMN catalog.exercises.difficulty_level_id IS 'Mức độ khó (FK → catalog.difficulty_levels).';
COMMENT ON COLUMN catalog.exercises.category IS 'Phân loại (strength/cardio/...).';
COMMENT ON COLUMN catalog.exercises.mechanic IS 'compound/isolation; NULL với bài cardio/giãn cơ.';
COMMENT ON COLUMN catalog.exercises.force_type IS 'push/pull/static.';
COMMENT ON COLUMN catalog.exercises.is_unilateral IS 'TRUE = tập từng bên (một tay/một chân).';
COMMENT ON COLUMN catalog.exercises.met_value IS 'Chỉ số MET để ước tính calo tiêu hao = MET × kg × giờ.';
COMMENT ON COLUMN catalog.exercises.supports_ai_tracking IS 'TRUE = có thuật toán AI chấm tư thế/đếm rep cho bài này.';
COMMENT ON COLUMN catalog.exercises.status IS 'Trạng thái biên tập (chỉ published hiển thị cho user).';
COMMENT ON COLUMN catalog.exercises.published_at IS 'Thời điểm xuất bản lần đầu.';
COMMENT ON COLUMN catalog.exercises.created_by IS 'Người tạo (biên tập viên).';
COMMENT ON COLUMN catalog.exercises.updated_by IS 'Người cập nhật gần nhất.';
COMMENT ON COLUMN catalog.exercises.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN catalog.exercises.updated_at IS 'Thời điểm cập nhật gần nhất.';
COMMENT ON COLUMN catalog.exercises.deleted_at IS 'Xoá mềm (bài tập đã có lịch sử tập không được xoá cứng).';

-- ---------------------------------------------------------------------
-- Bảng con của exercises
-- ---------------------------------------------------------------------
CREATE TABLE catalog.exercise_muscles (
    exercise_id         integer             NOT NULL,
    muscle_group_id     smallint            NOT NULL,
    role                catalog.muscle_role NOT NULL,
    activation_ratio    numeric(3,2)        NOT NULL,
    created_at          timestamptz         NOT NULL DEFAULT now(),
    CONSTRAINT pk_exercise_muscles PRIMARY KEY (exercise_id, muscle_group_id),
    CONSTRAINT fk_exercise_muscles_exercise FOREIGN KEY (exercise_id) REFERENCES catalog.exercises (id) ON DELETE CASCADE,
    CONSTRAINT fk_exercise_muscles_muscle_group FOREIGN KEY (muscle_group_id) REFERENCES catalog.muscle_groups (id) ON DELETE RESTRICT,
    CONSTRAINT ck_exercise_muscles_activation CHECK (activation_ratio > 0 AND activation_ratio <= 1)
);
CREATE INDEX ix_exercise_muscles_muscle_role ON catalog.exercise_muscles (muscle_group_id, role);
COMMENT ON TABLE  catalog.exercise_muscles IS 'Bài tập tác động nhóm cơ nào, vai trò và tỷ lệ kích hoạt (để phân bổ khối lượng tập cho mô hình phục hồi).';
COMMENT ON COLUMN catalog.exercise_muscles.exercise_id IS 'FK → catalog.exercises.';
COMMENT ON COLUMN catalog.exercise_muscles.muscle_group_id IS 'FK → catalog.muscle_groups (nên là nút lá).';
COMMENT ON COLUMN catalog.exercise_muscles.role IS 'primary/secondary/stabilizer.';
COMMENT ON COLUMN catalog.exercise_muscles.activation_ratio IS 'Tỷ lệ kích hoạt (0–1]: volume của set × tỷ lệ này = tải lên nhóm cơ.';
COMMENT ON COLUMN catalog.exercise_muscles.created_at IS 'Thời điểm tạo bản ghi.';

CREATE TABLE catalog.exercise_equipment (
    exercise_id     integer     NOT NULL,
    equipment_id    integer     NOT NULL,
    is_optional     boolean     NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_exercise_equipment PRIMARY KEY (exercise_id, equipment_id),
    CONSTRAINT fk_exercise_equipment_exercise FOREIGN KEY (exercise_id) REFERENCES catalog.exercises (id) ON DELETE CASCADE,
    CONSTRAINT fk_exercise_equipment_equipment FOREIGN KEY (equipment_id) REFERENCES catalog.equipment (id) ON DELETE RESTRICT
);
CREATE INDEX ix_exercise_equipment_equipment_id ON catalog.exercise_equipment (equipment_id);
COMMENT ON TABLE  catalog.exercise_equipment IS 'Thiết bị cần cho bài tập (N-N). Dùng cho lọc "thiết bị sẵn có", gợi ý bài thay thế và chức năng nhận diện thiết bị.';
COMMENT ON COLUMN catalog.exercise_equipment.exercise_id IS 'FK → catalog.exercises.';
COMMENT ON COLUMN catalog.exercise_equipment.equipment_id IS 'FK → catalog.equipment.';
COMMENT ON COLUMN catalog.exercise_equipment.is_optional IS 'TRUE = thiết bị tuỳ chọn (không bắt buộc để thực hiện).';
COMMENT ON COLUMN catalog.exercise_equipment.created_at IS 'Thời điểm tạo bản ghi.';

CREATE TABLE catalog.exercise_instructions (
    exercise_id integer     NOT NULL,
    step_no     smallint    NOT NULL,
    content     text        NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_exercise_instructions PRIMARY KEY (exercise_id, step_no),
    CONSTRAINT fk_exercise_instructions_exercise FOREIGN KEY (exercise_id) REFERENCES catalog.exercises (id) ON DELETE CASCADE,
    CONSTRAINT ck_exercise_instructions_step_no CHECK (step_no > 0),
    CONSTRAINT ck_exercise_instructions_content CHECK (length(btrim(content)) > 0)
);
COMMENT ON TABLE  catalog.exercise_instructions IS 'Các bước thực hiện bài tập theo thứ tự (mỗi bước một dòng, đạt 1NF).';
COMMENT ON COLUMN catalog.exercise_instructions.exercise_id IS 'FK → catalog.exercises.';
COMMENT ON COLUMN catalog.exercise_instructions.step_no IS 'Số thứ tự bước (bắt đầu từ 1).';
COMMENT ON COLUMN catalog.exercise_instructions.content IS 'Nội dung bước.';
COMMENT ON COLUMN catalog.exercise_instructions.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN catalog.exercise_instructions.updated_at IS 'Thời điểm cập nhật gần nhất.';

CREATE TABLE catalog.exercise_mistakes (
    id              integer             GENERATED ALWAYS AS IDENTITY,
    exercise_id     integer             NOT NULL,
    code            varchar(60)         NOT NULL,
    title           varchar(150)        NOT NULL,
    description     text,
    correction_cue  text,
    at_risk_joint   catalog.joint_type,
    ai_detectable   boolean             NOT NULL DEFAULT false,
    display_order   smallint            NOT NULL DEFAULT 0,
    created_at      timestamptz         NOT NULL DEFAULT now(),
    updated_at      timestamptz         NOT NULL DEFAULT now(),
    CONSTRAINT pk_exercise_mistakes PRIMARY KEY (id),
    CONSTRAINT uq_exercise_mistakes_code UNIQUE (code),
    CONSTRAINT fk_exercise_mistakes_exercise FOREIGN KEY (exercise_id) REFERENCES catalog.exercises (id) ON DELETE CASCADE,
    CONSTRAINT ck_exercise_mistakes_code_format CHECK (code ~ '^[A-Z][A-Z0-9_]*$')
);
CREATE INDEX ix_exercise_mistakes_exercise_id ON catalog.exercise_mistakes (exercise_id);
COMMENT ON TABLE  catalog.exercise_mistakes IS 'Lỗi sai thường gặp của bài tập. Dùng chung cho trang Wiki (cảnh báo) và module AI (ai.posture_issues tham chiếu mã lỗi này).';
COMMENT ON COLUMN catalog.exercise_mistakes.id IS 'Khoá chính.';
COMMENT ON COLUMN catalog.exercise_mistakes.exercise_id IS 'FK → catalog.exercises.';
COMMENT ON COLUMN catalog.exercise_mistakes.code IS 'Mã lỗi duy nhất, model AI trả về mã này (vd: SQUAT_BACK_ROUNDING).';
COMMENT ON COLUMN catalog.exercise_mistakes.title IS 'Tiêu đề lỗi.';
COMMENT ON COLUMN catalog.exercise_mistakes.description IS 'Mô tả lỗi và hậu quả.';
COMMENT ON COLUMN catalog.exercise_mistakes.correction_cue IS 'Gợi ý sửa (hiển thị/đọc khi AI phát hiện).';
COMMENT ON COLUMN catalog.exercise_mistakes.at_risk_joint IS 'Khớp có nguy cơ chấn thương.';
COMMENT ON COLUMN catalog.exercise_mistakes.ai_detectable IS 'TRUE = AI có thể phát hiện tự động.';
COMMENT ON COLUMN catalog.exercise_mistakes.display_order IS 'Thứ tự hiển thị.';
COMMENT ON COLUMN catalog.exercise_mistakes.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN catalog.exercise_mistakes.updated_at IS 'Thời điểm cập nhật gần nhất.';

CREATE TABLE catalog.exercise_media (
    exercise_id     integer             NOT NULL,
    media_id        uuid                NOT NULL,
    media_role      catalog.media_role  NOT NULL,
    is_primary      boolean             NOT NULL DEFAULT false,
    display_order   smallint            NOT NULL DEFAULT 0,
    caption         varchar(200),
    created_at      timestamptz         NOT NULL DEFAULT now(),
    CONSTRAINT pk_exercise_media PRIMARY KEY (exercise_id, media_id),
    CONSTRAINT fk_exercise_media_exercise FOREIGN KEY (exercise_id) REFERENCES catalog.exercises (id) ON DELETE CASCADE,
    CONSTRAINT fk_exercise_media_media FOREIGN KEY (media_id) REFERENCES media.media_files (id) ON DELETE RESTRICT
);
CREATE INDEX ix_exercise_media_media_id ON catalog.exercise_media (media_id);
CREATE UNIQUE INDEX uq_exercise_media_primary_per_role ON catalog.exercise_media (exercise_id, media_role) WHERE is_primary;
COMMENT ON TABLE  catalog.exercise_media IS 'Video/GIF/ảnh minh hoạ bài tập. Mỗi vai trò có tối đa một media chính.';
COMMENT ON COLUMN catalog.exercise_media.exercise_id IS 'FK → catalog.exercises.';
COMMENT ON COLUMN catalog.exercise_media.media_id IS 'FK → media.media_files.';
COMMENT ON COLUMN catalog.exercise_media.media_role IS 'thumbnail/gif/video/image.';
COMMENT ON COLUMN catalog.exercise_media.is_primary IS 'Media chính của vai trò đó.';
COMMENT ON COLUMN catalog.exercise_media.display_order IS 'Thứ tự hiển thị.';
COMMENT ON COLUMN catalog.exercise_media.caption IS 'Chú thích.';
COMMENT ON COLUMN catalog.exercise_media.created_at IS 'Thời điểm tạo bản ghi.';

CREATE TABLE catalog.exercise_alternatives (
    exercise_id             integer         NOT NULL,
    alternative_exercise_id integer         NOT NULL,
    note                    varchar(255),
    created_at              timestamptz     NOT NULL DEFAULT now(),
    CONSTRAINT pk_exercise_alternatives PRIMARY KEY (exercise_id, alternative_exercise_id),
    CONSTRAINT fk_exercise_alternatives_exercise FOREIGN KEY (exercise_id) REFERENCES catalog.exercises (id) ON DELETE CASCADE,
    CONSTRAINT fk_exercise_alternatives_alternative FOREIGN KEY (alternative_exercise_id) REFERENCES catalog.exercises (id) ON DELETE CASCADE,
    CONSTRAINT ck_exercise_alternatives_not_self CHECK (exercise_id <> alternative_exercise_id)
);
CREATE INDEX ix_exercise_alternatives_alternative_id ON catalog.exercise_alternatives (alternative_exercise_id);
COMMENT ON TABLE  catalog.exercise_alternatives IS 'Bài thay thế do biên tập viên chọn (quan hệ có hướng A → B). Gợi ý tự động theo nhóm cơ + thiết bị trống nằm ở hàm catalog.fn_suggest_alternatives().';
COMMENT ON COLUMN catalog.exercise_alternatives.exercise_id IS 'Bài gốc (FK → catalog.exercises).';
COMMENT ON COLUMN catalog.exercise_alternatives.alternative_exercise_id IS 'Bài thay thế (FK → catalog.exercises).';
COMMENT ON COLUMN catalog.exercise_alternatives.note IS 'Lý do/ghi chú khi thay thế.';
COMMENT ON COLUMN catalog.exercise_alternatives.created_at IS 'Thời điểm tạo bản ghi.';
