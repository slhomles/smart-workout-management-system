# Smart Workout AI - Backend (FastAPI)

## 🚀 Cài Đặt

### Yêu Cầu
- Python 3.11+
- PostgreSQL 15+
- MongoDB 7+
- Redis 7+

### Setup Môi Trường

```bash
# Tạo virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate

# Cài đặt dependencies
pip install -r requirements.txt

# Copy file env
cp .env.example .env
# → Chỉnh sửa .env theo cấu hình local

# Chạy migration
alembic upgrade head

# Seed dữ liệu mẫu
python scripts/seed_exercises.py

# Chạy server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Hai database: test và app/demo

Trên Postgres của VM (cùng server) có hai DB:

| DB | Dùng cho | Nội dung |
|---|---|---|
| `smart_workout_db` (`POSTGRES_DB` trong `backend/.env`) | pytest, agent flow, CI | Chỉ schema + seed (71 bài); test khẳng định đúng dữ liệu seed, **không nhập thêm dữ liệu vào đây** |
| `smart_workout_app` | chạy app thật, demo | Schema + seed + nội dung bài tập đầy đủ (GIF, ảnh trên S3, hướng dẫn tiếng Việt) |

Chạy backend cho app/demo bằng cách ghi đè biến môi trường, không sửa `backend/.env`:

```powershell
$env:POSTGRES_DB = "smart_workout_app"; uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Nạp lại nội dung bài tập (sau khi dựng lại `smart_workout_app`): clone dataset theo `AGENT_RESOURCES.md` §0 vào
`resources/`, rồi `python scripts\import_exercise_content.py --database smart_workout_app` (thử trước với
`--dry-run`). Dữ liệu đã ghép và dịch nằm trong `data/` (`exercise_map.json`, `new_exercises.json`, `muscle_map.json`,
`i18n/vi/`). Script chạy lại không tạo bản trùng và từ chối chạy trên DB test.

### API Documentation
Sau khi chạy server, truy cập:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📁 Cấu Trúc

```
backend/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── core/                # Config, DB, Security
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic schemas
│   ├── api/v1/              # API routers
│   ├── crud/                # Database CRUD operations
│   ├── services/            # Business logic
│   ├── middleware/           # Custom middleware
│   └── utils/               # Utilities
├── alembic/                 # Database migrations
├── tests/                   # Tests
└── scripts/                 # Utility scripts
```

## 🧪 Tests

```bash
# Chạy tất cả tests
pytest

# Chạy với coverage
pytest --cov=app --cov-report=html

# Chạy chỉ unit tests
pytest tests/unit/

# Chạy chỉ integration tests
pytest tests/integration/
```
