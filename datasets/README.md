# Dataset cho AI Models

> ⚠️ **Lưu ý**: Các file dataset lớn (ảnh, video) không được commit trực tiếp vào Git.

## 📂 Cấu Trúc

```
datasets/
├── gym-equipment/       # Ảnh thiết bị phòng gym (cho YOLOv8 classification)
├── pose-references/     # Ảnh/video tư thế chuẩn (cho pose estimation)
└── README.md
```

## 📥 Cách Sử Dụng

### Option 1: Git LFS (Recommended)
```bash
git lfs install
git lfs pull
```

### Option 2: Tải thủ công
Tải dataset từ Google Drive/S3 và giải nén vào thư mục tương ứng.

## 📊 Dataset Sources
- **Gym Equipment**: Custom dataset, fine-tune từ COCO
- **Pose References**: Tham khảo từ [Fitness Dataset](https://github.com/example)
