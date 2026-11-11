# CLAUDE.md: Quy chuẩn đặt tên nhánh và commit

> **Dành cho AI/coding assistant:** Mỗi khi tạo nhánh hoặc commit trong repo này, PHẢI theo file này.
> - KHÔNG tự bịa kiểu đặt tên nhánh hay kiểu commit message khác.
> - Không rõ công việc được giao là gì thì **hỏi người dùng** trước khi đặt tên, không đoán.

---

## 1. Đặt tên nhánh

Tên nhánh phản ánh **tính chất công việc được bàn giao**, không dùng mã ticket.

```
<type>/<mo-ta-cong-viec>
```

### Chọn `type` theo bản chất công việc

| Type | Công việc được giao là... |
|---|---|
| `feat` | Làm thêm chức năng / thành phần mới |
| `fix` | Sửa lỗi |
| `hotfix` | Sửa gấp lỗi đang xảy ra trên production |
| `refactor` | Dọn dẹp, đổi cấu trúc code nhưng không đổi hành vi |
| `perf` | Làm chạy nhanh hơn / nhẹ hơn |
| `docs` | Chỉ viết hoặc sửa tài liệu |
| `test` | Chỉ thêm hoặc sửa test |
| `chore` | Việc vặt: cập nhật thư viện, dọn file, cấu hình |
| `ci` | Sửa pipeline CI/CD |

### Cách viết phần mô tả

- Nói **việc cần làm**, dạng `động-từ + đối-tượng`, **2-5 từ**.
- Chữ **thường**, **kebab-case** (nối bằng dấu `-`), **không dấu**, không khoảng trắng, không gạch dưới, không chữ hoa.
- Đủ cụ thể để người khác đọc tên nhánh là hiểu nhánh làm gì.
- Toàn bộ tên nhánh ≤ 60 ký tự.

### Ví dụ ĐÚNG

```
feat/add-patch-user-endpoint
feat/add-score-export-job
fix/cursor-pagination-off-by-one
fix/null-score-crash
hotfix/payment-callback-timeout
refactor/extract-cursor-helpers
perf/add-index-user-email
docs/api-guidelines
test/cover-delete-user
chore/update-fastapi
ci/add-coverage-report
```

### Ví dụ SAI

| Sai | Lý do | Đúng |
|---|---|---|
| `Thanh_new branch` | Chữ hoa, khoảng trắng, gạch dưới, không có type | `feat/add-login-page` |
| `test` / `fix` / `update` | Không nói gì về công việc | `fix/null-score-crash` |
| `feature/AddUser` | Sai type, chữ hoa | `feat/add-user-endpoint` |
| `feat/them-chuc-nang-user` | Có thể đọc được nhưng không đúng quy tắc tiếng Anh, dễ lệch | `feat/add-user-endpoint` |
| `feat/DNA-123-add-user` | Không dùng mã ticket | `feat/add-user-endpoint` |
| `feat/add-user-endpoint-and-fix-pagination-and-update-docs` | Quá dài, gộp nhiều việc | Tách thành nhiều nhánh |

### Quy tắc khác

- Một nhánh = **một công việc**. Việc khác thì mở nhánh khác.
- Tạo nhánh từ `main` mới nhất:

```bash
git switch main
git pull origin main
git switch -c feat/add-patch-user-endpoint
```

- Tên nhánh viết bằng **tiếng Anh**.

---

## 2. Commit message: Conventional Commits

```
<type>(<scope>): <mô tả ngắn>

[body: giải thích VÌ SAO đổi]

[footer: BREAKING CHANGE: ...]
```

### Type được phép

`feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `build`, `ci`, `chore`, `style`, `revert`. KHÔNG dùng type nào khác.

| Type | Dùng khi |
|---|---|
| `feat` | Thêm tính năng mới |
| `fix` | Sửa bug |
| `refactor` | Đổi cấu trúc code, không đổi hành vi |
| `perf` | Cải thiện hiệu năng |
| `docs` | Chỉ sửa tài liệu |
| `test` | Thêm / sửa test |
| `build` | Build, dependency (`requirements.txt`, Dockerfile) |
| `ci` | Pipeline CI/CD |
| `chore` | Việc vặt không ảnh hưởng code chạy |
| `style` | Format, khoảng trắng, không đổi logic |
| `revert` | Hoàn tác một commit trước |

### Quy tắc viết

1. **Dòng đầu ≤ 72 ký tự**, không có dấu chấm cuối.
2. Viết **tiếng Anh**, thể **mệnh lệnh**, chữ thường sau dấu hai chấm: `add`, `fix`, `remove`, `rename`. KHÔNG dùng `added`, `fixed`, `fixes`, `adding`.
3. `scope` là module / khu vực bị ảnh hưởng, chữ thường, kebab-case: `users`, `auth`, `pagination`, `scoring`. Bỏ scope nếu thay đổi chạm nhiều nơi không rõ ràng.
4. **Một commit làm một việc.** Không gộp "sửa bug + refactor + thêm tính năng". Thay đổi lớn thì tách thành nhiều commit.
5. Có `body` khi thay đổi không tự giải thích: viết **vì sao** đổi. Cách dòng đầu một dòng trống, mỗi dòng ≤ 72 ký tự.
6. Thay đổi phá vỡ tương thích: thêm `!` sau type/scope **và** footer `BREAKING CHANGE: <mô tả>`.
7. KHÔNG ghi mã ticket.
8. **Commit KHÔNG được có Claude (hay bất kỳ AI nào) là author hoặc co-author:**
   - KHÔNG thêm dòng `Co-Authored-By: Claude ...` hay bất kỳ `Co-Authored-By` nào ở footer.
   - KHÔNG thêm dòng `Generated with Claude Code`, `🤖 ...` hay chữ ký/quảng cáo tương tự vào message.
   - KHÔNG đổi `user.name` / `user.email` trong git config (cả local lẫn global) và KHÔNG dùng `--author=` hay `GIT_AUTHOR_*` để đặt tác giả khác.
   - Tác giả commit luôn là danh tính Git sẵn có của người dùng. Nếu `git config user.name` / `user.email` đang trống hoặc trông không phải của người dùng thì **dừng lại và hỏi**, không tự điền.
   - Message chỉ gồm `type(scope): mô tả`, body (nếu cần) và footer `BREAKING CHANGE` (nếu có), không có gì khác.

### Ví dụ ĐÚNG

```
feat(users): add PATCH endpoint for partial user update
fix(users): return 409 when email already exists
fix(scoring): handle null score before saving
refactor(pagination): extract cursor helpers to schemas
test(users): cover PATCH success, 404 and 409 cases
docs(api): add PATCH response examples
build: bump fastapi to 0.115.0
ci: add coverage report to test job
```

Có body và breaking change:

```
feat(api)!: rename first_name to given_name

Align field naming with the identity provider so profile sync
does not need a mapping layer.

BREAKING CHANGE: response field first_name was renamed to given_name
```

### Ví dụ SAI

| Sai | Lý do | Đúng |
|---|---|---|
| `update code` | Không có type, không nói gì | `fix(users): handle null email in PATCH` |
| `Fixed bug.` | Sai thể, có dấu chấm, không có type | `fix(auth): reject expired refresh token` |
| `feat: Add Patch.` | Viết hoa, có dấu chấm | `feat: add patch endpoint` |
| `feat: add patch, fix pagination, update readme` | Gộp 3 việc | Tách thành 3 commit |
| `wip`, `test`, `asdf`, `.` | Vô nghĩa | Viết đúng chuẩn |
| `feat(users): add patch (DNA-123)` | Không ghi mã ticket | `feat(users): add patch endpoint` |
| Footer `Co-Authored-By: Claude <noreply@anthropic.com>` | Không được có AI là co-author | Xóa dòng này |
| Cuối message có `🤖 Generated with Claude Code` | Không được có chữ ký AI | Xóa dòng này |
| `git commit --author="Claude <...>"` | Không được đặt AI làm tác giả | Để mặc định danh tính Git của người dùng |

---

## 3. Checklist trước mỗi lần tạo nhánh / commit

**Tạo nhánh**
- [ ] Đã hiểu rõ công việc được giao (không rõ thì hỏi)
- [ ] Dạng `type/mo-ta-cong-viec`, chữ thường, kebab-case, không dấu, 2-5 từ mô tả
- [ ] Type đúng với bản chất công việc
- [ ] Tạo từ `main` mới nhất
- [ ] Không có mã ticket, không có khoảng trắng hay chữ hoa

**Commit**
- [ ] Không đang đứng ở `main`
- [ ] Đã xem `git status` và `git diff --staged`, chỉ chứa thay đổi có chủ đích
- [ ] Không có secret (`.env`, key, token) hay file rác
- [ ] Commit chỉ làm **một việc**
- [ ] Type hợp lệ, dòng đầu ≤ 72 ký tự, thể mệnh lệnh, không dấu chấm cuối
- [ ] Message KHÔNG có `Co-Authored-By`, `Generated with Claude Code` hay chữ ký AI nào
- [ ] Không đổi git config, không dùng `--author`: tác giả là người dùng

---

## 4. Khi không chắc

Hỏi người dùng thay vì đoán, đặc biệt khi:
- Không rõ công việc thuộc `feat`, `fix` hay `refactor`.
- Thay đổi có thể là một hoặc nhiều commit.
- Quy chuẩn này mâu thuẫn với yêu cầu của người dùng: nêu rõ mâu thuẫn và để họ chọn.