#!/usr/bin/env python3
"""Con đường commit DUY NHẤT của agent flow (Claude_git.md §2.8, ngoại lệ agent flow).

Chạy từ worktree của module, sau khi đã `git add <đường dẫn cụ thể>`:

    python scripts/agent-flow/flow_commit.py --state-dir <STATE_DIR> -F <file message>

Việc script làm:
1. Kiểm tra message theo Claude_git.md §2: type hợp lệ, chữ thường sau `:`, dòng đầu
   tối đa 72 ký tự, không có dấu chấm cuối, có dòng trống trước body, không có
   Co-Authored-By hay chữ ký AI.
2. Từ chối khi đang ở main/master/develop hoặc chưa stage gì.
3. Chọn tác giả theo `team.json` → `git.rotation`:
   - `owner`: người phụ trách module (`owner` trong spec; runner ghi vào STATE_DIR/git-identity.json);
   - `commit`: mỗi commit một thành viên kế tiếp (bộ đếm dùng chung mọi module);
   - `branch`: cả nhánh module dùng một thành viên (runner chọn lúc tạo worktree);
   - `off` hoặc không có team.json: danh tính git sẵn có của máy.
4. `git -c user.name=… -c user.email=… commit -F <file>`; không sửa git config.

Exit code: 0 thành công · 1 bị từ chối/lỗi.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import team  # noqa: E402

TYPES = "feat|fix|refactor|perf|docs|test|build|ci|chore|style|revert"
HEADER_RE = re.compile(rf"^({TYPES})(\([a-z0-9]+(?:-[a-z0-9]+)*\))?!?: \S")
FORBIDDEN_RE = re.compile(r"(?im)^\s*co-authored-by:|generated with \[?claude|🤖")
PROTECTED_BRANCHES = {"main", "master", "develop"}


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if check and proc.returncode != 0:
        raise SystemExit(f"TỪ CHỐI: git {' '.join(args)} lỗi: {proc.stderr.strip()}")
    return proc


def check_message(text: str) -> list[str]:
    lines = text.replace("\r\n", "\n").rstrip("\n").split("\n")
    header = lines[0] if lines else ""
    errors = []
    if not HEADER_RE.match(header):
        errors.append(f"dòng đầu '{header}' phải dạng <type>(<scope>): <mô tả>, type ∈ {{{TYPES}}}")
    else:
        desc = header.split(": ", 1)[1]
        if desc[:1].isupper() and not desc.split(" ", 1)[0].isupper():
            errors.append("mô tả sau ':' phải bắt đầu bằng chữ thường, thể mệnh lệnh (add, fix, ...)")
    if len(header) > 72:
        errors.append(f"dòng đầu dài {len(header)} ký tự (tối đa 72)")
    if header.endswith("."):
        errors.append("dòng đầu không được có dấu chấm cuối")
    if len(lines) > 1 and lines[1].strip():
        errors.append("phải có một dòng trống giữa dòng đầu và body")
    if FORBIDDEN_RE.search(text):
        errors.append("message có Co-Authored-By hoặc chữ ký AI (Claude_git.md §2.8)")
    return errors


def branch_identity(state_dir: Path, flow_root: Path, ids: list[dict]) -> dict:
    """Danh tính cố định cho cả nhánh; runner thường đã ghi sẵn lúc tạo worktree."""
    path = state_dir / "git-identity.json"
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        if any(i["email"] == saved.get("email") for i in ids):
            return saved
    with team.rotation_slot(flow_root, ids) as slot:
        slot.commit()
        path.write_text(json.dumps(slot.identity, ensure_ascii=False), encoding="utf-8")
        return slot.identity


def do_commit(msg_file: Path, identity: dict | None) -> str:
    cmd = ["git"]
    if identity:
        cmd += ["-c", f"user.name={identity['name']}", "-c", f"user.email={identity['email']}"]
    cmd += ["commit", "-q", "-F", str(msg_file)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise SystemExit(f"TỪ CHỐI: git commit lỗi:\n{proc.stdout}{proc.stderr}")
    return git("rev-parse", "--short", "HEAD").stdout.strip()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--state-dir", required=True, type=Path)
    ap.add_argument("-F", "--file", required=True, type=Path, help="file chứa commit message")
    args = ap.parse_args()

    message = args.file.read_text(encoding="utf-8")
    errors = check_message(message)
    if errors:
        print("TỪ CHỐI: message sai Claude_git.md §2:\n" + "\n".join(f"- {e}" for e in errors))
        return 1
    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch in PROTECTED_BRANCHES:
        print(f"TỪ CHỐI: đang ở nhánh {branch}; flow chỉ commit trên nhánh của module")
        return 1
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        print("TỪ CHỐI: chưa stage thay đổi nào (git add <đường dẫn cụ thể> trước)")
        return 1

    cfg, err = team.load()
    if err:
        print(f"TỪ CHỐI: {err}")
        return 1
    problems = team.git_problems(cfg)
    if problems:
        print("TỪ CHỐI: team.json chưa hợp lệ:\n" + "\n".join(f"- {p}" for p in problems))
        return 1

    mode = team.rotation(cfg)
    state_dir = args.state_dir.resolve()
    flow_root = state_dir.parent.parent  # <flow_root>/<module>/state
    ids, _ = team.git_identities(cfg)

    if mode == "commit":
        with team.rotation_slot(flow_root, ids) as slot:
            sha = do_commit(args.file, slot.identity)
            slot.commit()
            who = slot.identity
    elif mode == "branch":
        who = branch_identity(state_dir, flow_root, ids)
        sha = do_commit(args.file, who)
    elif mode == "owner":
        path = state_dir / "git-identity.json"
        saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not any(i["email"] == saved.get("email") for i in ids):
            print("TỪ CHỐI: rotation=owner nhưng runner chưa ghi danh tính owner hợp lệ "
                  f"({path}); kiểm tra 'owner' trong spec và team.json")
            return 1
        who = saved
        sha = do_commit(args.file, who)
    else:
        who = None
        sha = do_commit(args.file, None)

    author = f"{who['name']} <{who['email']}>" if who else "danh tính git mặc định của máy"
    print(f"OK {sha} · tác giả: {author} · rotation: {mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
