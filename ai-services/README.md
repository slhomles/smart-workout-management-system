# Smart Workout AI - AI Services

> Python-based AI/ML microservices cho phân tích tư thế, đếm rep, nhận diện thiết bị.

## 📁 Cấu Trúc

```
src/
├── pose-estimation/       # Phân tích tư thế (MediaPipe + YOLOv8-Pose)
├── rep-counter/           # Đếm Rep/Set & Đo Tempo (FSM)
├── equipment-recognition/ # Nhận diện thiết bị gym (YOLOv8 Classification)
├── recovery-prediction/   # Dự đoán phục hồi cơ bắp (PyTorch)
├── image-processing/      # Xử lý ảnh (Watermark, resize)
├── workers/               # Background workers (Queue consumers)
├── common/                # Config, logger, storage
└── app.py                 # Entry point
```

## 🚀 Cài Đặt

```bash
# Tạo virtual environment
python -m venv venv
.\venv\Scripts\activate  # Windows

# Cài dependencies
pip install -r requirements.txt

# Chạy service
python src/app.py
```

## 🤖 Models Sử Dụng

| Model | Mục đích | Chạy ở đâu |
|-------|----------|-------------|
| MediaPipe BlazePose | Pose estimation realtime | Mobile (Edge) |
| YOLOv8-Pose | Pose estimation chuyên sâu | Server (GPU) |
| YOLOv8 Classification | Nhận diện thiết bị gym | Server |
| PyTorch Custom | Dự đoán phục hồi cơ | Server |
