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
