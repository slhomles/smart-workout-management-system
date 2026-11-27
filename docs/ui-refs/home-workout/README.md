# Giao diện mẫu: app "Home Workout"

Ảnh chụp app tham khảo do nhóm chọn (27/11/2026). Giao diện đồ án học **phong cách và bố cục** của các màn này. Token, component và bản đồ màn hình chi tiết ở `docs/guides/frontend-standards.md` §4, §8.

KHÔNG dùng lại tài sản của app mẫu trong app đồ án:
- logo hay tên "HOME WORKOUT";
- ảnh người mẫu, hình động tác có watermark;
- nút PRO hay Premium;
- quảng cáo (dải quảng cáo ở cuối một số ảnh chỉ là quảng cáo của app mẫu, bỏ qua).

Ảnh và GIF bài tập của đồ án lấy theo `AGENT_RESOURCES.md` §1.

| Ảnh | Màn của mẫu | Dùng cho (module FE) | Điểm cần học |
|---|---|---|---|
| `01-home-top.jpg` | Trang chủ, phần đầu | `fe-workout` | Tiêu đề VIẾT HOA đậm + ngọn lửa chuỗi ngày; thanh tìm kiếm; thẻ "Mục tiêu hàng tuần" với dải 7 ngày (hôm nay có vòng xanh); băng chuyền thẻ gradient xanh (nhãn góc, lưới 2×2 thông số, nút trắng dạng viên thuốc) |
| `02-home-body-focus.jpg` | Trang chủ, "Cơ thể tập trung" | `fe-workout`, `fe-exercise-wiki` | Chip nhóm cơ (đang chọn: nền xanh nhạt, viền xanh); danh sách ảnh vuông bo góc + tên đậm + "phút • số bài" + tia sét độ khó; ô lọc nhanh có icon viền xanh |
| `03-home-custom-recommended.jpg` | Trang chủ, banner và gợi ý | `fe-workout` | Banner gradient "Tạo của riêng bạn" kèm nút trắng; nhãn vàng "MỚI"; tiêu đề mục kèm "Thêm ›" |
| `04-home-stretch-goals.jpg` | Trang chủ, khởi động và mục tiêu | `fe-workout`, `fe-exercise-wiki` | Thẻ ảnh ngang có chữ trắng đè; nhóm danh sách trong thẻ trắng lớn, có mũi tên tròn đen |
| `05-home-body-focus-arms.jpg` | Trang chủ, đổi chip nhóm cơ | `fe-exercise-wiki` | Trạng thái chip khi đổi lựa chọn |
| `06-explore-search.jpg` | Tìm kiếm / Khám phá | `fe-exercise-wiki` | Vòng tròn ảnh nhóm cơ; ô "Loại bài tập" (đồ án dùng cho **Thiết bị**); chip CẤP ĐỘ 3 màu (xanh, cam, đỏ); ô thời lượng |
| `07-challenges.jpg` | Danh sách thử thách | `fe-workout` (giáo án mẫu) | Tab lọc dạng viên thuốc (đang chọn là nền xanh đặc); thẻ gradient lớn xanh và cam, CTA trắng |
| `08-plan-detail.jpg` | Chi tiết giáo án | `fe-workout` | Ảnh lớn phía trên, tấm trắng bo góc phủ lên; dòng thông số có icon; nút gradient cyan → xanh to; danh sách bài có tay kéo, thumbnail, thời lượng hoặc số lần, nút đổi bài. **Đồ án hiển thị số hiệp × số rep × kg** |
| `09-workout-ready.jpg` | Màn sẵn sàng tập | `fe-workout` | Hình động tác lớn; chữ "ĐÃ SẴN SÀNG TẬP!" xanh rất đậm; vòng đếm ngược. **Đồ án thêm nút "AI đếm rep và chỉnh tư thế"** khi bài có luật AI |
| `10-workout-rest.jpg` | Màn nghỉ giữa hiệp | `fe-workout` | Nền xanh toàn màn; "TIẾP THEO x/y"; đồng hồ trắng rất lớn; nút "+20s" và "Bỏ qua" |
| `11-report-history-weight.jpg` | Báo cáo, phần đầu | `fe-dashboard` | Thẻ 3 chỉ số (icon, số lớn, nhãn); lịch sử tuần có ngày đã tập tô tròn xanh kèm tick; chuỗi ngày; nút "Ghi lại" cân nặng. **Đồ án bỏ kcal**, thay bằng tổng khối lượng (kg) |
| `12-report-weight-bmi.jpg` | Báo cáo, cân nặng và BMI | `fe-dashboard` | Biểu đồ đường với lưới chấm và bong bóng giá trị tối màu; thang BMI nhiều màu có kim chỉ; chiều cao kèm nút sửa |
| `13-settings.jpg` | Cài đặt | `fe-auth` (tab Cá nhân) | Dòng cài đặt: icon trong ô vuông bo màu, nhãn, chấm đỏ báo mới, mũi tên ›. **Đồ án thay "Sao lưu" bằng thông tin tài khoản**, bỏ Premium |

Thanh tab dưới của mẫu có 4 mục (Tập luyện, Khám phá, Báo cáo, Cài đặt). Đồ án dùng 4 tab: **Tập luyện · Khám phá · Báo cáo · Cá nhân**. AI không có tab riêng; nó gắn vào từng bài tập (xem `frontend-standards.md` §8).
