-- =====================================================================
-- Smart Workout AI — 07: AI results (schema ai)
-- Chức năng 5 (Posture Correction: 1A realtime / 1B video), 7 (Nhận diện thiết bị)
-- =====================================================================

CREATE TYPE ai.analysis_mode AS ENUM ('realtime_edge', 'video_server');
CREATE TYPE ai.issue_severity AS ENUM ('info', 'warning', 'critical');
CREATE TYPE ai.scan_feedback AS ENUM ('correct', 'incorrect');

COMMENT ON TYPE ai.analysis_mode IS 'realtime_edge = MediaPipe trên điện thoại (1A); video_server = YOLOv8-Pose trên server (1B).';
COMMENT ON TYPE ai.issue_severity IS 'Mức độ nghiêm trọng của lỗi tư thế.';
COMMENT ON TYPE ai.scan_feedback IS 'Phản hồi của user về kết quả nhận diện thiết bị.';

-- ---------------------------------------------------------------------
-- ai.pose_analyses — một lần phân tích tư thế cho một hiệp tập
-- ---------------------------------------------------------------------
CREATE TABLE ai.pose_analyses (
    id                  uuid                NOT NULL DEFAULT gen_random_uuid(),
    set_id              bigint              NOT NULL,
    mode                ai.analysis_mode    NOT NULL,
    model_name          varchar(50)         NOT NULL,
    model_version       varchar(50)         NOT NULL,
    overall_score       numeric(5,2),
    correct_form_pct    numeric(5,2),
    detected_rep_count  smallint,
    feedback_summary    text,
    keypoints_media_id  uuid,
    analyzed_at         timestamptz,
    created_at          timestamptz         NOT NULL DEFAULT now(),
    updated_at          timestamptz         NOT NULL DEFAULT now(),
    CONSTRAINT pk_pose_analyses PRIMARY KEY (id),
    CONSTRAINT fk_pose_analyses_set FOREIGN KEY (set_id) REFERENCES training.exercise_sets (id) ON DELETE CASCADE,
    CONSTRAINT fk_pose_analyses_keypoints_media FOREIGN KEY (keypoints_media_id) REFERENCES media.media_files (id) ON DELETE SET NULL,
    CONSTRAINT ck_pose_analyses_scores CHECK (
        (overall_score IS NULL OR overall_score BETWEEN 0 AND 100)
        AND (correct_form_pct IS NULL OR correct_form_pct BETWEEN 0 AND 100)),
    CONSTRAINT ck_pose_analyses_rep_count CHECK (detected_rep_count IS NULL OR detected_rep_count >= 0),
    CONSTRAINT ck_pose_analyses_realtime_done CHECK (mode <> 'realtime_edge' OR analyzed_at IS NOT NULL)
);
CREATE INDEX ix_pose_analyses_set_id ON ai.pose_analyses (set_id);
CREATE INDEX ix_pose_analyses_keypoints_media_id ON ai.pose_analyses (keypoints_media_id);
COMMENT ON TABLE  ai.pose_analyses IS 'Kết quả phân tích tư thế cho một hiệp tập (realtime trên thiết bị hoặc video trên server). User/bài tập suy ra qua set → session_exercise → session. Keypoint thô từng frame lưu thành file trên Object Storage (keypoints_media_id) thay vì JSON trong DB.';
COMMENT ON COLUMN ai.pose_analyses.id IS 'Khoá chính.';
COMMENT ON COLUMN ai.pose_analyses.set_id IS 'Hiệp được phân tích (FK → training.exercise_sets).';
COMMENT ON COLUMN ai.pose_analyses.mode IS 'realtime_edge/video_server.';
COMMENT ON COLUMN ai.pose_analyses.model_name IS 'Tên model (vd: mediapipe_blazepose, yolov8_pose).';
COMMENT ON COLUMN ai.pose_analyses.model_version IS 'Phiên bản model.';
COMMENT ON COLUMN ai.pose_analyses.overall_score IS 'Điểm kỹ thuật tổng (0–100), vd: 85/100.';
COMMENT ON COLUMN ai.pose_analyses.correct_form_pct IS 'Tỷ lệ % thời gian/frame đúng form.';
COMMENT ON COLUMN ai.pose_analyses.detected_rep_count IS 'Số rep AI phát hiện được.';
COMMENT ON COLUMN ai.pose_analyses.feedback_summary IS 'Nhận xét tổng hợp.';
COMMENT ON COLUMN ai.pose_analyses.keypoints_media_id IS 'File keypoint thô (JSON/NPZ) trên storage, phục vụ huấn luyện lại.';
COMMENT ON COLUMN ai.pose_analyses.analyzed_at IS 'Thời điểm có kết quả; NULL khi video đang chờ xử lý.';
COMMENT ON COLUMN ai.pose_analyses.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN ai.pose_analyses.updated_at IS 'Thời điểm cập nhật gần nhất.';

-- ---------------------------------------------------------------------
-- ai.video_analysis_jobs — vòng đời xử lý video bất đồng bộ (1B)
-- ---------------------------------------------------------------------
CREATE TABLE ai.video_analysis_jobs (
    id                      uuid            NOT NULL DEFAULT gen_random_uuid(),
    pose_analysis_id        uuid            NOT NULL,
    source_video_media_id   uuid            NOT NULL,
    result_video_media_id   uuid,
    status                  util.job_status NOT NULL DEFAULT 'queued',
    priority                smallint        NOT NULL DEFAULT 5,
    attempt_count           smallint        NOT NULL DEFAULT 0,
    max_attempts            smallint        NOT NULL DEFAULT 3,
    queued_at               timestamptz     NOT NULL DEFAULT now(),
    started_at              timestamptz,
    finished_at             timestamptz,
    worker_id               varchar(100),
    error_message           text,
    notified_at             timestamptz,
    created_at              timestamptz     NOT NULL DEFAULT now(),
    updated_at              timestamptz     NOT NULL DEFAULT now(),
    CONSTRAINT pk_video_analysis_jobs PRIMARY KEY (id),
    CONSTRAINT uq_video_analysis_jobs_pose_analysis UNIQUE (pose_analysis_id),
    CONSTRAINT fk_video_analysis_jobs_pose_analysis FOREIGN KEY (pose_analysis_id) REFERENCES ai.pose_analyses (id) ON DELETE CASCADE,
    CONSTRAINT fk_video_analysis_jobs_source_video FOREIGN KEY (source_video_media_id) REFERENCES media.media_files (id) ON DELETE RESTRICT,
    CONSTRAINT fk_video_analysis_jobs_result_video FOREIGN KEY (result_video_media_id) REFERENCES media.media_files (id) ON DELETE SET NULL,
    CONSTRAINT ck_video_analysis_jobs_priority CHECK (priority BETWEEN 1 AND 10),
    CONSTRAINT ck_video_analysis_jobs_attempts CHECK (attempt_count >= 0 AND max_attempts >= 1 AND attempt_count <= max_attempts),
    CONSTRAINT ck_video_analysis_jobs_times CHECK (
        (started_at IS NULL OR started_at >= queued_at)
        AND (finished_at IS NULL OR (started_at IS NOT NULL AND finished_at >= started_at))),
    CONSTRAINT ck_video_analysis_jobs_completed CHECK (status <> 'completed' OR (result_video_media_id IS NOT NULL AND finished_at IS NOT NULL)),
    CONSTRAINT ck_video_analysis_jobs_failed CHECK (status <> 'failed' OR error_message IS NOT NULL),
    CONSTRAINT ck_video_analysis_jobs_distinct_media CHECK (result_video_media_id IS NULL OR result_video_media_id <> source_video_media_id)
);
CREATE INDEX ix_video_analysis_jobs_source_video ON ai.video_analysis_jobs (source_video_media_id);
CREATE INDEX ix_video_analysis_jobs_result_video ON ai.video_analysis_jobs (result_video_media_id);
CREATE INDEX ix_video_analysis_jobs_queue ON ai.video_analysis_jobs (priority DESC, queued_at) WHERE status = 'queued';
COMMENT ON TABLE  ai.video_analysis_jobs IS 'Job phân tích video (1B): backend tạo job trạng thái queued + đẩy message vào queue; AI worker chuyển processing → completed/failed, upload video kết quả, backend gửi push (notified_at).';
COMMENT ON COLUMN ai.video_analysis_jobs.id IS 'Khoá chính (dùng làm message id trong queue).';
COMMENT ON COLUMN ai.video_analysis_jobs.pose_analysis_id IS 'Kết quả phân tích tương ứng (1-1, FK → ai.pose_analyses, mode phải là video_server).';
COMMENT ON COLUMN ai.video_analysis_jobs.source_video_media_id IS 'Video gốc user tải lên (FK → media.media_files).';
COMMENT ON COLUMN ai.video_analysis_jobs.result_video_media_id IS 'Video đã vẽ khung xương/nhãn cảnh báo.';
COMMENT ON COLUMN ai.video_analysis_jobs.status IS 'queued/processing/completed/failed/cancelled.';
COMMENT ON COLUMN ai.video_analysis_jobs.priority IS 'Độ ưu tiên 1–10 (cao xử lý trước).';
COMMENT ON COLUMN ai.video_analysis_jobs.attempt_count IS 'Số lần đã thử xử lý.';
COMMENT ON COLUMN ai.video_analysis_jobs.max_attempts IS 'Số lần thử tối đa trước khi failed.';
COMMENT ON COLUMN ai.video_analysis_jobs.queued_at IS 'Thời điểm vào hàng đợi.';
COMMENT ON COLUMN ai.video_analysis_jobs.started_at IS 'Thời điểm worker bắt đầu xử lý.';
COMMENT ON COLUMN ai.video_analysis_jobs.finished_at IS 'Thời điểm kết thúc xử lý.';
COMMENT ON COLUMN ai.video_analysis_jobs.worker_id IS 'Định danh worker xử lý.';
COMMENT ON COLUMN ai.video_analysis_jobs.error_message IS 'Thông báo lỗi khi failed.';
COMMENT ON COLUMN ai.video_analysis_jobs.notified_at IS 'Thời điểm đã gửi push notification cho user.';
COMMENT ON COLUMN ai.video_analysis_jobs.created_at IS 'Thời điểm tạo bản ghi.';
COMMENT ON COLUMN ai.video_analysis_jobs.updated_at IS 'Thời điểm cập nhật gần nhất.';

CREATE OR REPLACE FUNCTION ai.fn_check_video_job_mode()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM ai.pose_analyses pa WHERE pa.id = NEW.pose_analysis_id AND pa.mode <> 'video_server') THEN
        RAISE EXCEPTION 'pose_analysis % không phải chế độ video_server', NEW.pose_analysis_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;
COMMENT ON FUNCTION ai.fn_check_video_job_mode() IS 'Job video chỉ được gắn với pose_analysis ở chế độ video_server.';

CREATE TRIGGER trg_video_analysis_jobs_mode
    BEFORE INSERT OR UPDATE OF pose_analysis_id ON ai.video_analysis_jobs
    FOR EACH ROW EXECUTE FUNCTION ai.fn_check_video_job_mode();

-- ---------------------------------------------------------------------
-- ai.posture_issues — từng lỗi tư thế được phát hiện
-- ---------------------------------------------------------------------
CREATE TABLE ai.posture_issues (
    id                  bigint              GENERATED ALWAYS AS IDENTITY,
    pose_analysis_id    uuid                NOT NULL,
    mistake_id          integer             NOT NULL,
    rep_no              smallint,
    offset_ms           integer             NOT NULL,
    frame_index         integer,
    severity            ai.issue_severity   NOT NULL DEFAULT 'warning',
    measured_angle_deg  numeric(5,2),
    created_at          timestamptz         NOT NULL DEFAULT now(),
    CONSTRAINT pk_posture_issues PRIMARY KEY (id),
    CONSTRAINT fk_posture_issues_pose_analysis FOREIGN KEY (pose_analysis_id) REFERENCES ai.pose_analyses (id) ON DELETE CASCADE,
    CONSTRAINT fk_posture_issues_mistake FOREIGN KEY (mistake_id) REFERENCES catalog.exercise_mistakes (id) ON DELETE RESTRICT,
    CONSTRAINT ck_posture_issues_rep_no CHECK (rep_no IS NULL OR rep_no > 0),
    CONSTRAINT ck_posture_issues_offset CHECK (offset_ms >= 0),
    CONSTRAINT ck_posture_issues_frame CHECK (frame_index IS NULL OR frame_index >= 0),
    CONSTRAINT ck_posture_issues_angle CHECK (measured_angle_deg IS NULL OR measured_angle_deg BETWEEN 0 AND 360)
);
CREATE INDEX ix_posture_issues_pose_analysis_id ON ai.posture_issues (pose_analysis_id, offset_ms);
CREATE INDEX ix_posture_issues_mistake_id ON ai.posture_issues (mistake_id);
COMMENT ON TABLE  ai.posture_issues IS 'Các lỗi tư thế AI phát hiện (vd: lưng cong khi squat) kèm vị trí thời gian, dùng để tô đỏ khung xương và vẽ timeline cảnh báo. Mã lỗi tham chiếu catalog.exercise_mistakes của đúng bài tập (kiểm tra bằng trigger).';
COMMENT ON COLUMN ai.posture_issues.id IS 'Khoá chính.';
COMMENT ON COLUMN ai.posture_issues.pose_analysis_id IS 'FK → ai.pose_analyses.';
COMMENT ON COLUMN ai.posture_issues.mistake_id IS 'Loại lỗi (FK → catalog.exercise_mistakes).';
COMMENT ON COLUMN ai.posture_issues.rep_no IS 'Rep xảy ra lỗi (nếu xác định được).';
COMMENT ON COLUMN ai.posture_issues.offset_ms IS 'Thời điểm lỗi tính từ đầu hiệp/video (ms).';
COMMENT ON COLUMN ai.posture_issues.frame_index IS 'Chỉ số frame trong video (chế độ video).';
COMMENT ON COLUMN ai.posture_issues.severity IS 'info/warning/critical.';
COMMENT ON COLUMN ai.posture_issues.measured_angle_deg IS 'Góc khớp đo được tại thời điểm lỗi (độ).';
COMMENT ON COLUMN ai.posture_issues.created_at IS 'Thời điểm tạo bản ghi.';

CREATE OR REPLACE FUNCTION ai.fn_check_posture_issue_exercise()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_set_exercise_id     integer;
    v_mistake_exercise_id integer;
BEGIN
    SELECT se.exercise_id INTO v_set_exercise_id
    FROM ai.pose_analyses pa
    JOIN training.exercise_sets es ON es.id = pa.set_id
    JOIN training.session_exercises se ON se.id = es.session_exercise_id
    WHERE pa.id = NEW.pose_analysis_id;

    SELECT m.exercise_id INTO v_mistake_exercise_id
    FROM catalog.exercise_mistakes m
    WHERE m.id = NEW.mistake_id;

    IF v_set_exercise_id IS DISTINCT FROM v_mistake_exercise_id THEN
        RAISE EXCEPTION 'Lỗi tư thế % không thuộc bài tập của hiệp được phân tích', NEW.mistake_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;
COMMENT ON FUNCTION ai.fn_check_posture_issue_exercise() IS 'Đảm bảo mã lỗi tư thế thuộc đúng bài tập của hiệp đang phân tích.';

CREATE TRIGGER trg_posture_issues_exercise_match
    BEFORE INSERT OR UPDATE OF mistake_id, pose_analysis_id ON ai.posture_issues
    FOR EACH ROW EXECUTE FUNCTION ai.fn_check_posture_issue_exercise();

-- ---------------------------------------------------------------------
-- ai.bar_path_points — quỹ đạo thanh tạ (biểu đồ trong báo cáo video)
-- ---------------------------------------------------------------------
CREATE TABLE ai.bar_path_points (
    pose_analysis_id    uuid            NOT NULL,
    frame_index         integer         NOT NULL,
    offset_ms           integer         NOT NULL,
    x_norm              numeric(6,5)    NOT NULL,
    y_norm              numeric(6,5)    NOT NULL,
    CONSTRAINT pk_bar_path_points PRIMARY KEY (pose_analysis_id, frame_index),
    CONSTRAINT fk_bar_path_points_pose_analysis FOREIGN KEY (pose_analysis_id) REFERENCES ai.pose_analyses (id) ON DELETE CASCADE,
    CONSTRAINT ck_bar_path_points_frame CHECK (frame_index >= 0 AND offset_ms >= 0),
    CONSTRAINT ck_bar_path_points_coords CHECK (x_norm BETWEEN 0 AND 1 AND y_norm BETWEEN 0 AND 1)
);
COMMENT ON TABLE  ai.bar_path_points IS 'Toạ độ thanh tạ theo frame (chuẩn hoá 0–1 theo khung hình) để vẽ biểu đồ quỹ đạo.';
COMMENT ON COLUMN ai.bar_path_points.pose_analysis_id IS 'FK → ai.pose_analyses.';
COMMENT ON COLUMN ai.bar_path_points.frame_index IS 'Chỉ số frame.';
COMMENT ON COLUMN ai.bar_path_points.offset_ms IS 'Thời điểm frame trong video (ms).';
COMMENT ON COLUMN ai.bar_path_points.x_norm IS 'Toạ độ X chuẩn hoá (0 = trái, 1 = phải).';
COMMENT ON COLUMN ai.bar_path_points.y_norm IS 'Toạ độ Y chuẩn hoá (0 = trên, 1 = dưới).';

-- ---------------------------------------------------------------------
-- Nhận diện thiết bị (chức năng 7)
-- ---------------------------------------------------------------------
CREATE TABLE ai.equipment_scans (
    id                      uuid                NOT NULL DEFAULT gen_random_uuid(),
    user_id                 uuid                NOT NULL,
    image_media_id          uuid,
    model_name              varchar(50)         NOT NULL,
    model_version           varchar(50)         NOT NULL,
    latency_ms              integer,
    scanned_at              timestamptz         NOT NULL DEFAULT now(),
    feedback                ai.scan_feedback,
    feedback_at             timestamptz,
    corrected_equipment_id  integer,
    CONSTRAINT pk_equipment_scans PRIMARY KEY (id),
    CONSTRAINT fk_equipment_scans_user FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE CASCADE,
    CONSTRAINT fk_equipment_scans_image_media FOREIGN KEY (image_media_id) REFERENCES media.media_files (id) ON DELETE SET NULL,
    CONSTRAINT fk_equipment_scans_corrected_equipment FOREIGN KEY (corrected_equipment_id) REFERENCES catalog.equipment (id) ON DELETE SET NULL,
    CONSTRAINT ck_equipment_scans_latency CHECK (latency_ms IS NULL OR latency_ms >= 0),
    CONSTRAINT ck_equipment_scans_feedback CHECK ((feedback IS NULL) = (feedback_at IS NULL)),
    CONSTRAINT ck_equipment_scans_correction CHECK (corrected_equipment_id IS NULL OR feedback = 'incorrect')
);
CREATE INDEX ix_equipment_scans_user_time ON ai.equipment_scans (user_id, scanned_at DESC);
CREATE INDEX ix_equipment_scans_image_media_id ON ai.equipment_scans (image_media_id);
CREATE INDEX ix_equipment_scans_corrected_equipment_id ON ai.equipment_scans (corrected_equipment_id);
COMMENT ON TABLE  ai.equipment_scans IS 'Mỗi lần user quét thiết bị bằng camera. Phản hồi đúng/sai và nhãn sửa (corrected_equipment_id) dùng để fine-tune YOLOv8.';
COMMENT ON COLUMN ai.equipment_scans.id IS 'Khoá chính.';
COMMENT ON COLUMN ai.equipment_scans.user_id IS 'FK → auth.users.';
COMMENT ON COLUMN ai.equipment_scans.image_media_id IS 'Ảnh đã quét (có thể không lưu vì quyền riêng tư).';
COMMENT ON COLUMN ai.equipment_scans.model_name IS 'Tên model (vd: yolov8_cls_gym).';
COMMENT ON COLUMN ai.equipment_scans.model_version IS 'Phiên bản model.';
COMMENT ON COLUMN ai.equipment_scans.latency_ms IS 'Thời gian suy luận (ms).';
COMMENT ON COLUMN ai.equipment_scans.scanned_at IS 'Thời điểm quét.';
COMMENT ON COLUMN ai.equipment_scans.feedback IS 'User xác nhận kết quả đúng/sai.';
COMMENT ON COLUMN ai.equipment_scans.feedback_at IS 'Thời điểm phản hồi.';
COMMENT ON COLUMN ai.equipment_scans.corrected_equipment_id IS 'Thiết bị đúng do user chọn khi AI sai.';

CREATE TABLE ai.equipment_scan_predictions (
    scan_id         uuid            NOT NULL,
    equipment_id    integer         NOT NULL,
    confidence      numeric(5,4)    NOT NULL,
    CONSTRAINT pk_equipment_scan_predictions PRIMARY KEY (scan_id, equipment_id),
    CONSTRAINT fk_equipment_scan_predictions_scan FOREIGN KEY (scan_id) REFERENCES ai.equipment_scans (id) ON DELETE CASCADE,
    CONSTRAINT fk_equipment_scan_predictions_equipment FOREIGN KEY (equipment_id) REFERENCES catalog.equipment (id) ON DELETE RESTRICT,
    CONSTRAINT ck_equipment_scan_predictions_confidence CHECK (confidence BETWEEN 0 AND 1)
);
CREATE INDEX ix_equipment_scan_predictions_equipment_id ON ai.equipment_scan_predictions (equipment_id);
COMMENT ON TABLE  ai.equipment_scan_predictions IS 'Top-k dự đoán của model cho một lần quét (nhãn AI đã ánh xạ sang thiết bị qua catalog.equipment_aliases). Thứ hạng và kết quả top-1 suy ra từ confidence, không lưu riêng.';
COMMENT ON COLUMN ai.equipment_scan_predictions.scan_id IS 'FK → ai.equipment_scans.';
COMMENT ON COLUMN ai.equipment_scan_predictions.equipment_id IS 'Thiết bị dự đoán (FK → catalog.equipment).';
COMMENT ON COLUMN ai.equipment_scan_predictions.confidence IS 'Độ tin cậy (0–1).';
