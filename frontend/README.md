# Smart Workout AI - Frontend (React Native + Expo)

> Đọc trước khi sửa: **`docs/guides/frontend-standards.md`** (toàn bộ, nhất là §8 design system và bản đồ màn hình),
> ảnh mẫu `docs/ui-refs/home-workout/`, và `AGENT_RESOURCES.md` (dữ liệu bài tập, mặc định tập luyện, UI màn tập, muscle map).

Expo SDK 58 · React Native 0.88 · TypeScript strict · expo-router · React Query · zustand · jest-expo.

## Cấu trúc

```
frontend/
├── src/
│   ├── app/                      # route mỏng (expo-router): chỉ `export { default } from '@/screens/...'`
│   │   ├── _layout.tsx           # font, React Query, phiên đăng nhập — file core
│   │   ├── (tabs)/_layout.tsx    # 4 tab: Tập luyện · Khám phá · Báo cáo · Cá nhân — file core
│   │   ├── (tabs)/index|explore|report|profile.tsx
│   │   ├── (auth)/login.tsx
│   │   └── dev/components.tsx    # màn DEV xem bộ component
│   ├── screens/<feature>/        # màn hình theo feature (home, exercise-wiki, workout, dashboard, ...)
│   ├── components/common/        # component dùng chung theo ảnh mẫu (import từ '@/components/common')
│   ├── services/api/             # client.ts (axios + refresh token), errors.ts, session-storage.ts — file core
│   ├── services/<feature>.ts     # hàm gọi API có kiểu
│   ├── hooks/<feature>/ · types/<feature>.ts · store/ (zustand) · constants/ · utils/
│   └── styles/theme.ts           # token màu, chữ, bo góc, khoảng cách — file core
├── __tests__/                    # test jest (hoặc *.test.ts(x) cạnh file)
├── jest.config.js · jest.setup.ts · eslint.config.js · tsconfig.json · app.json
└── .env.example                  # EXPO_PUBLIC_API_URL
```

Các màn trong `src/screens/*` hiện là **giữ chỗ**. Mỗi module FE của agent flow thay màn của mình (xem bản đồ §8.3).
`src/constants/features.ts` có `AUTH_REQUIRED = false`; module `fe-auth` bật cờ này khi xong màn đăng nhập.

## Chạy

```powershell
cd frontend
npm ci
copy .env.example .env        # sửa EXPO_PUBLIC_API_URL = IP Tailscale/LAN của máy chạy backend
npx expo start                # web: phím w; điện thoại: cần dev build (expo-dev-client), không dùng Expo Go
npx expo run:android          # build dev build lên máy Android (cần Android SDK) hoặc: npx eas-cli build --profile development
```

Cần Node.js ≥ 22.13 (Expo 58).

## Kiểm tra (giống cổng của agent flow và CI)

```powershell
npx tsc --noEmit
npx eslint .
npx jest --coverage
```

Test đặt ID test case của spec ở **đầu tên test**: `it('FEA-01 hiện lỗi khi sai mật khẩu', ...)`.
Màn có gọi API phải đủ 4 trạng thái: tải, lỗi, rỗng, dữ liệu. Giả API bằng cách mock `src/services/<feature>.ts`.
