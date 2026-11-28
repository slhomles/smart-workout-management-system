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
| Lưu token | `expo-secure-store` (doc 04 §7 ý 1); riêng bản web dev/demo dùng `localStorage` (ngoại lệ doc 04 §7) |
| Test | `jest-expo` + `@testing-library/react-native` |
| Lint | `eslint` (cấu hình `eslint-config-expo`) + `prettier` |
| Giao diện | `expo-linear-gradient` (gradient), `@expo/vector-icons` (icon), `@expo-google-fonts/be-vietnam-pro` (font), `react-native-svg` + `react-native-body-highlighter` (muscle map), `expo-image` (GIF và ảnh) |

Thư viện đã có trong `frontend/package.json` thì dùng lại. Thêm thư viện mới PHẢI được spec cho phép (`allow_new_dependencies: yes`), vì `package.json` và lockfile là file bảo vệ.

## 2. Cấu trúc thư mục

Giữ layout của `frontend/README.md`, thêm `src/app/` cho `expo-router`:

```
src/
├── app/                    # CHỈ file route mỏng: import màn hình từ src/screens rồi export default
│   ├── _layout.tsx         # provider (QueryClient, theme, session) — file core
│   ├── (auth)/login.tsx …
│   └── (tabs)/_layout.tsx  # 4 tab cố định (§8.3) — file core; module KHÔNG thêm tab
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

- Giao diện theo app mẫu ở `docs/ui-refs/home-workout/` và design system §8. Trước khi dựng một màn PHẢI mở ảnh mẫu tương ứng (§8.3).
- Màu, cỡ chữ, khoảng cách, bo góc chỉ lấy từ `src/styles/theme.ts` (token §8.1), KHÔNG viết mã màu hay số pixel rời rạc trong màn hình. Có chế độ sáng và tối.
- Dùng component chung §8.2 (`ScreenHeader`, `Chip`, `HeroCard`, `ListItem`, `GradientButton`, …) cùng `Screen`, `TextField`, `EmptyState`, `ErrorState`, `LoadingState`. Thiếu component thì thêm vào `components/`, cùng phong cách.
- Mỗi màn hình gọi API PHẢI có đủ 4 trạng thái: đang tải, lỗi (có nút thử lại), rỗng, có dữ liệu.
- Chữ hiển thị bằng tiếng Việt. Số theo định dạng Việt Nam (`1.234,5`), ngày `dd/mm/yyyy`.
- Phần tử bấm được cao tối thiểu 44 pt và có `accessibilityLabel`.
- Chỉ học phong cách và bố cục của app mẫu, KHÔNG dùng logo, tên, ảnh người mẫu, hình động tác hay quảng cáo của app mẫu. Ảnh và GIF bài tập lấy từ backend (nguồn ở `AGENT_RESOURCES.md` §1).

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

## 8. Giao diện mẫu, design system và bản đồ màn hình

Mẫu là app "Home Workout", ảnh và ghi chú ở `docs/ui-refs/home-workout/`. Khi dựng màn hình PHẢI mở đúng ảnh mẫu ghi trong bảng §8.3 và spec module. Màn của đồ án giữ phong cách của mẫu nhưng nội dung theo API backend: đồ án ghi set, rep, kg ở phòng gym, còn app mẫu tập theo thời gian ở nhà.

### 8.1. Token (`src/styles/theme.ts`)

| Nhóm | Giá trị |
|---|---|
| Nền | `background #F5F6F8`, `surface #FFFFFF`, `surfaceMuted #EEF1F6` (ô lọc, chip chưa chọn), `divider #E7E9EE` |
| Màu chính | `primary #1E5EFF`, `primarySoft #EEF3FF`, `primaryGradient #19C6FF → #1E5EFF` (nút chính), `heroGradient #2F80FF → #0B4DFF` (thẻ lớn) |
| Màu nhấn | `accentOrange #FF7A2F` (thẻ phụ), `flame #FF4D4F` (chuỗi ngày, cảnh báo), `badgeYellow #FFD84D` (nhãn "MỚI"), `tagPeach #FBE3C4` (nhãn trên thẻ) |
| Cấp độ | `beginner` nền `#E8EEFF` chữ `#1E5EFF` · `intermediate` nền `#FFF1E4` chữ `#FF8A1E` · `advanced` nền `#FFE9EC` chữ `#F0384F`. Độ khó hiển thị 1–3 tia sét `primary` (tia chưa đạt màu `#D5D9E0`) |
| Chữ | `text #111318`, `textMuted #9A9FA8`, `link #1E5EFF`, `onPrimary #FFFFFF` |
| Font | **Be Vietnam Pro** (`@expo-google-fonts/be-vietnam-pro`): Regular 400, SemiBold 600, Bold 700, ExtraBold 800 |
| Cỡ chữ | `display` 28 ExtraBold VIẾT HOA (tiêu đề màn: "BÁO CÁO") · `title` 22 Bold (tiêu đề mục) · `itemTitle` 18 SemiBold · `body` 16 Regular · `meta` 15 Regular `textMuted` ("18 phút • 19 bài tập") · `number` 40–64 ExtraBold (số liệu lớn, đồng hồ) |
| Bo góc | `card` 20 · `hero` 24 (thẻ lớn, tấm trượt chi tiết) · `thumb` 20 · `pill` 999 (nút, chip, ô tìm kiếm) |
| Khoảng cách | Lề màn 16 · giữa các mục 32 · trong thẻ 16–20 · giữa phần tử 8/12 |
| Thanh tab | 4 tab, nền `surface`, icon đặc; tab đang chọn icon và chữ `primary`, tab khác `textMuted` |
| Chế độ tối | `background #0F1115`, `surface #1A1D23`, `surfaceMuted #242832`, `text #F3F4F6`; giữ nguyên `primary` và gradient |

### 8.2. Component dùng chung (`src/components/common/`, dựng sẵn trong `fe-core`; `LineChartCard`, `BmiScale` do `fe-dashboard` dựng, `MuscleHeatmap` do `fe-workout` dựng, cùng thư mục)

| Component | Theo ảnh mẫu | Mô tả |
|---|---|---|
| `ScreenHeader` | 01, 11 | Tiêu đề `display`; bên phải là ngọn lửa kèm số ngày tập liên tiếp (không có nút PRO) |
| `SearchBar` | 01, 06 | Ô `pill` nền `surfaceMuted`, icon kính lúp, nút "Huỷ" khi đang gõ |
| `SectionHeader` | 03, 04 | Tiêu đề `title`; tuỳ chọn nhãn "MỚI" và link "Thêm ›" |
| `Chip` | 02, 05, 07 | `pill`. Đang chọn: nền `primarySoft`, viền 2 px `primary`, chữ `primary`; biến thể `solid` (07): nền `primary`, chữ trắng. Chưa chọn: nền `surfaceMuted`, chữ `textMuted` |
| `LevelChip` | 06 | Chip theo màu cấp độ §8.1 |
| `DifficultyBolts` | 02 | 1–3 tia sét |
| `FilterTile` | 02, 06 | Ô bo `card` nền `surfaceMuted`, icon viền `primary` và nhãn |
| `HeroCard` | 01, 07 | Thẻ `heroGradient` (hoặc cam): nhãn góc nền `tagPeach`, tiêu đề VIẾT HOA trắng, lưới 2×2 thông số (icon trong ô vuông mờ, giá trị, nhãn), nút trắng `pill` chữ `primary` có mũi tên tròn |
| `ListItem` | 02, 04 | Ảnh vuông 96–120 bo `thumb`; tên `itemTitle`; dòng `meta`; `DifficultyBolts` hoặc `LevelChip`; tuỳ chọn mũi tên tròn đen hoặc nhãn "AI" |
| `MediaThumb` | — | Hiện GIF hoặc ảnh bài tập (GIF 180 px không phóng quá ~2 lần; không có GIF thì luân phiên 2 ảnh JPG ~0,8 giây, theo `AGENT_RESOURCES.md` §1.1, §1.2). Thiếu media thì dùng khối gradient kèm icon nhóm cơ |
| `WeekStrip` | 01, 11 | 7 ngày (T2…CN); hôm nay có vòng `primary`; ngày đã tập là hình tròn `primary` đặc kèm tick |
| `StatCard` | 11 | 3 cột: icon, số `number` nhỏ (40), nhãn `textMuted` |
| `GradientButton` | 08 | Nút `pill` cao 56, `primaryGradient`, chữ trắng Bold |
| `DetailSheet` | 08 | Ảnh hoặc media lớn phía trên; tấm `surface` bo góc trên 24 phủ lên; nút back và menu tròn mờ trên ảnh |
| `CountdownRing` | 09 | Vòng tiến độ `primary` trên nền xám, số `number` ở giữa |
| `FullscreenTimer` | 10 | Nền `primary` toàn màn; dòng "TIẾP THEO x/y"; đồng hồ trắng rất lớn; nút "+20s" (nền trắng mờ) và "Bỏ qua" (nền trắng, chữ `primary`) |
| `SettingsRow` | 13 | Icon trắng trong ô vuông bo 12 có màu; nhãn; tuỳ chọn chấm đỏ; mũi tên › |
| `LineChartCard` | 12 | Biểu đồ đường lưới chấm; điểm vòng `primary`; bong bóng giá trị nền tối |
| `BmiScale` | 12 | Thanh 6 dải màu (xanh đậm → đỏ) có kim chỉ tam giác |
| `MuscleHeatmap` | — | `react-native-body-highlighter` (`AGENT_RESOURCES.md` §3.3), màu theo `recovery_status` |
| Trạng thái | — | `LoadingState`, `EmptyState`, `ErrorState` (có nút "Thử lại") |

### 8.3. Bản đồ màn hình (4 tab)

AI không có tab riêng. Chỉnh tư thế và đếm rep phụ thuộc động tác, nên chỉ mở từ **một bài tập cụ thể**: từ chi tiết bài tập, hoặc từ hiệp đang tập. Nút AI chỉ hiện khi bài có luật tư thế (`supports_ai_tracking` và bảng luật `shared/constants/pose-rules.json`).

| Tab | Màn | Ảnh mẫu | Module FE | API |
|---|---|---|---|---|
| **Tập luyện** | Trang chủ (theo thứ tự): `ScreenHeader`; `SearchBar`; "Mục tiêu tuần" kèm `WeekStrip`; thẻ "Hôm nay" (buổi đã lên lịch); "Giáo án mẫu" là băng chuyền `HeroCard`; "Trạng thái phục hồi" là `MuscleHeatmap` thu gọn; chip "Cơ thể tập trung"; banner "Tạo giáo án của riêng bạn" | 01–05, 07 | `fe-workout` | `/scheduled-workouts`, `/plan-templates`, `/workout-plans`, `/recovery`, `/dashboard` |
| | Chi tiết giáo án: `DetailSheet`, `GradientButton` "Bắt đầu"; danh sách bài ghi **số hiệp × rep × kg**; nút đổi bài thay thế | 08 | `fe-workout` | `/workout-plans/{id}`, `/exercises/{id}/alternatives` |
| | Đang tập: sẵn sàng (`CountdownRing`); bảng hiệp tách **mục tiêu / lần trước / hôm nay** (`AGENT_RESOURCES.md` §3.1); nghỉ (`FullscreenTimer`, lưu thời điểm kết thúc); tổng kết. Mỗi hiệp có nút "AI đếm rep và chỉnh tư thế" | 09, 10 | `fe-workout` (+ `fe-ai-trainer`) | `/workout-sessions/...` |
| **Khám phá** | Tìm kiếm và lọc: vòng tròn nhóm cơ, `FilterTile` theo **thiết bị**, `LevelChip`; kết quả là `ListItem` có `MediaThumb` (nhãn "AI" nếu có luật). Ô "Quét thiết bị" ở đầu | 06, 02 | `fe-exercise-wiki`, `fe-equipment-scanner` | `/exercises`, `/muscle-groups`, `/equipment`, `/ai/equipment-scans` |
| | Chi tiết bài tập: `DetailSheet` (GIF lớn, các bước, lỗi thường gặp, nhóm cơ trên `MuscleHeatmap`, bài thay thế, "Thêm vào buổi tập", "Tập với AI") | 08 | `fe-exercise-wiki` | `/exercises/{id}` |
| (từ bài tập) | Camera AI cho một bài: khung xương phủ lên người, đoạn sai chuyển `flame`; rep và tempo cỡ `number`; tổng kết % đúng form | 09 | `fe-ai-trainer` | `/ai/pose-analyses` |
| (từ bài tập/hiệp) | Phân tích video: tải video lên, theo dõi trạng thái, xem kết quả | — | `fe-video-analysis` | `/ai/video-jobs` |
| **Báo cáo** | `StatCard` (số buổi, tổng khối lượng kg, phút; **không có kcal**); "Lịch sử" kèm `WeekStrip` và chuỗi ngày; "Cân nặng" kèm `LineChartCard` và nút "Ghi lại"; BMI kèm `BmiScale`, BMR, TDEE, % mỡ; "Phục hồi"; "Xuất báo cáo tuần"; lối vào "Nhật ký ảnh" | 11, 12 | `fe-dashboard` | `/dashboard`, `/body/...`, `/reports`, `/recovery` |
| | Nhật ký ảnh: lưới ảnh theo thời gian, so sánh Before/After bằng thanh trượt | — | `fe-progress-gallery` | `/progress-photos`, `/photo-comparisons`, `/media` |
| **Cá nhân** | Thẻ tài khoản (tên, email); `SettingsRow`: Hồ sơ, Mục tiêu, Đơn vị đo, Thiết bị đăng nhập, Đổi mật khẩu, Đăng xuất | 13 | `fe-auth` | `/auth/me`, `/auth/devices`, `/auth/change-password`, `/body/goals` |
| (ngoài tab) | Đăng nhập, đăng ký: cùng phong cách, `GradientButton` | — | `fe-auth` | `/auth/login`, `/auth/register` |

Nội dung bài tập (tên tiếng Việt, các bước, GIF, ảnh) lấy từ backend; backend nạp từ các nguồn trong `AGENT_RESOURCES.md` §1. Mặc định số hiệp, số rep và thời gian nghỉ theo `AGENT_RESOURCES.md` §2 (ACSM 2026), ghi nguồn trong comment. KHÔNG tự bịa số liệu tập luyện.

## 9. Checklist trước khi báo xong một màn hình

- [ ] Chỉ gọi endpoint có trong Swagger; đọc `res.data`, lỗi qua `getErrorCode`
- [ ] Đủ 4 trạng thái: tải, lỗi, rỗng, dữ liệu
- [ ] Đã mở ảnh mẫu tương ứng (§8.3); dùng component chung §8.2
- [ ] Không có màu hay kích thước viết cứng ngoài `theme.ts`; có chế độ tối
- [ ] Kiểu khớp schema backend (snake_case, UUID là string, ID danh mục là number)
- [ ] Mỗi test case trong spec có test jest mang đúng ID
- [ ] `tsc`, `eslint`, `jest` sạch; không có `any`, không `console.log`
- [ ] Không sửa file core, không thêm thư viện khi spec chưa cho phép
