# Frontend standards (React Native + Expo)

> Áp dụng cho mọi code trong `frontend/` do người hoặc AI viết. Tài liệu này **bổ sung** cho `CLAUDE.md`, `04-auth-strategy.md` §7 và `Claude_api_respone.md`. Khi mâu thuẫn về API, auth, git thì `CLAUDE.md` §3 quyết định.
> Từ khoá PHẢI / KHÔNG ĐƯỢC / NÊN theo nghĩa RFC 2119. Nhóm chốt ngày 27/11/2026.

## 1. Nền tảng

| Hạng mục | Lựa chọn |
|---|---|
| Framework | Expo (managed, **dev build**, không dùng Expo Go vì cần thư viện camera native), TypeScript `strict` |
| Điều hướng | `expo-router`, route nằm trong `src/app/` |
| Gọi API | Axios, một client duy nhất ở `src/services/api/client.ts` |
| Dữ liệu từ server | `@tanstack/react-query` |
| Trạng thái phiên đăng nhập | `zustand` (`src/store/session.ts`) |
| Lưu token | `expo-secure-store` (doc 04 §7 ý 1) |
| Test | `jest-expo` + `@testing-library/react-native` |
| Lint | `eslint` (cấu hình `eslint-config-expo`) + `prettier` |

Thư viện đã có trong `frontend/package.json` thì dùng lại. Thêm thư viện mới PHẢI được spec cho phép (`allow_new_dependencies: yes`), vì `package.json` và lockfile là file bảo vệ.

## 2. Cấu trúc thư mục

Giữ layout của `frontend/README.md`, thêm `src/app/` cho `expo-router`:

```
src/
├── app/                    # CHỈ file route mỏng: import màn hình từ src/screens rồi export default
│   ├── _layout.tsx         # provider (QueryClient, theme, session) — file core
│   ├── (auth)/login.tsx …
│   └── (tabs)/_layout.tsx  # 5 tab cố định — file core; module KHÔNG thêm tab
├── screens/<feature>/      # màn hình + component riêng của feature
├── components/common|layout|charts/   # component dùng chung (Button, Card, Screen, …)
├── services/api/           # client.ts, errors.ts, session-storage.ts — file core
├── services/<feature>.ts   # hàm gọi API của feature, có kiểu
├── hooks/<feature>/        # hook React Query của feature
├── types/<feature>.ts      # kiểu TypeScript khớp schema backend
├── store/                  # zustand
├── styles/theme.ts         # token màu, chữ, khoảng cách — file core
├── constants/ · utils/
```

- `<feature>` dùng đúng tên thư mục màn hình đã có: `auth`, `home`, `exercise-wiki`, `workout`, `dashboard`, `progress-gallery`, `ai-trainer`, `equipment-scanner`, `profile`.
- Module chỉ thêm hoặc sửa file trong thư mục của feature mình, cộng các file route của feature trong `src/app/`. Component dùng chung mới thì thêm vào `components/`, KHÔNG sửa component chung đang có trừ khi spec cho phép.
- **File core** (chỉ sửa khi spec có `allow_core_changes: yes`):
  - `src/app/_layout.tsx`, `src/app/(tabs)/_layout.tsx`;
  - `src/services/api/`;
  - `src/styles/theme.ts`;
  - `jest.config.js`, `jest.setup.ts`, `eslint.config.js`, `tsconfig.json`, `app.config.ts`.

## 3. Gọi API

- Base URL: `process.env.EXPO_PUBLIC_API_URL + '/api/v1'`, đặt trong `frontend/.env` (không commit; mẫu ở `.env.example`). Thiết bị thật trỏ tới IP Tailscale của VM.
- Đọc dữ liệu qua `res.data`, không có `.data.data`. Danh sách có dạng `{ data, pagination: { next_cursor, has_more } }`, nên dùng `useInfiniteQuery` với `getNextPageParam = (p) => p.pagination.has_more ? p.pagination.next_cursor : undefined` (`Claude_api_respone.md` §5).
- Đọc lỗi qua `getErrorCode(err)` trong `src/services/api/errors.ts`. Hàm này trả `error.response.data.error.code`, chữ thường (CLAUDE.md §3.1).
  - Rẽ nhánh theo `code`, KHÔNG so sánh `message`.
  - Lỗi `validation_error` thì hiện từng field theo `details[].field`.
- Kiểu dữ liệu giữ **snake_case** như JSON (`created_at`), KHÔNG đổi sang camelCase.
  - ID dữ liệu user là `string` (UUID); ID danh mục (`exercise_id`, `equipment_id`, `muscle_group_id`…) là `number` (doc 05 §2.4).
  - Thời gian là chuỗi ISO UTC; chỉ đổi sang giờ địa phương khi hiển thị.
- Đơn vị API là SI (kg, cm, giây, mili giây). Đổi đơn vị theo `unit_system` của `GET /auth/me` khi hiển thị.
- Token theo doc 04 §7 (single-flight refresh, ghi cả hai token trước khi retry, logout xoá SecureStore), nhưng đọc mã lỗi chữ thường: `token_expired`, `token_invalid`, `token_reused`, `account_disabled`. Logic này nằm sẵn trong `client.ts` của `fe-core`; module KHÔNG tự gắn header hay tự refresh.
- Chỉ gọi endpoint đã có trong Swagger (`/docs`) của backend (doc 05 §1.3). Thiếu endpoint thì dừng lại và hỏi, KHÔNG tự bịa.

## 4. Giao diện

- Màu, cỡ chữ, khoảng cách, bo góc chỉ lấy từ `src/styles/theme.ts` (token), KHÔNG viết mã màu hay số pixel rời rạc trong màn hình. Có chế độ sáng và tối.
- Dùng component chung: `Screen`, `Button`, `Card`, `TextField`, `EmptyState`, `ErrorState`, `LoadingState`.
- Mỗi màn hình gọi API PHẢI có đủ 4 trạng thái: đang tải, lỗi (có nút thử lại), rỗng, có dữ liệu.
- Chữ hiển thị bằng tiếng Việt. Số theo định dạng Việt Nam (`1.234,5`), ngày `dd/mm/yyyy`.
- Phần tử bấm được cao tối thiểu 44 pt và có `accessibilityLabel`.
- Ảnh hoặc giao diện mẫu nhóm chọn để tham khảo được mô tả ở §8. Chỉ học phong cách và bố cục, KHÔNG dùng logo, tên, hình hay icon có bản quyền của app khác.

## 5. Kích thước và đặt tên

| Đối tượng | Ngưỡng (cảnh báo) |
|---|---|
| Component hoặc hàm | ≤ 40 dòng logic (không tính JSX thuần), ≤ 4 tham số (props gom thành một object có kiểu) |
| File | ≤ 300 dòng (file test được dài hơn) |
| Độ lồng | ≤ 3 cấp |

- Component dùng `PascalCase`, file component trùng tên (`ExerciseCard.tsx`). Hook bắt đầu bằng `use`. File khác dùng kebab-case.
- Biến boolean bắt đầu bằng `is`, `has`, `can`.
- KHÔNG dùng `any`. Kiểu chưa rõ thì dùng `unknown` rồi thu hẹp.
- KHÔNG để `console.log` trong code. KHÔNG log token hay dữ liệu cá nhân.

## 6. Kiểm thử

- Mỗi test case trong spec module là **ít nhất một** test jest, có **ID của test case ở đầu tên test**: `it('FEA-01 hiện lỗi khi sai mật khẩu', …)`. Cổng `tc` của agent flow đọc ID này từ `jest --json`.
- Test màn hình dùng `@testing-library/react-native`:
  - giả API bằng cách mock module `src/services/<feature>.ts`, hoặc mock adapter của Axios;
  - KHÔNG gọi backend thật trong jest.
- Logic thuần (tính góc, FSM đếm rep, định dạng số) PHẢI có unit test cho cả biên và lỗi.
- Coverage tối thiểu theo `coverage_min` của spec, mặc định 70% dòng, tính trên file module thêm hoặc sửa.
- Lệnh chạy trong `frontend/`: `npx tsc --noEmit`, `npx eslint .`, `npx jest --coverage`.

## 7. Kiểm tra bằng máy (agent flow)

Spec có `target: frontend` thì `check_done.py` chạy các cổng `spec`, `protected`, `clean`, `tsc`, `eslint`, `jest`, `tc`, `coverage`. Cổng `standards` áp dụng các ngưỡng ở §5 cho file `.ts`/`.tsx`; như bản Python (`coding-standards.md` §6), đây chỉ là cảnh báo. Agent không nhìn thấy giao diện, nên owner PHẢI mở app trên điện thoại kiểm tra sau khi module merge, thấy lỗi thì chạy lại module.

## 8. Giao diện tham khảo

Chưa chốt. Khi nhóm gửi ảnh chụp app tham khảo, cập nhật mục này (bảng màu, kiểu chữ, khoảng cách, kiểu card, nút, tab bar) và `src/styles/theme.ts`. Trước đó dùng theme trung tính của `fe-core`.

## 9. Checklist trước khi báo xong một màn hình

- [ ] Chỉ gọi endpoint có trong Swagger; đọc `res.data`, lỗi qua `getErrorCode`
- [ ] Đủ 4 trạng thái: tải, lỗi, rỗng, dữ liệu
- [ ] Không có màu hay kích thước viết cứng ngoài `theme.ts`; có chế độ tối
- [ ] Kiểu khớp schema backend (snake_case, UUID là string, ID danh mục là number)
- [ ] Mỗi test case trong spec có test jest mang đúng ID
- [ ] `tsc`, `eslint`, `jest` sạch; không có `any`, không `console.log`
- [ ] Không sửa file core, không thêm thư viện khi spec chưa cho phép
