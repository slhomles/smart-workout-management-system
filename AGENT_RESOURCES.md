# AGENT_RESOURCES.md — Nguồn tham chiếu cho Gym App

Đọc file này **trước khi**: import dữ liệu động tác, dựng màn hình bài tập, viết logic giáo án/tiến độ, làm UI, hoặc làm tính năng chỉnh tư thế.
Dự án chạy **LOCAL** → không cần quan tâm license; chỉ quan tâm độ ổn định và chất lượng dữ liệu.

---

## 0. Quy tắc chung

1. **Local trước, online sau.** Dữ liệu + media lấy từ repo đã clone trong `resources/`. Không gọi API ngoài lúc app chạy; nếu buộc phải dùng API online thì viết script tải **một lần** rồi cache thành file JSON.
2. **Đọc schema gốc trước khi viết parser** (`README`, `schema.json`, `exercises.schema.json`). Không đoán tên field.
3. **Không bịa số liệu tập luyện.** Mọi default (sets, reps, %1RM, thời gian nghỉ, volume) lấy từ mục 2 và ghi nguồn trong comment.
4. **Không sửa file dataset gốc.** Bản dịch tiếng Việt, mapping, dữ liệu bổ sung → file riêng trong `data/`.
5. **Một bộ từ vựng nhóm cơ duy nhất.** Mỗi dataset đặt tên cơ khác nhau → tạo `data/muscle_map.json` (tên cơ của từng dataset → slug của muscle map ở mục 3.3) và cả app chỉ dùng bộ slug đó.

### Chuẩn bị (chạy 1 lần; nếu thư mục đã có thì `git pull`)

```bash
mkdir -p resources && cd resources
git clone --depth 1 https://github.com/yuhonas/free-exercise-db.git
git clone --depth 1 https://github.com/hasaneyldrm/exercises-dataset.git
git clone --depth 1 https://github.com/skulptapp/skulpt.git   # chỉ đọc code để tham khảo
```

---

## 1. Dữ liệu động tác, ảnh, GIF

| Cần gì | Dùng nguồn | Ghi chú |
|---|---|---|
| GIF động tác (list, chi tiết) | `exercises-dataset` (1.1) | 1.324 động tác, mỗi động tác 1 GIF + 1 thumbnail, **180×180** |
| Ảnh tĩnh + metadata (level, force, mechanic) | `free-exercise-db` (1.2) | 800+ động tác, ảnh JPG, **không có GIF** |
| Động tác/GIF không có trong 2 bộ trên | ExerciseDB V1 (1.3) | online, chỉ để tải về |
| Backend mẫu có routine/log/video | wger (1.4) | tuỳ chọn, nặng |

### 1.1 `resources/exercises-dataset` — nguồn GIF chính
- Data: `data/exercises.json` (mảng); schema: `data/exercises.schema.json`.
- Field: `id, name, category, body_part, equipment, target, muscle_group, secondary_muscles[], instructions{lang}, instruction_steps{lang:[]}, image, gif_url, media_id`.
- Media là đường dẫn tương đối từ root repo: `image` → `images/...` (thumbnail), `gif_url` → `videos/<id>-<media_id>.gif`.
- `index.html`: trình duyệt offline để xem nhanh dữ liệu. `setup.html`: sinh câu SQL CREATE/INSERT cho PostgreSQL/MySQL/SQLite.
- Hạn chế: GIF chỉ 180px → không phóng quá ~2x. Hướng dẫn có nhiều ngôn ngữ (en, zh, …) nhưng **không có tiếng Việt** → dịch vào `data/i18n/vi/exercises.json`, key theo `id`.

### 1.2 `resources/free-exercise-db` — ảnh tĩnh + metadata
- Mỗi động tác 1 file `exercises/<Name>.json`; bản gộp `dist/exercises.json`; `dist/exercises.nd.json` (NDJSON) để `COPY` vào Postgres. Build: `make dist/exercises.json` (cần `jq`).
- Field: `id, name, force, level, mechanic, equipment, primaryMuscles[], secondaryMuscles[], instructions[], category, images[]`. `force`, `mechanic`, `equipment` có thể `null`.
- Ảnh: `images[]` chứa path dạng `Air_Bike/0.jpg` → file local `exercises/Air_Bike/0.jpg`; URL host: `https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises/<path>`.
- Thường có 2 ảnh (`0.jpg`, `1.jpg`) → khi không có GIF, có thể luân phiên 2 ảnh (~0.8s) để giả lập chuyển động.
- Có ~25 ảnh trùng. Lấy danh sách tên cơ: `jq '[.[].primaryMuscles[]] | unique' dist/exercises.json`.

### 1.3 ExerciseDB V1 (exercisedb.dev, nay là AscendAPI) — chỉ để tải bổ sung
- Base: `https://oss.exercisedb.dev/api/v1`, không cần key. Ví dụ: `GET /exercises`.
- Field: `exerciseId, name, gifUrl, bodyParts[], targetMuscles[], secondaryMuscles[], equipments[], instructions[]`. GIF 180p: `https://static.exercisedb.dev/media/{exerciseId}.gif`.
- Danh sách endpoint (search, lọc theo bodyparts/muscles/equipments, by id, list muscles/bodyparts/equipments): đọc `https://docs.ascendapi.com/llms.txt` hoặc `https://oss.exercisedb.dev/docs` **trước khi gọi**. Spec ghi `limit` tối đa 25, phân trang bằng cursor `after`/`before` — kiểm tra lại trên bản free.
- Endpoint free có thể bị rate limit/không ổn định → script tải về `resources/exercisedb-v1/` một lần; app chỉ đọc file local.

### 1.4 wger (tuỳ chọn)
- Self-host: `git clone https://github.com/wger-project/docker.git && cd docker && docker compose up -d`.
  Tải media: `docker compose exec web python3 manage.py download-exercise-images` (và `download-exercise-videos`).
- API: `/api/v2/` (liệt kê endpoint), `/api/v2/schema` (OpenAPI), `/api/v2/exerciseinfo/<id>/` (đủ thông tin 1 động tác). Endpoint public không cần auth.
- Dùng khi cần tham khảo thiết kế API routine/workout log, hoặc cần video. Cần ~2 GB RAM (Postgres + Redis + Celery).

---

## 2. Kiến thức tập luyện

| Việc cần làm | Đọc |
|---|---|
| Default sets/reps/%1RM/tần suất | ACSM Position Stand 2026 |
| Volume tuần theo nhóm cơ, cảnh báo tập quá tải | RP — Volume Landmarks |
| Giáo án mẫu, quy tắc tăng tạ | r/Fitness wiki, Liftosaur |
| Cơ tham gia, kinesiology, strength standards | ExRx.net |
| Cách thực hiện từng động tác | field `instructions` của dataset mục 1 |

**Default khi chưa có yêu cầu riêng (ACSM 2026, người trưởng thành khoẻ mạnh):**
- Tập tất cả nhóm cơ lớn ≥ 2 buổi/tuần.
- Sức mạnh: tải nặng (~80% 1RM), 2–3 set/bài.
- Phì đại cơ: ~10 set/nhóm cơ/tuần.
- Power: 30–70% 1RM, đẩy nhanh nhất có thể ở pha concentric.
- Đều đặn quan trọng hơn chương trình phức tạp → logic mặc định nên đơn giản, dễ duy trì.

**Volume (RP):** MV ≈ 6 set/tuần để duy trì; MEV → MAV → MRV là các ngưỡng tăng dần và khác nhau theo người → cho người dùng chỉnh, không hard-code một con số.

**1RM ước tính** (chỉ dùng khi reps ≤ 10):
- Epley: `1RM = w × (1 + reps / 30)`
- Brzycki: `1RM = w × 36 / (37 − reps)`

**Links**
- ACSM: https://acsm.org/resistance-training-guidelines-update-2026/ — bài gốc trên MSSE: *Resistance Training Prescription for Muscle Function, Hypertrophy, and Physical Performance in Healthy Adults: An Overview of Reviews*.
- RP: https://rpstrength.com/training-volume-landmarks-muscle-growth/
- r/Fitness wiki: https://thefitness.wiki/routines/ — Basic Beginner Routine: 3 buổi/tuần, xen kẽ A/B, 2×5 + 1×5+ (AMRAP).
- Liftosaur: https://github.com/astashov/liftosaur, giáo án mẫu: https://www.liftosaur.com/programs/basicBeginner — giáo án viết bằng "Liftoscript", progression rõ ràng → tham khảo khi mô hình hoá giáo án/progression.
- ExRx: https://exrx.net/Exercise · https://exrx.net/Muscles · https://exrx.net/WorkoutTools/OneRepMax (nhiều bài mới cần Premium; chỉ dùng phần free).

---

## 3. UI

### 3.1 Pattern màn hình tập — đọc trước khi làm luồng log
- https://screensdesign.com/articles/workout-tracker-app-design-examples/ (mô tả bằng chữ: active session, set table, rest timer, thay bài, tổng kết).
- Quy tắc mặc định:
  - Set table tách rõ 3 loại giá trị: **mục tiêu / lần trước / hôm nay đã xác nhận**. Giá trị điền sẵn chưa tính là đã làm cho đến khi user bấm xác nhận.
  - Rest timer gắn với set vừa xong; có +/−, pause, skip, tắt. Lưu **thời điểm kết thúc (deadline)**, không đếm ngược trong RAM → app chạy nền vẫn đúng.
  - Undo/sửa/xoá set không reset timer hay session. Lưu local ngay sau mỗi set.
  - Mở lại app → quay về session đang dở. Bấm kết thúc khi còn set chưa log → hỏi xác nhận, cho lưu một phần.
  - Thay bài giữa buổi: giữ các set đã làm, ghi lại bài gốc và bài thay.
  - Màn tổng kết: thời lượng, volume, PR, set bỏ qua, ghi chú; cho sửa trước khi lưu.
- Ảnh tham khảo app thật (Strong, Hevy, …) do người dùng lưu trong `docs/ui-refs/` → khi dựng màn hình, đọc ảnh trong thư mục này trước.

### 3.2 Code app mã nguồn mở để tham khảo cấu trúc
- `resources/skulpt` (React Native + Expo, SQLite + Drizzle, offline-first): xem `screens/`, schema DB, các loại set (warm-up, drop, failure, time, distance), superset/circuit.
- Liftosaur (Preact + TypeScript PWA): luồng chạy giáo án có progression.

### 3.3 Muscle map (tô màu nhóm cơ)

| Stack FE | Package |
|---|---|
| Web, framework nào cũng được | `body-highlighter` — github.com/lahaxearnaud/body-highlighter |
| React web (bản gốc, nhiều người dùng hơn) | `react-body-highlighter` |
| React Native / Expo | `react-native-body-highlighter` (cần `react-native-svg`) |

- Slug chung của cả 3: `trapezius, upper-back, lower-back, chest, biceps, triceps, forearm, back-deltoids, front-deltoids, abs, obliques, adductor, hamstring, quadriceps, abductors, calves, gluteal, head, neck`. Có view trước/sau.
- Map tên cơ của dataset → slug trong `data/muscle_map.json` (quy tắc 0.5).

### 3.4 Figma (chỉ khi có file thiết kế)
- MCP chính thức của Figma cần seat Dev/Full của gói trả phí; bản miễn phí thay thế: Framelink MCP (community).
- Không có MCP → export frame ra PNG vào `docs/ui-refs/`.

---

## 4. (Tuỳ chọn) AI chỉnh tư thế
- MediaPipe Pose Landmarker: https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker — 33 landmark/người, có toạ độ chuẩn hoá và toạ độ 3D (world). Web: `npm i @mediapipe/tasks-vision`, mode `VIDEO` hoặc `LIVE_STREAM` cho camera.
- Chạy detect trong Web Worker để không chặn UI.
- Chấm tư thế = tính góc khớp từ landmark (vd hông–gối–cổ chân cho squat). Ngưỡng góc để trong file config, không hard-code; ghi nguồn khi đặt giá trị.

---

## 5. KHÔNG dùng
- Blog brightcoding.dev về free-exercise-db: chỉ tóm tắt lại README, có code minh hoạ không khớp repo → đọc README gốc (1.2).
- figma-free.com "Fitness & Workout App UI Kit": trang đăng lại, chỉ có ảnh preview đã flatten, không có link Figma gốc → không trích được layout/component.
- Trang chủ exercisedb.dev: chỉ là landing page → dùng docs ở 1.3.
