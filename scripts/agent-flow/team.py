"""Đọc `team.json` (thông tin thành viên) và xoay vòng danh tính git cho agent flow.

`team.json` nằm cạnh file này, đã gitignore vì chứa token Telegram. Mẫu: `team.example.json`.
Quy tắc xoay vòng tác giả: `docs/architecture/Claude_git.md` §2.8 (ngoại lệ agent flow).
Chỉ dùng thư viện chuẩn.

Kiểm tra file (không in token):

    python scripts/agent-flow/team.py check          # git, GitHub, Telegram (không gửi tin)
    python scripts/agent-flow/team.py check --send   # thêm: gửi một tin thử qua mỗi bot
"""

from __future__ import annotations

import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.environ.get("FLOW_TEAM_CONFIG", HERE / "team.json"))
ROTATIONS = ("owner", "commit", "branch", "off")
EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")


def is_blank(value: object) -> bool:
    """Trống hoặc còn là chỗ điền của file mẫu (`<...>`)."""
    text = str(value or "").strip()
    return not text or text.startswith("<")


def load() -> tuple[dict, str | None]:
    """Trả (config, lỗi). Không có file thì config rỗng, không lỗi."""
    if not CONFIG_PATH.exists():
        return {}, None
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8")), None
    except ValueError as exc:
        return {}, f"{CONFIG_PATH.name} không phải JSON hợp lệ: {exc}"


def rotation(cfg: dict) -> str:
    mode = str((cfg.get("git") or {}).get("rotation", "off")).strip().lower()
    return mode if mode in ROTATIONS else "invalid"


def git_identities(cfg: dict) -> tuple[list[dict], list[str]]:
    """Danh sách {key, name, email} theo thứ tự trong file + lỗi cấu hình."""
    ids, errors = [], []
    for key, member in (cfg.get("members") or {}).items():
        name = member.get("git_name") or member.get("name")
        email = member.get("git_email")
        if is_blank(name) or is_blank(email):
            errors.append(f"thành viên '{key}': thiếu git_name/name hoặc git_email")
        elif not EMAIL_RE.match(str(email).strip()):
            errors.append(f"thành viên '{key}': git_email '{email}' không hợp lệ")
        else:
            ids.append({"key": key, "name": str(name).strip(), "email": str(email).strip()})
    return ids, errors


def identity_for(cfg: dict, key: str | None) -> dict | None:
    """Danh tính git của một thành viên (dùng cho rotation=owner)."""
    ids, _ = git_identities(cfg)
    return next((i for i in ids if i["key"] == key), None)


def git_problems(cfg: dict) -> list[str]:
    """Lỗi chặn flow khi bật xoay vòng (tránh ghi commit cho email điền sai)."""
    mode = rotation(cfg)
    if mode == "invalid":
        return [f"git.rotation phải là một trong {ROTATIONS}"]
    if mode == "off":
        return []
    ids, errors = git_identities(cfg)
    if not ids and not errors:
        errors.append("git.rotation đang bật nhưng chưa có thành viên nào")
    return errors


@contextmanager
def _locked(path: Path, timeout: float = 60.0):
    lock = path.with_suffix(path.suffix + ".lock")
    deadline = time.time() + timeout
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if time.time() - lock.stat().st_mtime > 120:  # khoá mồ côi do tiến trình chết
                lock.unlink(missing_ok=True)
                continue
            if time.time() > deadline:
                raise TimeoutError(f"không lấy được khoá {lock}")
            time.sleep(0.2)
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


@contextmanager
def rotation_slot(flow_root: Path, ids: list[dict]):
    """Giữ khoá bộ đếm dùng chung, trả danh tính kế tiếp; gọi `commit()` để tiến bộ đếm.

    Bộ đếm nằm ở `<flow_root>/git-rotation.json`, dùng chung cho mọi module, nên các
    module chạy song song vẫn xoay đều giữa các thành viên.
    """
    flow_root.mkdir(parents=True, exist_ok=True)
    counter = flow_root / "git-rotation.json"
    with _locked(counter):
        try:
            data = json.loads(counter.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        index = int(data.get("next", 0))
        who = ids[index % len(ids)]

        class Slot:
            identity = who

            @staticmethod
            def commit() -> None:
                data["next"] = (index + 1) % len(ids)
                data["last"] = who["key"]
                counter.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        yield Slot


# ------------------------------------------------------------------ kiểm tra file

NOREPLY_RE = re.compile(r"^(?:(\d+)\+)?([^@]+)@users\.noreply\.github\.com$", re.I)


def _github_user(login: str) -> tuple[dict | None, str | None]:
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        f"https://api.github.com/users/{login}",
        headers={"User-Agent": "smart-workout-agent-flow", "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None, "không tồn tại trên GitHub"
        return None, f"GitHub API lỗi HTTP {exc.code} (có thể hết lượt gọi, thử lại sau)"
    except OSError as exc:
        return None, f"không gọi được GitHub API: {exc}"


def check(send: bool = False) -> int:
    """In kết quả kiểm tra team.json; trả số lỗi (cảnh báo không tính)."""
    import notify  # import muộn: notify import team

    errors = 0

    def bad(msg: str) -> None:
        nonlocal errors
        errors += 1
        print(f"  [LỖI]  {msg}")

    def warn(msg: str) -> None:
        print(f"  [CHÚ Ý] {msg}")

    def ok(msg: str) -> None:
        print(f"  [OK]   {msg}")

    cfg, err = load()
    print(f"File: {CONFIG_PATH}")
    if err or not cfg:
        bad(err or "chưa có team.json (copy từ team.example.json)")
        return errors
    members = cfg.get("members") or {}

    print("\n1. Git / xoay vòng tác giả")
    mode = rotation(cfg)
    if mode == "invalid":
        bad(f"git.rotation phải là một trong {ROTATIONS}")
    else:
        ok(f"git.rotation = {mode}")
    ids, id_errors = git_identities(cfg)
    for e in id_errors:
        bad(e)
    for i in ids:
        ok(f"{i['key']}: {i['name']} <{i['email']}>")
    emails = [i["email"].lower() for i in ids]
    for dup in sorted({e for e in emails if emails.count(e) > 1}):
        bad(f"email {dup} bị trùng giữa nhiều thành viên")

    print("\n2. GitHub (email có được tính cho đúng tài khoản không)")
    for key, m in members.items():
        login, email = m.get("github"), str(m.get("git_email") or "").strip()
        if is_blank(login):
            warn(f"{key}: chưa điền github, bỏ qua")
            continue
        user, gh_err = _github_user(str(login).strip())
        if gh_err:
            (warn if "API" in gh_err else bad)(f"{key}: github '{login}' {gh_err}")
            continue
        match = NOREPLY_RE.match(email)
        if not match:
            warn(f"{key}: @{user['login']} tồn tại; email '{email}' không phải noreply nên không tự "
                 "kiểm tra được. Hãy chắc nó đã được verify trong GitHub → Settings → Emails")
            continue
        gid, guser = match.groups()
        if guser.lower() != user["login"].lower():
            bad(f"{key}: email noreply ghi username '{guser}' nhưng github là '{user['login']}'")
        elif gid and int(gid) != user["id"]:
            bad(f"{key}: email noreply có ID {gid} nhưng ID thật của @{user['login']} là {user['id']}")
        else:
            ok(f"{key}: email noreply khớp tài khoản @{user['login']} (ID {user['id']})")

    print("\n3. Telegram")
    tg = cfg.get("telegram") or {}
    if not tg.get("enabled", True):
        warn("telegram.enabled = false, flow sẽ không gửi tin")
    targets: list[tuple[str, str, str]] = []
    tokens: dict[str, str] = {}
    for key, m in members.items():
        token, chat = m.get("telegram_token"), m.get("telegram_chat_id")
        if is_blank(token) or is_blank(chat):
            bad(f"{key}: thiếu telegram_token hoặc telegram_chat_id")
            continue
        targets.append((key, str(token).strip(), str(chat).strip()))
    common = tg.get("common") or {}
    if is_blank(common.get("token")):
        warn("bot chung chưa có token → chỉ bot riêng nhận tin")
    else:
        chats = [str(c).strip() for c in common.get("chat_ids", []) if not is_blank(c)]
        if not chats:
            bad("bot chung có token nhưng chưa có chat_ids")
        targets += [("common", str(common["token"]).strip(), c) for c in chats]

    for label, token, chat in targets:
        me = notify._call(token, "getMe")
        if not me.get("ok"):
            bad(f"{label}: token {notify.mask(token)} không hợp lệ ({me.get('description')})")
            continue
        bot = me["result"].get("username")
        if label != "common" and tokens.get(bot):
            warn(f"{label}: dùng chung bot @{bot} với {tokens[bot]} (dự kiến mỗi người một bot)")
        tokens.setdefault(bot, label)
        info = notify._call(token, "getChat", {"chat_id": chat})
        if not info.get("ok"):
            bad(f"{label}: bot @{bot} không liên lạc được chat_id {chat} ({info.get('description')}). "
                "Người nhận phải mở bot và bấm Start; với group phải thêm bot vào group")
            continue
        c = info["result"]
        who = c.get("title") or " ".join(x for x in (c.get("first_name"), c.get("last_name")) if x)
        user = f" @{c['username']}" if c.get("username") else ""
        line = f"{label}: bot @{bot} → {c.get('type')} '{who}'{user}"
        if send:
            sent = notify.Notifier(cfg, log=print).send_one(
                label, token, chat, f"🔔 <b>Agent flow</b>: kiểm tra team.json, bot <code>{label}</code> OK.")
            if not sent:
                bad(f"{line}: gửi tin thử thất bại")
                continue
            line += " · đã gửi tin thử"
        ok(line)

    print("\n4. owner trong các spec (docs/features)")
    features = HERE.parent.parent / "docs" / "features"
    specs = sorted(p for p in features.glob("*.md") if not p.name.startswith("_")) if features.exists() else []
    if not specs:
        warn("chưa có spec module nào; key thành viên dùng cho owner: " + ", ".join(members))
    for spec in specs:
        found = re.search(r"(?m)^owner:\s*([^\s#]+)", spec.read_text(encoding="utf-8"))
        owner = found.group(1) if found else None
        if not owner:
            warn(f"{spec.name}: chưa có owner")
        elif owner not in members:
            bad(f"{spec.name}: owner '{owner}' không có trong members ({', '.join(members)})")
        else:
            ok(f"{spec.name}: owner {owner}")

    print(f"\nKết luận: {'ĐẠT' if not errors else f'{errors} lỗi cần sửa'}")
    return errors


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2 or sys.argv[1] != "check":
        print(__doc__)
        sys.exit(2)
    sys.exit(1 if check(send="--send" in sys.argv[2:]) else 0)
