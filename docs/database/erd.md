# Sơ đồ thực thể – quan hệ (ERD) — Smart Workout AI

> PostgreSQL 16 · 7 schema nghiệp vụ · 51 bảng. Tên thực thể trong sơ đồ được viết dạng `schema_table`
> (Mermaid không cho phép dấu chấm), ví dụ `training_workout_sessions` = `training.workout_sessions`.
> Chi tiết từng cột xem [data-dictionary.md](data-dictionary.md).

Ký hiệu Mermaid: `||` đúng một · `o|` không hoặc một · `o{` không hoặc nhiều · `|{` một hoặc nhiều.
Nét liền = khoá ngoại thật; nét đứt (`..`) = quan hệ **logic** được suy ra bằng truy vấn (không lưu FK — xem [normalization.md](normalization.md)).

## 1. Tổng quan giữa các module

```mermaid
erDiagram
    auth_users ||--o| auth_user_profiles : "hồ sơ"
    auth_users ||--o| body_user_body_profiles : "hồ sơ thể chất"
    auth_users ||--o{ body_body_measurements : "đo"
    auth_users ||--o{ training_workout_plans : "sở hữu"
    auth_users ||--o{ training_scheduled_workouts : "xếp lịch"
    auth_users ||--o{ training_workout_sessions : "tập"
    training_workout_sessions ||--o{ training_session_exercises : "gồm"
    catalog_exercises ||--o{ training_session_exercises : "được tập"
    training_session_exercises ||--o{ training_exercise_sets : "gồm"
    training_exercise_sets ||--o{ ai_pose_analyses : "được phân tích"
    training_workout_sessions ||--o{ training_recovery_predictions : "sinh dự đoán"
    catalog_muscle_groups ||--o{ training_recovery_predictions : "của nhóm cơ"
    catalog_exercises ||--o{ catalog_exercise_muscles : "tác động"
    catalog_muscle_groups ||--o{ catalog_exercise_muscles : ""
    catalog_exercises ||--o{ catalog_exercise_equipment : "cần"
    catalog_equipment ||--o{ catalog_exercise_equipment : ""
    auth_users ||--o{ ai_equipment_scans : "quét"
    catalog_equipment ||--o{ ai_equipment_scan_predictions : "được dự đoán"
    auth_users ||--o{ media_progress_photos : "chụp"
    media_media_files ||--o{ media_progress_photos : "file ảnh"
    body_body_measurements |o..o{ media_progress_photos : "số đo tại thời điểm chụp"
    auth_users ||--o{ analytics_report_exports : "xuất báo cáo"
```

## 2. `auth` — Định danh & phân quyền (RBAC)

```mermaid
erDiagram
    auth_users {
        uuid id PK
        citext email UK "unique khi chưa xoá"
        varchar phone_number UK
        varchar password_hash "NULL nếu chỉ OAuth"
        enum status "pending_verification/active/locked/disabled"
        timestamptz email_verified_at
        timestamptz locked_until
        timestamptz deleted_at "xoá mềm"
    }
    auth_user_profiles {
        uuid user_id PK, FK
        varchar display_name
        uuid avatar_media_id FK
        varchar locale
        varchar timezone
        enum unit_system
    }
    auth_roles {
        smallint id PK
        varchar code UK
        varchar name
        boolean is_system
    }
    auth_permissions {
        smallint id PK
        varchar resource UK "UQ(resource, action)"
        varchar action UK
    }
    auth_role_permissions {
        smallint role_id PK, FK
        smallint permission_id PK, FK
    }
    auth_user_roles {
        uuid user_id PK, FK
        smallint role_id PK, FK
        uuid granted_by FK
        timestamptz expires_at
    }
    auth_oauth_accounts {
        uuid id PK
        uuid user_id FK
        enum provider UK "UQ(provider, provider_subject)"
        varchar provider_subject UK
    }
    auth_user_devices {
        uuid id PK
        uuid user_id FK
        enum platform
        varchar push_token UK "FCM/APNs"
        timestamptz revoked_at
    }
    auth_refresh_tokens {
        uuid id PK
        uuid device_id FK "user suy ra qua device"
        uuid family_id "chuỗi xoay vòng"
        uuid parent_token_id FK
        char token_hash UK "SHA-256"
        timestamptz expires_at
        enum revoke_reason
    }
    auth_verification_tokens {
        uuid id PK
        uuid user_id FK
        enum purpose
        char token_hash UK
        timestamptz consumed_at
    }
    auth_login_attempts {
        bigint id PK
        uuid user_id FK
        citext email_attempted
        inet ip_address
        boolean succeeded
        enum failure_reason
    }

    auth_users ||--o| auth_user_profiles : ""
    auth_users ||--o{ auth_user_roles : ""
    auth_roles ||--o{ auth_user_roles : ""
    auth_roles ||--o{ auth_role_permissions : ""
    auth_permissions ||--o{ auth_role_permissions : ""
    auth_users ||--o{ auth_oauth_accounts : ""
    auth_users ||--o{ auth_user_devices : ""
    auth_user_devices ||--o{ auth_refresh_tokens : ""
    auth_refresh_tokens |o--o{ auth_refresh_tokens : "token con"
    auth_users ||--o{ auth_verification_tokens : ""
    auth_users |o--o{ auth_login_attempts : ""
```

## 3. `catalog` — Thư viện bài tập (Exercise Wiki)

```mermaid
erDiagram
    catalog_difficulty_levels {
        smallint id PK
        varchar code UK
        smallint rank UK "sắp xếp độ khó"
    }
    catalog_body_regions {
        smallint id PK
        varchar code UK
    }
    catalog_muscle_groups {
        smallint id PK
        varchar code UK
        varchar name "vd: Lưng xô"
        smallint parent_id FK "phân cấp"
        smallint body_region_id FK "chỉ ở nút gốc"
        varchar heatmap_region_key UK
        smallint base_recovery_hours
    }
    catalog_equipment_categories {
        smallint id PK
        varchar code UK
    }
    catalog_equipment {
        integer id PK
        varchar code UK
        varchar name
        smallint category_id FK
        uuid image_media_id FK
    }
    catalog_equipment_aliases {
        integer id PK
        integer equipment_id FK
        varchar alias "ai_label unique toàn bảng"
        enum alias_type "synonym/ai_label"
    }
    catalog_exercises {
        integer id PK
        varchar slug UK
        varchar name
        smallint difficulty_level_id FK
        enum category
        enum mechanic
        enum force_type
        numeric met_value "tính calo"
        boolean supports_ai_tracking
        enum status "draft/published/archived"
    }
    catalog_exercise_muscles {
        integer exercise_id PK, FK
        smallint muscle_group_id PK, FK
        enum role "primary/secondary/stabilizer"
        numeric activation_ratio
    }
    catalog_exercise_equipment {
        integer exercise_id PK, FK
        integer equipment_id PK, FK
        boolean is_optional
    }
    catalog_exercise_instructions {
        integer exercise_id PK, FK
        smallint step_no PK
        text content
    }
    catalog_exercise_mistakes {
        integer id PK
        integer exercise_id FK
        varchar code UK "mã lỗi AI trả về"
        varchar title
        enum at_risk_joint
        boolean ai_detectable
    }
    catalog_exercise_media {
        integer exercise_id PK, FK
        uuid media_id PK, FK
        enum media_role
        boolean is_primary
    }
    catalog_exercise_alternatives {
        integer exercise_id PK, FK
        integer alternative_exercise_id PK, FK
    }
    media_media_files {
        uuid id PK
    }

    catalog_body_regions ||--o{ catalog_muscle_groups : "nút gốc"
    catalog_muscle_groups |o--o{ catalog_muscle_groups : "cha - con"
    catalog_equipment_categories ||--o{ catalog_equipment : ""
    catalog_equipment ||--o{ catalog_equipment_aliases : ""
    catalog_difficulty_levels ||--o{ catalog_exercises : ""
    catalog_exercises ||--o{ catalog_exercise_muscles : ""
    catalog_muscle_groups ||--o{ catalog_exercise_muscles : ""
    catalog_exercises ||--o{ catalog_exercise_equipment : ""
    catalog_equipment ||--o{ catalog_exercise_equipment : ""
    catalog_exercises ||--|{ catalog_exercise_instructions : ""
    catalog_exercises ||--o{ catalog_exercise_mistakes : ""
    catalog_exercises ||--o{ catalog_exercise_media : ""
    media_media_files ||--o{ catalog_exercise_media : ""
    catalog_exercises ||--o{ catalog_exercise_alternatives : "bài gốc"
    catalog_exercises ||--o{ catalog_exercise_alternatives : "bài thay thế"
    media_media_files |o--o{ catalog_equipment : "ảnh"
```

## 4. `body` — Chỉ số cơ thể & mục tiêu

```mermaid
erDiagram
    auth_users {
        uuid id PK
    }
    body_activity_levels {
        smallint id PK
        varchar code UK
        numeric multiplier "hệ số TDEE"
    }
    body_fitness_goal_types {
        smallint id PK
        varchar code UK
    }
    body_body_sites {
        smallint id PK
        varchar code UK
    }
    body_user_body_profiles {
        uuid user_id PK, FK
        enum gender
        date date_of_birth "tuổi = tính"
        numeric height_cm
        smallint activity_level_id FK
        smallint experience_level_id FK
    }
    body_body_measurements {
        uuid id PK
        uuid user_id FK "UQ(user_id, measured_at)"
        timestamptz measured_at
        numeric weight_kg
        numeric body_fat_pct
        numeric muscle_mass_kg
        enum source
    }
    body_body_circumferences {
        uuid measurement_id PK, FK
        smallint body_site_id PK, FK
        numeric value_cm
    }
    body_user_goals {
        uuid id PK
        uuid user_id FK "tối đa 1 goal active"
        smallint goal_type_id FK
        numeric target_weight_kg
        date target_date
        enum status
    }
    catalog_difficulty_levels {
        smallint id PK
    }

    auth_users ||--o| body_user_body_profiles : ""
    body_activity_levels |o--o{ body_user_body_profiles : ""
    catalog_difficulty_levels |o--o{ body_user_body_profiles : "trình độ"
    auth_users ||--o{ body_body_measurements : ""
    body_body_measurements ||--o{ body_body_circumferences : ""
    body_body_sites ||--o{ body_body_circumferences : ""
    auth_users ||--o{ body_user_goals : ""
    body_fitness_goal_types ||--o{ body_user_goals : ""
```

## 5. `training` — Giáo án, lịch tập, buổi tập, phục hồi

```mermaid
erDiagram
    auth_users {
        uuid id PK
    }
    catalog_exercises {
        integer id PK
    }
    catalog_muscle_groups {
        smallint id PK
    }
    training_workout_plans {
        uuid id PK
        uuid owner_user_id FK "NULL = giáo án mẫu"
        uuid source_plan_id FK
        varchar name
        smallint goal_type_id FK
        smallint difficulty_level_id FK
        enum status
    }
    training_workout_plan_days {
        uuid id PK
        uuid plan_id FK "UQ(plan_id, day_no)"
        smallint day_no
        varchar name
    }
    training_workout_plan_exercises {
        uuid id PK
        uuid plan_day_id FK
        integer exercise_id FK
        smallint order_no
        smallint target_sets
        smallint target_reps_min
        smallint target_reps_max
        numeric target_weight_kg
        smallint tempo_eccentric_s "tempo tách 4 cột"
    }
    training_scheduled_workouts {
        uuid id PK
        uuid user_id FK
        uuid plan_day_id FK
        date scheduled_date
        enum status "planned/skipped/cancelled"
        timestamptz recovery_warning_ack_at
    }
    training_workout_sessions {
        uuid id PK
        uuid user_id FK
        uuid scheduled_workout_id FK "FK kép (id, user_id)"
        timestamptz started_at
        timestamptz ended_at
        enum status "1 in_progress / user"
    }
    training_session_exercises {
        uuid id PK
        uuid session_id FK
        integer exercise_id FK "bài thực tế"
        uuid plan_exercise_id FK
        smallint order_no
        enum added_via
    }
    training_exercise_sets {
        bigint id PK
        uuid session_exercise_id FK
        smallint set_no
        enum set_type
        smallint reps
        numeric weight_kg
        numeric rpe
        enum source "manual/ai_realtime/ai_video"
    }
    training_set_rep_events {
        bigint set_id PK, FK
        smallint rep_no PK
        integer eccentric_ms
        integer concentric_ms
        boolean is_full_rom
    }
    training_recovery_predictions {
        uuid session_id PK, FK
        smallint muscle_group_id PK, FK
        varchar model_version PK
        numeric fatigue_score
        timestamptz recovered_at
    }
    training_muscle_soreness_reports {
        bigint id PK
        uuid user_id FK
        smallint muscle_group_id FK
        smallint soreness_level
    }

    auth_users |o--o{ training_workout_plans : "sở hữu"
    training_workout_plans |o--o{ training_workout_plans : "nhân bản từ"
    training_workout_plans ||--|{ training_workout_plan_days : ""
    training_workout_plan_days ||--o{ training_workout_plan_exercises : ""
    catalog_exercises ||--o{ training_workout_plan_exercises : ""
    auth_users ||--o{ training_scheduled_workouts : ""
    training_workout_plan_days |o--o{ training_scheduled_workouts : ""
    auth_users ||--o{ training_workout_sessions : ""
    training_scheduled_workouts |o--o| training_workout_sessions : "được thực hiện"
    training_workout_sessions ||--o{ training_session_exercises : ""
    catalog_exercises ||--o{ training_session_exercises : ""
    training_workout_plan_exercises |o--o{ training_session_exercises : "chỉ tiêu"
    training_session_exercises ||--o{ training_exercise_sets : ""
    training_exercise_sets ||--o{ training_set_rep_events : ""
    training_workout_sessions ||--o{ training_recovery_predictions : ""
    catalog_muscle_groups ||--o{ training_recovery_predictions : ""
    auth_users ||--o{ training_muscle_soreness_reports : ""
    catalog_muscle_groups ||--o{ training_muscle_soreness_reports : ""
```

## 6. `ai` — Phân tích tư thế & nhận diện thiết bị

```mermaid
erDiagram
    training_exercise_sets {
        bigint id PK
    }
    catalog_exercise_mistakes {
        integer id PK
        varchar code UK
    }
    catalog_equipment {
        integer id PK
    }
    media_media_files {
        uuid id PK
    }
    auth_users {
        uuid id PK
    }
    ai_pose_analyses {
        uuid id PK
        bigint set_id FK
        enum mode "realtime_edge/video_server"
        varchar model_name
        varchar model_version
        numeric overall_score
        numeric correct_form_pct
        smallint detected_rep_count
        uuid keypoints_media_id FK
    }
    ai_video_analysis_jobs {
        uuid id PK
        uuid pose_analysis_id FK, UK
        uuid source_video_media_id FK
        uuid result_video_media_id FK
        enum status "queued→processing→completed/failed"
        smallint attempt_count
        timestamptz notified_at
    }
    ai_posture_issues {
        bigint id PK
        uuid pose_analysis_id FK
        integer mistake_id FK
        smallint rep_no
        integer offset_ms
        enum severity
        numeric measured_angle_deg
    }
    ai_bar_path_points {
        uuid pose_analysis_id PK, FK
        integer frame_index PK
        numeric x_norm
        numeric y_norm
    }
    ai_equipment_scans {
        uuid id PK
        uuid user_id FK
        uuid image_media_id FK
        varchar model_version
        enum feedback
        integer corrected_equipment_id FK
    }
    ai_equipment_scan_predictions {
        uuid scan_id PK, FK
        integer equipment_id PK, FK
        numeric confidence "top-1 = max"
    }

    training_exercise_sets ||--o{ ai_pose_analyses : ""
    ai_pose_analyses ||--o| ai_video_analysis_jobs : "chế độ video"
    media_media_files ||--o{ ai_video_analysis_jobs : "video gốc/kết quả"
    ai_pose_analyses ||--o{ ai_posture_issues : ""
    catalog_exercise_mistakes ||--o{ ai_posture_issues : "mã lỗi"
    ai_pose_analyses ||--o{ ai_bar_path_points : ""
    media_media_files |o--o{ ai_pose_analyses : "keypoints"
    auth_users ||--o{ ai_equipment_scans : ""
    media_media_files |o--o{ ai_equipment_scans : "ảnh quét"
    ai_equipment_scans ||--o{ ai_equipment_scan_predictions : ""
    catalog_equipment ||--o{ ai_equipment_scan_predictions : ""
    catalog_equipment |o--o{ ai_equipment_scans : "nhãn sửa"
```

## 7. `media` & `analytics` — File, Progress Gallery, báo cáo

```mermaid
erDiagram
    auth_users {
        uuid id PK
    }
    body_body_measurements {
        uuid id PK
        timestamptz measured_at
    }
    media_media_files {
        uuid id PK
        uuid uploaded_by_user_id FK
        enum storage_provider
        varchar bucket UK "UQ(provider, bucket, key)"
        varchar object_key UK
        varchar mime_type
        bigint size_bytes
        char checksum_sha256
        enum status
    }
    media_progress_photos {
        uuid id PK
        uuid user_id FK
        uuid original_media_id FK, UK
        uuid watermarked_media_id FK
        uuid thumbnail_media_id FK
        enum angle "front/side/back"
        timestamptz taken_at
        enum processing_status
    }
    media_photo_comparisons {
        uuid id PK
        uuid before_photo_id FK
        uuid after_photo_id FK
        varchar title
    }
    analytics_report_exports {
        uuid id PK
        uuid user_id FK
        enum report_type UK "UQ(user, type, period_start)"
        date period_start UK
        uuid media_id FK
    }

    auth_users |o--o{ media_media_files : "tải lên"
    auth_users ||--o{ media_progress_photos : ""
    media_media_files ||--o| media_progress_photos : "gốc / watermark / thumbnail"
    media_progress_photos ||--o{ media_photo_comparisons : "before"
    media_progress_photos ||--o{ media_photo_comparisons : "after"
    body_body_measurements |o..o{ media_progress_photos : "lần đo gần nhất ≤ taken_at"
    auth_users ||--o{ analytics_report_exports : ""
    media_media_files ||--o{ analytics_report_exports : "ảnh báo cáo"
```
