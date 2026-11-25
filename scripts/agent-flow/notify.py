#!/usr/bin/env python3
"""Gửi thông báo tiến độ agent flow qua Telegram.

Mỗi thành viên có một bot riêng nhắn cho chính họ khi flow chạy module họ phụ trách
(`owner` trong frontmatter của spec). Bot chung nhắn MỌI thông báo của mọi module
(thường vào group của nhóm).

Cấu hình: `scripts/agent-flow/team.json` (đã gitignore, KHÔNG commit, chứa token).
Mẫu: `team.example.json`. Các khoá dùng ở đây:
  telegram.enabled, telegram.common.{token, chat_ids}
  members.<key>.{name, telegram_token, telegram_chat_id}

    python scripts/agent-flow/notify.py chat-id <member|common>   # lấy chat_id sau khi nhắn /start cho bot
    python scripts/agent-flow/notify.py test                      # gửi thử tới mọi bot đã cấu hình
    python scripts/agent-flow/notify.py send <member|common> "nội dung"

Chỉ dùng thư viện chuẩn. Lỗi mạng/Telegram chỉ ghi cảnh báo, không bao giờ làm dừng flow.
"""

from __future__ import annotations

import html
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import team  # noqa: E402
from team import is_blank  # noqa: E402

API_BASE = os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org")
MAX_LEN = 4000  # Telegram giới hạn 4096 ký tự / tin


def esc(text: object) -> str:
    return html.escape(str(text), quote=False)


def _call(token: str, method: str, payload: dict | None = None, timeout: int = 15) -> dict:
    url = f"{API_BASE}/bot{token}/{method}"
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode("utf-8"))
        except ValueError:
            return {"ok": False, "description": f"HTTP {exc.code}"}


def mask(token: str) -> str:
    return token.split(":", 1)[0] + ":***" if token else "(trống)"


class Notifier:
    """Định tuyến tin nhắn: bot của owner module + bot chung."""

    def __init__(self, config: dict | None, log=print) -> None:
        self.config = config or {}
        tg = self.config.get("telegram") or {}
        self.enabled = bool(tg) and bool(tg.get("enabled", True))
        self.log = log

    @classmethod
    def load(cls, log=print) -> "Notifier":
        cfg, err = team.load()
        if err:
            log(f"CẢNH BÁO: {err}; tắt thông báo")
        return cls(cfg, log)

    # ------------------------------------------------------------- cấu hình
    def members(self) -> dict:
        return self.config.get("members") or {}

    def common(self) -> dict:
        return (self.config.get("telegram") or {}).get("common") or {}

    def member_name(self, key: str | None) -> str:
        name = self.members().get(key or "", {}).get("name")
        return name if not is_blank(name) else (key or "(chưa gán)")

    def member_target(self, key: str) -> tuple[str, str] | None:
        m = self.members().get(key) or {}
        token, chat = m.get("telegram_token"), m.get("telegram_chat_id")
        if is_blank(token) or is_blank(chat):
            return None
        return str(token), str(chat)

    def common_targets(self) -> list[tuple[str, str]]:
        token = self.common().get("token")
        if is_blank(token):
            return []
        return [(str(token), str(c)) for c in self.common().get("chat_ids", []) if not is_blank(c)]

    def targets(self, owner: str | None) -> list[tuple[str, str, str]]:
        """[(nhãn, token, chat_id)] cho một module có owner này."""
        out = []
        mine = self.member_target(owner) if owner else None
        if mine:
            out.append((f"owner:{owner}", *mine))
        out += [("common", token, chat) for token, chat in self.common_targets()]
        return out

    def problems(self, owner: str | None) -> list[str]:
        """Cảnh báo cấu hình để runner in lúc khởi động."""
        if not self.enabled:
            return ["Telegram đang tắt (không có team.json hoặc telegram.enabled=false)"]
        issues = []
        if not owner:
            issues.append("spec chưa có 'owner' → chỉ bot chung nhận tin")
        elif owner not in self.members():
            issues.append(f"owner '{owner}' của spec không có trong team.json → chỉ bot chung nhận tin")
        elif not self.member_target(owner):
            issues.append(f"bot của '{owner}' thiếu telegram_token hoặc telegram_chat_id")
        if not self.common_targets():
            issues.append("bot chung thiếu token hoặc chat_ids")
        return issues

    # ------------------------------------------------------------- gửi
    def send_with_buttons(self, owner: str | None, text: str, buttons: list[list[dict]]) -> list[dict]:
        """Gửi tin có nút bấm tới owner + nhóm; trả [{token, chat_id, message_id}] để sửa tin sau."""
        sent = []
        if not self.enabled:
            return sent
        for label, token, chat in self.targets(owner):
            try:
                res = _call(token, "sendMessage", {
                    "chat_id": chat, "text": text[:MAX_LEN], "parse_mode": "HTML",
                    "disable_web_page_preview": True, "reply_markup": {"inline_keyboard": buttons},
                })
            except (urllib.error.URLError, OSError, ValueError) as exc:  # một bot lỗi mạng không chặn bot khác
                res = {"ok": False, "description": str(exc)}
            if res.get("ok"):
                sent.append({"token": token, "chat_id": chat, "message_id": res["result"]["message_id"]})
            else:
                self.log(f"CẢNH BÁO: gửi Telegram ({label}) lỗi: {res.get('description')}")
        return sent

    @staticmethod
    def edit(messages: list[dict], text: str) -> None:
        """Sửa nội dung (và bỏ nút) của các tin đã gửi bằng send_with_buttons."""
        for m in messages:
            try:
                _call(m["token"], "editMessageText", {
                    "chat_id": m["chat_id"], "message_id": m["message_id"], "text": text[:MAX_LEN],
                    "parse_mode": "HTML", "disable_web_page_preview": True,
                })
            except (urllib.error.URLError, OSError, ValueError):
                pass

    def send(self, owner: str | None, text: str) -> None:
        if not self.enabled:
            return
        if len(text) > MAX_LEN:
            text = text[: MAX_LEN - 20] + "\n…(đã cắt bớt)"
        for label, token, chat in self.targets(owner):
            self.send_one(label, token, chat, text)

    def send_one(self, label: str, token: str, chat: str, text: str) -> bool:
        payload = {"chat_id": chat, "text": text, "parse_mode": "HTML",
                   "disable_web_page_preview": True}
        for attempt in range(3):
            try:
                res = _call(token, "sendMessage", payload)
            except (urllib.error.URLError, OSError, ValueError) as exc:
                res = {"ok": False, "description": str(exc)}
            if res.get("ok"):
                return True
            retry = (res.get("parameters") or {}).get("retry_after")
            if retry and attempt < 2:
                time.sleep(min(int(retry), 60))
                continue
            if attempt < 2 and not res.get("error_code"):
                time.sleep(3)  # lỗi mạng tạm thời
                continue
            self.log(f"CẢNH BÁO: gửi Telegram ({label}, bot {mask(token)}) lỗi: "
                     f"{res.get('description')}")
            return False
        return False


# ----------------------------------------------------------------- CLI

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    if not args or args[0] not in ("chat-id", "test", "send"):
        print(__doc__)
        return 2
    if not team.CONFIG_PATH.exists():
        print(f"Chưa có {team.CONFIG_PATH}. Copy team.example.json thành team.json rồi điền.")
        return 2
    notifier = Notifier.load()

    if args[0] == "chat-id":
        if len(args) < 2:
            print("Cách dùng: notify.py chat-id <member|common>")
            return 2
        who = args[1]
        token = notifier.common().get("token") if who == "common" else \
            (notifier.members().get(who) or {}).get("telegram_token")
        if is_blank(token):
            print(f"'{who}' chưa có token trong team.json")
            return 2
        res = _call(str(token), "getUpdates", {"timeout": 0})
        if not res.get("ok"):
            print(f"Lỗi: {res.get('description')}")
            return 1
        chats = {}
        for upd in res.get("result", []):
            msg = upd.get("message") or upd.get("channel_post") or upd.get("my_chat_member") or {}
            chat = msg.get("chat") or {}
            if chat.get("id") is not None:
                title = chat.get("title") or " ".join(
                    x for x in (chat.get("first_name"), chat.get("last_name")) if x)
                user = f" · @{chat['username']}" if chat.get("username") else ""
                chats[chat["id"]] = f"{chat.get('type')} · {title}{user}"
        if not chats:
            print("Chưa thấy tin nào. Mở bot trên Telegram, bấm Start (hoặc gõ /start trong group "
                  "có bot), rồi chạy lại lệnh này.")
            return 1
        for cid, desc in chats.items():
            print(f"chat_id={cid}   ({desc})")
        return 0

    if args[0] == "test":
        if not notifier.enabled:
            print("Telegram đang tắt (telegram.enabled=false)")
            return 1
        targets = [("common", t, c) for t, c in notifier.common_targets()]
        for key in notifier.members():
            mine = notifier.member_target(key)
            if mine:
                targets.append((f"owner:{key}", *mine))
            else:
                print(f"BỎ QUA owner:{key} (chưa điền telegram_token/telegram_chat_id)")
        if not targets:
            print("Không có bot nào đủ token + chat_id")
            return 1
        ok = True
        for label, token, chat in targets:
            text = f"🔔 <b>Agent flow</b>: thử kết nối bot <code>{esc(label)}</code> thành công."
            sent = notifier.send_one(label, token, chat, text)
            ok &= sent
            print(f"{'OK  ' if sent else 'LỖI'} {label:<16} bot {mask(token)} → chat {chat}")
        return 0 if ok else 1

    if len(args) < 3:
        print("Cách dùng: notify.py send <member|common> \"nội dung\"")
        return 2
    target, text = args[1], esc(args[2])
    pairs = notifier.common_targets() if target == "common" else \
        [p for p in [notifier.member_target(target)] if p]
    for token, chat in pairs:
        notifier.send_one(target, token, chat, text)
    return 0 if pairs else 1


if __name__ == "__main__":
    sys.exit(main())
