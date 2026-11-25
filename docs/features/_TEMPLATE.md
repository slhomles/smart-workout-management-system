---
module: ten-module                      # kebab-case, dùng làm tên thư mục flow
branch: feat/add-ten-module-api         # Claude_git.md §1: <type>/<dong-tu-doi-tuong>, 2-5 từ
commit_scope: ten-module                # scope trong commit message (Claude_git.md §2)
owner: phuc                             # key thành viên trong scripts/agent-flow/team.json (nhận Telegram)
gates: spec, protected, clean, pytest, tc, coverage, ruff, mypy
coverage_min: 70                        # doc 05 §10
allow_core_changes: no                  # yes nếu module được sửa file core (doc 05 §7.2)
allow_new_dependencies: no              # yes nếu được thêm thư viện vào requirements.txt
---

# Module: <Tên module>

> Spec này là **đầu vào duy nhất** của agent flow (`scripts/agent-flow/README.md`).
> Agent không được sửa file này. Muốn đổi phạm vi hay test case thì bạn sửa file rồi chạy lại runner.
> Copy file này thành `docs/features/<module>.md` và điền vào.

## 1. Mục tiêu

<Module giải quyết việc gì cho người dùng, thuộc chức năng số mấy của đề tài.>

## 2. Phạm vi

| Method | Path | Mô tả | Quyền (permission) |
|---|---|---|---|
| GET | `/api/v1/<prefix>` | ... | public / `<permission>` |

- Tiền tố route theo doc 05 §6.3.
- Bảng/view DB dùng: `<schema>.<table>` (xem `docs/database/data-dictionary.md`).

## 3. Ngoài phạm vi

- ...

## 4. Tài liệu bắt buộc đọc (ngoài bảng CLAUDE.md §2)

- ...

## 5. Test cases

Mỗi dòng là một tiêu chí nghiệm thu. Flow chỉ xong khi **mọi** dòng có ít nhất một test gắn
`@pytest.mark.tc("<ID>")` và tất cả các test đó pass. ID dạng `ABC-01` (chữ hoa, gạch ngang, số).

| ID | Đối tượng | Tình huống | Kết quả mong đợi |
|---|---|---|---|
| MOD-01 | `GET /api/v1/<prefix>` | Không truyền tham số | `200`, `Page[...]`, `limit` mặc định, `pagination.has_more` đúng |
| MOD-02 | `GET /api/v1/<prefix>/{id}` | `id` không tồn tại | `404`, `error.code = "<resource>_not_found"` |

## 6. Quyết định đã chốt / trả lời câu hỏi của agent

- ...
