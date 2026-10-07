# Thiết kế cơ sở dữ liệu — Smart Workout AI

| | |
|---|---|
| Hệ quản trị | **PostgreSQL 16** (nguồn dữ liệu duy nhất) |
| Quy mô | 7 schema nghiệp vụ + `util` · **51 bảng** · 15 view/materialized view · 4 hàm nghiệp vụ · 84 khoá ngoại |
| Chuẩn hoá | 3NF cho toàn bộ bảng, phần lớn đạt BCNF — xem [normalization.md](normalization.md) |
| Tài liệu liên quan | [erd.md](erd.md) · [data-dictionary.md](data-dictionary.md) (tự sinh) · [`database/postgresql/README.md`](../../database/postgresql/README.md) |

---

## 1. Phạm vi

Cơ sở dữ liệu phục vụ các chức năng trong *Mô tả dự án*, cộng module bảo mật tài khoản & phân quyền (RBAC):

| # | Chức năng | Schema chính |
|---|---|---|
| 1 | Exercise Wiki — thư viện, lọc đa điều kiện, bài thay thế | `catalog` |
| 2 | Workout Routine — giáo án, lịch tập, theo dõi phục hồi cơ (Heatmap) | `training` |
| 3 | Dashboard — chỉ số cơ thể (cân nặng, %mỡ, BMI/BMR/TDEE), calo tiêu hao, tiến độ tập, báo cáo tuần | `body`, `training`, `analytics` |
| 4 | Progress Gallery — ảnh tiến độ, watermark tự động, so sánh Before/After | `media` |
| 5 | Posture Correction — realtime (1A) & phân tích video (1B) | `ai` |
| 6 | Đếm Set/Rep & đo Tempo | `training` (`set_rep_events`) |
| 7 | Nhận diện thiết bị & gợi ý bài tập | `ai`, `catalog` |
| + | Tài khoản, RBAC, OAuth, thiết bị, refresh token, nhật ký đăng nhập | `auth` |

**Ngoài phạm vi:** dinh dưỡng / kiểm soát ăn uống (Food control, Calo/Macro nạp vào) đã được loại khỏi dự án.

## 2. Kiến trúc lưu trữ

```
Mobile App ──▶ Core Backend (FastAPI) ──▶ PostgreSQL 16  (nguồn dữ liệu duy nhất, 3NF)
                     │        │     └───▶ Redis          (cache "hôm nay", rate-limit, hàng đợi job)
                     │        └─────────▶ Object Storage (S3/Firebase: ảnh, GIF, video, keypoint)
                     └──▶ AI Services ──▶ ghi kết quả về PostgreSQL qua backend/worker
```

- **PostgreSQL** lưu mọi dữ liệu có cấu trúc. Dữ liệu AI khối lượng lớn (keypoint từng frame) lưu thành file trên Object Storage, DB chỉ giữ tham chiếu `media_files`.
- **Redis** không phải nguồn dữ liệu chính; mất Redis không mất dữ liệu.
- **Object Storage**: DB không lưu URL mà lưu `(provider, bucket, object_key)`. Ứng dụng sinh URL/presigned URL khi cần.

## 3. Tổ chức schema

| Schema | Số bảng | Nội dung |
|---|---|---|
| `auth` | 11 | users, user_profiles, roles, permissions, role_permissions, user_roles, oauth_accounts, user_devices, refresh_tokens, verification_tokens, login_attempts |
| `media` | 3 | media_files, progress_photos, photo_comparisons |
| `catalog` | 13 | difficulty_levels, body_regions, muscle_groups, equipment_categories, equipment, equipment_aliases, exercises, exercise_muscles, exercise_equipment, exercise_instructions, exercise_mistakes, exercise_media, exercise_alternatives |
| `body` | 7 | activity_levels, fitness_goal_types, body_sites, user_body_profiles, body_measurements, body_circumferences, user_goals |
| `training` | 10 | workout_plans, workout_plan_days, workout_plan_exercises, scheduled_workouts, workout_sessions, session_exercises, exercise_sets, set_rep_events, recovery_predictions, muscle_soreness_reports |
| `ai` | 6 | pose_analyses, video_analysis_jobs, posture_issues, bar_path_points, equipment_scans, equipment_scan_predictions |
| `analytics` | 1 (+ MV) | report_exports, mv_daily_user_summary |
| `util` | — | `set_updated_at()`, `immutable_unaccent()`, `search_norm()`, kiểu `job_status` |

Tách schema theo *bounded context* giúp phân quyền theo nhóm dữ liệu (vd: BI không được đọc `auth` bí mật) và dễ tách microservice về sau.

## 4. Quy ước thiết kế

| Hạng mục | Quy ước |
|---|---|
| Tên | `snake_case`, tên bảng số nhiều, tiếng Anh; mô tả tiếng Việt bằng `COMMENT ON` cho **mọi** bảng và cột |
| Constraint / index | `pk_<bảng>`, `fk_<bảng>_<tham chiếu>`, `uq_<bảng>_<cột>`, `ck_<bảng>_<quy tắc>`, `ix_<bảng>_<cột>`, `brin_<bảng>_<cột>` (khớp `naming_convention` của SQLAlchemy) |
| Khoá chính | Bảng tra cứu/danh mục: `smallint`/`integer GENERATED ALWAYS AS IDENTITY` + khoá tự nhiên `code UNIQUE`. Thực thể của người dùng: `uuid DEFAULT gen_random_uuid()` (không lộ số lượng, sinh được phía client). Bảng con nhiều dòng: `bigint IDENTITY` hoặc khoá kép |
| Thời gian | Luôn `timestamptz`, DB đặt `timezone = UTC`. Chia ngày theo `user_profiles.timezone` (mặc định `Asia/Ho_Chi_Minh`) |
| Đơn vị | SI: kg, cm, g, ms, độ, kcal. Quy đổi imperial ở tầng ứng dụng (`user_profiles.unit_system`) |
| Cột kiểm toán | `created_at`, `updated_at` (trigger `trg_set_updated_at` tự gắn cho mọi bảng có cột này); nội dung biên tập có thêm `created_by`, `updated_by` |
| Xoá mềm | `deleted_at` trên thực thể chính (users, exercises, equipment, plans, sessions, photos, media). Unique index loại trừ bản ghi đã xoá |
| Giá trị liệt kê | `ENUM` cho trạng thái kỹ thuật ổn định; **bảng tra cứu** cho dữ liệu nghiệp vụ có thuộc tính (vd: `activity_levels.multiplier`, `difficulty_levels.rank`) |
| Thứ tự trong danh sách | `UNIQUE (cha, order_no) DEFERRABLE INITIALLY DEFERRED` để đổi thứ tự trong một transaction |

## 5. Toàn vẹn dữ liệu

- **CHECK miền giá trị:** cân nặng 20–400 kg, %mỡ 2–70, chiều cao 80–250 cm, RPE 1–10 bước 0.5, điểm 0–100, confidence 0–1, `ended_at ≥ started_at`, định dạng email/SĐT/slug/mã, hash SHA-256 hex...
- **CHECK trạng thái nhất quán:** job `completed` phải có video kết quả; job `failed` phải có lỗi; buổi tập `in_progress` ⇔ `ended_at IS NULL`; token bị thu hồi phải có lý do; báo cáo tuần bắt đầu thứ Hai.
- **Unique có điều kiện:** email/SĐT duy nhất trong tài khoản chưa xoá; tối đa 1 mục tiêu `active` mỗi user; tối đa 1 buổi tập `in_progress` mỗi user; 1 media chính cho mỗi vai trò của bài tập; nhãn AI ánh xạ tới đúng 1 thiết bị; push token duy nhất trong các thiết bị còn hiệu lực.
- **Khoá ngoại kép:** `workout_sessions (scheduled_workout_id, user_id) → scheduled_workouts (id, user_id)` để lịch tập luôn thuộc đúng user.
- **Trigger nghiệp vụ:**

  | Trigger | Quy tắc |
  |---|---|
  | `trg_scheduled_workouts_plan_access` | Chỉ xếp lịch từ giáo án của chính mình hoặc giáo án mẫu |
  | `trg_video_analysis_jobs_mode` | Job video chỉ gắn với phân tích chế độ `video_server` |
  | `trg_posture_issues_exercise_match` | Mã lỗi tư thế phải thuộc đúng bài tập của hiệp được phân tích |
  | `trg_photo_comparisons_owner` | Hai ảnh so sánh phải cùng một chủ |

- **Chính sách `ON DELETE`:**

  | Loại quan hệ | Hành vi |
  |---|---|
  | Dữ liệu thuộc user (sessions, measurements, photos, scans, goals...) | `CASCADE`: xoá cứng tài khoản (quyền được quên – GDPR) dọn sạch dữ liệu cá nhân |
  | Tham chiếu danh mục (exercise, equipment, muscle group, lookup) | `RESTRICT`: bài tập đã có lịch sử chỉ được archive/xoá mềm |
  | Tham chiếu tuỳ chọn (avatar, ảnh minh hoạ, người cấp quyền, video kết quả) | `SET NULL` |
  | Nhật ký bảo mật (`login_attempts.user_id`) | `SET NULL`: giữ log khi xoá user |

## 6. Bảo mật

### 6.1 RBAC ở tầng ứng dụng

`users ⟷ user_roles ⟷ roles ⟷ role_permissions ⟷ permissions(resource, action)`

| Vai trò | Quyền tiêu biểu |
|---|---|
| `admin` | Toàn bộ quyền (quản lý user, gán vai trò, giám sát job AI, báo cáo hệ thống) |
| `content_editor` | `exercise:*`, `equipment:manage`, `muscle_group:manage`, `plan_template:manage`, `media:upload` |
| `user` | `*:read` nội dung, `workout/body_metric/progress_photo:manage_own`, `report:export_own`, `ai:use` |

Backend kiểm tra quyền bằng một truy vấn duy nhất: `user_roles` (còn hạn) → `role_permissions` → `permissions`. Kết quả nên được cache trong Redis theo `user_id`.

### 6.2 Xác thực

- Mật khẩu: chỉ lưu `password_hash` (bcrypt/argon2, dùng `passlib`). Tài khoản chỉ đăng nhập OAuth có `password_hash = NULL`.
- **Refresh token xoay vòng:** chỉ lưu SHA-256 của token. Mỗi lần refresh sinh token con (`parent_token_id`, cùng `family_id`). Nếu token cũ bị dùng lại thì thu hồi cả family (`revoke_reason = 'reuse_detected'`). Token gắn với `user_devices`, nên đăng xuất từ xa = thu hồi thiết bị.
- Token xác thực email / đặt lại mật khẩu: dùng một lần, có hạn, chỉ lưu hash.
- **Chống brute-force:** đếm lần sai gần đây trong `login_attempts` theo `user_id`, email, IP (đều có index), rồi đặt `users.locked_until`.

### 6.3 Phân quyền ở tầng database

| Role (NOLOGIN) | Quyền |
|---|---|
| `sw_app_rw` | DML trên mọi schema nghiệp vụ, EXECUTE hàm; được gọi `analytics.refresh_materialized_views()` (SECURITY DEFINER) |
| `sw_readonly` | SELECT dữ liệu nghiệp vụ & view cho BI. **Không** đọc được `users.password_hash`, `refresh_tokens`, `verification_tokens`, `oauth_accounts`, `user_devices`, `login_attempts` |

Tài khoản đăng nhập thật do DevOps tạo và gán vào nhóm (`CREATE ROLE sw_backend LOGIN ... IN ROLE sw_app_rw`). Backend **không** nên dùng tài khoản owner/superuser khi chạy production.

## 7. Index & hiệu năng

| Nhu cầu truy vấn | Index |
|---|---|
| Mọi khoá ngoại (JOIN, xoá cascade) | Index trên mọi cột FK (PostgreSQL không tự tạo); kiểm tra tự động trong `verify_schema.sql` |
| Chuỗi thời gian theo user | `(user_id, measured_at)`, `(user_id, started_at DESC)`, `(user_id, taken_at DESC)`, `(user_id, scanned_at DESC)`, `(user_id, scheduled_date)` |
| Tìm kiếm tiếng Việt không dấu ("lung xo" → "Lưng xô") | GIN `pg_trgm` trên `util.search_norm(name)` cho bài tập, nhóm cơ, thiết bị, alias |
| Lọc bài tập đã xuất bản theo độ khó | Partial index `ix_exercises_published (difficulty_level_id, name) WHERE status='published'` |
| Hàng đợi job video | Partial index `(priority DESC, queued_at) WHERE status='queued'`, worker lấy job bằng `FOR UPDATE SKIP LOCKED` |
| Dọn token hết hạn, upload treo | Partial index trên `expires_at` / `created_at` |
| Log đăng nhập lớn, chỉ ghi thêm | BRIN trên `attempted_at` |
| Dashboard theo tháng/3 tháng | Materialized view `analytics.mv_daily_user_summary` + unique index để `REFRESH ... CONCURRENTLY` |

**Mở rộng khi dữ liệu lớn:** partition theo thời gian (RANGE theo tháng) cho `set_rep_events`, `posture_issues`, `bar_path_points`, `login_attempts`; read replica cho BI; đồng bộ CDC (dựa trên `updated_at`/`deleted_at`) sang BigQuery để phân tích OLAP như mô tả dự án.

## 8. Luồng dữ liệu theo chức năng

### Chức năng 1 — Exercise Wiki

| Bước | Dữ liệu |
|---|---|
| Tìm kiếm, lọc nhóm cơ chính/phụ, thiết bị sẵn có, độ khó | `catalog.fn_search_exercises(keyword, muscle_ids, primary_only, available_equipment_ids, max_rank)`, kết quả sắp xếp theo `difficulty_levels.rank` |
| Xem chi tiết | `exercises` + `exercise_media` (GIF/video) + `exercise_instructions` + `exercise_mistakes` |
| Bài thay thế khi máy bận | `catalog.fn_suggest_alternatives(exercise_id, unavailable_equipment_ids)` |
| Thêm vào buổi tập | INSERT `training.session_exercises` (`added_via = 'wiki'`) vào buổi `in_progress` (tối đa 1 buổi mỗi user) |

### Chức năng 2 — Workout Routine & phục hồi

| Bước | Dữ liệu |
|---|---|
| Heatmap phục hồi | `training.v_muscle_recovery_status` (ready / recovering / fatigued theo % thời gian nghỉ) |
| Ghi nhận buổi tập, Volume | `workout_sessions` → `session_exercises` → `exercise_sets`; volume tính ở `v_set_metrics` / `v_session_summary` |
| AI dự đoán phục hồi | Đầu vào `v_session_muscle_load` (+ lịch sử, `muscle_soreness_reports`) → đầu ra `recovery_predictions` |
| Cảnh báo khi xếp lịch nhóm cơ chưa hồi phục | App đối chiếu buổi trong `scheduled_workouts` với Heatmap; user vẫn xác nhận thì ghi `recovery_warning_ack_at` |
| Báo cáo phục hồi dài hạn | Lịch sử `recovery_predictions` ⨝ `workout_sessions` |

### Chức năng 3 — Dashboard

| Bước | Dữ liệu |
|---|---|
| Tổng quan ngày: calo tiêu hao, tiến độ tuần | `v_session_summary.est_calories_kcal`, `v_weekly_adherence`, cache Redis cho "hôm nay" |
| Cập nhật cân nặng/%mỡ → BMI, BMR, TDEE | INSERT `body_measurements` (+ `body_circumferences`); đọc `body.v_body_metrics` |
| Biểu đồ Tháng / 3 Tháng, cảnh báo chững cân | `analytics.mv_daily_user_summary`, `body.v_weekly_weight_trend.is_plateau` |
| Xuất báo cáo tuần | Sinh ảnh → `media_files` → `analytics.report_exports` |

### Chức năng 4 — Progress Gallery

| Bước | Dữ liệu |
|---|---|
| Upload / chụp ảnh, gán góc chụp | `media_files` (pending_upload → available) + `progress_photos (angle, capture_source, taken_at)` |
| Watermark tự động | Worker đọc `media.v_progress_photo_cards` (cân nặng/%mỡ tại thời điểm chụp), ghi `watermarked_media_id`, `thumbnail_media_id`, `processing_status` |
| Lưới ảnh & so sánh | `v_progress_photo_cards` theo `taken_at`; lưu cặp vào `photo_comparisons` |

### Chức năng 5 — Posture Correction

| Chế độ | Dữ liệu |
|---|---|
| 1A Realtime (MediaPipe trên máy) | Kết thúc hiệp → `pose_analyses (mode='realtime_edge', correct_form_pct)` + `posture_issues` (mã lỗi từ `exercise_mistakes`) |
| 1B Video (YOLOv8-Pose trên server) | Upload → `media_files` → `pose_analyses (mode='video_server')` + `video_analysis_jobs (queued)` → worker `processing → completed` + video kết quả + `posture_issues` + `bar_path_points` → push qua `user_devices.push_token`, ghi `notified_at` |

### Chức năng 6 — Đếm Set/Rep & Tempo

FSM trên thiết bị ghi từng rep vào `training.set_rep_events` (thời lượng 4 pha, góc khớp). Khi kết thúc hiệp, app tạo `exercise_sets (source='ai_realtime', reps, weight_kg)`. Tempo trung bình và TUT lấy từ `training.v_set_tempo`.

### Chức năng 7 — Nhận diện thiết bị

YOLOv8 trả nhãn lớp → `catalog.equipment_aliases (alias_type='ai_label')` → thiết bị. Lưu `ai.equipment_scans` + `equipment_scan_predictions`. Gợi ý bài qua `catalog.fn_exercises_for_ai_label(label)`; thêm vào buổi tập với `added_via = 'equipment_scan'`. Phản hồi đúng/sai và nhãn sửa (`corrected_equipment_id`) dùng để fine-tune model.

## 9. Vòng đời dữ liệu

| Dữ liệu | Chính sách đề xuất |
|---|---|
| Tài khoản bị xoá | Xoá mềm (`deleted_at`) ngay; job xoá cứng sau 30 ngày (CASCADE dữ liệu cá nhân) và xoá object trên storage |
| `refresh_tokens`, `verification_tokens` hết hạn | Job dọn hằng ngày (index trên `expires_at`) |
| `login_attempts` | Giữ 180 ngày |
| `media_files` ở trạng thái `pending_upload` quá 24h hoặc không còn được tham chiếu | Job dọn dẹp xoá object và bản ghi |
| Ảnh quét thiết bị | Có thể không lưu (`image_media_id = NULL`) để bảo vệ quyền riêng tư |
| `analytics.mv_daily_user_summary` | Làm mới mỗi 15–60 phút bằng `SELECT analytics.refresh_materialized_views();` |

## 10. Triển khai & bước tiếp theo

- Khởi tạo: xem [`database/postgresql/README.md`](../../database/postgresql/README.md). Docker tự chạy `init.sh` khi volume trống.
- **SQLAlchemy/Alembic (bước sau):** viết model khớp lược đồ này (dùng `__table_args__ = {"schema": ...}`, `MetaData(naming_convention=...)`), tạo migration baseline chạy các file SQL hoặc `alembic stamp head` trên DB đã khởi tạo. Từ đó mọi thay đổi lược đồ đi qua Alembic.
- Sinh lại từ điển dữ liệu sau mỗi thay đổi: `tools/data_dictionary.sql`.
