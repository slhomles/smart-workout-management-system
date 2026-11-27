# Smart Workout AI - AI Services

> FastAPI nội bộ phục vụ backend: dự đoán phục hồi cơ, nhận diện thiết bị, và worker phân tích video.
> Hợp đồng với backend: **`docs/architecture/06-ai-contracts.md`** (đọc trước khi sửa bất kỳ code nào ở đây).
> Chuẩn code Python: `docs/guides/coding-standards.md`. Nguồn dữ liệu và luật tư thế: `AGENT_RESOURCES.md`.

## Cấu trúc

```
ai-services/
├── app/
│   ├── main.py            # create_app(): middleware X-Request-ID, handler lỗi, router — file core
│   ├── contracts.py       # model Pydantic của hợp đồng (06-ai-contracts §2) — file core
│   ├── core/              # config, errors (format lỗi chung), logging, models (sổ đăng ký model cho /health) — file core
│   ├── api/
│   │   ├── router.py      # mỗi module thêm 1 dòng import + 1 dòng include_router, theo chữ cái
│   │   └── health.py      # GET /health
│   └── <module>/          # code của từng module (vd recovery/, equipment/, video_worker/)
├── tests/                 # pytest; conftest.py (client, sổ đăng ký model sạch mỗi test) — file core
├── models/                # trọng số model, KHÔNG commit (.gitignore)
├── notebooks/             # R&D, huấn luyện
├── requirements.txt       # API + test + lint (nhẹ, không cần GPU) — CI và agent flow dùng file này
└── requirements-ml.txt    # torch, ultralytics, mediapipe, opencv — cài thêm khi chạy model thật / Docker
```

Quy tắc:
- Đường dẫn và field đúng `06-ai-contracts.md`. Lỗi luôn `raise AppError` hoặc lớp con (`app/core/errors.py`), body `{"error": {code, message, details, request_id}}`, chỉ mã đã đăng ký.
- Model nạp lười (lazy) và đăng ký vào `app.core.models.registry` để `/health` báo đúng. Import `torch`/`ultralytics`/`mediapipe` **bên trong** hàm nạp model, để test và CI chạy được mà không cần các gói này.
- Test dùng model giả cùng giao diện; không tải model, không gọi mạng.

## Cài đặt và chạy

```powershell
py -3.12 -m venv ai-services\.venv
ai-services\.venv\Scripts\python -m pip install -r ai-services\requirements.txt
# Khi cần model thật:
ai-services\.venv\Scripts\python -m pip install -r ai-services\requirements-ml.txt

cd ai-services
copy .env.example .env
.venv\Scripts\python -m uvicorn app.main:app --port 8001 --reload
```

Kiểm tra: `GET http://localhost:8001/health`. Backend trỏ `AI_SERVICE_URL=http://localhost:8001` (docker-compose: `http://ai-services:8001`).

## Test, lint

```powershell
cd ai-services
.venv\Scripts\python -m pytest --cov=app
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m mypy app/
```

Agent flow: spec có `target: ai-services` (xem `scripts/agent-flow/README.md`).

## Model dự kiến

| Module | Model | Ghi chú |
|---|---|---|
| `ai-recovery-predict` | Heuristic `heuristic-v1` | PyTorch là hướng phát triển |
| `ai-equipment-classify` | YOLOv8-cls (fine-tune `datasets/gym-equipment`) | Thiếu trọng số thì dùng model dự phòng, `model_version` có hậu tố `-fallback` |
| `ai-video-worker` | YOLOv8-Pose + OpenCV | Luật tư thế và FSM đếm rep dùng chung `shared/constants/pose-rules.json` với app |
