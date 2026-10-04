# Smart Workout AI - Frontend

> ⚠️ Framework chưa được chọn. Thư mục này đã chuẩn bị sẵn cấu trúc tổng quát.

## 📁 Cấu Trúc Đã Chuẩn Bị

```
src/
├── assets/          # Tài nguyên tĩnh (images, icons, fonts, animations)
├── components/      # UI components tái sử dụng
│   ├── common/      # Button, Input, Modal, Card...
│   ├── layout/      # Header, Footer, Sidebar, Navigation
│   └── charts/      # Biểu đồ tương tác
├── screens/         # Các màn hình chính
│   ├── auth/        # Đăng nhập, Đăng ký
│   ├── home/        # Trang chủ
│   ├── exercise-wiki/
│   ├── workout/
│   ├── dashboard/
│   ├── progress-gallery/
│   ├── ai-trainer/
│   ├── equipment-scanner/
│   └── profile/
├── services/        # API client & service layer
├── store/           # State management
├── hooks/           # Custom hooks
├── utils/           # Helper functions
├── constants/       # Hằng số
├── navigation/      # Cấu hình điều hướng
├── styles/          # Global styles & theme
└── types/           # Type definitions
```

## 🔧 Lựa Chọn Framework

| Option | Phù hợp khi |
|--------|-------------|
| **React Native** | Cần app mobile (iOS + Android) - đề cập nhiều trong mô tả |
| **Flutter** | Cần app mobile + hiệu năng camera cao |
| **Next.js** | Cần web app thay vì mobile |
