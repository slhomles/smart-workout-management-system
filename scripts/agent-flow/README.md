# Agent flow: 2 agent tự xây một module, chạy không cần người trực

Flow cho Claude Code tự làm một module từ spec đến khi **mọi test case trong spec pass**, kể cả khi bạn không ngồi trước máy.
Flow dùng chính tài khoản Claude đang đăng nhập trong `claude` CLI và chạy trên máy này.

```
run_flow.py (vòng lặp, không phải AI)
  │  mỗi iteration: tạo phiên `claude -p --agent orchestrator` mới, context sạch
  ▼
orchestrator ── giao 1 task / lần ──► implementer (subagent)
  │  ▲                                  viết test (TDD) + code, không commit
  │  └──── báo cáo DONE/BLOCKED ────────┘
  │  tự kiểm chứng: git diff + check_done.py + review theo docs
  │  đạt → commit · không đạt → rework (tối đa 3 lần) · thiếu tài liệu → question
  ▼
state/ (state.json, journal.md): trí nhớ giữa các iteration
  │
  ▼
runner tự chạy check_done.py trên HEAD → chỉ dừng "XONG" khi:
  state.status = approved  VÀ  approved_sha = HEAD  VÀ  mọi cổng đạt
```

| File | Vai trò |
|---|---|
| `.claude/agents/orchestrator.md` | Agent điều phối + kiểm duyệt (không viết code sản phẩm) |
| `.claude/agents/implementer.md` | Agent triển khai, mỗi lần làm đúng một task |
| `scripts/agent-flow/run_flow.py` | Vòng lặp chạy không giám sát: worktree, preflight, giới hạn sử dụng, phát hiện kẹt, báo cáo |
| `scripts/agent-flow/check_done.py` | Cổng "xong" chạy độc lập với model |
| `scripts/agent-flow/tc_plugin.py` | Plugin pytest ánh xạ `@pytest.mark.tc("ID")` → kết quả |
| `scripts/agent-flow/flow-settings.json` | Quyền cho chế độ không giám sát + tắt chữ ký AI trong commit |
| `scripts/agent-flow/team.example.json` | **Mẫu file thành viên**: danh tính git, module phụ trách, bot Telegram. Bản thật `team.json` bị gitignore |
| `scripts/agent-flow/team.py` | Đọc `team.json`, xoay vòng tác giả commit |
| `scripts/agent-flow/flow_commit.py` | Con đường commit duy nhất của agent: kiểm tra message, chọn tác giả theo vòng xoay |
| `scripts/agent-flow/notify.py` | Gửi tiến độ qua Telegram: bot riêng của owner module + bot chung |
| `scripts/agent-flow/bot.py` | **Bot điều khiển qua Telegram**: `/run`, `/status`, `/stop`, `/answer`, `/owner`; hàng đợi mỗi lúc một flow |
| `scripts/agent-flow/modules.json` | Danh mục module (tính năng trong Mô tả dự án ↔ route/schema ở doc 05 §6.3 ↔ owner) |
| `.claude/agents/spec-writer.md` | Agent chỉ đọc: soạn spec module khi có lệnh `/run` |
| `scripts/agent-flow/perm_mcp.py` | Hỏi quyền qua Telegram (nút Cho phép/Từ chối, chờ tối đa 30 phút) |
| `docs/features/_TEMPLATE.md` | Mẫu spec module (bạn viết test case ở đây) |

## 1. Chuẩn bị một lần

```powershell
# Python venv cho backend (runner và cổng dùng venv này)
py -3.11 -m venv backend\.venv
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt

# backend/.env: DB + Redis chạy trên VM team-stack (doc 05 §8.2), cần bật Tailscale.
#   POSTGRES_HOST=100.72.175.1, POSTGRES_DB=smart_workout_db, REDIS_HOST=100.72.175.1
# Runner chỉ tự bật Docker local khi backend/.env trỏ tới localhost (làm việc offline).

# Kiểm tra agent + quyền (gọi Claude một lần, không sửa file):
python scripts\agent-flow\run_flow.py --smoke
```

Smoke test phải cho thấy: agent là `orchestrator`, lệnh `git config` bị **BLOCKED**, python chạy được, và subagent `implementer` trả lời.
Nếu `git config` không bị chặn, nghĩa là `flow-settings.json` không được nạp. Đừng chạy flow cho đến khi sửa xong.

## 2. Viết spec module

Copy `docs/features/_TEMPLATE.md` thành `docs/features/<module>.md`, rồi điền:
- frontmatter: `module`, `branch` (theo `Claude_git.md`), `commit_scope`, các cổng, quyền sửa core / thêm thư viện;
- **mục "Test cases"**: mỗi dòng một tiêu chí nghiệm thu, ID dạng `ABC-01`. Đây là định nghĩa của "xong".

Kiểm tra spec: `python scripts\agent-flow\check_done.py --spec docs\features\<module>.md --meta`

## 3. Chạy

```powershell
# Kiểm tra môi trường (venv, .env, DB, git identity, spec) mà không gọi Claude:
python scripts\agent-flow\run_flow.py docs\features\<module>.md --preflight-only

# Chạy ở cửa sổ riêng (đóng VS Code vẫn chạy tiếp):
Start-Process -WindowStyle Minimized python -ArgumentList "scripts\agent-flow\run_flow.py","docs\features\<module>.md"
```

Runner tự làm các việc sau:
- tạo **git worktree riêng** `..\smart_workout-flow\<module>\repo` trên nhánh của spec, từ `main` mới nhất. Thư mục bạn đang làm việc không bị đụng tới;
- chặn Windows tự sleep trong lúc chạy (tự hoàn nguyên khi xong). **Gập nắp laptop thì máy vẫn có thể sleep**: cắm sạc và chỉnh "When I close the lid" thành "Do nothing";
- khi chạm giới hạn sử dụng của tài khoản: chờ đến giờ reset (hoặc 30 phút) rồi chạy tiếp, không tính là một iteration;
- dừng khi: xong (0), bị chặn cần bạn trả lời (2), 3 iteration liền không tiến triển (3), hết 40 iteration (4).

Tuỳ chọn hay dùng: `--max-iterations 60`, `--model sonnet` (tiết kiệm hạn mức), `--iteration-timeout 7200`, `--skip-services`.

## 4. Theo dõi và nhận kết quả

Mọi thứ nằm trong `..\smart_workout-flow\<module>\`:

| File | Nội dung |
|---|---|
| `RUN-REPORT.md` | **Đọc đầu tiên khi quay lại**: kết luận, cổng, danh sách commit, câu hỏi cho bạn |
| `flow.log` | Nhật ký runner theo thời gian |
| `state\state.json` | Kế hoạch task, trạng thái, câu hỏi |
| `state\journal.md` | Nhật ký orchestrator theo từng iteration |
| `state\REPORT.md` | Báo cáo nghiệm thu của orchestrator: TC → test → commit, checklist tài liệu |
| `logs\iter-NNN.*` | Output thô của từng phiên Claude |

Xem lại code: `git log main..<branch>` hoặc mở thư mục worktree trong VS Code. Runner **không push, không mở PR**. Việc đó là của bạn, làm theo `Claude_git.md`.

## 5. Khi flow bị chặn (exit 2)

Orchestrator gặp chỗ tài liệu thiếu hoặc mâu thuẫn (ví dụ mã lỗi chưa đăng ký ở `Claude_api_respone.md` §10) thì nó **không đoán**. Nó ghi câu hỏi vào `state.json`, sau đó `RUN-REPORT.md` liệt kê lại. Bạn trả lời bằng một trong hai cách:
- ghi câu trả lời vào `state\ANSWERS.md`, rồi chạy lại với `--resume-blocked`; hoặc
- sửa spec (mục 6 "Quyết định đã chốt") hoặc sửa tài liệu theo CLAUDE.md §5, rồi chạy lại. Runner tự nhận ra spec đã đổi.

Chạy lại cùng lệnh thì flow tiếp tục từ state cũ, không làm lại từ đầu.

## 6. File thành viên `team.json`

Mọi thông tin về thành viên nằm trong **một file**: `scripts/agent-flow/team.json`. File này đã bị gitignore vì chứa token. Tạo bằng `copy scripts\agent-flow\team.example.json scripts\agent-flow\team.json`, rồi điền mỗi người một mục trong `members`:

| Trường | Ý nghĩa |
|---|---|
| key (`phuc`, …) | Mã thành viên, ghi vào `owner:` trong spec |
| `name` | Tên hiện trên commit và trên Telegram |
| `github` | Username GitHub (để tham khảo) |
| `git_email` | **Email noreply GitHub** của người đó (GitHub → Settings → Emails, bật "Keep my email addresses private"), dạng `1234567+username@users.noreply.github.com`. GitHub tính commit cho tài khoản có email này |
| `modules` | Các module người đó phụ trách (để tham khảo) |
| `telegram_token`, `telegram_chat_id` | Bot riêng (xem mục 7) |

Ô nào còn để dạng `<...>` được coi là chưa điền.

### Xoay vòng tác giả commit (`git.rotation`)

Đây là ngoại lệ đã được ghi vào `Claude_git.md` §2.8. Agent không gọi `git commit` được (bị chặn); nó commit qua `flow_commit.py`, và script này chọn tác giả:

| Giá trị | Cách xoay |
|---|---|
| `owner` (đang dùng) | Mọi commit của module mang tên **người phụ trách**, tức `owner` trong spec. Spec thiếu `owner` hoặc owner chưa có `git_email` hợp lệ thì preflight chặn |
| `commit` | Mỗi commit một người kế tiếp theo thứ tự trong `members`. Bộ đếm dùng chung mọi module (`..\smart_workout-flow\git-rotation.json`) |
| `branch` | Cả nhánh module một người, lần lượt theo từng module mới. **Nên chọn khi nhóm squash merge** (doc 05 §9.3), vì squash gộp các commit trong PR làm một |
| `off` | Dùng danh tính git sẵn có của máy |

Script chỉ dùng `git -c user.name=… -c user.email=…` cho từng commit, không sửa git config. Khi đang bật xoay vòng mà một thành viên thiếu hoặc sai `git_email`, preflight sẽ báo lỗi và flow không chạy, để tránh gán commit cho email điền sai. Sau mỗi iteration, runner kiểm tra: commit nào mang email ngoài danh sách sẽ bị cảnh báo.

Push dùng tài khoản của bạn như bình thường; không cần mật khẩu hay SSH key của người khác. Lưu ý: commit chỉ hiện trên biểu đồ đóng góp sau khi đã vào nhánh mặc định, và không có dấu "Verified" vì không được ký bằng khoá của người được ghi tên.

## 7. Thông báo Telegram

Runner (không phải agent) gửi tin. Token chỉ nằm trong `team.json`.

| Bot | Nhận tin gì |
|---|---|
| Bot riêng của từng thành viên (3 bot) | Chỉ tin của module mà người đó là `owner` trong spec |
| Bot chung (gửi vào group nhóm) | Mọi tin của mọi module |

Các loại tin:
- bắt đầu flow;
- tiến độ sau mỗi iteration: số TC pass, task, commit mới kèm tác giả, tóm tắt của orchestrator;
- **câu hỏi mới** cần người trả lời, gửi ngay khi orchestrator ghi vào `state.json`;
- **thao tác bị chặn vì quyền**: mỗi thao tác báo một lần, kèm lệnh cụ thể;
- tạm dừng vì giới hạn sử dụng;
- kết thúc: xong / bị chặn kèm câu hỏi / kẹt / hết iteration / lỗi / crash / môi trường chưa sẵn sàng.

Mọi tin đều gửi tới cả bot riêng của owner lẫn group chung.

**Cài đặt:**
1. Trên Telegram, nhắn `@BotFather` → `/newbot` **4 lần**: 3 bot riêng và 1 bot chung. Lưu lại 4 token.
2. Mỗi thành viên mở bot riêng của mình và bấm **Start**. Tạo group gồm 3 người, thêm bot chung vào, rồi gõ `/start` trong group.
3. Điền `telegram_token` của từng thành viên và `telegram.common.token` vào `team.json`.
4. Lấy chat_id: `python scripts\agent-flow\notify.py chat-id phuc` (tương tự cho từng thành viên), `python scripts\agent-flow\notify.py chat-id common` cho group. Điền vào `telegram_chat_id` và `telegram.common.chat_ids`.
5. Gửi thử: `python scripts\agent-flow\notify.py test`. Mỗi bot phải báo `OK`.

`--preflight-only` sẽ cảnh báo nếu `owner` của spec chưa được cấu hình. Thiếu `team.json` thì flow vẫn chạy, chỉ không gửi tin và không xoay vòng tác giả.

## 8. Điều khiển qua Telegram (`bot.py`)

Bật bot trên máy này (máy phải luôn bật, có Tailscale, và `claude` đã đăng nhập):

```powershell
Start-Process -WindowStyle Minimized python -ArgumentList "scripts\agent-flow\bot.py"
```

Bot chặn Windows tự sleep trong lúc chạy. Muốn bot tự bật khi đăng nhập Windows, tạo một Task Scheduler chạy đúng lệnh trên với trigger "At log on".

| Lệnh | Việc |
|---|---|
| `/run <module>` | Nếu chưa có spec: agent `spec-writer` soạn `docs/features/<module>.md` từ Mô tả dự án + doc 05 + tài liệu DB. Bot kiểm tra spec (cấu trúc, owner, `error.code` phải có trong §10), gửi bảng test case lên Telegram, rồi **chạy luôn** flow (nhóm đã chọn không cần duyệt spec) |
| `/run <module> --respec` | Soạn lại spec rồi chạy |
| `/run <module> --force` | Chạy lại module đã đánh dấu `"status": "done"` trong `modules.json`. Không có `--force` thì bot từ chối để tránh làm trùng việc đã xong (vd `core` đã làm tay qua PR #2, #3) |
| `/status` | Flow đang chạy (iteration, TC pass, task, yêu cầu quyền đang chờ), hàng đợi, kết quả gần nhất |
| `/stop <module>` | Dừng flow đang chạy hoặc bỏ khỏi hàng đợi. `/run` lại sẽ tiếp tục từ chỗ dừng |
| `/answer <module> <nội dung>` | Trả lời câu hỏi của agent. Flow đang bị chặn sẽ tự được xếp hàng chạy tiếp |
| `/owner <module> <thành viên>` | Đổi người phụ trách (commit của module mang tên người này) |
| `/modules`, `/help` | Danh mục module, hướng dẫn |

- Gõ lệnh trong group cho bot chung, hoặc nhắn riêng bot của mình. Trong group nên gõ dạng `/run@ten_bot_chung …`, hoặc tắt privacy mode của bot chung (@BotFather → `/setprivacy` → Disable) để bot nhận được `/run …`.
- Chỉ 3 tài khoản Telegram trong `team.json` ra lệnh và bấm nút được; người khác nhận "⛔".
- Mỗi lúc chỉ chạy **một** flow (DB dùng chung, doc 05 §8.2); các lệnh `/run` khác xếp hàng.
- **Xin quyền**: mặc định **không hỏi**. Thao tác thuộc danh sách `ask` trong `flow-settings.json` (hiện để trống) hoặc thao tác auto mode không chắc chắn bị từ chối ngay, agent tự làm cách khác hoặc ghi câu hỏi (trả lời bằng `/answer`). Muốn duyệt bằng nút ✅/⛔ trên Telegram thì bật bot với `bot.py --ask-permissions`: khi đó yêu cầu được gửi lên owner + group, ai bấm trước thì quyết định, quá 30 phút không ai bấm thì tự từ chối. Thao tác trong danh sách `deny` (push, reset --hard, git config, …) luôn bị chặn, không hỏi.
- Bot tắt giữa chừng thì flow vẫn chạy; bật lại bot sẽ nhận lại flow đó. Riêng nút xin quyền chỉ hoạt động khi bot đang bật.
- Lệnh `notify.py chat-id` dùng `getUpdates`, nên chỉ chạy được khi bot đang tắt.

## 9. Hàng rào an toàn

- **Model không tự tuyên bố xong được.** Runner dùng bản `check_done.py` của repo chính, không dùng bản trong worktree, và tự chạy trên HEAD.
  Các cổng: spec hợp lệ · không đụng file bảo vệ (docs, schema DB baseline, tooling, core nếu không cho phép) · không xoá test · worktree sạch · toàn bộ pytest pass · **mọi TC có test gắn marker và đều pass** (skip/xfail không tính) · coverage · ruff · mypy.
- Spec và file agent trong worktree bị sửa thì runner khôi phục và ghi cảnh báo.
- `flow-settings.json` chặn: `git commit` và `git -c` trực tiếp (agent phải commit qua `flow_commit.py`), push/pull/merge/rebase/switch/checkout/reset --hard/stash, git config, `docker compose down`, xoá volume, web, hỏi người dùng. `pip install/uninstall` được phép chạy không cần hỏi; việc thêm thư viện vào `requirements.txt` vẫn bị cổng `protected` chặn khi spec để `allow_new_dependencies: no`.
- `flow_commit.py` từ chối message sai `Claude_git.md` §2 (type, chữ thường, tối đa 72 ký tự, dấu chấm cuối, có `Co-Authored-By`/chữ ký AI), từ chối commit khi đang ở `main`/`develop` hoặc chưa stage gì.
- Chế độ quyền mặc định là `auto`, kèm `--permission-prompts none`: thao tác nào cần hỏi thì bị từ chối ngay, nên flow không treo chờ người bấm.

## 10. Giới hạn cần biết

- Máy phải bật, có mạng, và Docker Desktop phải chạy. Muốn chạy khi tắt máy thì cần chuyển sang cloud (routine), nhưng khi đó PostgreSQL thật phải được dựng trong môi trường cloud.
- Mọi phiên dùng chung hạn mức của tài khoản. Phiên Claude Code tương tác bạn mở cùng lúc sẽ dùng chung hạn mức đó.
- `git fetch origin main` chạy một lần lúc tạo worktree. Nếu `main` cục bộ và `origin/main` đã rẽ nhánh, runner dừng và yêu cầu bạn đồng bộ trước.
- Marker `tc` chỉ được đăng ký khi chạy qua plugin. Chạy `pytest` thường sẽ có cảnh báo `PytestUnknownMarkWarning`, không ảnh hưởng kết quả. Muốn tắt cảnh báo thì Core owner thêm `markers = tc(*ids): ...` vào cấu hình pytest.
