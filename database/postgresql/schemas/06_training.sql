-- =====================================================================
-- Smart Workout AI — 06: Training (schema training)
-- Chức năng 2 (Workout Routine + phục hồi cơ), 6 (Set/Rep/Tempo), một phần 1 & 7 (thêm bài vào buổi tập)
-- Volume, thời lượng, calo tiêu hao, tempo trung bình, trạng thái phục hồi hiện tại: tính ở views.
-- =====================================================================

CREATE TYPE training.plan_status AS ENUM ('draft', 'active', 'archived');
CREATE TYPE training.schedule_status AS ENUM ('planned', 'skipped', 'cancelled');
CREATE TYPE training.session_status AS ENUM ('in_progress', 'completed', 'abandoned');
CREATE TYPE training.set_type AS ENUM ('warmup', 'working', 'drop', 'failure');
CREATE TYPE training.log_source AS ENUM ('manual', 'ai_realtime', 'ai_video');
CREATE TYPE training.added_via AS ENUM ('plan', 'manual', 'wiki', 'equipment_scan');

COMMENT ON TYPE training.plan_status IS 'Trạng thái giáo án.';
COMMENT ON TYPE training.schedule_status IS 'Trạng thái lịch tập. Việc "đã hoàn thành" suy ra từ buổi tập liên kết, không lưu ở đây.';
COMMENT ON TYPE training.session_status IS 'Trạng thái buổi tập thực tế.';
COMMENT ON TYPE training.set_type IS 'Loại hiệp: khởi động / chính / drop set / tới thất bại.';
COMMENT ON TYPE training.log_source IS 'Nguồn dữ liệu hiệp tập: nhập tay, AI realtime (đếm rep), AI phân tích video.';
COMMENT ON TYPE training.added_via IS 'Bài tập được thêm vào buổi tập từ đâu (giáo án, thủ công, Wiki, quét thiết bị).';

-- ---------------------------------------------------------------------
-- Giáo án (template hoặc của user)
-- ---------------------------------------------------------------------
CREATE TABLE training.workout_plans (
    id                  uuid                    NOT NULL DEFAULT gen_random_uuid(),
    owner_user_id       uuid,
    source_plan_id      uuid,
    name                varchar(150)            NOT NULL,
    description         text,
    goal_type_id        smallint,
    difficulty_level_id smallint,
    duration_weeks      smallint,
    status              training.plan_status    NOT NULL DEFAULT 'draft',
    created_at          timestamptz             NOT NULL DEFAULT now(),
    updated_at          timestamptz             NOT NULL DEFAULT now(),
    deleted_at          timestamptz,
    CONSTRAINT pk_workout_plans PRIMARY KEY (id),
    CONSTRAINT fk_workout_plans_owner FOREIGN KEY (owner_user_id) REFERENCES auth.users (id) ON DELETE CASCADE,
    CONSTRAINT fk_workout_plans_source_plan FOREIGN KEY (source_plan_id) REFERENCES training.workout_plans (id) ON DELETE SET NULL,
    CONSTRAINT fk_workout_plans_goal_type FOREIGN KEY (goal_type_id) REFERENCES body.fitness_goal_types (id) ON DELETE RESTRICT,
    CONSTRAINT fk_workout_plans_difficulty_level FOREIGN KEY (difficulty_level_id) REFERENCES catalog.difficulty_levels (id) ON DELETE RESTRICT,
    CONSTRAINT ck_workout_plans_duration CHECK (duration_weeks IS NULL OR duration_weeks BETWEEN 1 AND 104),
    CONSTRAINT ck_workout_plans_not_self_source CHECK (source_plan_id IS NULL OR source_plan_id <> id)
);
CREATE INDEX ix_workout_plans_owner_user_id ON training.workout_plans (owner_user_id);
CREATE INDEX ix_workout_plans_source_plan_id ON training.workout_plans (source_plan_id);
CREATE INDEX ix_workout_plans_goal_type_id ON training.workout_plans (goal_type_id);
CREATE INDEX ix_workout_plans_difficulty_level_id ON training.workout_plans (difficulty_level_id);
CREATE INDEX ix_workout_plans_templates ON training.workout_plans (difficulty_level_id) WHERE owner_user_id IS NULL AND status = 'active' AND deleted_at IS NULL;
COMMENT ON TABLE  training.workout_plans IS 'Giáo án tập. owner_user_id NULL = giáo án mẫu của hệ thống (do biên tập viên tạo, mọi user dùng được). Số buổi/tuần suy ra từ số ngày trong giáo án.';
COMMENT ON COLUMN training.workout_plans.id IS 'Khoá chính.';
COMMENT ON COLUMN training.workout_plans.owner_user_id IS 'Chủ sở hữu (FK → auth.users); NULL = giáo án mẫu.';
COMMENT ON COLUMN training.workout_plans.source_plan_id IS 'Giáo án gốc nếu được nhân bản từ mẫu.';
COMMENT ON COLUMN training.workout_plans.name IS 'Tên giáo án.';
COMMENT ON COLUMN training.workout_plans.description IS 'Mô tả.';
COMMENT ON COLUMN training.workout_plans.goal_type_id IS 'Mục tiêu phù hợp (FK → body.fitness_goal_types).';
COMMENT ON COLUMN training.workout_plans.difficulty_level_id IS 'Độ khó (FK → catalog.difficulty_levels).';
COMMENT ON COLUMN training.workout_plans.duration_weeks IS 'Thời lượng chương trình (tuần).';
COMMENT ON COLUMN training.workout_plans.status IS 'draft/active/archived.';
COMMENT ON COLUMN training.workout_plans.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN training.workout_plans.updated_at IS 'Thời điểm cập nhật gần nhất.';
COMMENT ON COLUMN training.workout_plans.deleted_at IS 'Xoá mềm.';

CREATE TABLE training.workout_plan_days (
    id          uuid            NOT NULL DEFAULT gen_random_uuid(),
    plan_id     uuid            NOT NULL,
    day_no      smallint        NOT NULL,
    name        varchar(100)    NOT NULL,
    notes       text,
    created_at  timestamptz     NOT NULL DEFAULT now(),
    updated_at  timestamptz     NOT NULL DEFAULT now(),
    CONSTRAINT pk_workout_plan_days PRIMARY KEY (id),
    CONSTRAINT fk_workout_plan_days_plan FOREIGN KEY (plan_id) REFERENCES training.workout_plans (id) ON DELETE CASCADE,
    CONSTRAINT uq_workout_plan_days_plan_day UNIQUE (plan_id, day_no) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT ck_workout_plan_days_day_no CHECK (day_no BETWEEN 1 AND 31)
);
COMMENT ON TABLE  training.workout_plan_days IS 'Các buổi trong một chu kỳ giáo án (vd: Ngày 1 – Push, Ngày 2 – Pull).';
COMMENT ON COLUMN training.workout_plan_days.id IS 'Khoá chính.';
COMMENT ON COLUMN training.workout_plan_days.plan_id IS 'FK → training.workout_plans.';
COMMENT ON COLUMN training.workout_plan_days.day_no IS 'Thứ tự buổi trong chu kỳ (unique trong giáo án, deferrable để sắp xếp lại).';
COMMENT ON COLUMN training.workout_plan_days.name IS 'Tên buổi.';
COMMENT ON COLUMN training.workout_plan_days.notes IS 'Ghi chú.';
COMMENT ON COLUMN training.workout_plan_days.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN training.workout_plan_days.updated_at IS 'Thời điểm cập nhật gần nhất.';

CREATE TABLE training.workout_plan_exercises (
    id                      uuid            NOT NULL DEFAULT gen_random_uuid(),
    plan_day_id             uuid            NOT NULL,
    exercise_id             integer         NOT NULL,
    order_no                smallint        NOT NULL,
    target_sets             smallint        NOT NULL,
    target_reps_min         smallint,
    target_reps_max         smallint,
    target_duration_seconds smallint,
    target_weight_kg        numeric(6,2),
    target_rpe              numeric(3,1),
    rest_seconds            smallint,
    tempo_eccentric_s       smallint,
    tempo_pause_bottom_s    smallint,
    tempo_concentric_s      smallint,
    tempo_pause_top_s       smallint,
    notes                   varchar(500),
    created_at              timestamptz     NOT NULL DEFAULT now(),
    updated_at              timestamptz     NOT NULL DEFAULT now(),
    CONSTRAINT pk_workout_plan_exercises PRIMARY KEY (id),
    CONSTRAINT fk_workout_plan_exercises_plan_day FOREIGN KEY (plan_day_id) REFERENCES training.workout_plan_days (id) ON DELETE CASCADE,
    CONSTRAINT fk_workout_plan_exercises_exercise FOREIGN KEY (exercise_id) REFERENCES catalog.exercises (id) ON DELETE RESTRICT,
    CONSTRAINT uq_workout_plan_exercises_order UNIQUE (plan_day_id, order_no) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT ck_workout_plan_exercises_order CHECK (order_no > 0),
    CONSTRAINT ck_workout_plan_exercises_sets CHECK (target_sets BETWEEN 1 AND 20),
    CONSTRAINT ck_workout_plan_exercises_reps CHECK (
        (target_reps_min IS NULL OR target_reps_min BETWEEN 1 AND 100)
        AND (target_reps_max IS NULL OR target_reps_max BETWEEN 1 AND 100)
        AND (target_reps_min IS NULL OR target_reps_max IS NULL OR target_reps_max >= target_reps_min)),
    CONSTRAINT ck_workout_plan_exercises_duration CHECK (target_duration_seconds IS NULL OR target_duration_seconds BETWEEN 1 AND 7200),
    CONSTRAINT ck_workout_plan_exercises_has_target CHECK (target_reps_min IS NOT NULL OR target_duration_seconds IS NOT NULL),
    CONSTRAINT ck_workout_plan_exercises_weight CHECK (target_weight_kg IS NULL OR target_weight_kg BETWEEN 0 AND 1000),
    CONSTRAINT ck_workout_plan_exercises_rpe CHECK (target_rpe IS NULL OR target_rpe BETWEEN 1 AND 10),
    CONSTRAINT ck_workout_plan_exercises_rest CHECK (rest_seconds IS NULL OR rest_seconds BETWEEN 0 AND 900),
    CONSTRAINT ck_workout_plan_exercises_tempo_range CHECK (
        coalesce(tempo_eccentric_s, 0) BETWEEN 0 AND 20 AND coalesce(tempo_pause_bottom_s, 0) BETWEEN 0 AND 20
        AND coalesce(tempo_concentric_s, 0) BETWEEN 0 AND 20 AND coalesce(tempo_pause_top_s, 0) BETWEEN 0 AND 20),
    CONSTRAINT ck_workout_plan_exercises_tempo_all_or_none CHECK (
        num_nulls(tempo_eccentric_s, tempo_pause_bottom_s, tempo_concentric_s, tempo_pause_top_s) IN (0, 4))
);
CREATE INDEX ix_workout_plan_exercises_exercise_id ON training.workout_plan_exercises (exercise_id);
COMMENT ON TABLE  training.workout_plan_exercises IS 'Bài tập được kê trong một buổi của giáo án (chỉ tiêu set/rep hoặc thời gian/tạ/tempo). Tempo tách thành 4 cột nguyên tử thay vì chuỗi "3-1-1-0" (1NF).';
COMMENT ON COLUMN training.workout_plan_exercises.id IS 'Khoá chính.';
COMMENT ON COLUMN training.workout_plan_exercises.plan_day_id IS 'FK → training.workout_plan_days.';
COMMENT ON COLUMN training.workout_plan_exercises.exercise_id IS 'FK → catalog.exercises.';
COMMENT ON COLUMN training.workout_plan_exercises.order_no IS 'Thứ tự trong buổi.';
COMMENT ON COLUMN training.workout_plan_exercises.target_sets IS 'Số hiệp mục tiêu.';
COMMENT ON COLUMN training.workout_plan_exercises.target_reps_min IS 'Số rep tối thiểu mục tiêu.';
COMMENT ON COLUMN training.workout_plan_exercises.target_reps_max IS 'Số rep tối đa mục tiêu.';
COMMENT ON COLUMN training.workout_plan_exercises.target_duration_seconds IS 'Thời gian mục tiêu mỗi hiệp (giây) cho bài giữ tĩnh/cardio (vd: Plank 60s, chạy bộ 1200s). Phải có rep mục tiêu hoặc thời gian mục tiêu.';
COMMENT ON COLUMN training.workout_plan_exercises.target_weight_kg IS 'Mức tạ mục tiêu (kg).';
COMMENT ON COLUMN training.workout_plan_exercises.target_rpe IS 'RPE mục tiêu (1–10).';
COMMENT ON COLUMN training.workout_plan_exercises.rest_seconds IS 'Thời gian nghỉ giữa hiệp (giây).';
COMMENT ON COLUMN training.workout_plan_exercises.tempo_eccentric_s IS 'Tempo pha hạ/co dài (giây).';
COMMENT ON COLUMN training.workout_plan_exercises.tempo_pause_bottom_s IS 'Tempo dừng ở điểm thấp (giây).';
COMMENT ON COLUMN training.workout_plan_exercises.tempo_concentric_s IS 'Tempo pha đẩy/co ngắn (giây).';
COMMENT ON COLUMN training.workout_plan_exercises.tempo_pause_top_s IS 'Tempo dừng ở điểm cao (giây).';
COMMENT ON COLUMN training.workout_plan_exercises.notes IS 'Ghi chú cho bài tập.';
COMMENT ON COLUMN training.workout_plan_exercises.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN training.workout_plan_exercises.updated_at IS 'Thời điểm cập nhật gần nhất.';

-- ---------------------------------------------------------------------
-- training.scheduled_workouts — lịch tập theo ngày
-- ---------------------------------------------------------------------
CREATE TABLE training.scheduled_workouts (
    id                          uuid                        NOT NULL DEFAULT gen_random_uuid(),
    user_id                     uuid                        NOT NULL,
    plan_day_id                 uuid,
    scheduled_date              date                        NOT NULL,
    title                       varchar(150),
    status                      training.schedule_status    NOT NULL DEFAULT 'planned',
    recovery_warning_ack_at     timestamptz,
    notes                       varchar(500),
    created_at                  timestamptz                 NOT NULL DEFAULT now(),
    updated_at                  timestamptz                 NOT NULL DEFAULT now(),
    CONSTRAINT pk_scheduled_workouts PRIMARY KEY (id),
    CONSTRAINT uq_scheduled_workouts_id_user UNIQUE (id, user_id),
    CONSTRAINT fk_scheduled_workouts_user FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE CASCADE,
    CONSTRAINT fk_scheduled_workouts_plan_day FOREIGN KEY (plan_day_id) REFERENCES training.workout_plan_days (id) ON DELETE CASCADE,
    CONSTRAINT ck_scheduled_workouts_has_content CHECK (plan_day_id IS NOT NULL OR title IS NOT NULL)
);
CREATE INDEX ix_scheduled_workouts_user_date ON training.scheduled_workouts (user_id, scheduled_date);
CREATE INDEX ix_scheduled_workouts_plan_day_id ON training.scheduled_workouts (plan_day_id);
COMMENT ON TABLE  training.scheduled_workouts IS 'Lịch tập của user theo ngày, có thể gắn một buổi trong giáo án (của user hoặc giáo án mẫu). Khi xếp lịch nhóm cơ chưa hồi phục, app cảnh báo; nếu user vẫn xác nhận thì ghi recovery_warning_ack_at.';
COMMENT ON COLUMN training.scheduled_workouts.id IS 'Khoá chính.';
COMMENT ON COLUMN training.scheduled_workouts.user_id IS 'FK → auth.users.';
COMMENT ON COLUMN training.scheduled_workouts.plan_day_id IS 'Buổi giáo án áp dụng (FK → training.workout_plan_days); NULL = buổi tự do.';
COMMENT ON COLUMN training.scheduled_workouts.scheduled_date IS 'Ngày tập dự kiến (theo múi giờ user).';
COMMENT ON COLUMN training.scheduled_workouts.title IS 'Tiêu đề buổi tự do (hoặc ghi đè tên buổi giáo án).';
COMMENT ON COLUMN training.scheduled_workouts.status IS 'planned/skipped/cancelled.';
COMMENT ON COLUMN training.scheduled_workouts.recovery_warning_ack_at IS 'Thời điểm user xác nhận vẫn tập dù được cảnh báo nhóm cơ chưa hồi phục.';
COMMENT ON COLUMN training.scheduled_workouts.notes IS 'Ghi chú.';
COMMENT ON COLUMN training.scheduled_workouts.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN training.scheduled_workouts.updated_at IS 'Thời điểm cập nhật gần nhất.';

-- Lịch tập chỉ được dùng buổi thuộc giáo án của chính user hoặc giáo án mẫu
CREATE OR REPLACE FUNCTION training.fn_check_schedule_plan_access()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_owner uuid;
BEGIN
    IF NEW.plan_day_id IS NULL THEN
        RETURN NEW;
    END IF;
    SELECT p.owner_user_id INTO v_owner
    FROM training.workout_plan_days d
    JOIN training.workout_plans p ON p.id = d.plan_id
    WHERE d.id = NEW.plan_day_id;
    IF v_owner IS NOT NULL AND v_owner <> NEW.user_id THEN
        RAISE EXCEPTION 'Buổi giáo án % không thuộc user %', NEW.plan_day_id, NEW.user_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;
COMMENT ON FUNCTION training.fn_check_schedule_plan_access() IS 'Đảm bảo scheduled_workouts chỉ tham chiếu buổi giáo án của chính user hoặc giáo án mẫu.';

CREATE TRIGGER trg_scheduled_workouts_plan_access
    BEFORE INSERT OR UPDATE OF plan_day_id, user_id ON training.scheduled_workouts
    FOR EACH ROW EXECUTE FUNCTION training.fn_check_schedule_plan_access();

-- ---------------------------------------------------------------------
-- training.workout_sessions — buổi tập thực tế (Workout_Log)
-- ---------------------------------------------------------------------
CREATE TABLE training.workout_sessions (
    id                      uuid                        NOT NULL DEFAULT gen_random_uuid(),
    user_id                 uuid                        NOT NULL,
    scheduled_workout_id    uuid,
    name                    varchar(150),
    started_at              timestamptz                 NOT NULL DEFAULT now(),
    ended_at                timestamptz,
    status                  training.session_status     NOT NULL DEFAULT 'in_progress',
    session_rpe             numeric(3,1),
    notes                   text,
    created_at              timestamptz                 NOT NULL DEFAULT now(),
    updated_at              timestamptz                 NOT NULL DEFAULT now(),
    deleted_at              timestamptz,
    CONSTRAINT pk_workout_sessions PRIMARY KEY (id),
    CONSTRAINT fk_workout_sessions_user FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE CASCADE,
    -- FK kép đảm bảo lịch tập được liên kết thuộc cùng user; xoá lịch thì chỉ NULL cột scheduled_workout_id
    CONSTRAINT fk_workout_sessions_scheduled_workout FOREIGN KEY (scheduled_workout_id, user_id)
        REFERENCES training.scheduled_workouts (id, user_id) ON DELETE SET NULL (scheduled_workout_id),
    CONSTRAINT uq_workout_sessions_scheduled_workout UNIQUE (scheduled_workout_id),
    CONSTRAINT ck_workout_sessions_time CHECK (ended_at IS NULL OR ended_at >= started_at),
    CONSTRAINT ck_workout_sessions_ended CHECK ((status = 'in_progress') = (ended_at IS NULL)),
    CONSTRAINT ck_workout_sessions_rpe CHECK (session_rpe IS NULL OR session_rpe BETWEEN 1 AND 10)
);
CREATE INDEX ix_workout_sessions_user_started ON training.workout_sessions (user_id, started_at DESC);
CREATE UNIQUE INDEX uq_workout_sessions_one_in_progress ON training.workout_sessions (user_id)
    WHERE status = 'in_progress' AND deleted_at IS NULL;
COMMENT ON TABLE  training.workout_sessions IS 'Buổi tập thực tế. Mỗi user chỉ có tối đa 1 buổi in_progress (bài thêm từ Wiki/quét thiết bị sẽ vào buổi này). Thời lượng, volume, calo tiêu hao xem training.v_session_summary.';
COMMENT ON COLUMN training.workout_sessions.id IS 'Khoá chính.';
COMMENT ON COLUMN training.workout_sessions.user_id IS 'FK → auth.users.';
COMMENT ON COLUMN training.workout_sessions.scheduled_workout_id IS 'Lịch tập được thực hiện (FK kép → scheduled_workouts(id, user_id)); NULL = buổi tập ngoài lịch.';
COMMENT ON COLUMN training.workout_sessions.name IS 'Tên buổi tập.';
COMMENT ON COLUMN training.workout_sessions.started_at IS 'Bắt đầu.';
COMMENT ON COLUMN training.workout_sessions.ended_at IS 'Kết thúc; NULL khi đang tập.';
COMMENT ON COLUMN training.workout_sessions.status IS 'in_progress/completed/abandoned.';
COMMENT ON COLUMN training.workout_sessions.session_rpe IS 'Cảm nhận gắng sức cả buổi (1–10).';
COMMENT ON COLUMN training.workout_sessions.notes IS 'Ghi chú.';
COMMENT ON COLUMN training.workout_sessions.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN training.workout_sessions.updated_at IS 'Thời điểm cập nhật gần nhất.';
COMMENT ON COLUMN training.workout_sessions.deleted_at IS 'Xoá mềm.';

CREATE TABLE training.session_exercises (
    id                  uuid                    NOT NULL DEFAULT gen_random_uuid(),
    session_id          uuid                    NOT NULL,
    exercise_id         integer                 NOT NULL,
    plan_exercise_id    uuid,
    order_no            smallint                NOT NULL,
    added_via           training.added_via      NOT NULL DEFAULT 'manual',
    notes               varchar(500),
    created_at          timestamptz             NOT NULL DEFAULT now(),
    updated_at          timestamptz             NOT NULL DEFAULT now(),
    CONSTRAINT pk_session_exercises PRIMARY KEY (id),
    CONSTRAINT fk_session_exercises_session FOREIGN KEY (session_id) REFERENCES training.workout_sessions (id) ON DELETE CASCADE,
    CONSTRAINT fk_session_exercises_exercise FOREIGN KEY (exercise_id) REFERENCES catalog.exercises (id) ON DELETE RESTRICT,
    CONSTRAINT fk_session_exercises_plan_exercise FOREIGN KEY (plan_exercise_id) REFERENCES training.workout_plan_exercises (id) ON DELETE SET NULL,
    CONSTRAINT uq_session_exercises_order UNIQUE (session_id, order_no) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT ck_session_exercises_order CHECK (order_no > 0)
);
CREATE INDEX ix_session_exercises_exercise_id ON training.session_exercises (exercise_id);
CREATE INDEX ix_session_exercises_plan_exercise_id ON training.session_exercises (plan_exercise_id);
COMMENT ON TABLE  training.session_exercises IS 'Bài tập được thực hiện trong buổi. exercise_id là bài THỰC TẾ (có thể khác bài kê trong giáo án khi đổi sang bài thay thế), nên không phụ thuộc hàm vào plan_exercise_id.';
COMMENT ON COLUMN training.session_exercises.id IS 'Khoá chính.';
COMMENT ON COLUMN training.session_exercises.session_id IS 'FK → training.workout_sessions.';
COMMENT ON COLUMN training.session_exercises.exercise_id IS 'Bài thực tế (FK → catalog.exercises).';
COMMENT ON COLUMN training.session_exercises.plan_exercise_id IS 'Chỉ tiêu giáo án mà bài này thực hiện (FK → training.workout_plan_exercises).';
COMMENT ON COLUMN training.session_exercises.order_no IS 'Thứ tự trong buổi.';
COMMENT ON COLUMN training.session_exercises.added_via IS 'Nguồn thêm bài (plan/manual/wiki/equipment_scan).';
COMMENT ON COLUMN training.session_exercises.notes IS 'Ghi chú.';
COMMENT ON COLUMN training.session_exercises.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN training.session_exercises.updated_at IS 'Thời điểm cập nhật gần nhất.';

-- ---------------------------------------------------------------------
-- training.exercise_sets — từng hiệp tập
-- ---------------------------------------------------------------------
CREATE TABLE training.exercise_sets (
    id                  bigint                  GENERATED ALWAYS AS IDENTITY,
    session_exercise_id uuid                    NOT NULL,
    set_no              smallint                NOT NULL,
    set_type            training.set_type       NOT NULL DEFAULT 'working',
    reps                smallint,
    weight_kg           numeric(6,2),
    duration_seconds    integer,
    distance_m          numeric(8,2),
    rpe                 numeric(3,1),
    rest_seconds        smallint,
    source              training.log_source     NOT NULL DEFAULT 'manual',
    completed_at        timestamptz,
    created_at          timestamptz             NOT NULL DEFAULT now(),
    updated_at          timestamptz             NOT NULL DEFAULT now(),
    CONSTRAINT pk_exercise_sets PRIMARY KEY (id),
    CONSTRAINT fk_exercise_sets_session_exercise FOREIGN KEY (session_exercise_id) REFERENCES training.session_exercises (id) ON DELETE CASCADE,
    CONSTRAINT uq_exercise_sets_set_no UNIQUE (session_exercise_id, set_no) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT ck_exercise_sets_set_no CHECK (set_no > 0),
    CONSTRAINT ck_exercise_sets_reps CHECK (reps IS NULL OR reps BETWEEN 0 AND 1000),
    CONSTRAINT ck_exercise_sets_weight CHECK (weight_kg IS NULL OR weight_kg BETWEEN 0 AND 1000),
    CONSTRAINT ck_exercise_sets_duration CHECK (duration_seconds IS NULL OR duration_seconds BETWEEN 0 AND 86400),
    CONSTRAINT ck_exercise_sets_distance CHECK (distance_m IS NULL OR distance_m >= 0),
    CONSTRAINT ck_exercise_sets_rpe CHECK (rpe IS NULL OR (rpe BETWEEN 1 AND 10 AND rpe * 2 = trunc(rpe * 2))),
    CONSTRAINT ck_exercise_sets_rest CHECK (rest_seconds IS NULL OR rest_seconds BETWEEN 0 AND 3600),
    CONSTRAINT ck_exercise_sets_has_metric CHECK (reps IS NOT NULL OR duration_seconds IS NOT NULL OR distance_m IS NOT NULL)
);
CREATE INDEX ix_exercise_sets_completed ON training.exercise_sets (completed_at) WHERE completed_at IS NOT NULL;
COMMENT ON TABLE  training.exercise_sets IS 'Từng hiệp tập. Volume = reps × weight_kg được tính ở view (không lưu). reps là số đã được user xác nhận (có thể khác số AI đếm trong set_rep_events nếu user sửa).';
COMMENT ON COLUMN training.exercise_sets.id IS 'Khoá chính.';
COMMENT ON COLUMN training.exercise_sets.session_exercise_id IS 'FK → training.session_exercises.';
COMMENT ON COLUMN training.exercise_sets.set_no IS 'Thứ tự hiệp trong bài.';
COMMENT ON COLUMN training.exercise_sets.set_type IS 'warmup/working/drop/failure.';
COMMENT ON COLUMN training.exercise_sets.reps IS 'Số rep đã xác nhận.';
COMMENT ON COLUMN training.exercise_sets.weight_kg IS 'Mức tạ (kg); NULL với bài tự thân.';
COMMENT ON COLUMN training.exercise_sets.duration_seconds IS 'Thời gian (giây) cho bài giữ tĩnh/cardio.';
COMMENT ON COLUMN training.exercise_sets.distance_m IS 'Quãng đường (m) cho cardio.';
COMMENT ON COLUMN training.exercise_sets.rpe IS 'RPE của hiệp (1–10, bước 0.5). RIR ≈ 10 − RPE nên không lưu riêng.';
COMMENT ON COLUMN training.exercise_sets.rest_seconds IS 'Thời gian nghỉ sau hiệp (giây).';
COMMENT ON COLUMN training.exercise_sets.source IS 'Nguồn dữ liệu (manual/ai_realtime/ai_video).';
COMMENT ON COLUMN training.exercise_sets.completed_at IS 'Thời điểm hoàn thành hiệp; NULL = hiệp dự kiến chưa tập.';
COMMENT ON COLUMN training.exercise_sets.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN training.exercise_sets.updated_at IS 'Thời điểm cập nhật gần nhất.';

-- ---------------------------------------------------------------------
-- training.set_rep_events — từng rep do AI (FSM) ghi nhận: đếm rep & đo tempo
-- ---------------------------------------------------------------------
CREATE TABLE training.set_rep_events (
    set_id                  bigint          NOT NULL,
    rep_no                  smallint        NOT NULL,
    start_offset_ms         integer         NOT NULL,
    eccentric_ms            integer         NOT NULL,
    pause_bottom_ms         integer         NOT NULL DEFAULT 0,
    concentric_ms           integer         NOT NULL,
    pause_top_ms            integer         NOT NULL DEFAULT 0,
    min_joint_angle_deg     numeric(5,2),
    max_joint_angle_deg     numeric(5,2),
    is_full_rom             boolean         NOT NULL DEFAULT true,
    created_at              timestamptz     NOT NULL DEFAULT now(),
    CONSTRAINT pk_set_rep_events PRIMARY KEY (set_id, rep_no),
    CONSTRAINT fk_set_rep_events_set FOREIGN KEY (set_id) REFERENCES training.exercise_sets (id) ON DELETE CASCADE,
    CONSTRAINT ck_set_rep_events_rep_no CHECK (rep_no > 0),
    CONSTRAINT ck_set_rep_events_durations CHECK (start_offset_ms >= 0 AND eccentric_ms >= 0 AND pause_bottom_ms >= 0 AND concentric_ms >= 0 AND pause_top_ms >= 0),
    CONSTRAINT ck_set_rep_events_angles CHECK (
        (min_joint_angle_deg IS NULL OR min_joint_angle_deg BETWEEN 0 AND 180)
        AND (max_joint_angle_deg IS NULL OR max_joint_angle_deg BETWEEN 0 AND 180)
        AND (min_joint_angle_deg IS NULL OR max_joint_angle_deg IS NULL OR max_joint_angle_deg >= min_joint_angle_deg))
);
COMMENT ON TABLE  training.set_rep_events IS 'Dữ liệu từng rep do máy trạng thái (FSM) trên thiết bị ghi nhận: thời lượng các pha (tempo) và biên độ góc khớp. Tempo trung bình/TUT tính ở training.v_set_tempo.';
COMMENT ON COLUMN training.set_rep_events.set_id IS 'FK → training.exercise_sets.';
COMMENT ON COLUMN training.set_rep_events.rep_no IS 'Số thứ tự rep trong hiệp.';
COMMENT ON COLUMN training.set_rep_events.start_offset_ms IS 'Thời điểm bắt đầu rep tính từ đầu hiệp (ms).';
COMMENT ON COLUMN training.set_rep_events.eccentric_ms IS 'Thời lượng pha hạ (ms).';
COMMENT ON COLUMN training.set_rep_events.pause_bottom_ms IS 'Thời gian dừng ở điểm thấp (ms).';
COMMENT ON COLUMN training.set_rep_events.concentric_ms IS 'Thời lượng pha đẩy lên (ms).';
COMMENT ON COLUMN training.set_rep_events.pause_top_ms IS 'Thời gian dừng ở điểm cao (ms).';
COMMENT ON COLUMN training.set_rep_events.min_joint_angle_deg IS 'Góc khớp nhỏ nhất trong rep (độ).';
COMMENT ON COLUMN training.set_rep_events.max_joint_angle_deg IS 'Góc khớp lớn nhất trong rep (độ).';
COMMENT ON COLUMN training.set_rep_events.is_full_rom IS 'TRUE = đạt đủ biên độ chuyển động theo ngưỡng.';
COMMENT ON COLUMN training.set_rep_events.created_at IS 'Thời điểm tạo bản ghi.';

-- ---------------------------------------------------------------------
-- Phục hồi cơ
-- ---------------------------------------------------------------------
CREATE TABLE training.recovery_predictions (
    session_id      uuid            NOT NULL,
    muscle_group_id smallint        NOT NULL,
    model_version   varchar(50)     NOT NULL,
    fatigue_score   numeric(5,2)    NOT NULL,
    recovered_at    timestamptz     NOT NULL,
    predicted_at    timestamptz     NOT NULL DEFAULT now(),
    CONSTRAINT pk_recovery_predictions PRIMARY KEY (session_id, muscle_group_id, model_version),
    CONSTRAINT fk_recovery_predictions_session FOREIGN KEY (session_id) REFERENCES training.workout_sessions (id) ON DELETE CASCADE,
    CONSTRAINT fk_recovery_predictions_muscle_group FOREIGN KEY (muscle_group_id) REFERENCES catalog.muscle_groups (id) ON DELETE RESTRICT,
    CONSTRAINT ck_recovery_predictions_fatigue CHECK (fatigue_score BETWEEN 0 AND 100)
);
CREATE INDEX ix_recovery_predictions_muscle_group_id ON training.recovery_predictions (muscle_group_id);
COMMENT ON TABLE  training.recovery_predictions IS 'Kết quả model PyTorch sau mỗi buổi tập: mức mệt mỏi và thời điểm hồi phục hoàn toàn của từng nhóm cơ. User suy ra qua session (không lưu). Trạng thái Heatmap hiện tại tính ở training.v_muscle_recovery_status.';
COMMENT ON COLUMN training.recovery_predictions.session_id IS 'Buổi tập kích hoạt dự đoán (FK → training.workout_sessions).';
COMMENT ON COLUMN training.recovery_predictions.muscle_group_id IS 'FK → catalog.muscle_groups.';
COMMENT ON COLUMN training.recovery_predictions.model_version IS 'Phiên bản model (cho phép so sánh nhiều phiên bản).';
COMMENT ON COLUMN training.recovery_predictions.fatigue_score IS 'Mức mệt mỏi ngay sau buổi tập (0–100).';
COMMENT ON COLUMN training.recovery_predictions.recovered_at IS 'Thời điểm dự kiến hồi phục hoàn toàn.';
COMMENT ON COLUMN training.recovery_predictions.predicted_at IS 'Thời điểm chạy dự đoán.';

CREATE TABLE training.muscle_soreness_reports (
    id              bigint          GENERATED ALWAYS AS IDENTITY,
    user_id         uuid            NOT NULL,
    muscle_group_id smallint        NOT NULL,
    soreness_level  smallint        NOT NULL,
    reported_at     timestamptz     NOT NULL DEFAULT now(),
    note            varchar(255),
    created_at      timestamptz     NOT NULL DEFAULT now(),
    CONSTRAINT pk_muscle_soreness_reports PRIMARY KEY (id),
    CONSTRAINT fk_muscle_soreness_reports_user FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE CASCADE,
    CONSTRAINT fk_muscle_soreness_reports_muscle_group FOREIGN KEY (muscle_group_id) REFERENCES catalog.muscle_groups (id) ON DELETE RESTRICT,
    CONSTRAINT uq_muscle_soreness_reports UNIQUE (user_id, muscle_group_id, reported_at),
    CONSTRAINT ck_muscle_soreness_reports_level CHECK (soreness_level BETWEEN 0 AND 10)
);
CREATE INDEX ix_muscle_soreness_reports_muscle_group_id ON training.muscle_soreness_reports (muscle_group_id);
COMMENT ON TABLE  training.muscle_soreness_reports IS 'User tự báo mức đau mỏi cơ (DOMS). Là nhãn thực tế để huấn luyện/cá nhân hoá model dự đoán phục hồi.';
COMMENT ON COLUMN training.muscle_soreness_reports.id IS 'Khoá chính.';
COMMENT ON COLUMN training.muscle_soreness_reports.user_id IS 'FK → auth.users.';
COMMENT ON COLUMN training.muscle_soreness_reports.muscle_group_id IS 'FK → catalog.muscle_groups.';
COMMENT ON COLUMN training.muscle_soreness_reports.soreness_level IS 'Mức đau mỏi 0 (không) – 10 (rất đau).';
COMMENT ON COLUMN training.muscle_soreness_reports.reported_at IS 'Thời điểm báo cáo.';
COMMENT ON COLUMN training.muscle_soreness_reports.note IS 'Ghi chú.';
COMMENT ON COLUMN training.muscle_soreness_reports.created_at IS 'Thời điểm tạo bản ghi.';
