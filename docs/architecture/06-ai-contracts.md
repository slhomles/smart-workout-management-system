# Hợp đồng giữa backend và AI services

> **Dành cho AI/coding assistant:** Code trong `ai-services/` và code backend gọi AI PHẢI theo file này: đường dẫn, tên field, kiểu, đơn vị, mã lỗi. KHÔNG tự đổi hợp đồng ở một phía. Đổi hợp đồng thì sửa file này trước (CLAUDE.md §5), rồi sửa cả hai phía trong cùng một module.
> Từ khoá PHẢI / KHÔNG ĐƯỢC / NÊN theo nghĩa RFC 2119. Nhóm chốt ngày 27/11/2026.

## 1. Bối cảnh và nguyên tắc

- Doc 05 §1.3 để hợp đồng backend ↔ AI "ngoài phạm vi". File này lấp chỗ đó, dựa trên hợp đồng tạm mà các module backend đã code:
  - `recovery_ai_client.py`: workout-routine, câu hỏi Q5;
  - `equipment_recognition_client.py`: equipment-recognition, Q2;
  - `video_job_service.py`: set-rep-tempo, Q1.
- Có **hai chiều gọi**:
  1. **Backend → AI service** (đồng bộ, HTTP): dự đoán phục hồi, nhận diện thiết bị. AI service là FastAPI trong `ai-services/`, địa chỉ `AI_SERVICE_URL` (mặc định `http://localhost:8001`, trong docker-compose là `http://ai-services:8001`).
  2. **Worker video → backend** (bất đồng bộ): worker trong `ai-services/` lấy job từ backend, xử lý video, báo kết quả về backend. Worker **không** ghi thẳng DB.
- AI service **không** có quyền vào PostgreSQL và **không** biết user. Mọi dữ liệu nghiệp vụ đi qua backend.
- Đơn vị SI, thời gian ISO 8601 UTC có `Z`, JSON snake_case (doc 05 §2, `Claude_api_respone.md` §2).
- Chức năng 5 Option 1A và chức năng 6 chạy **trên điện thoại** (MediaPipe + FSM). Ứng dụng gửi kết quả qua `/api/v1/ai/pose-analyses` và API buổi tập. Hai chức năng này không gọi AI service.

## 2. AI service: các endpoint backend gọi

Không có tiền tố `/api/v1`. Đây là API nội bộ, chỉ mở trong mạng docker hoặc Tailscale, không đưa ra Internet. Không có xác thực.

| Method | Path | Gọi từ | Timeout phía backend |
|---|---|---|---|
| GET | `/health` | `health_service._check_ai_service` | `AI_HEALTH_TIMEOUT_SECONDS` |
| POST | `/recovery/predict` | `recovery_ai_client.predict_recovery` | 10 giây |
| POST | `/equipment-recognition/classify` | `equipment_recognition_client.classify_image` | 10 giây |

### 2.1. Quy tắc chung

- Thành công: `200`, body trả thẳng. Lỗi: format lỗi của `Claude_api_respone.md` §3, chỉ dùng mã đã đăng ký: `validation_error` 422, `bad_request` 400, `internal_error` 500, `service_unavailable` 503 (model chưa nạp xong).
- Backend coi **mọi** phản hồi khác `200`, JSON hỏng hoặc sai schema là AI service lỗi:
  - với người dùng: trả `503 service_unavailable`;
  - với `/health`: báo `ai_service: degraded`.
- Backend validate response bằng Pydantic, nên AI service PHẢI trả đúng tên field, kiểu và giới hạn ở dưới. Field thừa bị bỏ qua.

### 2.2. `GET /health`

`200` khi service chạy và model bắt buộc đã nạp xong (hoặc đang dùng model dự phòng, xem §2.4):

```json
{ "status": "ok", "models": { "recovery": "heuristic-v1", "equipment": "yolov8_cls_gym@1.0.0" }, "checked_at": "2026-11-27T13:00:00Z" }
```

Model chưa sẵn sàng thì trả `503 service_unavailable`. Backend chỉ xét status code.

### 2.3. `POST /recovery/predict`

Request: `RecoveryPredictionInput` trong `backend/app/schemas/recovery.py`.

```json
{
  "session_id": "7c1e9a52-3b8d-4f60-a2e4-9d5b1c7f3a10",
  "user_id": "00000000-0000-0000-0000-000000000003",
  "trained_at": "2026-11-27T01:00:00Z",
  "muscle_loads": [
    { "muscle_group_id": 1, "direct_sets": 4, "effective_sets": 5.5, "total_reps": 40,
      "weighted_volume_kg": 2400.0, "avg_rpe": 8.0, "base_recovery_hours": 72 }
  ]
}
```

Response `200`: `RecoveryPredictionOutput`.

```json
{
  "model_version": "heuristic-v1",
  "predictions": [
    { "muscle_group_id": 1, "fatigue_score": 80.0, "recovered_at": "2026-11-29T13:00:00Z" }
  ]
}
```

| Field | Quy tắc |
|---|---|
| `model_version` | 1–50 ký tự. Bản heuristic dùng `heuristic-v1`; model PyTorch sau này dùng `recovery-torch-<semver>` |
| `predictions` | Một phần tử cho **mỗi** `muscle_group_id` trong request, không thêm nhóm khác |
| `fatigue_score` | Số thực trong [0, 100] (CHECK `ck_recovery_predictions_fatigue`) |
| `recovered_at` | Có múi giờ, `>= trained_at` |

`muscle_loads` rỗng thì trả `predictions: []`. Thuật toán `heuristic-v1` do module `ai-recovery-predict` định nghĩa trong spec. Thuật toán PHẢI tất định, tức cùng input thì cùng output, để test được.

### 2.4. `POST /equipment-recognition/classify`

Request: `multipart/form-data`, một part tên `image` (JPEG/PNG/WebP, backend đã kiểm kích thước và định dạng trước khi gửi). Không có field khác.

Response `200`: `AiClassifyResult` trong `backend/app/schemas/equipment_scan.py`.

```json
{
  "model_name": "yolov8_cls_gym",
  "model_version": "1.0.0",
  "latency_ms": 180,
  "predictions": [
    { "label": "cable_crossover_machine", "confidence": 0.9234 },
    { "label": "lat_pulldown_machine", "confidence": 0.0512 }
  ]
}
```

| Field | Quy tắc |
|---|---|
| `model_name`, `model_version` | 1–50 ký tự |
| `latency_ms` | Thời gian suy luận, số nguyên ≥ 0, hoặc `null` |
| `predictions` | Tối đa 20 phần tử (top-k), sắp `confidence` giảm dần |
| `label` | PHẢI là một nhãn trong §2.5. Nhãn lạ bị backend bỏ qua |
| `confidence` | Số thực trong [0, 1] |

Không có file trọng số đã fine-tune (`ai-services/models/equipment/best.pt`, không commit vào git) thì service vẫn chạy bằng model dự phòng do module `ai-equipment-classify` chọn, với `model_version` có hậu tố `-fallback`. Không được trả `503` chỉ vì thiếu trọng số fine-tune.

### 2.5. Danh sách nhãn thiết bị (`ai_label`)

Nguồn sự thật là `catalog.equipment_aliases` với `alias_type = 'ai_label'` trong `database/postgresql/seeds/02_reference.sql`. Danh sách lớp của model PHẢI trùng đúng danh sách này (27 nhãn):

`barbell`, `ez_curl_bar`, `dumbbell`, `kettlebell`, `flat_bench`, `adjustable_bench`, `power_rack`, `smith_machine`, `cable_crossover_machine`, `lat_pulldown_machine`, `seated_cable_row_machine`, `leg_press_machine`, `leg_extension_machine`, `leg_curl_machine`, `chest_press_machine`, `pec_deck_machine`, `shoulder_press_machine`, `pull_up_bar`, `dip_station`, `treadmill`, `stationary_bike`, `rowing_machine`, `resistance_band`, `jump_rope`, `plyo_box`, `medicine_ball`, `ab_wheel`.

Thêm thiết bị thì thêm dòng `ai_label` trong seed hoặc migration trước, rồi mới thêm lớp cho model.

## 3. Worker video: các route backend mở cho worker

Phục vụ chức năng 5 Option 1B và chức năng 6 (luồng video). Đây là câu hỏi Q1 của `set-rep-tempo`. Hàng đợi là các dòng `ai.video_analysis_jobs` ở trạng thái `queued` (design-overview §5). Backend lấy job bằng `FOR UPDATE SKIP LOCKED`.

### 3.1. Xác thực worker

- Worker gửi header `X-Worker-Token: <AI_WORKER_TOKEN>`. Cả backend và ai-services đọc cùng biến môi trường `AI_WORKER_TOKEN`, tối thiểu 32 ký tự ngẫu nhiên. Biến này nằm trong `.env`, KHÔNG commit.
- Ngoài môi trường `development`, backend PHẢI từ chối khởi động nếu `AI_WORKER_TOKEN` trống (giống `JWT_SECRET_KEY`, doc 04 §6.4).
- Sai hoặc thiếu token: `401 unauthorized`. Không dùng JWT của user cho worker, và worker không có `user_id`.
- So sánh token bằng `hmac.compare_digest`. Không log token.

### 3.2. Route

Thuộc tiền tố `/api/v1/ai/video-jobs` của module set-rep-tempo (doc 05 §6.3). Dùng lại các hàm `start_job`, `record_result`, `record_failure` trong `video_job_service.py`.

| Method | Path | Thành công | Mô tả |
|---|---|---|---|
| POST | `/api/v1/ai/video-jobs/claim` | `200` job, hoặc `204` khi hết job | Lấy job `queued` ưu tiên cao nhất, cũ nhất (`FOR UPDATE SKIP LOCKED`) rồi `start_job`. Body `{ "worker_id": "worker-01" }` (1–100 ký tự) |
| GET | `/api/v1/ai/video-jobs/{job_id}/source-video` | `200` stream file (`Content-Type` của video gốc) | Chỉ khi job đang `processing` |
| POST | `/api/v1/ai/video-jobs/{job_id}/result` | `200` `VideoJobResponse` | `multipart/form-data`: part `video` (MP4 kết quả đã vẽ khung xương) và part `result` (JSON `VideoJobResultRequest` **không** có `result_video_media_id`). Backend lưu video qua `storage_service`, tạo `media_files`, rồi gọi `record_result` |
| POST | `/api/v1/ai/video-jobs/{job_id}/failure` | `200` `VideoJobResponse` | Body `VideoJobFailureRequest` `{ "error_message": "…" }` |

Response của `claim`:

```json
{
  "job_id": "3f1c…",
  "set_id": 1234,
  "exercise_id": 12,
  "exercise_slug": "barbell-back-squat",
  "attempt_count": 1,
  "source_video_content_type": "video/mp4"
}
```

Lỗi chỉ dùng mã đã đăng ký: `unauthorized` 401, `not_found` 404 (job không tồn tại), `conflict` 409 (job không ở trạng thái cho phép, đúng như service hiện có), `validation_error` 422, `service_unavailable` 503. Muốn có mã riêng `video_job_not_found` thì đăng ký vào `Claude_api_respone.md` §10 trước (Q2 của set-rep-tempo).

### 3.3. Vòng lặp của worker

1. `POST …/claim`. Nhận `204` thì chờ `AI_WORKER_POLL_SECONDS` (mặc định 5 giây) rồi gọi lại.
2. Tải video gốc bằng `GET …/source-video`.
3. Chạy YOLOv8-Pose và OpenCV:
   - suy ra các rep (`rep_events`: số mili giây từng pha, đúng `RepEventInput`);
   - chấm `overall_score`, `correct_form_pct` trên thang [0, 100];
   - viết `feedback_summary` bằng tiếng Việt;
   - render MP4 có khung xương.
4. `POST …/result`. Gặp lỗi xử lý (không giải mã được video, không thấy người…) thì `POST …/failure` kèm thông báo ngắn, không lộ stack trace.
5. Lỗi mạng khi báo kết quả thì thử lại tối đa 3 lần (backoff 2, 4, 8 giây). Job kẹt ở `processing` do worker chết thì xử lý sau (ngoài phạm vi, Q10 của set-rep-tempo).

Luật tư thế và FSM đếm rep dùng **cùng ngưỡng** với bản trên điện thoại (module `fe-pose-logic`). Bảng ngưỡng theo bài tập đặt ở `shared/constants/pose-rules.json` để hai phía đọc chung.

## 4. Kiểm thử

- **Backend:** giả AI service bằng `httpx.MockTransport` hoặc `respx` như các module đã làm. Test route worker gửi header `X-Worker-Token` đặt trong fixture, không dùng giá trị thật.
- **ai-services:** test endpoint bằng `fastapi.testclient.TestClient`. Model thật được thay bằng model giả cùng giao diện, nên CI không cần GPU hay trọng số.
- **Test hợp đồng:**
  - ai-services có test kiểm response mẫu ở §2 qua JSON Schema lấy từ chính các model Pydantic ở `ai-services/src/common/contracts.py`;
  - các model này PHẢI khớp field với schema backend nêu trên.

## 5. Checklist khi sửa code chạm hợp đồng

- [ ] Đường dẫn, method, tên field, kiểu, giới hạn khớp §2, §3
- [ ] AI service chỉ trả mã lỗi đã đăng ký; backend quy mọi lỗi AI thành `503 service_unavailable`
- [ ] Nhãn thiết bị nằm trong §2.5
- [ ] Không log token, ảnh hay video của người dùng; không ghi dữ liệu cá nhân vào log
- [ ] Test giả model, không cần GPU hay trọng số
