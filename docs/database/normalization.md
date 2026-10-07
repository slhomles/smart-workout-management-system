# Phân tích chuẩn hoá (1NF → 3NF / BCNF) — Smart Workout AI

Tài liệu này chứng minh lược đồ PostgreSQL của dự án đạt **3NF cho toàn bộ 51 bảng**, và hầu hết đạt **BCNF**. Các trường hợp còn lại là quyết định thiết kế có chủ đích, được liệt kê ở mục 6 kèm cơ chế giữ toàn vẹn dữ liệu.

- Lược đồ: [`database/postgresql/schemas/`](../../database/postgresql/schemas/)
- Sơ đồ ERD: [erd.md](erd.md) · Từ điển dữ liệu: [data-dictionary.md](data-dictionary.md)
- Kiểm chứng tự động: [`database/postgresql/tools/verify_schema.sql`](../../database/postgresql/tools/verify_schema.sql)

---

## 1. Nhắc lại định nghĩa

| Dạng chuẩn | Điều kiện | Câu hỏi kiểm tra trên mỗi bảng |
|---|---|---|
| **1NF** | Mọi thuộc tính mang giá trị nguyên tử; không có nhóm lặp; mỗi bảng có khoá chính. | Có cột nào chứa danh sách, chuỗi ghép, JSON hay nhóm cột lặp (`x1, x2, x3`) không? |
| **2NF** | 1NF và mọi thuộc tính không khoá phụ thuộc **đầy đủ** vào khoá chính (không phụ thuộc một phần khoá). | Với khoá kép, có cột nào chỉ phụ thuộc vào một phần của khoá không? |
| **3NF** | 2NF và không có **phụ thuộc bắc cầu**: thuộc tính không khoá không phụ thuộc vào thuộc tính không khoá khác. | Có cột nào suy ra được từ một cột không khoá khác (kể cả qua bảng khác) không? |
| **BCNF** | Mọi phụ thuộc hàm X → Y không tầm thường đều có X là siêu khoá. | Có định thuộc (determinant) nào không phải khoá ứng viên không? |

Ngoài ra, thiết kế áp dụng nguyên tắc **"không lưu giá trị dẫn xuất"**: những gì tính được từ dữ liệu khác thì tính bằng view hoặc hàm (mục 5). Nhờ vậy không có bất thường khi cập nhật (update anomaly).

---

## 2. 1NF — giá trị nguyên tử, không nhóm lặp

Mọi bảng đều có khoá chính (kiểm tra số 2 trong `verify_schema.sql`). Không có cột kiểu mảng, `json` hay `jsonb` (kiểm tra số 10). Những chỗ dễ vi phạm 1NF trong bài toán này đã được xử lý như sau:

| Cách làm "ngây thơ" (vi phạm 1NF) | Cách xử lý trong lược đồ |
|---|---|
| `exercises.muscles = 'Ngực, Tay sau, Vai trước'` | Bảng `catalog.exercise_muscles(exercise_id, muscle_group_id, role, activation_ratio)` |
| `exercises.equipment = 'Tạ đòn, Ghế phẳng'` | Bảng `catalog.exercise_equipment(exercise_id, equipment_id, is_optional)` |
| `exercises.instructions = '1. ... 2. ... 3. ...'` | Bảng `catalog.exercise_instructions(exercise_id, step_no, content)` |
| `exercises.common_mistakes` (đoạn văn dài) | Bảng `catalog.exercise_mistakes` với `code` duy nhất, dùng chung cho AI |
| `equipment.synonyms = 'tạ tay; dumbbell'` | Bảng `catalog.equipment_aliases(alias, alias_type)` |
| `plan_exercises.tempo = '3-1-1-0'` | 4 cột nguyên tử `tempo_eccentric_s`, `tempo_pause_bottom_s`, `tempo_concentric_s`, `tempo_pause_top_s` (+ CHECK "đủ cả 4 hoặc không cột nào") |
| `body_measurements.waist_cm, chest_cm, hip_cm, arm_cm, ...` (nhóm cột lặp, thưa) | Bảng `body.body_circumferences(measurement_id, body_site_id, value_cm)` + tra cứu `body.body_sites` |
| `pose_analyses.keypoints = '[[x,y,z,v], ...]'` (JSON hàng nghìn frame) | Lưu thành file trên Object Storage, DB chỉ giữ `keypoints_media_id` |
| `pose_analyses.bar_path = '[(x,y), ...]'` | Bảng `ai.bar_path_points(pose_analysis_id, frame_index, offset_ms, x_norm, y_norm)` |
| `equipment_scans.top_k = '[{label, conf}, ...]'` | Bảng `ai.equipment_scan_predictions(scan_id, equipment_id, confidence)` |
| `set.rep_tempos = '2.9,3.0,3.1,...'` | Bảng `training.set_rep_events(set_id, rep_no, eccentric_ms, ...)` |

---

## 3. 2NF — không phụ thuộc một phần khoá

2NF chỉ cần xét ở các bảng có **khoá chính kép**. Với từng bảng, mọi thuộc tính không khoá đều cần **toàn bộ** khoá mới xác định được:

| Bảng (khoá chính) | Thuộc tính không khoá | Vì sao phụ thuộc đầy đủ |
|---|---|---|
| `catalog.exercise_muscles (exercise_id, muscle_group_id)` | `role`, `activation_ratio` | Cùng nhóm cơ Tay sau là *secondary 0.5* trong Bench Press nhưng *primary 1.0* trong Pushdown. |
| `catalog.exercise_equipment (exercise_id, equipment_id)` | `is_optional` | Tạ đơn bắt buộc với Dumbbell Row nhưng tuỳ chọn với Calf Raise. |
| `catalog.exercise_instructions (exercise_id, step_no)` | `content` | Nội dung là bước *thứ n* của *bài x*. |
| `catalog.exercise_media (exercise_id, media_id)` | `media_role`, `is_primary`, `display_order`, `caption` | Một file có thể dùng cho nhiều bài với vai trò khác nhau. |
| `catalog.exercise_alternatives (exercise_id, alternative_exercise_id)` | `note` | Lý do thay thế gắn với cặp bài. |
| `auth.role_permissions (role_id, permission_id)` | `created_at` | Thời điểm gán quyền gắn với cặp. |
| `auth.user_roles (user_id, role_id)` | `granted_by`, `granted_at`, `expires_at` | Mỗi lần cấp một vai trò cho một người. |
| `body.body_circumferences (measurement_id, body_site_id)` | `value_cm` | Số đo của vị trí *s* trong lần đo *m*. |
| `training.set_rep_events (set_id, rep_no)` | thời lượng 4 pha, góc min/max, `is_full_rom` | Dữ liệu của rep thứ *n* trong hiệp *s*. |
| `training.recovery_predictions (session_id, muscle_group_id, model_version)` | `fatigue_score`, `recovered_at`, `predicted_at` | Kết quả của một model cho một nhóm cơ sau một buổi. |
| `ai.bar_path_points (pose_analysis_id, frame_index)` | `offset_ms`, `x_norm`, `y_norm` | `offset_ms` không suy ra được chỉ từ `frame_index` vì FPS mỗi video khác nhau. |
| `ai.equipment_scan_predictions (scan_id, equipment_id)` | `confidence` | Độ tin cậy của thiết bị *e* trong lần quét *s*. |

**Ví dụ vi phạm đã tránh:** nếu `exercise_muscles` có thêm cột `muscle_name` thì `muscle_name` chỉ phụ thuộc `muscle_group_id`, tức một phần của khoá, và vi phạm 2NF. Lược đồ chỉ lưu khoá ngoại, còn tên lấy bằng phép nối (join).

---

## 4. 3NF — loại bỏ phụ thuộc bắc cầu

Đây là phần quan trọng nhất. Bảng dưới liệt kê mọi phụ thuộc bắc cầu tiềm ẩn đã phát hiện khi thiết kế, cùng cách loại bỏ:

| Bảng | Phụ thuộc bắc cầu tiềm ẩn | Quyết định |
|---|---|---|
| `auth.refresh_tokens` | `device_id → user_devices.user_id` | **Không lưu `user_id`**. User suy ra qua thiết bị. |
| `auth.permissions` | `(resource, action) → code 'resource:action'` | **Không lưu `code`**. Chuỗi được ghép ở tầng ứng dụng. |
| `auth.users` | `failed_login_count`, `last_login_at` suy ra từ `login_attempts` | **Không lưu**. Truy vấn `login_attempts` (có index `(user_id, attempted_at DESC)`). |
| `catalog.muscle_groups` | `parent_id → parent.body_region_id` | `body_region_id` **chỉ đặt ở nút gốc**. CHECK `ck_muscle_groups_region_on_root` bắt buộc `(parent_id IS NULL) = (body_region_id IS NOT NULL)`. |
| `media.media_files` | URL = f(provider, bucket, object_key, CDN); loại media = f(mime_type) | **Không lưu URL / loại**. |
| `media.progress_photos` | Nếu có FK `body_measurement_id`: `body_measurement_id → user_id` (trùng `progress_photos.user_id`) | **Không FK tới lần đo**. Cân nặng/%mỡ = lần đo gần nhất `≤ taken_at`, tính trong `media.v_progress_photo_cards` (LATERAL JOIN). |
| `media.photo_comparisons` | `before_photo_id → progress_photos.user_id` | **Không lưu `user_id`**. Trigger `fn_check_photo_comparison_owner` bảo đảm hai ảnh cùng chủ. |
| `training.recovery_predictions` | `session_id → workout_sessions.user_id` | **Không lưu `user_id`**. |
| `training.workout_plans` | `days_per_week = count(workout_plan_days)` | **Không lưu**. |
| `training.workout_sessions` | `duration = ended_at − started_at` | **Không lưu**. Tính trong `v_session_summary`. |
| `training.exercise_sets` | `volume = reps × weight_kg`; `RIR ≈ 10 − RPE` | **Không lưu volume, không lưu RIR**. |
| `ai.pose_analyses` | `set_id → session → user_id`, `set_id → session_exercise → exercise_id` | **Không lưu `user_id`, `exercise_id`**. Lấy qua `ai.v_pose_analysis_details`. |
| `ai.posture_issues` | `pose_analysis_id → … → exercise_id` | **Không lưu `exercise_id`**. Trigger `fn_check_posture_issue_exercise` kiểm tra mã lỗi thuộc đúng bài. |
| `ai.equipment_scans` / `…_predictions` | `rank` và `top-1` suy ra từ thứ tự `confidence` | **Không lưu `rank` / `predicted_equipment_id`**. Lấy qua `ai.v_equipment_scan_results`. |
| `analytics.report_exports` | `(report_type, period_start) → period_end` | **Không lưu `period_end`**. CHECK bắt buộc tuần bắt đầu thứ Hai, tháng bắt đầu ngày 1. |
| `body.body_measurements` | BMI = f(weight, height); BMR/TDEE = f(weight, height, age, gender, activity) | **Không lưu**. Tính trong `body.v_body_metrics`. |
| `body.user_body_profiles` | `age = f(date_of_birth, ngày đo)` | **Chỉ lưu ngày sinh**. |
| `catalog.exercises` | Tên độ khó, tên nhóm cơ… | Chỉ lưu FK (`difficulty_level_id`). Mô tả nằm ở bảng tra cứu. |

---

## 5. BCNF

Mọi bảng tra cứu dùng **khoá thay thế** (`id` IDENTITY) kèm **khoá tự nhiên** `code UNIQUE`. Cả hai đều là khoá ứng viên nên các phụ thuộc `id → *` và `code → *` đều có định thuộc là siêu khoá, tức đạt BCNF. Một số bảng có nhiều khoá ứng viên:

| Bảng | Các khoá ứng viên |
|---|---|
| `catalog.difficulty_levels` | `id`, `code`, `rank` |
| `catalog.exercises` | `id`, `slug` |
| `catalog.exercise_mistakes` | `id`, `code` |
| `catalog.muscle_groups` | `id`, `code`, `heatmap_region_key` (khi khác NULL) |
| `media.media_files` | `id`, `(storage_provider, bucket, object_key)` |
| `auth.permissions` | `id`, `(resource, action)` |
| `auth.oauth_accounts` | `id`, `(provider, provider_subject)`, `(user_id, provider)` |
| `body.body_measurements` | `id`, `(user_id, measured_at)` |
| `training.workout_plan_days` | `id`, `(plan_id, day_no)` |
| `training.exercise_sets` | `id`, `(session_exercise_id, set_no)` |

`catalog.equipment_aliases` có phụ thuộc `alias → equipment_id` **chỉ trên tập con** `alias_type = 'ai_label'`. Phụ thuộc này được hiện thực hoá bằng unique index có điều kiện `uq_equipment_aliases_ai_label`, nên trong tập con đó `alias` là khoá.

---

## 6. Quyết định có chủ đích (được kiểm soát toàn vẹn)

Những điểm sau trông như dư thừa nhưng thực chất không phải phụ thuộc hàm, hoặc là phi chuẩn hoá có kiểm soát:

| # | Điểm cần lưu ý | Giải thích & cơ chế bảo đảm |
|---|---|---|
| 1 | `training.workout_sessions` có cả `user_id` và `scheduled_workout_id` | Buổi tập **ngoài lịch** (`scheduled_workout_id IS NULL`) vẫn cần `user_id`, nên không bỏ cột này được. Khi có lịch, **FK kép** `(scheduled_workout_id, user_id) → scheduled_workouts(id, user_id)` bảo đảm hai giá trị luôn khớp. Xoá lịch dùng `ON DELETE SET NULL (scheduled_workout_id)` của PostgreSQL 15+, chỉ NULL một cột. |
| 2 | `training.scheduled_workouts` có `user_id` và `plan_day_id` | Không có phụ thuộc `plan_day_id → user_id`, vì buổi trong **giáo án mẫu** (`owner_user_id IS NULL`) được nhiều user dùng chung. Trigger `fn_check_schedule_plan_access` chặn việc dùng giáo án của người khác. |
| 3 | `training.session_exercises` có `exercise_id` và `plan_exercise_id` | Không có phụ thuộc hàm: user có thể **đổi sang bài thay thế** (kê Bench Press nhưng tập Dumbbell Press). `exercise_id` là bài thực tế, `plan_exercise_id` là chỉ tiêu được đáp ứng. |
| 4 | `training.exercise_sets.reps` và số dòng `set_rep_events` | Đây là hai sự kiện khác nhau: `reps` là số **user xác nhận** (có thể sửa khi AI đếm sai), còn `set_rep_events` là **quan sát thô** của AI. Sai lệch giữa hai nguồn chính là dữ liệu để cải thiện model. |
| 5 | `media.media_files.uploaded_by_user_id` và chủ sở hữu ở bảng nghiệp vụ | Khác ngữ nghĩa: *người tải file* (phục vụ kiểm toán, phân quyền gắn file) khác *chủ dữ liệu*. File do hệ thống sinh (ảnh watermark, video kết quả) có `uploaded_by_user_id = NULL`. |
| 6 | Điểm AI (`overall_score`, `correct_form_pct`, `fatigue_score`) được lưu | Đây là **kết quả của model tại thời điểm chạy**, không tái tạo được từ dữ liệu khác (model đổi version), nên là dữ kiện gốc chứ không phải giá trị dẫn xuất. |
| 7 | `body.v_body_metrics` dùng chiều cao và mức vận động **hiện tại** | Hạn chế được chấp nhận vì người trưởng thành ít đổi chiều cao. Nếu cần BMR lịch sử chính xác tuyệt đối, có thể tách thêm bảng lịch sử hồ sơ. |
| 8 | `analytics.mv_daily_user_summary` | **Phi chuẩn hoá có kiểm soát ở tầng đọc** (materialized view). Nguồn dữ liệu gốc vẫn là các bảng 3NF; MV được làm mới định kỳ bằng `analytics.refresh_materialized_views()` (dùng CONCURRENTLY nên không khoá đọc). |
| 9 | Chuỗi ghép trong `catalog.v_exercise_cards` | Chỉ có ở **view hiển thị**, không lưu trong bảng. |

---

## 7. Bảng tổng hợp giá trị dẫn xuất

| Giá trị | Công thức | Nơi tính |
|---|---|---|
| Tuổi | `age(ngày đo, date_of_birth)` | `body.v_body_metrics` |
| BMI (+ phân loại châu Á) | `kg / m²`; < 18.5 / < 23 / < 25 / ≥ 25 | `body.v_body_metrics` |
| Khối nạc (LBM) | `kg × (1 − %mỡ/100)` | `body.v_body_metrics` |
| BMR | Mifflin-St Jeor `10·kg + 6.25·cm − 5·tuổi + s` (s = +5 / −161 / −78); Katch-McArdle `370 + 21.6·LBM` | `body.v_body_metrics` |
| TDEE | `BMR × activity_levels.multiplier` | `body.v_body_metrics` |
| Xu hướng cân nặng & chững cân | TB tuần, chênh lệch tuần, 3 tuần liên tiếp thay đổi < 0.2 kg | `body.v_weekly_weight_trend` |
| Volume hiệp | `reps × weight_kg` | `training.v_set_metrics` |
| 1RM ước tính | Epley `kg × (1 + reps/30)` | `training.v_set_metrics` |
| Thời lượng / tổng volume / calo tiêu hao buổi tập | `ended − started`; Σ volume (không tính khởi động); `MET × kg × giờ` | `training.v_session_summary` |
| Tải theo nhóm cơ | Σ `reps × kg × activation_ratio` | `training.v_session_muscle_load` |
| Tempo TB, TUT, % đủ biên độ | AVG/SUM trên `set_rep_events` | `training.v_set_tempo` |
| Trạng thái phục hồi (Heatmap) | `% = (now − trained_at) / (recovered_at − trained_at)` → fatigued / recovering / ready | `training.v_muscle_recovery_status` |
| % tuân thủ lịch | buổi hoàn thành / buổi dự kiến (không tính buổi huỷ) | `training.v_weekly_adherence` |
| Kết quả nhận diện top-1 | `max(confidence)` | `ai.v_equipment_scan_results` |
| Số đo in trên ảnh tiến độ | lần đo gần nhất `≤ taken_at` | `media.v_progress_photo_cards` |
| Bài tập thay thế | độ trùng nhóm cơ chính + ưu tiên bài biên tập viên chọn − thiết bị đang bận | `catalog.fn_suggest_alternatives()` |

---

## 8. Kiểm chứng tự động

`database/postgresql/tools/verify_schema.sql` kiểm tra các điều kiện sau trên database thật; mọi mục vi phạm phải trả về 0 dòng:

1. Số bảng theo schema (tổng 51)
2. Bảng không có khoá chính
3. Khoá ngoại không có index hỗ trợ
4. Bảng/view thiếu `COMMENT`
5. Cột thiếu `COMMENT`
6. Constraint sai quy ước tên (`pk_/fk_/uq_/ck_`)
7. Index sai quy ước tên (`pk_/uq_/ix_/brin_`)
8. Bảng có `updated_at` mà thiếu trigger cập nhật
9. Cột `timestamp` không có múi giờ
10. Cột kiểu mảng / `json` (vi phạm 1NF)
