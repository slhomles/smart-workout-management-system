"""Đưa module đã xong vào main: gộp main, giải xung đột, chạy lại cổng, push, mở PR, chờ CI, merge.

Gọi từ run_flow.py khi orchestrator đã duyệt và mọi cổng đạt, hoặc qua `run_flow.py <spec> --merge-only`.
Ngoại lệ agent flow ở doc 05 §9.3: PR vào `main`, tự merge khi CI xanh, dùng merge commit để giữ tác giả
theo team.json. Chỉ runner (file này) push/merge; agent `integrator` chỉ sửa file, mọi lệnh git ghi và `gh`
của agent vẫn bị flow-settings.json chặn. Thất bại thì nhánh giữ nguyên và ném IntegrationError.
"""

from __future__ import annotations

import json
from pathlib import Path

import check_done
import merge_resolvers
import pr_publish
from flowgit import IntegrationError, git, git_ok, sh

__all__ = ["IntegrationError", "integrate", "sync_main"]

HERE = Path(__file__).resolve().parent
MAX_MERGE_ROUNDS = 2
MAX_FIX_ATTEMPTS = 2
SYNCED_PREFIXES = (".claude/agents/",)  # runner chép vào worktree khi nhánh chưa track


# ------------------------------------------------------------------ tiện ích

def scope(flow) -> str:
    return flow.spec["meta"].get("commit_scope") or flow.module


def save_run(flow) -> None:
    flow.run_file.write_text(json.dumps(flow.run_info, ensure_ascii=False, indent=2), encoding="utf-8")


def commit(flow, message: str) -> str:
    """Commit qua flow_commit.py để tác giả đúng team.json (Claude_git.md §2.8)."""
    msg_file = flow.state_dir / "commit-msg.txt"
    msg_file.write_text(message + "\n", encoding="utf-8")
    proc = sh([str(flow.python), str(HERE / "flow_commit.py"), "--state-dir", str(flow.state_dir),
               "-F", str(msg_file)], flow.wt)
    if proc.returncode != 0:
        raise IntegrationError(f"flow_commit từ chối: {(proc.stdout + proc.stderr).strip()[-400:]}")
    return git(flow.wt, "rev-parse", "HEAD")


def ask_integrator(flow, prompt: str, name: str) -> None:
    res = flow.call_integrator(prompt, name)
    if res["is_error"]:
        raise IntegrationError(f"agent integrator lỗi ({name}), xem log {flow.logs / name}")


# ------------------------------------------------------------------ gộp main vào nhánh

def conflicted(wt: Path) -> list[str]:
    return [p for p in git(wt, "diff", "--name-only", "--diff-filter=U").splitlines() if p]


def stage_text(wt: Path, stage: int, path: str) -> str | None:
    proc = sh(["git", "show", f":{stage}:{path}"], wt)
    return proc.stdout if proc.returncode == 0 else None


def resolve_known(wt: Path, paths: list[str]) -> list[str]:
    """Giải các file có cách giải hiển nhiên (merge_resolvers); trả về các file còn xung đột."""
    left = []
    for path in paths:
        text = merge_resolvers.resolve(path, stage_text(wt, 2, path), stage_text(wt, 3, path))
        if text is None:
            left.append(path)
            continue
        (wt / path).write_text(text, encoding="utf-8", newline="")
        git(wt, "add", "--", path)
    return left


def has_markers(wt: Path, path: str) -> bool:
    target = wt / path
    try:
        return target.is_file() and merge_resolvers.has_conflict_markers(target.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return False  # file nhị phân: git đã báo xung đột riêng nếu có


def settle(wt: Path, paths: list[str]) -> None:
    """Sau khi integrator sửa: chỉ khi MỌI file hết dấu xung đột mới stage (kể cả sửa phụ trong backend/)."""
    unresolved = [p for p in paths if has_markers(wt, p)]
    if unresolved:
        raise IntegrationError(f"còn xung đột chưa giải được: {', '.join(unresolved)}")
    git(wt, "add", "-A", "--", *paths)
    git(wt, "add", "-A", "--", "backend")


def assert_no_markers(wt: Path) -> None:
    """Chốt chặn cuối: không file nào sắp commit còn dấu `<<<<<<<`/`>>>>>>>`."""
    staged = [p for p in git(wt, "diff", "--cached", "--name-only").splitlines() if p]
    leftovers = [p for p in staged if has_markers(wt, p)]
    if leftovers:
        raise IntegrationError(f"còn dấu xung đột trong: {', '.join(leftovers)}")


def resolve_prompt(flow, paths: list[str]) -> str:
    files = "\n".join(f"- {p}" for p in paths)
    return (f"Chế độ GIẢI XUNG ĐỘT. Worktree (cwd): `{flow.wt}`. Nhánh `{flow.spec['branch']}` của module "
            f"`{flow.module}` đang gộp `origin/main` và còn xung đột ở:\n{files}\n"
            "Sửa từng file theo hướng dẫn agent integrator rồi kết thúc bằng một dòng tóm tắt.")


def clear_synced_copies(wt: Path, sha: str) -> None:
    """Bản chép chưa track mà main có track thì xoá, để merge không bị chặn (runner chép lại sau)."""
    tracked = set(git(wt, "ls-tree", "-r", "--name-only", sha).splitlines())
    for path in git(wt, "ls-files", "--others", "--exclude-standard").splitlines():
        if path in tracked and path.startswith(SYNCED_PREFIXES):
            (wt / path).unlink(missing_ok=True)


def finish_merge(flow, log) -> bool:
    """Giải xung đột rồi commit gộp; False nếu gộp không đổi gì (nhánh đã có đủ nội dung của main)."""
    left = resolve_known(flow.wt, conflicted(flow.wt))
    if left:
        log(f"tích hợp: nhờ integrator giải {len(left)} file: {', '.join(left)}")
        ask_integrator(flow, resolve_prompt(flow, left), "integrate-resolve")
        settle(flow.wt, left)
    remaining = conflicted(flow.wt)
    if remaining:
        raise IntegrationError(f"còn xung đột chưa giải được: {', '.join(remaining)}")
    assert_no_markers(flow.wt)
    if not git(flow.wt, "diff", "--cached", "--name-only"):
        return False
    commit(flow, f"chore({scope(flow)}): merge main into {flow.spec['branch']}")
    return True


def sync_main(flow, log) -> bool:
    """Gộp origin/main vào nhánh module; True nếu vừa tạo commit gộp. Lỗi thì huỷ gộp, nhánh như cũ."""
    wt = flow.wt
    git(wt, "fetch", "origin", "main")
    sha = git(wt, "rev-parse", "origin/main")
    if git_ok(wt, "merge-base", "--is-ancestor", sha, "HEAD"):
        return False
    if git(wt, "status", "--porcelain", "--untracked-files=no"):
        raise IntegrationError("worktree còn thay đổi chưa commit, không gộp main")
    clear_synced_copies(wt, sha)
    proc = sh(["git", "merge", "--no-ff", "--no-commit", sha], wt)
    if not git_ok(wt, "rev-parse", "-q", "--verify", "MERGE_HEAD"):
        raise IntegrationError(f"git merge lỗi: {(proc.stderr or proc.stdout).strip()[:400]}")
    try:
        changed = finish_merge(flow, log)
    except Exception:
        sh(["git", "merge", "--abort"], wt)
        raise
    if not changed:
        sh(["git", "merge", "--abort"], wt)
        return False
    flow.base_sha = flow.run_info["base_sha"] = sha  # cổng chỉ xét thay đổi của module so với main mới
    save_run(flow)
    log(f"tích hợp: đã gộp origin/main {sha[:10]} vào {flow.spec['branch']}")
    return True


# ------------------------------------------------------------------ kiểm tra sau khi gộp

def fix_prompt(report: dict) -> str:
    failed = {n: g for n, g in report["gates"].items() if not g["ok"]}
    details = "\n\n".join(f"[{n}]\n{str(g.get('details', ''))[-3000:]}" for n, g in failed.items())
    return ("Chế độ SỬA LỖI SAU KHI GỘP MAIN. Cổng kiểm tra trượt:\n```\n"
            f"{check_done.format_summary(report)}\n```\nChi tiết:\n```\n{details[:8000]}\n```\n"
            "Sửa tối thiểu theo hướng dẫn agent integrator rồi kết thúc bằng một dòng tóm tắt.")


def mark_approved(flow, head: str) -> None:
    """Cổng đạt trên HEAD đã gộp: ghi approved_sha mới để lần chạy sau không bắt orchestrator duyệt lại."""
    state = json.loads(flow.state_file.read_text(encoding="utf-8"))
    state["approved_sha"] = head
    flow.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def verify(flow, log) -> dict:
    report = flow.run_gate()
    for attempt in range(1, MAX_FIX_ATTEMPTS + 1):
        if report["ok"]:
            break
        log(f"tích hợp: cổng trượt sau khi gộp main, integrator sửa (lần {attempt})")
        ask_integrator(flow, fix_prompt(report), f"integrate-fix-{attempt}")
        git(flow.wt, "add", "-A", "--", "backend")
        if git(flow.wt, "diff", "--cached", "--name-only"):
            commit(flow, f"fix({scope(flow)}): adapt module to latest main")
        report = flow.run_gate()
    if not report["ok"]:
        raise IntegrationError("cổng vẫn trượt sau khi gộp main:\n" + check_done.format_summary(report))
    mark_approved(flow, report["head"])
    return report


# ------------------------------------------------------------------ toàn bộ

def integrate(flow, log, dry_run: bool = False) -> str:
    """Đưa module vào main; trả mô tả kết quả, ném IntegrationError nếu không được."""
    git(flow.wt, "fetch", "origin", "main")
    if git_ok(flow.wt, "merge-base", "--is-ancestor", "HEAD", "origin/main"):
        return "nhánh đã nằm trong main, không cần merge"
    for _ in range(MAX_MERGE_ROUNDS + 1):
        if sync_main(flow, log):
            flow.notify(f"🔀 {flow.tag()} đã gộp main mới nhất vào nhánh module, đang chạy lại cổng…")
        report = verify(flow, log)
        if dry_run:
            return "dry-run: đã gộp main và mọi cổng đạt, không push"
        merged = pr_publish.publish(flow, report, scope(flow), log)
        if merged:
            flow.run_info.update(merged)
            save_run(flow)
            return f"PR #{merged['merged_pr']} đã merge vào main"
        log("tích hợp: main vừa đổi nên PR xung đột, gộp lại")
    raise IntegrationError(f"main thay đổi liên tục, đã gộp lại {MAX_MERGE_ROUNDS + 1} lần vẫn xung đột")
