# Coding standards

> Áp dụng cho mọi code Python do người hoặc AI viết trong repo này. Tài liệu này **bổ sung** cho `CLAUDE.md` và các tài liệu trong `docs/architecture/`; khi mâu thuẫn về API, auth, DB, git thì `CLAUDE.md` §3 quyết định.
> Từ khoá PHẢI / KHÔNG ĐƯỢC / NÊN theo nghĩa RFC 2119.

## 1. Kích thước (ngưỡng cảnh báo)

| Đối tượng | Ngưỡng |
|---|---|
| Hàm | ≤ 40 dòng |
| File | ≤ 300 dòng |
| Tham số của hàm | ≤ 4 |
| Độ lồng (if/for/while/try/with) | ≤ 3 cấp |
| Cyclomatic complexity | ≤ 10 |

Vượt ngưỡng thì tách theo trách nhiệm, KHÔNG tách cơ học chỉ để đủ số dòng.

## 2. Thiết kế

- Mỗi hàm, mỗi module một trách nhiệm (SRP). Chọn giải pháp đơn giản nhất chạy được (KISS, YAGNI).
- Chỉ trích xuất code dùng chung khi logic lặp lại từ lần thứ 3. Code đã có sẵn trong repo (`CRUDBase`, `AppException`, `Page`, fixture trong `conftest.py`…) thì dùng lại, KHÔNG viết lại.
- Theo cấu trúc thư mục, pattern và thư viện đang có trong repo (layout ở `05-tooling-workflow.md` §6.2, §7.2).

## 3. Đặt tên và comment

- Tên thể hiện ý định, dùng thuật ngữ nghiệp vụ thống nhất của dự án; KHÔNG viết tắt tự chế.
- Biến boolean bắt đầu bằng `is_`, `has_`, `can_`.
- Comment giải thích "tại sao", KHÔNG mô tả lại code làm gì.

## 4. Lỗi và bảo mật

- KHÔNG nuốt exception. Log lỗi kèm ngữ cảnh nhưng KHÔNG log dữ liệu cá nhân.
- KHÔNG hardcode secret. Test và fixture chỉ dùng dữ liệu giả lập.

## 5. Quy trình

- Đọc code liên quan trước khi sửa. KHÔNG refactor ngoài phạm vi task.
- KHÔNG thêm dependency mới khi chưa hỏi.
- Mỗi thay đổi kèm test; chạy formatter, linter, test trước khi báo hoàn thành.
- Báo rõ phần nào chưa kiểm thử.

## 6. Kiểm tra bằng máy (agent flow)

Cổng `standards` (`scripts/agent-flow/standards.py`, gọi từ `check_done.py`) đo các ngưỡng ở mục 1 bằng thư viện chuẩn (`ast`), theo các quy ước sau:

- Chỉ xét file `.py` được **thêm hoặc sửa** từ `BASE_SHA` của module. Code cũ vượt ngưỡng (ví dụ `body_service.py` hơn 300 dòng) không bị tính cho tới khi có người sửa nó.
- Bỏ qua `backend/alembic/versions/`. Giới hạn 300 dòng mỗi file chỉ áp dụng cho code ứng dụng, không áp dụng cho file test (một file test API gom nhiều test case nên dài tự nhiên); các ngưỡng theo hàm vẫn áp dụng cho test.
- Số tham số không tính `self`, `cls` và tham số FastAPI tiêm vào route handler (mặc định là `Depends(...)` hoặc `Security(...)`), vì endpoint luôn có `db` và `current_user`. Nhiều query parameter thì gom vào một model Pydantic.
- Complexity là xấp xỉ McCabe: 1 + số `if`, `for`, `while`, `except`, `with`, `assert`, biểu thức điều kiện, điều kiện trong comprehension và toán tử `and`/`or`.
- Đây là **cảnh báo**, không làm cổng trượt. Mỗi cảnh báo PHẢI được sửa, hoặc orchestrator ghi lý do chấp nhận vào `REPORT.md` trước khi duyệt.
