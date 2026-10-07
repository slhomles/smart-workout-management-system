# Bộ dữ liệu test — Smart Workout AI

Tài liệu tra cứu cho người viết test backend (API, integration test, Postman). Dữ liệu nằm trong [`database/postgresql/seeds/`](../../database/postgresql/seeds/) và được nạp tự động khi khởi tạo database.

| | |
|---|---|
| Bật/tắt | `SW_SEED_TEST` trong `docker-compose.yml` (mặc định `"true"`). `"false"` = chỉ nạp master data `seeds/0*.sql` |
| Mật khẩu chung | `Demo@123` (bcrypt, tương thích `passlib[bcrypt]`) |
| UUID persona | `5eed0000-0000-4000-8000-0000000000NN` (NN = số thứ tự persona, 2 chữ số) |
| UUID giáo án mẫu | `5eed1000-0000-4000-8000-0000000000NN` |
| Thời gian | **Tương đối** theo thời điểm khởi tạo DB (buổi tập "hôm qua", số đo "6 tuần trước"...). Muốn dữ liệu "mới" lại thì khởi tạo lại DB |
| Ngẫu nhiên | Phần sinh tự động (power@) dùng `setseed()` cố định, nên cùng ngày init sẽ cho cùng kết quả |
| Kiểm chứng | `database/postgresql/tools/verify_seed.sql`: không được có dòng `FAIL` |

> **Không có dữ liệu AI.** Các bảng `ai.*`, `training.recovery_predictions`, `training.set_rep_events` đều trống, và mọi hiệp tập có `source = 'manual'`. Vì vậy `training.v_muscle_recovery_status` hiện báo mọi nhóm cơ `ready`.

---

## 1. Master data (mọi môi trường)

| File | Nội dung |
|---|---|
| `01_rbac.sql` | 3 vai trò (`admin`, `content_editor`, `user`), 26 quyền |
| `02_reference.sql` | 3 mức độ khó, 3 vùng cơ thể, 23 nhóm cơ (6 nhóm gốc + 17 nhóm con; 18 vùng heatmap), 7 nhóm thiết bị, 27 thiết bị (mỗi thiết bị có nhãn AI `ai_label`), 5 mức vận động, 5 loại mục tiêu, 11 vị trí đo |
| `03_exercises.sql` + `04_exercises_more.sql` | **71 bài tập** published: 55 strength, 5 cardio, 5 plyometric, 4 stretching, 2 mobility. Mỗi bài có ≥ 1 nhóm cơ primary, ≥ 3 bước, ≥ 1 lỗi sai; kèm danh sách bài thay thế |
| `05_plan_templates.sql` | 6 giáo án mẫu (bảng dưới) |

### Giáo án mẫu

| UUID (đuôi) | Tên | Mục tiêu | Độ khó | Buổi | Ghi chú |
|---|---|---|---|---|---|
| `…0001` | Full Body cho người mới | recomposition | beginner | 2 | Có plank theo thời gian |
| `…0002` | Push / Pull / Legs | gain_muscle | intermediate | 3 | Có tempo |
| `…0003` | Upper / Lower 4 buổi | gain_muscle | intermediate | 4 | Giáo án của power@ |
| `…0004` | Sức mạnh 5×5 | strength | intermediate | 2 | Deadlift 1×5 |
| `…0005` | Giảm mỡ – Circuit + Cardio | lose_fat | beginner | 3 | Dùng `target_duration_seconds` (cardio 15–30 phút) |
| `…0006` | Bodyweight tại nhà | maintain | beginner | 3 | Không bài nào cần thiết bị bắt buộc |
| `…0007` | [TEST] Giáo án mẫu nháp | — | — | 1 | `draft`, chỉ có khi bật test |
| `…0008` | [TEST] Giáo án mẫu ngừng áp dụng | — | — | 1 | `archived`, chỉ có khi bật test |

---

## 2. Persona

| NN | Email (`@smartworkout.local`) | Vai trò | Trạng thái | Dùng để test |
|---|---|---|---|---|
| 01 | `admin` | admin | active | Quyền quản trị; là người cấp vai trò cho editor |
| 02 | `editor` | content_editor | active | CRUD danh mục; là `created_by` của mọi bài tập/thiết bị và người upload media danh mục |
| 03 | `demo` (An, nam, 2003) | user | active | **Happy path**: giáo án clone từ PPL (`source_plan_id = …0002`), ~4 tuần buổi tập, lịch quá khứ/tương lai (có `skipped`, `cancelled`), lịch ngày mai đã xác nhận cảnh báo phục hồi, buổi ngoài lịch có bài thêm từ `wiki` và `equipment_scan`, 7 lần cân + số đo vòng, goal `lose_fat` active, avatar, liên kết Google, chuỗi refresh token xoay vòng, 4 ảnh tiến độ (1 đang xử lý, 1 đã xoá mềm) + 1 cặp so sánh, 1 báo cáo tuần, báo đau cơ |
| 04 | `power` (Bình, nam, 1996) | user | active | **Dữ liệu dài 6 tháng**: ~94 buổi, ~1.700 hiệp (tăng tạ dần, deload), ~108 lịch, 26 lần cân, số đo vòng mỗi 4 tuần, goal `achieved` + `active`, 11 ảnh, 25 báo cáo tuần + 5 báo cáo tháng, 3 thiết bị (1 đã thu hồi). Dùng cho phân trang, biểu đồ Tháng/3 Tháng, `mv_daily_user_summary` |
| 05 | `dung` (Dung, nữ, 1999) | user | active | Nhánh **BMR nữ**; cân tăng dần (gain_muscle); **xếp lịch trực tiếp từ giáo án mẫu** …0001 (không clone); múi giờ `Asia/Tokyo`; ảnh `completed`/`failed`/`queued`; báo cáo tháng; 1 refresh token hết hạn chưa thu hồi |
| 06 | `plateau` (Hải, nam, 1991) | user | active | Cân đứng yên 6 tuần, nên `v_weekly_weight_trend.is_plateau = true`; goal `abandoned` + `active`; giáo án **tự tạo** (không clone) + giáo án `archived` + giáo án nháp đã xoá mềm; buổi tập tự do không gắn lịch (chạy bộ có quãng đường) |
| 07 | `inprogress` (Khoa, nam, 2000) | user | active | **1 buổi `in_progress`** hôm nay (có hiệp chưa làm, có bài thêm từ wiki chưa có hiệp), 1 buổi `abandoned`, 1 buổi **đã xoá mềm**; hiệp `drop` / `failure`, hiệp theo thời gian (`duration_seconds`) và quãng đường (`distance_m`); upload còn `pending_upload` |
| 08 | `newbie` (Mai) | user | active | **Trạng thái rỗng**: chỉ có `user_profiles`, không hồ sơ thể chất, không dữ liệu |
| 09 | `unspecified` (Nam) | user | active | Giới tính `unspecified`, thiếu ngày sinh/chiều cao/mức vận động → BMI/BMR/TDEE = **NULL** |
| 10 | `other` (Phương) | user | active | Giới tính `other` → BMR dùng hằng số **−78**; locale `en-US`, `unit_system = imperial`; giáo án bodyweight (hiệp không có mức tạ) |
| 11 | `pending` (Quang) | user | **pending_verification** | Chưa xác thực email; có token xác thực còn hạn + 1 token hết hạn; đăng nhập thất bại `email_not_verified` |
| 12 | `locked` (Sơn) | user | **locked** | `locked_until` ở tương lai; 5 lần sai mật khẩu trong 15 phút gần nhất + 1 lần `account_locked`; family refresh token bị thu hồi `reuse_detected`; file bị `quarantined` |
| 13 | `disabled` (Tâm) | user | **disabled** | Bị admin vô hiệu hoá; token bị thu hồi `admin_revoked`; đăng nhập thất bại `account_disabled` |
| 14 | `deleted` (Uyên) | user | active + **`deleted_at`** | Đã xoá mềm nhưng còn số đo, buổi tập, ảnh; API **không được** trả dữ liệu này; email có thể đăng ký lại |
| 15 | `oauth` (Vy) | user | active | **Chỉ OAuth**: `password_hash = NULL`, liên kết Google + Apple |
| 16 | `trainer` (Coach Xuân) | user + content_editor **(hết hạn)** | active | Vai trò hết hạn phải bị bỏ qua khi kiểm tra quyền; token reset mật khẩu còn hạn/hết hạn/đã dùng; giáo án clone 5×5 + giáo án `draft`; số đo `imported` |

Ngoài ra còn 8 lần đăng nhập thất bại từ IP `185.220.101.4` với email không tồn tại (`user_id = NULL`), dùng để test giới hạn theo IP.

## 3. Token thô để test

Database chỉ lưu SHA-256. Chuỗi gốc dưới đây sinh ra hash tương ứng, nên test có thể gửi thẳng lên API:

| Token gốc | Loại | Trạng thái |
|---|---|---|
| `seed-refresh-demo-2` | refresh token của demo@ (Pixel 8) | **còn hiệu lực**, cha là `seed-refresh-demo-1` |
| `seed-refresh-demo-1` | refresh token của demo@ | đã `rotated`, dùng lại token này phải bị phát hiện là tái sử dụng |
| `seed-refresh-power-ios` / `seed-refresh-power-web` | refresh token của power@ | còn hiệu lực |
| `seed-refresh-dung-exp` | refresh token của dung@ | hết hạn, chưa thu hồi |
| `seed-refresh-locked-2` | refresh token của locked@ | `reuse_detected` |
| `seed-refresh-disabled-1` | refresh token của disabled@ | `admin_revoked` |
| `seed-verify-pending-valid` | xác thực email của pending@ | còn hạn (~23 giờ) |
| `seed-verify-pending-expired` | xác thực email của pending@ | hết hạn |
| `seed-reset-trainer-valid` | reset mật khẩu của trainer@ | còn hạn (~25 phút sau khi init) |
| `seed-reset-trainer-expired` / `seed-reset-trainer-used` | reset mật khẩu của trainer@ | hết hạn / đã dùng |

Mọi token khác có dạng `seed-refresh-<key>`, với `<key>` lấy từ bảng `tmp_tokens` trong `seeds/90_test_users.sql`.

## 4. Ca biên trong danh mục (chỉ khi bật test)

| Đối tượng | Giá trị | Kỳ vọng |
|---|---|---|
| Bài `test-draft-exercise` | `status = draft` | Không xuất hiện ở API/`v_exercise_cards`/`fn_search_exercises` |
| Bài `test-archived-exercise` | `status = archived` | Như trên |
| Bài `test-deleted-exercise` | `deleted_at` có giá trị | Như trên |
| Thiết bị `test_retired_machine` | `deleted_at`, nhãn AI `test_retired_machine` | `fn_exercises_for_ai_label('test_retired_machine')` trả rỗng |
| Media bài tập | thumbnail + GIF chính cho 71 bài; video cho 20 bài compound; `barbell-back-squat` có 3 ảnh phụ `display_order` 3–5 | Test sắp xếp & chọn media chính |
| Media đặc biệt | `pending_upload` treo 2 ngày (cần dọn) và 5 phút (không dọn), `failed`, `quarantined`, avatar cũ đã xoá mềm | Test job dọn dẹp storage |

Key media theo quy ước `catalog/exercises/<slug>/{thumbnail.jpg, demo.gif, tutorial.mp4}`, `catalog/equipment/<code>.jpg`, `users/<...>/...`. **File thật trên S3 chưa tồn tại.**

## 5. Cấu trúc file seed

| File | Nhóm | Nội dung |
|---|---|---|
| `01`–`05` | master | Xem mục 1 |
| `90_test_users.sql` | test | Hàm hỗ trợ (schema tạm `test_seed`) + persona: users, profiles, roles, OAuth, thiết bị, refresh token, verification token, login attempts |
| `91_test_catalog.sql` | test | Media placeholder danh mục, ca biên bài tập/thiết bị/giáo án |
| `92_test_body.sql` | test | Hồ sơ thể chất, số đo, số đo vòng, mục tiêu |
| `93_test_training.sql` | test | Giáo án, lịch, buổi tập, hiệp của các persona viết tay |
| `94_test_power_user.sql` | test | Sinh lịch sử 6 tháng cho power@ |
| `95_test_media_reports.sql` | test | Avatar, ảnh tiến độ, so sánh, báo cáo, báo đau cơ, media đặc biệt |
| `99_test_cleanup.sql` | test | Xoá schema `test_seed` |

Có thể dùng các hàm trong `test_seed` (đọc phần đầu `90_test_users.sql`) để thêm persona mới nhanh: `clone_plan`, `schedule`, `log_plan_session`, `log_session`, `media`.
