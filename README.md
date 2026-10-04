# 🏋️ Smart Workout AI

> Ứng dụng Quản lý Tập luyện Thể hình (Gym) tích hợp AI hỗ trợ phân tích tư thế

[![CI Backend](https://img.shields.io/badge/CI-Backend-blue)]()
[![CI Frontend](https://img.shields.io/badge/CI-Frontend-green)]()
[![CI AI Services](https://img.shields.io/badge/CI-AI_Services-orange)]()

## 📋 Mô Tả

Smart Workout AI là ứng dụng di động quản lý tập luyện thể hình toàn diện, đóng vai trò như một **"Huấn luyện viên cá nhân ảo"**. Hệ thống kết hợp giữa quản lý lịch trình tập luyện, theo dõi thể chất và ứng dụng thị giác máy tính cùng học máy để phân tích, hỗ trợ người dùng ngay trong lúc tập.

## ✨ Tính Năng Chính

### 🤖 AI Core
| # | Tính năng | Mô tả | Công nghệ |
|---|-----------|-------|-----------|
| 1 | **Phân tích tư thế (Realtime)** | Camera phân tích khung xương, cảnh báo sai form | MediaPipe BlazePose |
| 2 | **Đánh giá video chuyên sâu** | Upload video → AI phân tích chi tiết, trả kết quả | YOLOv8-Pose |
| 3 | **Đếm Rep/Set & Tempo** | Tự động đếm số lần lặp, đo nhịp vận động | FSM + MediaPipe |
| 4 | **Nhận diện thiết bị gym** | Quét camera → nhận diện máy → gợi ý bài tập | YOLOv8 Classification |
| 5 | **Dự đoán phục hồi cơ** | Phân tích khối lượng tập → dự đoán thời gian hồi phục | PyTorch |

### 📱 Quản Lý & Nghiệp Vụ
| # | Tính năng | Mô tả |
|---|-----------|-------|
| 6 | **Thư viện bài tập (Exercise Wiki)** | Tra cứu kỹ thuật qua video/GIF, lọc theo nhóm cơ/thiết bị |
| 7 | **Kế hoạch tập (Workout Routine)** | Lập giáo án, theo dõi phục hồi cơ bắp (Heatmap) |
| 8 | **Dashboard thống kê** | BMR, TDEE, BMI, quản lý Calo/Macro, cảnh báo |
| 9 | **Nhật ký ảnh (Progress Gallery)** | Upload ảnh, auto watermark, so sánh Before/After |

## 🏗️ Kiến Trúc Hệ Thống

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Mobile App │────▶│  Core Backend   │────▶│   AI Services    │
│  (Frontend) │     │  (FastAPI)      │     │   (Python)       │
└─────────────┘     └────────┬────────┘     └──────────────────┘
                             │                        │
                    ┌────────┼────────┐               │
                    ▼        ▼        ▼               ▼
              PostgreSQL  MongoDB   Redis      Message Queue
```

## 🛠️ Tech Stack

| Layer | Công nghệ |
|-------|-----------|
| **Frontend** | *Chưa chốt* |
| **Backend** | FastAPI (Python) |
| **AI/ML** | MediaPipe, YOLOv8, PyTorch, OpenCV |
| **Database** | PostgreSQL + MongoDB + Redis |
| **Queue** | RabbitMQ / Redis |
| **Storage** | AWS S3 / Firebase Storage |
| **DevOps** | Docker, GitHub Actions |

## 📁 Cấu Trúc Dự Án

```
smart_workout/
├── frontend/          # Mobile/Web App
├── backend/           # FastAPI Core API
├── ai-services/       # AI/ML Microservices (Python)
├── database/          # DB Schemas & Seeds
├── docs/              # Tài liệu dự án
├── infrastructure/    # Docker, Nginx, K8s
├── datasets/          # Training data (Git LFS)
├── shared/            # Shared types & constants
└── scripts/           # Project-level utilities
```

## 🚀 Bắt Đầu

### Yêu Cầu
- Python 3.11+
- Docker & Docker Compose
- Node.js 18+ (cho frontend)
- PostgreSQL 15+
- MongoDB 7+
- Redis 7+

### Cài Đặt

```bash
# Clone repository
git clone https://github.com/<your-org>/smart-workout-ai.git
cd smart-workout-ai

# Khởi động tất cả services bằng Docker
docker-compose -f docker-compose.dev.yml up -d

# Hoặc cài đặt thủ công - xem docs/guides/development-setup.md
```

## 📖 Tài Liệu

- [Hướng dẫn cài đặt môi trường](docs/guides/development-setup.md)
- [Kiến trúc hệ thống](docs/architecture/system-overview.md)
- [API Specification](docs/api/api-specification.yaml)
- [Quy chuẩn code](docs/guides/coding-standards.md)
- [Hướng dẫn đóng góp](CONTRIBUTING.md)

## 👥 Nhóm Phát Triển

| Thành viên | Vai trò |
|-----------|---------|
| | |

## 📄 License

Dự án này được cấp phép theo [MIT License](LICENSE).
