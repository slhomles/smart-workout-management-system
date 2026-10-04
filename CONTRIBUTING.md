# Đóng Góp Cho Smart Workout AI

Cảm ơn bạn đã quan tâm đến việc đóng góp cho dự án! 🎉

## 📋 Quy Trình

1. **Fork** repository
2. Tạo **branch** mới từ `develop`: `git checkout -b feature/ten-tinh-nang`
3. **Commit** theo convention: `git commit -m "feat(module): mô tả ngắn"`
4. **Push** branch: `git push origin feature/ten-tinh-nang`
5. Tạo **Pull Request** vào branch `develop`

## 📝 Commit Convention

Format: `<type>(<scope>): <description>`

| Type | Mô tả |
|------|--------|
| `feat` | Tính năng mới |
| `fix` | Sửa lỗi |
| `docs` | Thay đổi tài liệu |
| `style` | Format code (không ảnh hưởng logic) |
| `refactor` | Tái cấu trúc code |
| `test` | Thêm/sửa tests |
| `chore` | Cập nhật build, dependencies |

**Scope**: `backend`, `frontend`, `ai`, `db`, `docs`, `infra`

**Ví dụ:**
```
feat(backend): thêm API endpoint cho exercise wiki
fix(ai): sửa lỗi tính góc khớp trong pose estimation
docs(api): cập nhật swagger specification
```

## 🌿 Branching Strategy

```
main          ← Production (chỉ merge từ develop, có tag version)
  └── develop ← Integration branch
       ├── feature/xxx  ← Tính năng mới
       ├── fix/xxx      ← Sửa lỗi
       └── hotfix/xxx   ← Sửa lỗi khẩn cấp (merge thẳng vào main)
```

## ✅ Checklist Trước Khi Tạo PR

- [ ] Code đã được format đúng chuẩn
- [ ] Đã viết tests cho tính năng mới
- [ ] Tất cả tests pass
- [ ] Đã cập nhật tài liệu (nếu cần)
- [ ] PR description mô tả rõ thay đổi
