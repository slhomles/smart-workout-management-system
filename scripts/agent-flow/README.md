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
| `scripts/agent-flow/timeline.py`, `transcript.py`, `timeline_render.py` | Dựng và hiển thị timeline thời gian của từng phiên (mục 4) |
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

### Target: backend, ai-services, frontend

Frontmatter `target` (mặc định `backend`) chọn thư mục code, bộ cổng, file core và venv (`targets.py`):

| Target | Thư mục | Cổng mặc định | Cần cài trên máy chạy bot |
|---|---|---|---|
| `backend` | `backend/` | spec, protected, clean, pytest, tc, coverage, ruff, mypy, standards | `backend\.venv`, `backend/.env`, Tailscale tới VM |
| `ai-services` | `ai-services/` | như backend | `ai-services\.venv` (`py -3.11 -m venv ai-services\.venv`, rồi `pip install -r ai-services\requirements.txt`) |
| `frontend` | `frontend/` | spec, protected, clean, tsc, eslint, jest, tc, coverage, standards | Node.js + npm; cổng tự `npm ci` khi `node_modules` lệch `package-lock.json` (`check_frontend.py`) |

- Frontend gắn test case bằng ID ở đầu tên test jest (`it('FEA-01 …')`).
- Cổng `standards` của frontend lấy cảnh báo kích thước từ eslint (`max-lines`, `max-lines-per-function`, `max-params`, `max-depth`, `complexity`).
- Mỗi target có bản tóm tắt quy tắc riêng (`_shared/rules-digest[-<target>].md`), lập từ danh sách `DIGEST_SOURCES` trong `run_flow.py`.

### Phụ thuộc giữa module (`depends_on` trong `modules.json`)

- Tự xếp hàng (`/auto on`) chỉ xếp một module khi mọi module trong `depends_on` đã vào `main`: `status: done` trong `modules.json`, hoặc `run.json` của module đó có `merged_pr`.
- Module đang chờ phụ thuộc hiện ở `/status` (dòng "Chờ phụ thuộc vào main"). Phụ thuộc bị chặn thì module phụ thuộc cứ chờ; hàng đợi vẫn chạy các module khác.
- `/run <module>` bằng tay không kiểm phụ thuộc (người chạy tự chịu).

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
- chạy lại module trên worktree có sẵn (`/run`, `--resume-blocked`) mà `main` đã có commit mới: **gộp `main` mới nhất vào nhánh trước** (giải xung đột như bên dưới), để module dùng được code các module đã merge (tắt bằng `--no-sync`);
- **xong thì tự đưa module vào `main`** (ngoại lệ agent flow, doc 05 §9.3; tắt bằng `--no-merge`), xem "Đưa module vào main" bên dưới;
- dừng khi: xong và đã vào main (0), bị chặn cần bạn trả lời (2), 3 iteration liền không tiến triển (3), hết 40 iteration (4), xong nhưng chưa vào main được (6).

### Đưa module vào main

Khi orchestrator duyệt và mọi cổng đạt, runner (`integrate.py`, `pr_publish.py`):
1. `git fetch` rồi gộp `origin/main` vào nhánh module (`git merge --no-ff`).
2. Giải xung đột: `router.py` và file hai phía thêm giống hệt nhau được giải tự động (`merge_resolvers.py`); còn lại agent **`integrator`** giải, giữ tính năng của cả hai phía. Commit gộp đi qua `flow_commit.py` (`chore(<scope>): merge main into <branch>`), tác giả theo `team.json`.
3. Đặt BASE mới = `origin/main` vừa gộp, chạy **cổng đầy đủ**. Trượt thì `integrator` sửa (tối đa 2 lần, commit `fix(<scope>): adapt module to latest main`).
4. Push nhánh (không bao giờ `--force`), mở PR vào `main` (hoặc dùng PR đang mở), **chờ CI xanh**, rồi `gh pr merge --merge` (merge commit để giữ tác giả từng commit). PR báo xung đột vì `main` vừa đổi thì quay lại bước 1 (tối đa 3 vòng).

Bất kỳ bước nào thất bại (xung đột không giải được, cổng vẫn trượt, CI đỏ, push bị từ chối): runner **không merge**, nhánh giữ nguyên, exit 6, báo Telegram kèm lý do. Xử lý xong thì `/merge <module>` (hoặc `run_flow.py <spec> --merge-only`; thêm `--dry-run` để chỉ gộp + chạy cổng, không push). Chỉ runner push/merge; agent LLM vẫn bị chặn mọi lệnh git ghi và `gh`.

Tuỳ chọn hay dùng: `--max-iterations 60`, `--model sonnet` (tiết kiệm hạn mức), `--iteration-timeout 3600` (mặc định 2700 giây), `--time-box-minutes 90` (mặc định 60, `0` = tắt), `--skip-services`.

Mục tiêu một module xong trong khoảng 1 giờ, nhờ:
- **Bản tóm tắt quy tắc dùng chung** (`<flow-root>/_shared/rules-digest.md`): orchestrator đọc toàn bộ tài liệu một lần rồi tóm tắt; implementer và các lần sau chỉ đọc bản tóm tắt cộng đúng các mục được chỉ định (ngoại lệ ở CLAUDE.md §1). Runner băm các tài liệu nguồn (`DIGEST_SOURCES` trong `run_flow.py`); tài liệu đổi thì brief báo "CẦN TẠO LẠI". Muốn ép lập lại thì xoá `_shared/rules-digest.sha`.
- **Cổng nhanh chỉ chạy test của task**: `check_done.py ... --gates spec,protected,pytest,tc,ruff,standards --tests <file test>`. Toàn bộ suite chỉ chạy ở cổng của runner và cổng cuối.
- **Task gộp lớn hơn**: 4–6 task mỗi module.
- **Mốc thời gian**: quá `--time-box-minutes` phút chạy thật (không tính chờ hạn mức) thì runner báo Telegram một lần, flow vẫn chạy tiếp.

## 4. Theo dõi và nhận kết quả

Mọi thứ nằm trong `..\smart_workout-flow\<module>\`:

| File | Nội dung |
|---|---|
| `RUN-REPORT.md` | **Đọc đầu tiên khi quay lại**: kết luận, cổng, danh sách commit, câu hỏi cho bạn |
| `flow.log` | Nhật ký runner theo thời gian |
| `state\state.json` | Kế hoạch task, trạng thái, câu hỏi |
| `state\journal.md` | Nhật ký orchestrator theo từng iteration |
| `state\REPORT.md` | Báo cáo nghiệm thu của orchestrator: TC → test → commit, checklist tài liệu |
| `state\TIMELINE.md` | **Thời gian đi đâu**: từng iteration, từng task, bước chậm nhất (xem mục "Xem thời gian đi đâu" bên dưới) |
| `state\timeline.jsonl` | Sự kiện thời gian của runner: cổng (chạy thật hay dùng lại kết quả cũ, mất bao lâu), chờ hạn mức, ranh giới iteration |
| `logs\iter-NNN.*` | Output thô của từng phiên Claude |

### Xem thời gian đi đâu

Sau mỗi iteration, tin Telegram có thêm khối `⏱ Thời gian` (ví dụ `implementer 35,2 (53%) · chờ test chạy nền 10,9 (16%) · ...`, thời gian từng task, bước chậm nhất), và `state\TIMELINE.md` được ghi lại. Xem bất cứ lúc nào:

- Telegram: `/timeline [module]` (kèm dòng "đang làm" của flow đang chạy); `/status` cũng có dòng "đang làm".
- Máy tính: `python scripts\agent-flow\timeline.py <module>` (dùng được cả cho phiên đã chạy từ trước).

Các nhóm thời gian: `implementer` (cả lần gọi implementer, bên trong tách tiếp pytest/đọc/ghi code/model), `chờ test chạy nền` (vòng lặp `sleep` đợi kết quả test hoặc cổng đang chạy nền), `cổng check_done`, `pytest`, `ruff/mypy`, `commit`, `đọc tài liệu/code`, `ghi state/journal`, `lệnh khác`. Đoạn không có lệnh nào đang chạy là `model suy nghĩ/viết`. Hai nhóm tính cạnh nhau thì nhóm ưu tiên (thứ tự ở trên) được tính, nên tổng các nhóm luôn bằng tổng thời gian phiên.

Dữ liệu lấy từ transcript của Claude Code (`~/.claude/projects/...`, chỉ đọc) và `timeline.jsonl` của runner. Hạn chế:
- chỉ có trên máy chạy flow; định dạng transcript là nội bộ của Claude Code nên có thể đổi theo phiên bản (khi đó chỉ mất phần timeline, flow vẫn chạy);
- thời lượng mỗi lệnh là từ lúc gọi đến lúc có kết quả, sai số vài giây;
- phiên chạy trước khi có tính năng này thiếu thời gian cổng của runner và thời gian chờ hạn mức.

Xem lại code: PR do runner mở trên GitHub (link ở tin kết thúc và `RUN-REPORT.md`), hoặc `git log main..<branch>` trong thư mục worktree. Module dùng `--no-merge` hoặc chưa vào main được thì vẫn ở nhánh local cho tới khi `/merge`.

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
| `/run <module>` | Đưa module lên **đầu** hàng đợi (đã có trong hàng thì chuyển lên đầu); **không** dừng flow đang chạy. Nếu chưa có spec: agent `spec-writer` soạn `docs/features/<module>.md` từ Mô tả dự án + doc 05 + tài liệu DB. Bot kiểm tra spec (cấu trúc, owner, `error.code` phải có trong §10), gửi bảng test case lên Telegram, rồi **chạy luôn** flow (nhóm đã chọn không cần duyệt spec) |
| `/run <module> --respec` | Soạn lại spec rồi chạy |
| `/timeline [module]` | Thời gian đi đâu: từng iteration, từng task, bước chậm nhất, thời gian cổng và chờ hạn mức, và việc agent đang làm lúc này. Bỏ trống module thì dùng module đang chạy |
| `/auto [on\|off]` | Bật/tắt **tự xếp hàng** (mặc định bật): khi rảnh, bot tự thêm vào cuối hàng đợi các module chưa xong, có owner, chưa từng chạy, theo thứ tự `modules.json`. Module đã chạy mà lỗi/kẹt/bị chặn không tự chạy lại. `/stop` một module đang xếp hàng thì bot không tự thêm lại nó |
| `/run <module> --force` | Chạy lại module đã đánh dấu `"status": "done"` trong `modules.json`. Không có `--force` thì bot từ chối để tránh làm trùng việc đã xong (vd `core` đã làm tay qua PR #2, #3) |
| `/status` | Flow đang chạy (iteration, TC pass, task, yêu cầu quyền đang chờ, **token đã dùng**), **hạn mức Claude còn lại** (cửa sổ 5 giờ và 7 ngày, giờ reset), hàng đợi, kết quả gần nhất |
| `/stop <module>` | Dừng flow đang chạy hoặc bỏ khỏi hàng đợi. `/run` lại sẽ tiếp tục từ chỗ dừng |
| `/answer <module> <nội dung>` | Trả lời câu hỏi của agent. Flow đang bị chặn sẽ tự được xếp hàng chạy tiếp |
| `/merge <module>` | Đưa module **đã được duyệt** vào main (gộp main, giải xung đột, chạy lại cổng, PR, chờ CI, merge). Dùng để thử lại khi kết quả là "⚠️ xong, chưa vào main" |
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
  Các cổng: spec hợp lệ · không đụng file bảo vệ (docs, schema DB baseline, tooling, core nếu không cho phép) · không xoá test · worktree sạch · toàn bộ pytest pass · **mọi TC có test gắn marker và đều pass** (skip/xfail không tính) · coverage · ruff · mypy · **standards** (cảnh báo, không làm trượt: hàm > 40 dòng, file > 300 dòng, > 4 tham số, lồng > 3, complexity > 10 ở code thêm/sửa từ BASE_SHA; xem `docs/guides/coding-standards.md` §6, mã ở `standards.py`).
  Kết quả cổng chỉ được dùng lại (`gate-runner.json`, trường `cache_key`) khi khớp **cả** HEAD, spec, base, danh sách cổng, python và nội dung `check_done.py`, **và** worktree sạch. Khác bất kỳ điểm nào, hoặc lần trước chính cổng bị lỗi, thì runner chạy lại đầy đủ. Mục đích: không tốn 10+ phút chạy lại toàn bộ pytest trên cùng một commit. Nếu lần chạy trước trượt vì môi trường (DB/Redis sập giữa chừng) thì xoá `state/gate-runner.json` để ép chạy lại.
- Spec và file agent trong worktree bị sửa thì runner khôi phục và ghi cảnh báo.
- `flow-settings.json` chặn: `git commit` và `git -c` trực tiếp (agent phải commit qua `flow_commit.py`), push/pull/merge/rebase/switch/checkout/reset --hard/stash, `gh`, git config, `docker compose down`, xoá volume, web, hỏi người dùng. Push, mở PR và merge vào `main` chỉ do runner (Python) làm sau khi cổng đạt và CI xanh; không bao giờ `--force`. `pip install/uninstall` được phép chạy không cần hỏi; việc thêm thư viện vào `requirements.txt` vẫn bị cổng `protected` chặn khi spec để `allow_new_dependencies: no`.
- `flow_commit.py` từ chối message sai `Claude_git.md` §2 (type, chữ thường, tối đa 72 ký tự, dấu chấm cuối, có `Co-Authored-By`/chữ ký AI), từ chối commit khi đang ở `main`/`develop` hoặc chưa stage gì.
- Chế độ quyền mặc định là `auto`, kèm `--permission-prompts none`: thao tác nào cần hỏi thì bị từ chối ngay, nên flow không treo chờ người bấm.

## 10. Giới hạn cần biết

- Máy phải bật, có mạng, và Docker Desktop phải chạy. Muốn chạy khi tắt máy thì cần chuyển sang cloud (routine), nhưng khi đó PostgreSQL thật phải được dựng trong môi trường cloud.
- Mọi phiên dùng chung hạn mức của tài khoản. Phiên Claude Code tương tác bạn mở cùng lúc sẽ dùng chung hạn mức đó.
- `git fetch origin main` chạy một lần lúc tạo worktree. Nếu `main` cục bộ và `origin/main` đã rẽ nhánh, runner dừng và yêu cầu bạn đồng bộ trước.
- Marker `tc` chỉ được đăng ký khi chạy qua plugin. Chạy `pytest` thường sẽ có cảnh báo `PytestUnknownMarkWarning`, không ảnh hưởng kết quả. Muốn tắt cảnh báo thì Core owner thêm `markers = tc(*ids): ...` vào cấu hình pytest.
