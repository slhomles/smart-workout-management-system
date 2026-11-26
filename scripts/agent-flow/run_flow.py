#!/usr/bin/env python3
"""Runner cho agent flow 2 vai (orchestrator + implementer) chạy không giám sát.

    python scripts/agent-flow/run_flow.py docs/features/<module>.md [tuỳ chọn]
    python scripts/agent-flow/run_flow.py --smoke          # kiểm tra agent + quyền
    python scripts/agent-flow/run_flow.py <spec> --preflight-only

Mỗi iteration là một phiên `claude -p --agent orchestrator` mới (context sạch);
trí nhớ nằm trong thư mục state. Runner tự chạy check_done.py trên HEAD và chỉ
dừng "xong" khi: orchestrator đã duyệt đúng commit HEAD VÀ mọi cổng đạt.

Exit code: 0 xong · 1 lỗi · 2 bị chặn (cần người trả lời) · 3 kẹt (không tiến triển)
           4 hết số iteration · 5 kiểm tra môi trường thất bại.
Chi tiết: scripts/agent-flow/README.md
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
import check_done  # noqa: E402
import notify  # noqa: E402
import team  # noqa: E402
import timeline  # noqa: E402
import timeline_render  # noqa: E402
import usage  # noqa: E402
from notify import esc  # noqa: E402

AGENT_FILES = [".claude/agents/orchestrator.md", ".claude/agents/implementer.md",
               ".claude/agents/spec-writer.md"]
SETTINGS = HERE / "flow-settings.json"
MANDATORY_GATES = ["spec", "protected", "clean", "pytest", "tc", "standards"]
# Tài liệu nguồn của bản tóm tắt quy tắc dùng chung; một trong số này đổi thì phải lập lại bản tóm tắt.
DIGEST_SOURCES = [
    "CLAUDE.md",
    "docs/architecture/Claude_api_respone.md",
    "docs/architecture/04-auth-strategy.md",
    "docs/architecture/05-tooling-workflow.md",
    "docs/architecture/Claude_git.md",
    "docs/guides/coding-standards.md",
    "docs/database/design-overview.md",
    "docs/database/test-dataset.md",
]

EXIT_DONE, EXIT_ERROR, EXIT_BLOCKED, EXIT_STALLED, EXIT_BUDGET, EXIT_PREFLIGHT = 0, 1, 2, 3, 4, 5

LIMIT_RE = re.compile(
    r"usage limit|rate.?limit|hit your limit|limit reached|overloaded|\b529\b|quota", re.I
)
RESET_EPOCH_RE = re.compile(r"limit reached\|(\d{10})")

# Kiểm tra PostgreSQL và Redis RIÊNG từng cái, in JSON {"postgres": {...}, "redis": {...}} với
# "kind" phân loại lỗi, để preflight báo đúng thành phần hỏng và cách sửa (không đoán chung chung).
DB_PROBE = r"""
import asyncio, json, os, socket
import asyncpg, redis

def classify(exc):
    text = str(exc).lower()
    if isinstance(exc, asyncpg.InvalidPasswordError) or "password authentication failed" in text:
        return "auth"
    if isinstance(exc, asyncpg.InvalidCatalogNameError) or ("database" in text and "does not exist" in text):
        return "db_missing"
    if isinstance(exc, socket.gaierror) or "getaddrinfo" in text or "name or service not known" in text:
        return "dns"
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or "timeout" in text or "timed out" in text:
        return "timeout"
    if isinstance(exc, ConnectionRefusedError) or "refused" in text or "10061" in text:
        return "refused"
    return "other"

def failed(exc):
    return {"ok": False, "kind": classify(exc), "detail": f"{type(exc).__name__}: {exc}"[:200]}

async def pg():
    conn = await asyncpg.connect(
        host=os.environ["FLOW_PGH"], port=int(os.environ["FLOW_PGP"]),
        user=os.environ["FLOW_PGU"], password=os.environ["FLOW_PGW"],
        database=os.environ["FLOW_PGD"], timeout=5)
    await conn.execute("SELECT 1")
    await conn.close()

out = {}
try:
    asyncio.run(pg())
    out["postgres"] = {"ok": True}
except Exception as exc:
    out["postgres"] = failed(exc)
try:
    redis.Redis(host=os.environ["FLOW_RH"], port=int(os.environ["FLOW_RP"]),
                socket_timeout=5, socket_connect_timeout=5).ping()
    out["redis"] = {"ok": True}
except Exception as exc:
    out["redis"] = failed(exc)
print(json.dumps(out))
"""

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def explain_service_failure(name: str, status: dict, env: dict, env_vals: dict) -> str:
    """Một dòng cho người đọc trên Telegram: thành phần nào hỏng, vì sao, và người cần làm gì."""
    if name == "postgres":
        label, host_var, host, port = "PostgreSQL", "POSTGRES_HOST", env["FLOW_PGH"], env["FLOW_PGP"]
        other_host = env["FLOW_RH"]
    else:
        label, host_var, host, port = "Redis", "REDIS_HOST", env["FLOW_RH"], env["FLOW_RP"]
        other_host = env["FLOW_PGH"]
    kind, detail = status.get("kind", "other"), status.get("detail", "")
    vm_host = other_host if other_host not in LOCAL_HOSTS else "<IP Tailscale của VM team-stack>"
    where = f"{label} {host}:{port}"

    if kind == "refused" and host in LOCAL_HOSTS:
        if host_var not in env_vals:
            cause = (f"backend/.env không có dòng {host_var} nên dùng mặc định localhost, "
                     f"nhưng máy chạy bot không có {label} local")
        else:
            cause = f"backend/.env đặt {host_var}={host} nhưng máy chạy bot không có {label} local"
        fix = (f"thêm/sửa dòng `{host_var}={vm_host}` trong backend/.env của máy chạy bot "
               "(dịch vụ chạy trên VM team-stack, doc 05 §8.2) rồi /run lại")
    elif kind == "refused":
        cause = (f"tới được máy {host} nhưng cổng {port} từ chối kết nối, tức dịch vụ {label} trên VM "
                 "đang tắt hoặc không mở cổng này")
        fix = (f"người quản lý VM (repo team-stack) kiểm tra container {label} bằng `docker ps` trên VM; "
               f"nếu {label} đã chuyển cổng thì sửa cổng trong backend/.env")
    elif kind == "timeout":
        cause = f"không có phản hồi từ {host}:{port} sau 5 giây"
        fix = ("trên máy chạy bot: mở Tailscale, kiểm tra trạng thái Connected và `tailscale status` thấy "
               "máy team-stack; nếu Tailscale ổn thì báo người quản lý VM kiểm tra VM có đang bật không")
    elif kind == "dns":
        cause = f"không phân giải được tên máy '{host}' ({host_var} trong backend/.env)"
        fix = f"sửa {host_var} trong backend/.env thành địa chỉ IP Tailscale của VM ({vm_host})"
    elif kind == "auth":
        cause = (f"{label} từ chối đăng nhập user '{env['FLOW_PGU']}': sai POSTGRES_USER hoặc "
                 "POSTGRES_PASSWORD trong backend/.env (hoặc mật khẩu trên server đã bị đổi)")
        fix = ("lấy mật khẩu đúng từ người tạo DB rồi sửa backend/.env trên máy chạy bot; "
               "KHÔNG gửi mật khẩu qua Telegram")
    elif kind == "db_missing":
        cause = f"database '{env['FLOW_PGD']}' không tồn tại trên {host}"
        fix = "sửa POSTGRES_DB trong backend/.env (DB của dự án là smart_workout_db)"
    else:
        cause = "lỗi không xác định"
        fix = "gửi nguyên thông báo này cho người phụ trách hạ tầng"
    return f"{where}: {cause}. Cần làm: {fix}. (chi tiết kỹ thuật: {detail})"

SMOKE_PROMPT = """ĐÂY LÀ SMOKE TEST cho agent flow. KHÔNG làm quy trình iteration, KHÔNG sửa file nào.
1. Cho biết tên agent của bạn và danh sách tool bạn đang có.
2. Chạy đúng một lần lệnh shell `git config --get user.name`; cho biết lệnh bị CHẶN bởi permission hay chạy được.
3. Chạy đúng một lần lệnh `"{py}" --version`; báo kết quả hoặc bị chặn.
4. Gọi subagent `implementer` với yêu cầu: "SMOKE TEST: chỉ trả lời tên agent của bạn và danh sách tool bạn có, không làm gì khác." rồi chép lại câu trả lời.
Trả lời đúng dạng:
AGENT: ...
TOOLS: ...
GIT_CONFIG: BLOCKED|ALLOWED (chi tiết)
PYTHON: ...
IMPLEMENTER: ...
"""


class FlowError(Exception):
    pass


# --------------------------------------------------------------------------- utils

def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Logger:
    def __init__(self) -> None:
        self.file: Path | None = None

    def __call__(self, msg: str) -> None:
        line = f"[{now()}] {msg}"
        print(line, flush=True)
        if self.file:
            with self.file.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")


log = Logger()


def run(cmd: list[str], cwd: Path, timeout: int = 300, env: dict | None = None):
    return subprocess.run(
        cmd, cwd=cwd, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )


def git(cwd: Path, *args: str, check: bool = True) -> str:
    proc = run(["git", *args], cwd=cwd, timeout=300)
    if check and proc.returncode != 0:
        raise FlowError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def git_ok(cwd: Path, *args: str) -> bool:
    return run(["git", *args], cwd=cwd, timeout=300).returncode == 0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def same_text(a: Path, b: Path) -> bool:
    """So nội dung, bỏ qua khác biệt CRLF/LF do core.autocrlf."""
    return a.read_bytes().replace(b"\r\n", b"\n") == b.read_bytes().replace(b"\r\n", b"\n")


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def keep_awake(enable: bool) -> None:
    """Chặn Windows tự sleep khi flow đang chạy (tự hoàn nguyên khi thoát)."""
    if os.name != "nt":
        return
    es_continuous, es_system_required = 0x80000000, 0x00000001
    flags = es_continuous | (es_system_required if enable else 0)
    ctypes.windll.kernel32.SetThreadExecutionState(flags)


def kill_tree(proc: subprocess.Popen) -> None:
    kill_pid_tree(proc.pid)


def kill_pid_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
    else:
        try:
            os.killpg(os.getpgid(pid), 9)
        except OSError:
            pass


def pid_alive(pid: int) -> bool:
    """Tiến trình còn sống? (Windows: KHÔNG dùng os.kill vì nó sẽ giết tiến trình)."""
    if pid <= 0:
        return False
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                             capture_output=True, text=True, errors="replace").stdout
        return f'"{pid}"' in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def find_claude() -> str:
    path = shutil.which("claude")
    if not path:
        raise FlowError("không tìm thấy lệnh `claude` trong PATH")
    return path


def default_python() -> Path:
    sub = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
    return REPO / "backend" / ".venv" / sub[0] / sub[1]


def read_env(path: Path) -> dict[str, str]:
    out = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.split(" #", 1)[0].strip().strip('"').strip("'")
    return out


# --------------------------------------------------------------------------- claude

PERM_TOOL = "mcp__flowperm__approve"


def perm_mcp_config(state_dir: Path, module: str, owner: str | None, timeout_s: int) -> Path:
    """Cấu hình MCP để Claude hỏi quyền qua Telegram (perm_mcp.py)."""
    env = {"FLOW_STATE_DIR": str(state_dir), "FLOW_MODULE": module, "FLOW_OWNER": owner or "",
           "FLOW_PERM_TIMEOUT": str(timeout_s), "PYTHONIOENCODING": "utf-8"}
    for key in ("FLOW_TEAM_CONFIG", "TELEGRAM_API_BASE"):
        if os.environ.get(key):
            env[key] = os.environ[key]
    path = state_dir / "perm-mcp.json"
    write_json(path, {"mcpServers": {"flowperm": {
        "type": "stdio", "command": sys.executable, "args": [str(HERE / "perm_mcp.py")], "env": env}}})
    return path


def call_claude(args, prompt: str, cwd: Path, add_dirs: list[Path], log_prefix: Path | None,
                perm_config: Path | None = None):
    cmd = [
        find_claude(), "-p",
        "--agent", "orchestrator",
        "--permission-mode", args.permission_mode,
        "--settings", str(SETTINGS),
        "--output-format", "stream-json", "--verbose",  # stream-json mới có rate_limit_event (hạn mức)
    ]
    env = dict(os.environ)
    if perm_config:  # hỏi quyền qua Telegram; quá hạn thì perm_mcp tự từ chối
        cmd += ["--mcp-config", str(perm_config), "--permission-prompts", "host",
                "--permission-prompt-tool", PERM_TOOL]
        env["MCP_TOOL_TIMEOUT"] = str((args.perm_timeout + 600) * 1000)
    else:  # không ai trả lời: thao tác cần hỏi sẽ bị từ chối ngay, flow không treo
        cmd += ["--permission-prompts", "none"]
    if args.model:
        cmd += ["--model", args.model]
    for d in add_dirs:
        cmd += ["--add-dir", str(d)]
    proc = subprocess.Popen(
        cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", env=env,
    )
    timed_out = False
    try:
        out, err = proc.communicate(prompt, timeout=args.iteration_timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_tree(proc)
        out, err = proc.communicate()
    if log_prefix:
        log_prefix.with_suffix(".out.json").write_text(out or "", encoding="utf-8")
        log_prefix.with_suffix(".err.txt").write_text(err or "", encoding="utf-8")
    data, rate_limit = usage.parse_stream(out or "")
    is_error = timed_out or proc.returncode != 0 or not data or bool(data.get("is_error"))
    text = (out or "") + "\n" + (err or "")
    # Chỉ xét lỗi + câu trả lời cuối: stream-json luôn có dòng rate_limit_event, khớp nhầm LIMIT_RE.
    limit_text = (err or "") + "\n" + str(data.get("result", ""))
    rejected = any(w.get("status") == "rejected" for w in usage.windows(rate_limit).values())
    return {
        "rc": proc.returncode,
        "timed_out": timed_out,
        "data": data,
        "is_error": is_error,
        "is_limit": is_error and not timed_out and (rejected or bool(LIMIT_RE.search(limit_text))),
        "text": text,
        "rate_limit": rate_limit,
        "tokens": usage.tokens_of(data),
    }


def limit_wait_seconds(text: str, default: int) -> int:
    match = RESET_EPOCH_RE.search(text)
    if match:
        return int(min(max(60, int(match.group(1)) - time.time() + 90), 6 * 3600))
    return default


# --------------------------------------------------------------------------- flow

class Flow:
    def __init__(self, args) -> None:
        self.args = args
        spec_arg = Path(args.spec)
        self.spec_src = (spec_arg if spec_arg.is_absolute() else Path.cwd() / spec_arg).resolve()
        try:
            self.spec_rel = self.spec_src.relative_to(REPO).as_posix()
        except ValueError as exc:
            raise FlowError(f"spec phải nằm trong repo {REPO}") from exc
        self.spec = check_done.parse_spec(self.spec_src)
        self.module = self.spec.get("module") or "unknown"
        root = Path(args.flow_root) if args.flow_root else REPO.parent / f"{REPO.name}-flow"
        self.quota_file = root / "quota-alerts.json"  # mốc hạn mức đã báo, dùng chung mọi module
        self.shared_dir = root / "_shared"  # bản tóm tắt quy tắc, dùng chung mọi module
        self.mod_dir = root / self.module
        self.wt = self.mod_dir / "repo"
        self.state_dir = self.mod_dir / "state"
        self.logs = self.mod_dir / "logs"
        self.python = Path(args.python) if args.python else default_python()
        self.run_file = self.state_dir / "run.json"
        self.state_file = self.state_dir / "state.json"
        self.gate_file = self.state_dir / "gate-runner.json"
        self.warnings: list[str] = []
        self.tick = time.monotonic()  # mốc đo thời gian chạy thật của module (xem check_timebox)
        self.gates = list(dict.fromkeys(MANDATORY_GATES + self.spec.get("gates", [])))
        self.owner = self.spec.get("owner") or None
        self.notifier = notify.Notifier.load(log)
        self.team_cfg, self.team_err = team.load()
        self.rotation = team.rotation(self.team_cfg) if not self.team_err else "off"

    # ----------------------------------------------------------- telegram
    def notify(self, text: str) -> None:
        """Gửi tới bot của owner module + bot chung (không bao giờ ném lỗi)."""
        try:
            self.notifier.send(self.owner, text)
        except Exception as exc:  # noqa: BLE001 - thông báo không được làm sập flow
            log(f"CẢNH BÁO: gửi thông báo lỗi: {exc}")

    def tag(self) -> str:
        return f"<b>[{esc(self.module)}]</b>"

    def alert_new_questions(self, state: dict) -> None:
        """Câu hỏi mới trong state.json → nhắn ngay (flow vẫn làm task khác trong lúc chờ)."""
        seen = set(self.run_info.setdefault("notified_questions", []))
        new = []
        for q in state.get("questions") or []:
            key = str((q.get("id") or q.get("question")) if isinstance(q, dict) else q)[:200]
            if key not in seen:
                new.append(q)
                seen.add(key)
        if not new:
            return
        self.run_info["notified_questions"] = sorted(seen)
        write_json(self.run_file, self.run_info)
        lines = [f"❓ {self.tag()} cần người trả lời {len(new)} câu hỏi (flow vẫn làm các task khác):"]
        for q in new[:5]:
            if isinstance(q, dict):
                text = f"<b>{esc(q.get('id', ''))}</b> {esc(str(q.get('question', ''))[:400])}"
                if q.get("proposal"):
                    text += f"\n   Đề xuất của agent: {esc(str(q['proposal'])[:250])}"
            else:
                text = esc(str(q)[:400])
            lines.append("• " + text)
        lines.append(f"Trả lời: <code>/answer {esc(self.module)} &lt;nội dung&gt;</code> "
                     f"(hoặc ghi vào <code>{esc(self.state_dir / 'ANSWERS.md')}</code>)")
        log(f"đã báo {len(new)} câu hỏi mới qua Telegram")
        self.notify("\n".join(lines))

    def alert_denials(self, i: int, data: dict) -> None:
        """Thao tác bị chặn vì quyền → nhắn owner + nhóm (mỗi thao tác một lần mỗi lần chạy)."""
        seen = set(self.run_info.setdefault("notified_denials", []))
        lines = []
        for d in data.get("permission_denials") or []:
            inp = d.get("tool_input") or {}
            detail = str(inp.get("command") or inp.get("file_path") or inp.get("url")
                         or json.dumps(inp, ensure_ascii=False))[:200]
            key = f"{d.get('tool_name')}:{detail}"
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"• {esc(d.get('tool_name', '?'))}: <code>{esc(detail)}</code>")
        if not lines:
            return
        self.run_info["notified_denials"] = sorted(seen)
        write_json(self.run_file, self.run_info)
        log(f"agent bị chặn {len(lines)} thao tác cần quyền (đã báo Telegram)")
        self.notify("\n".join(
            [f"🔐 {self.tag()} iteration {i}: agent bị chặn {len(lines)} thao tác cần quyền"]
            + lines[:8]
            + ["Flow không treo, agent tự tìm cách khác. Nếu thao tác đó thật sự cần thì thêm quy tắc "
               "allow vào <code>scripts/agent-flow/flow-settings.json</code>."]))

    def progress_message(self, p: dict, gate: dict, state: dict, since: str) -> str:
        tc = gate.get("gates", {}).get("tc", {})
        tasks = state.get("tasks", [])
        counts: dict[str, int] = {}
        for t in tasks:
            counts[t.get("status", "?")] = counts.get(t.get("status", "?"), 0) + 1
        icon = "⚠️" if p["error"] else "🔄"
        lines = [f"{icon} {self.tag()} iteration {p['i']}/{self.args.max_iterations} · {p['minutes']} phút",
                 f"Test case: {esc(tc.get('summary', '?'))}"]
        if tasks:
            lines.append("Task: " + ", ".join(f"{esc(k)} {v}" for k, v in counts.items())
                         + f" (tổng {len(tasks)})")
        commits = git(self.wt, "log", "--format=%h · %an · %s", f"{since}..HEAD", check=False) \
            if since else ""
        if commits:
            lines.append("Commit mới:")
            lines += [f"• <code>{esc(c)}</code>" for c in commits.splitlines()[:10]]
        if state.get("questions"):
            lines.append(f"Câu hỏi đang chờ bạn: {len(state['questions'])}")
        lines.append(f"Token: iteration này {usage.format_tokens(p.get('tokens'))} · "
                     f"cả flow {usage.format_tokens(self.run_info.get('usage_total'))}")
        lines.append(usage.format_quota(self.run_info.get("rate_limit")))
        lines += self.timeline_lines(p.get("session_id"))
        if p["error"]:
            lines.append("Iteration lỗi" + (" (quá thời gian)" if p["timed_out"] else "")
                         + f", xem <code>{esc(self.logs)}</code>")
        elif p["result"]:
            lines.append(f"Orchestrator: {esc(p['result'][-600:])}")
        return "\n".join(lines)

    # ----------------------------------------------------------- preflight
    def preflight(self) -> list[str]:
        errors = []
        if self.spec["errors"]:
            errors += [f"spec: {e}" for e in self.spec["errors"]]
        try:
            find_claude()
        except FlowError as exc:
            errors.append(str(exc))
        if self.team_err:
            errors.append(f"team.json: {self.team_err}")
        errors += [f"team.json: {p}" for p in team.git_problems(self.team_cfg)]
        if self.rotation == "owner" and not team.identity_for(self.team_cfg, self.owner):
            errors.append(f"rotation=owner nhưng owner '{self.owner}' của spec không có danh tính git "
                          "hợp lệ trong team.json (key thành viên + name + git_email)")
        if self.rotation == "off":
            name = git(REPO, "config", "user.name", check=False)
            email = git(REPO, "config", "user.email", check=False)
            if not name or not email:
                errors.append("git user.name/user.email trống (Claude_git.md §2.8: phải hỏi người dùng)")
        if not self.python.exists():
            errors.append(
                f"không có python venv tại {self.python}. Tạo bằng:\n"
                f"    py -3.11 -m venv backend\\.venv\n"
                f"    backend\\.venv\\Scripts\\python -m pip install -r backend\\requirements.txt"
            )
        else:
            probe = run([str(self.python), "-c",
                         "import pytest, pytest_asyncio, pytest_cov, httpx, fastapi, asyncpg, redis"],
                        cwd=REPO)
            if probe.returncode != 0:
                errors.append(f"venv thiếu thư viện test: {probe.stderr.strip()[-300:]}")
            for tool in ("ruff", "mypy"):
                if tool in self.gates and run([str(self.python), "-m", tool, "--version"],
                                              cwd=REPO).returncode != 0:
                    errors.append(f"venv thiếu {tool} (cổng '{tool}' đang bật trong spec)")
        if not (REPO / "backend" / ".env").exists():
            errors.append("thiếu backend/.env (copy từ backend/.env.example, sửa POSTGRES_PASSWORD "
                          "khớp docker-compose.yml)")
        if errors or self.args.skip_services:
            return errors
        return self.ensure_services()

    def ensure_services(self) -> list[str]:
        env_vals = read_env(REPO / "backend" / ".env")
        env = dict(os.environ)
        env.update({
            "FLOW_PGH": env_vals.get("POSTGRES_HOST", "localhost"),
            "FLOW_PGP": env_vals.get("POSTGRES_PORT", "5432"),
            "FLOW_PGU": env_vals.get("POSTGRES_USER", ""),
            "FLOW_PGW": env_vals.get("POSTGRES_PASSWORD", ""),
            "FLOW_PGD": env_vals.get("POSTGRES_DB", ""),
            "FLOW_RH": env_vals.get("REDIS_HOST", "localhost"),
            "FLOW_RP": env_vals.get("REDIS_PORT", "6379"),
        })

        def probe() -> tuple[dict | None, str]:
            result = run([str(self.python), "-c", DB_PROBE], cwd=REPO, env=env, timeout=60)
            try:
                return json.loads(result.stdout.strip().splitlines()[-1]), ""
            except (ValueError, IndexError):
                return None, (result.stderr or result.stdout).strip()[-400:]

        def problems(status: dict) -> list[str]:
            return [explain_service_failure(name, status[name], env, env_vals)
                    for name in ("postgres", "redis") if not status[name]["ok"]]

        status, crash = probe()
        if status is None:
            return [f"script kiểm tra kết nối không chạy được trong {self.python}: {crash}. "
                    "Cách sửa: cài lại thư viện của venv (`backend\\.venv\\Scripts\\python -m pip install "
                    "-r backend\\requirements.txt`) rồi /run lại."]
        errors = problems(status)
        if not errors:
            return []
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        if env["FLOW_PGH"] not in local_hosts or env["FLOW_RH"] not in local_hosts:
            # Doc 05 §8.2: DB/Redis chạy trên VM team-stack; KHÔNG tự bật Docker local thay thế
            return errors
        if shutil.which("docker"):
            log("PostgreSQL/Redis chưa sẵn sàng -> docker compose up -d postgres redis")
            up = run(["docker", "compose", "up", "-d", "postgres", "redis"], cwd=REPO, timeout=600)
            if up.returncode != 0:
                return [f"`docker compose up -d postgres redis` lỗi: {up.stderr.strip()[-300:]}. "
                        "Cách sửa: mở Docker Desktop, đợi trạng thái 'Engine running' rồi /run lại; hoặc sửa "
                        "POSTGRES_HOST/REDIS_HOST trong backend/.env trỏ tới VM team-stack (doc 05 §8.2)."]
            deadline = time.time() + 300
            while time.time() < deadline:
                time.sleep(5)
                status, crash = probe()
                if status is not None and not problems(status):
                    return []
            if status is not None:
                return problems(status)
        return errors

    # ----------------------------------------------------------- worktree
    def setup_worktree(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)
        log.file = self.mod_dir / "flow.log"
        run_info = read_json(self.run_file, {})
        branch = self.spec["branch"]

        if (self.wt / ".git").exists():
            current = git(self.wt, "rev-parse", "--abbrev-ref", "HEAD")
            if current != branch:
                raise FlowError(f"worktree {self.wt} đang ở nhánh {current}, spec yêu cầu {branch}")
            log(f"dùng lại worktree {self.wt} ({branch})")
        else:
            if run(["git", "fetch", "origin", "main"], cwd=REPO, timeout=300).returncode != 0:
                log("CẢNH BÁO: git fetch origin main lỗi, dùng main cục bộ")
            base_ref = self.pick_base_ref()
            if git_ok(REPO, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"):
                git(REPO, "worktree", "add", str(self.wt), branch)
            else:
                git(REPO, "worktree", "add", "-b", branch, str(self.wt), base_ref)
            run_info["base_sha"] = git(REPO, "rev-parse", base_ref)
            run_info["created_at"] = now()
            log(f"tạo worktree {self.wt} nhánh {branch} từ {base_ref}")

        if not run_info.get("base_sha"):
            run_info["base_sha"] = git(self.wt, "merge-base", "HEAD", "main")
        self.base_sha = run_info["base_sha"]

        env_dst = self.wt / "backend" / ".env"
        if not env_dst.exists():
            if git_ok(self.wt, "check-ignore", "-q", "backend/.env"):
                shutil.copy2(REPO / "backend" / ".env", env_dst)
            else:
                raise FlowError("backend/.env không bị .gitignore trong nhánh, từ chối copy secret")

        self.sync_files(first=True)
        if self.rotation == "owner":  # ghi lại mỗi lần chạy: spec đổi owner thì commit sau theo owner mới
            who = team.identity_for(self.team_cfg, self.owner)
            write_json(self.state_dir / "git-identity.json", who)
            log(f"rotation=owner: commit của module mang tên {who['name']} <{who['email']}>")
        elif self.rotation == "branch" and not (self.state_dir / "git-identity.json").exists():
            ids, _ = team.git_identities(self.team_cfg)
            with team.rotation_slot(self.mod_dir.parent, ids) as slot:
                slot.commit()
                write_json(self.state_dir / "git-identity.json", slot.identity)
            log(f"rotation=branch: mọi commit của nhánh này mang tên {slot.identity['name']}")
        spec_hash = sha256(self.wt / self.spec_rel)
        self.spec_changed = bool(run_info.get("spec_sha")) and run_info["spec_sha"] != spec_hash
        run_info["spec_sha"] = spec_hash
        shutil.copy2(self.wt / self.spec_rel, self.state_dir / "spec.locked.md")
        write_json(self.run_file, run_info)
        self.run_info = run_info

    def pick_base_ref(self) -> str:
        has_origin = git_ok(REPO, "rev-parse", "--verify", "--quiet", "origin/main")
        if not has_origin:
            return "main"
        if git_ok(REPO, "merge-base", "--is-ancestor", "origin/main", "main"):
            return "main"  # main cục bộ bằng hoặc mới hơn origin/main
        if git_ok(REPO, "merge-base", "--is-ancestor", "main", "origin/main"):
            return "origin/main"
        raise FlowError("main cục bộ và origin/main đã rẽ nhánh; hãy đồng bộ main trước")

    def sync_files(self, first: bool = False) -> None:
        """Chép agent + spec (nếu chưa được track trong nhánh) vào worktree; phát hiện bị sửa."""
        spec_dst = self.wt / self.spec_rel
        if first and not (spec_dst.exists() and same_text(spec_dst, self.spec_src)):
            # spec ở repo chính là nguồn sự thật (bot có thể soạn lại bằng /run --respec)
            spec_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.spec_src, spec_dst)
        for rel in AGENT_FILES:
            src, dst = REPO / rel, self.wt / rel
            if git_ok(self.wt, "ls-files", "--error-unmatch", rel):
                if first and dst.exists() and src.exists() and not same_text(dst, src):
                    log(f"CẢNH BÁO: {rel} trong nhánh khác bản ở repo chính; dùng bản trong nhánh")
                continue
            if dst.exists() and not first and not same_text(dst, src):
                self.warnings.append(f"file tooling {rel} trong worktree bị sửa; runner đã khôi phục")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    def check_spec_lock(self) -> None:
        spec_wt = self.wt / self.spec_rel
        if sha256(spec_wt) != self.run_info["spec_sha"]:
            shutil.copy2(self.state_dir / "spec.locked.md", spec_wt)
            self.warnings.append("spec module bị sửa trong lúc chạy; runner đã khôi phục bản khoá")
            log("CẢNH BÁO: spec bị sửa, đã khôi phục")

    # ----------------------------------------------------------- gate + brief
    def gate_cache_key(self) -> str | None:
        """Khoá kết quả cổng; None (không dùng lại) khi worktree còn thay đổi chưa commit."""
        if git(self.wt, "status", "--porcelain", "-uall", check=False).strip():
            return None
        parts = [git(self.wt, "rev-parse", "HEAD"), self.run_info.get("spec_sha", ""), self.base_sha,
                 ",".join(self.gates), str(self.python), sha256(HERE / "check_done.py"), sha256(HERE / "standards.py")]
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

    def check_timebox(self, gate: dict, state: dict) -> None:
        """Quá mốc thời gian thì báo MỘT lần; flow vẫn chạy tiếp (quyết định của người phụ trách module)."""
        now_tick = time.monotonic()
        spent = self.run_info.get("active_seconds", 0) + (now_tick - self.tick)
        self.run_info["active_seconds"], self.tick = spent, now_tick
        limit = self.args.time_box_minutes
        if not limit or self.run_info.get("timebox_warned") or spent < limit * 60:
            return
        self.run_info["timebox_warned"] = True
        write_json(self.run_file, self.run_info)
        tasks = state.get("tasks", [])
        done = sum(1 for t in tasks if t.get("status") == "done")
        tc = gate.get("gates", {}).get("tc", {}).get("summary", "?")
        self.notify(f"⏱ {self.tag()} đã chạy {round(spent / 60)} phút (mốc {limit} phút, không tính thời gian "
                    f"chờ hạn mức): {esc(tc)}, task {done}/{len(tasks)} xong. Flow vẫn chạy tiếp.")

    def docs_sha(self) -> str:
        """Băm nội dung các tài liệu nguồn; khác lần lập bản tóm tắt trước thì phải đọc và lập lại."""
        digest = hashlib.sha256()
        for rel in DIGEST_SOURCES:
            path = self.wt / rel
            digest.update(rel.encode("utf-8") + (path.read_bytes() if path.exists() else b"-"))
        return digest.hexdigest()

    def digest_lines(self) -> list[str]:
        digest, sha_file = self.shared_dir / "rules-digest.md", self.shared_dir / "rules-digest.sha"
        current = self.docs_sha()
        is_fresh = digest.exists() and sha_file.exists() and sha_file.read_text(encoding="utf-8").strip() == current
        if is_fresh:
            return [f"- RULES_DIGEST: `{digest}` · **CÒN HIỆU LỰC**: đọc nó thay vì đọc lại toàn bộ tài liệu."]
        return [f"- RULES_DIGEST: `{digest}` · **CẦN TẠO LẠI** (tài liệu đã đổi hoặc chưa có): đọc toàn bộ "
                f"tài liệu một lần, ghi bản tóm tắt vào file này, rồi ghi đúng chuỗi `{current}` vào `{sha_file}`."]

    def run_gate(self) -> dict:
        # Bộ test chạy trên DB ở VM mất 10+ phút; HEAD không đổi thì kết quả cổng cũng không đổi.
        key = self.gate_cache_key()
        cached = read_json(self.gate_file, {})
        if key and cached.get("cache_key") == key and "gates" in cached:
            log(f"cổng: HEAD {str(cached.get('head', ''))[:10]} không đổi, dùng lại kết quả lần trước")
            self.mark("gate", cached=True, seconds=0, head=cached.get("head"))
            return cached
        began = time.monotonic()
        try:
            report = check_done.evaluate(
                self.wt, self.wt / self.spec_rel, self.base_sha, self.gates, str(self.python)
            )
        except Exception as exc:  # noqa: BLE001 - gate lỗi không được làm sập runner
            report = {"ok": False, "head": git(self.wt, "rev-parse", "HEAD"),
                      "gates": {"runner": {"ok": False, "summary": f"gate lỗi: {exc}"}}}
            key = None  # lỗi của chính cổng thì lần sau phải chạy lại
        report["cache_key"] = key
        write_json(self.gate_file, report)
        self.mark("gate", cached=False, seconds=round(time.monotonic() - began, 1), head=report.get("head"),
                  per_gate={n: g.get("seconds") for n, g in report.get("gates", {}).items() if g.get("seconds")})
        return report

    def mark(self, kind: str, **fields) -> None:
        """Ghi một sự kiện thời gian của runner vào state/timeline.jsonl (xem timeline.py)."""
        entry = {"at": now(), "t": time.time(), "kind": kind, **fields}
        try:
            with (self.state_dir / "timeline.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            log(f"CẢNH BÁO: không ghi được timeline: {exc}")

    def write_timeline(self) -> Path | None:
        """Ghi state/TIMELINE.md; lỗi ở đây không được làm sập flow."""
        try:
            report = timeline.build_report(self.wt, self.state_dir)
            path = self.state_dir / "TIMELINE.md"
            path.write_text(timeline_render.markdown(self.module, report), encoding="utf-8")
            return path
        except Exception as exc:  # noqa: BLE001 - báo cáo thời gian chỉ để xem, không phải điều kiện của flow
            log(f"CẢNH BÁO: không dựng được timeline: {exc}")
            return None

    def timeline_lines(self, session_id: str | None) -> list[str]:
        try:
            summary = timeline.session_summary(self.wt, session_id)
        except Exception as exc:  # noqa: BLE001 - xem write_timeline
            log(f"CẢNH BÁO: không tóm tắt được thời gian iteration: {exc}")
            return []
        return timeline_render.iteration_lines(summary) if summary else []

    def write_brief(self, i: int, gate: dict, notes: list[str]) -> Path:
        py = self.python
        gate_cmd = (f'"{py}" "{HERE / "check_done.py"}" --spec "{self.spec_rel}" '
                    f'--base {self.base_sha} --python "{py}" --json-out "{self.state_dir / "gate.json"}"')
        answers = self.state_dir / "ANSWERS.md"
        lines = [
            f"# Brief iteration {i}/{self.args.max_iterations} ({now()})",
            "",
            f"- MODULE: `{self.module}`",
            f"- WORKTREE (cwd của bạn): `{self.wt}`",
            f"- SPEC (đã khoá, KHÔNG sửa): `{self.spec_rel}`",
            f"- BRANCH: `{self.spec['branch']}` · BASE_SHA: `{self.base_sha}` · HEAD: `{gate.get('head', '')}`",
            f"- STATE_DIR: `{self.state_dir}` (state.json, journal.md, REPORT.md, gate.json)",
            *self.digest_lines(),
            f"- PYTHON (venv backend): `{py}`",
            f"- Cổng do runner bật: {', '.join(self.gates)} · coverage_min: {self.spec['coverage_min']:g}",
            f"- allow_core_changes: {self.spec['allow_core_changes']} · "
            f"allow_new_dependencies: {self.spec['allow_new_dependencies']}",
            f"- Iteration còn lại sau lần này: {self.args.max_iterations - i}",
            f"- Câu trả lời của người dùng: `{answers}` "
            + ("(CÓ, đọc trước khi làm)" if answers.exists() else "(chưa có)"),
            "",
            "## Lệnh",
            "",
            "Cổng đầy đủ (chạy từ WORKTREE):",
            f"```\n{gate_cmd}\n```",
            "Cổng nhanh cho một task: thêm `--gates spec,protected,pytest,tc,ruff,standards "
            "--tests <file test của task>` (chỉ chạy file test đó; cổng đầy đủ không có `--tests`).",
            "",
            "Commit (CÁCH DUY NHẤT; `git commit` trực tiếp bị chặn). Viết message vào file, "
            "`git add <đường dẫn cụ thể>`, rồi chạy từ WORKTREE:",
            f'```\n"{py}" "{HERE / "flow_commit.py"}" --state-dir "{self.state_dir}" '
            f'-F "{self.state_dir / "commit-msg.txt"}"\n```',
            f"Script tự chọn tác giả (rotation: `{self.rotation}`) và kiểm tra message theo "
            "Claude_git.md §2. Nếu bị TỪ CHỐI thì sửa đúng lỗi được báo, KHÔNG tìm cách lách.",
            "",
            f"Test nhanh (cwd = `{self.wt / 'backend'}`): "
            f'`"{py}" -m pytest tests -q -p tc_plugin` với PYTHONPATH chứa `{HERE}`, '
            f'hoặc đơn giản `"{py}" -m pytest tests/<file> -q`.',
            "",
            "## Kết quả cổng runner vừa chạy trên HEAD",
            "",
            "```",
            check_done.format_summary(gate) if "head" in gate else json.dumps(gate)[:2000],
            "```",
            f"Chi tiết: `{self.gate_file}`",
        ]
        if notes:
            lines += ["", "## Ghi chú từ runner", ""] + [f"- {n}" for n in notes]
        path = self.state_dir / "brief.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    # ----------------------------------------------------------- loop
    def loop(self) -> int:
        lock = self.state_dir / "runner.lock"
        if lock.exists():  # khoá mồ côi (runner bị kill) thì gỡ
            try:
                old_pid = int(lock.read_text(encoding="utf-8").split()[0])
            except (ValueError, IndexError, OSError):
                old_pid = 0
            if not pid_alive(old_pid):
                log(f"gỡ khoá mồ côi của runner cũ (pid {old_pid})")
                lock.unlink(missing_ok=True)
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise FlowError(f"đã có runner khác đang chạy module này ({lock}).")
        os.write(fd, f"{os.getpid()} {now()}".encode())
        os.close(fd)
        keep_awake(True)
        try:
            return self._loop()
        finally:
            keep_awake(False)
            lock.unlink(missing_ok=True)

    def _loop(self) -> int:
        args = self.args
        history = self.run_info.setdefault("history", [])
        state = read_json(self.state_file, {})
        notes: list[str] = []
        if state.get("status") == "blocked" and (self.spec_changed or args.resume_blocked):
            state["status"] = "in_progress"
            write_json(self.state_file, state)
            notes.append("Người dùng đã cập nhật spec hoặc ANSWERS.md: xem lại các câu hỏi/task blocked.")
        if self.spec_changed:
            notes.append("Spec đã thay đổi so với lần chạy trước: rà lại kế hoạch với spec mới.")

        i = int(self.run_info.get("iterations_done", 0))
        last_fp, stall, errors_in_row, limit_waits = None, 0, 0, 0
        just_waited = False
        pending: dict | None = None  # iteration vừa chạy, chờ cổng chạy lại để báo tiến độ
        last_head = git(self.wt, "rev-parse", "HEAD")
        for problem in self.notifier.problems(self.owner):
            log(f"CẢNH BÁO thông báo: {problem}")
        resumed = f" (chạy tiếp, đã xong {i} iteration)" if i else ""
        self.notify(
            f"🚀 {self.tag()} bắt đầu flow{resumed}\n"
            f"Phụ trách: {esc(self.notifier.member_name(self.owner))} · "
            f"nhánh <code>{esc(self.spec['branch'])}</code>\n"
            f"{len(self.spec['tcs'])} test case · tối đa {args.max_iterations} iteration\n"
            "Tác giả commit: "
            + ("danh tính git của máy" if self.rotation == "off" else f"xoay vòng theo {esc(self.rotation)}")
        )
        while True:
            gate = self.run_gate()
            state = read_json(self.state_file, {})
            head = gate.get("head", "")
            log(check_done.format_summary(gate) if "gates" in gate else str(gate))
            if pending:
                self.notify(self.progress_message(pending, gate, state, last_head))
                pending, last_head = None, head or last_head

            if state.get("status") == "approved":
                if state.get("approved_sha") == head and gate["ok"]:
                    return self.finish(EXIT_DONE, "XONG: orchestrator đã duyệt và mọi cổng đạt", gate)
                state["status"] = "in_progress"
                write_json(self.state_file, state)
                notes.append("Trạng thái approved bị runner huỷ: approved_sha khác HEAD hoặc cổng trượt.")
            if state.get("status") == "blocked":
                return self.finish(EXIT_BLOCKED, "BỊ CHẶN: cần người dùng trả lời câu hỏi trong state.json", gate)
            self.alert_new_questions(state)
            self.check_timebox(gate, state)

            tc_status = gate.get("gates", {}).get("tc", {}).get("per_tc", {})
            fp = json.dumps([head, sorted(k for k, v in tc_status.items() if v["status"] == "passed"),
                             [(t.get("id"), t.get("status")) for t in state.get("tasks", [])]])
            if not just_waited:  # chờ giới hạn sử dụng không phải là "không tiến triển"
                stall = stall + 1 if fp == last_fp else 0
            last_fp, just_waited = fp, False
            if stall >= args.max_stall:
                return self.finish(EXIT_STALLED, f"KẸT: {stall} iteration liền không tiến triển", gate)
            if i >= args.max_iterations:
                return self.finish(EXIT_BUDGET, f"HẾT {args.max_iterations} iteration", gate)

            i += 1
            notes += self.warnings
            self.warnings = []
            brief = self.write_brief(i, gate, notes)
            notes = []
            log(f"--- iteration {i}/{args.max_iterations} ---")
            started = now()
            prompt = (f"Iteration {i} của agent flow module `{self.module}`. "
                      f"Đọc brief tại `{brief}` rồi làm đúng quy trình trong hướng dẫn agent orchestrator. "
                      "Kết thúc bằng một dòng tóm tắt việc đã làm.")
            perm_config = (perm_mcp_config(self.state_dir, self.module, self.owner, args.perm_timeout)
                           if args.ask_permissions else None)
            self.shared_dir.mkdir(parents=True, exist_ok=True)
            res = call_claude(args, prompt, self.wt, [self.state_dir, self.shared_dir],
                              self.logs / f"iter-{i:03d}", perm_config)
            data = res["data"]
            history.append({
                "i": i, "started": started, "ended": now(), "rc": res["rc"],
                "timed_out": res["timed_out"], "is_error": res["is_error"],
                "cost_usd": data.get("total_cost_usd"), "turns": data.get("num_turns"),
                "tokens": res["tokens"], "rate_limit": res["rate_limit"],
                "result": str(data.get("result", ""))[:500],
            })
            self.track_usage(res)
            self.mark("iteration", i=i, session_id=data.get("session_id"), started=started, ended=now(),
                      tokens=res["tokens"], cost_usd=data.get("total_cost_usd"), turns=data.get("num_turns"))

            if res["is_limit"]:
                i -= 1
                limit_waits += 1
                if limit_waits > args.max_limit_waits:
                    return self.finish(EXIT_ERROR, "Chạm giới hạn sử dụng quá nhiều lần", gate)
                wait = limit_wait_seconds(res["text"], args.limit_wait)
                resets = [int(w["resetsAt"]) for w in usage.windows(res["rate_limit"]).values()
                          if w.get("status") == "rejected" and w.get("resetsAt")]
                if resets:  # chờ đúng tới giờ reset của cửa sổ đang chặn
                    wait = max(60, max(resets) - int(time.time()) + 60)
                log(f"chạm giới hạn sử dụng, chờ {wait // 60} phút rồi chạy lại")
                resume_at = (dt.datetime.now() + dt.timedelta(seconds=wait)).strftime("%H:%M")
                self.notify(f"⏸ {self.tag()} chạm giới hạn sử dụng của tài khoản, "
                            f"tạm dừng đến khoảng {resume_at} rồi chạy tiếp")
                self.save_run(i)
                time.sleep(wait)
                self.mark("wait", reason="hạn mức", seconds=wait)
                self.tick = time.monotonic()  # thời gian chờ hạn mức không tính vào mốc thời gian của module
                just_waited = True
                continue
            if res["is_error"]:
                errors_in_row += 1
                log(f"iteration lỗi (rc={res['rc']}, timeout={res['timed_out']}); "
                    f"xem {self.logs / f'iter-{i:03d}.err.txt'}")
                if errors_in_row >= 3:
                    self.save_run(i)
                    return self.finish(EXIT_ERROR, "3 iteration lỗi liên tiếp", gate)
            else:
                errors_in_row = 0
                log(f"orchestrator: {str(data.get('result', '')).strip()[-400:]}")
            self.save_run(i)
            self.alert_denials(i, data)
            minutes = round((dt.datetime.now()
                             - dt.datetime.strptime(started, "%Y-%m-%d %H:%M:%S")).total_seconds() / 60)
            pending = {"i": i, "minutes": minutes, "error": res["is_error"],
                       "timed_out": res["timed_out"], "result": str(data.get("result", "")).strip(),
                       "tokens": res["tokens"], "session_id": data.get("session_id")}
            self.write_timeline()

            current = git(self.wt, "rev-parse", "--abbrev-ref", "HEAD")
            if current != self.spec["branch"]:
                return self.finish(EXIT_ERROR, f"worktree bị chuyển sang nhánh {current}", gate)
            self.check_spec_lock()
            self.sync_files()
            self.check_authors()

    def check_authors(self) -> None:
        """Bật xoay vòng mà có commit mang email ngoài danh sách = agent đã lách flow_commit.py."""
        if self.rotation == "off":
            return
        if self.rotation == "owner":
            owner_id = team.identity_for(self.team_cfg, self.owner)
            allowed = {owner_id["email"].lower()} if owner_id else set()
        else:
            allowed = {i["email"].lower() for i in team.git_identities(self.team_cfg)[0]}
        out = git(self.wt, "log", "--format=%h %ae", f"{self.base_sha}..HEAD", check=False)
        strays = [line for line in out.splitlines()
                  if line.split(" ", 1)[-1].lower() not in allowed]
        if strays:
            msg = (f"{len(strays)} commit có tác giả ngoài team.json ({', '.join(strays[:5])}); "
                   "chỉ được commit qua flow_commit.py")
            self.warnings.append(msg)
            log(f"CẢNH BÁO: {msg}")

    def track_usage(self, res: dict) -> None:
        """Cộng token vào run.json, lưu hạn mức mới nhất, cảnh báo khi hạn mức vượt 80/90/95%."""
        self.run_info["usage_total"] = usage.add(self.run_info.get("usage_total"), res["tokens"])
        info = res.get("rate_limit")
        if not info:
            return
        self.run_info["rate_limit"] = info
        self.run_info["rate_limit_at"] = now()
        alerted = read_json(self.quota_file, {"tags": []})
        for key, level, tag in usage.new_alerts(info, alerted["tags"]):
            alerted["tags"].append(tag)
            self.notify(f"{self.tag()} {usage.format_alert(info, key, level)}")
        alerted["tags"] = alerted["tags"][-50:]
        write_json(self.quota_file, alerted)

    def save_run(self, i: int) -> None:
        self.run_info["iterations_done"] = i
        write_json(self.run_file, self.run_info)

    def finish(self, code: int, message: str, gate: dict) -> int:
        state = read_json(self.state_file, {})
        commits = git(self.wt, "log", "--format=%h %an: %s", f"{self.base_sha}..HEAD", check=False)
        questions = state.get("questions", [])
        if questions:  # tin kết thúc đã liệt kê → lần chạy tiếp không báo lại như câu hỏi mới
            seen = set(self.run_info.setdefault("notified_questions", []))
            seen |= {str((q.get("id") or q.get("question")) if isinstance(q, dict) else q)[:200]
                     for q in questions}
            self.run_info["notified_questions"] = sorted(seen)
            write_json(self.run_file, self.run_info)
        lines = [
            f"# Kết quả flow: {self.module}",
            "",
            f"- Kết luận: **{message}** (exit {code})",
            f"- Thời điểm: {now()}",
            f"- Nhánh: `{self.spec['branch']}` · worktree: `{self.wt}`",
            f"- Iteration đã chạy: {self.run_info.get('iterations_done', 0)}",
            "",
            "## Cổng (runner tự chạy)",
            "```",
            check_done.format_summary(gate) if "gates" in gate and "head" in gate else str(gate),
            "```",
            "",
            "## Commit trên nhánh",
            "```",
            commits or "(chưa có)",
            "```",
        ]
        if questions:
            lines += ["", "## Câu hỏi cần bạn trả lời",
                      f"Ghi câu trả lời vào `{self.state_dir / 'ANSWERS.md'}` (hoặc sửa spec), "
                      "rồi chạy lại runner với `--resume-blocked`.", ""]
            lines += [f"- {q}" if isinstance(q, str) else f"- {json.dumps(q, ensure_ascii=False)}"
                      for q in questions]
        if (self.state_dir / "REPORT.md").exists():
            lines += ["", f"Báo cáo của orchestrator: `{self.state_dir / 'REPORT.md'}`"]
        timeline_file = self.write_timeline()
        if timeline_file:
            lines += ["", f"Thời gian đi đâu (từng iteration, từng task, bước chậm nhất): `{timeline_file}`"]
        lines += ["", "Runner KHÔNG push/merge. Xem lại nhánh rồi tự push/mở PR theo Claude_git.md."]
        report = self.mod_dir / "RUN-REPORT.md"
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        log(f"{message}. Báo cáo: {report}")

        icon = {EXIT_DONE: "✅", EXIT_BLOCKED: "⛔", EXIT_STALLED: "🧱", EXIT_BUDGET: "⌛"}.get(code, "❌")
        gate_line = check_done.format_summary(gate).splitlines() if "head" in gate and "gates" in gate else []
        tc_line = gate.get("gates", {}).get("tc", {}).get("summary", "?")
        msg = [f"{icon} {self.tag()} {esc(message)}",
               f"Nhánh <code>{esc(self.spec['branch'])}</code> · "
               f"{len(commits.splitlines()) if commits else 0} commit · "
               f"{self.run_info.get('iterations_done', 0)} iteration",
               f"Test case: {esc(tc_line)}",
               f"Token cả flow: {usage.format_tokens(self.run_info.get('usage_total'))}",
               usage.format_quota(self.run_info.get("rate_limit"))]
        if gate_line:
            msg.append(f"Cổng: {esc(gate_line[0])}")
        if questions:
            msg.append("Câu hỏi cần trả lời:")
            for q in questions[:5]:
                text = q.get("question", q) if isinstance(q, dict) else q
                msg.append(f"• {esc(str(text)[:300])}")
        if code == EXIT_DONE:
            msg.append("Runner không push. Hãy review nhánh rồi tự push/mở PR.")
        msg.append(f"Báo cáo: <code>{esc(report)}</code>")
        self.notify("\n".join(msg))
        return code


# --------------------------------------------------------------------------- main

def smoke(args) -> int:
    py = Path(args.python) if args.python else default_python()
    log("smoke test: gọi orchestrator một lần trong repo chính (không sửa file)")
    res = call_claude(args, SMOKE_PROMPT.format(py=py), REPO, [], None)
    print(res["data"].get("result") or res["text"][-3000:])
    print(f"\nrc={res['rc']} is_error={res['is_error']} cost_usd={res['data'].get('total_cost_usd')}")
    return 0 if not res["is_error"] else 1


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("spec", nargs="?", help="đường dẫn spec module, vd docs/features/exercise-catalog.md")
    ap.add_argument("--max-iterations", type=int, default=40)
    ap.add_argument("--max-stall", type=int, default=3,
                    help="số iteration liên tiếp không tiến triển thì dừng")
    ap.add_argument("--iteration-timeout", type=int, default=2700, help="giây cho mỗi iteration")
    ap.add_argument("--time-box-minutes", type=int, default=60,
                    help="quá số phút này (không tính chờ hạn mức) thì báo một lần, flow chạy tiếp; 0 = tắt")
    ap.add_argument("--limit-wait", type=int, default=1800,
                    help="giây chờ khi chạm giới hạn sử dụng mà không biết giờ reset")
    ap.add_argument("--max-limit-waits", type=int, default=30)
    ap.add_argument("--model", default="opus", help="model cho orchestrator (implementer: inherit)")
    ap.add_argument("--permission-mode", default="auto",
                    choices=["auto", "acceptEdits", "dontAsk", "bypassPermissions"])
    ap.add_argument("--python", help="python của venv backend (mặc định backend/.venv)")
    ap.add_argument("--flow-root", help="thư mục chứa worktree + state (mặc định ../<repo>-flow)")
    ap.add_argument("--skip-services", action="store_true", help="bỏ kiểm tra/khởi động PostgreSQL+Redis")
    ap.add_argument("--resume-blocked", action="store_true",
                    help="đã trả lời câu hỏi trong ANSWERS.md, cho flow chạy tiếp")
    ap.add_argument("--ask-permissions", action="store_true",
                    help="hỏi quyền qua Telegram (nút Cho phép/Từ chối) thay vì tự từ chối; bot.py bật cờ này")
    ap.add_argument("--perm-timeout", type=int, default=1800,
                    help="giây chờ người duyệt quyền trước khi tự từ chối (mặc định 30 phút)")
    ap.add_argument("--preflight-only", action="store_true")
    ap.add_argument("--smoke", action="store_true", help="kiểm tra agent/quyền rồi thoát")
    args = ap.parse_args()

    flow: Flow | None = None
    try:
        if args.smoke:
            return smoke(args)
        if not args.spec:
            ap.error("thiếu đường dẫn spec")
        flow = Flow(args)
        errors = flow.preflight()
        if errors:
            for e in errors:
                log(f"PREFLIGHT: {e}")
            if not args.preflight_only:
                # Giữ đủ dài để phần "Cần làm" không bị cắt (Telegram cho tối đa 4096 ký tự/tin).
                flow.notify(f"❌ {flow.tag()} không khởi động được, môi trường chưa sẵn sàng:\n"
                            + "\n".join(f"• {esc(e[:900])}" for e in errors))
            return EXIT_PREFLIGHT
        log("preflight OK")
        if args.preflight_only:
            for problem in flow.notifier.problems(flow.owner):
                log(f"CẢNH BÁO thông báo: {problem}")
            return EXIT_DONE
        flow.setup_worktree()
        return flow.loop()
    except FlowError as exc:
        log(f"LỖI: {exc}")
        if flow:
            flow.notify(f"❌ {flow.tag()} runner dừng vì lỗi: {esc(exc)}")
        return EXIT_ERROR
    except KeyboardInterrupt:
        log("dừng theo yêu cầu (Ctrl+C)")
        if flow:
            flow.notify(f"⏹ {flow.tag()} runner bị dừng bằng tay")
        return EXIT_ERROR
    except Exception as exc:  # noqa: BLE001 - chạy không giám sát: phải báo trước khi chết
        import traceback
        log("LỖI KHÔNG LƯỜNG TRƯỚC:\n" + traceback.format_exc())
        if flow:
            flow.notify(f"❌ {flow.tag()} runner bị crash: {esc(type(exc).__name__)}: {esc(exc)}\n"
                        f"Xem <code>{esc(flow.mod_dir / 'flow.log')}</code>")
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
