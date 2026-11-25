#!/usr/bin/env python3
"""MCP server (stdio) trả lời yêu cầu xin quyền của agent flow qua Telegram.

Runner khởi động Claude với:
    --mcp-config <state>/perm-mcp.json --permission-prompts host
    --permission-prompt-tool mcp__flowperm__approve

Mỗi khi Claude cần hỏi quyền (quy tắc "ask" trong flow-settings.json, hoặc auto mode
không chắc chắn), tool `approve` sẽ:
1. ghi yêu cầu vào <FLOW_STATE_DIR>/perm/<id>.req.json;
2. gửi tin có nút ✅ Cho phép / ⛔ Từ chối tới bot của owner + nhóm chung;
3. chờ bot.py ghi <id>.res.json khi có người bấm nút; quá FLOW_PERM_TIMEOUT giây
   (mặc định 1800 = 30 phút) thì tự TỪ CHỐI để flow không treo.

Biến môi trường: FLOW_STATE_DIR, FLOW_MODULE, FLOW_OWNER, FLOW_PERM_TIMEOUT.
Chỉ dùng thư viện chuẩn; giao thức MCP = JSON-RPC 2.0, mỗi dòng một message.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import notify  # noqa: E402
from notify import esc  # noqa: E402

STATE_DIR = Path(os.environ.get("FLOW_STATE_DIR", "."))
MODULE = os.environ.get("FLOW_MODULE", "?")
OWNER = os.environ.get("FLOW_OWNER") or None
TIMEOUT = int(os.environ.get("FLOW_PERM_TIMEOUT", "1800"))
PERM_DIR = STATE_DIR / "perm"

TOOL = {
    "name": "approve",
    "description": "Hỏi người trong nhóm (qua Telegram) có cho agent dùng một tool cần quyền không.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "tool_name": {"type": "string"},
            "input": {"type": "object"},
            "tool_use_id": {"type": "string"},
        },
        "required": ["tool_name", "input"],
    },
}


def log(msg: str) -> None:
    PERM_DIR.mkdir(parents=True, exist_ok=True)
    with (PERM_DIR / "perm-mcp.log").open("a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def describe(tool_name: str, tool_input: dict) -> str:
    detail = (tool_input.get("command") or tool_input.get("file_path") or tool_input.get("url")
              or json.dumps(tool_input, ensure_ascii=False))
    return f"{tool_name}: {str(detail)[:600]}"


def decide(tool_name: str, tool_input: dict) -> dict:
    """Gửi yêu cầu lên Telegram và chờ câu trả lời; trả quyết định theo định dạng Claude cần."""
    PERM_DIR.mkdir(parents=True, exist_ok=True)
    req_id = uuid.uuid4().hex[:8]
    req_path, res_path = PERM_DIR / f"{req_id}.req.json", PERM_DIR / f"{req_id}.res.json"
    what = describe(tool_name, tool_input)
    notifier = notify.Notifier.load(log)
    minutes = f"{TIMEOUT // 60} phút" if TIMEOUT >= 60 else f"{TIMEOUT} giây"
    text = (f"🔐 <b>[{esc(MODULE)}]</b> agent xin quyền:\n<code>{esc(what)}</code>\n"
            f"Flow đang chờ; quá {minutes} không ai trả lời thì tự từ chối.")
    buttons = [[{"text": "✅ Cho phép", "callback_data": f"perm|{MODULE}|{req_id}|allow"[:64]},
                {"text": "⛔ Từ chối", "callback_data": f"perm|{MODULE}|{req_id}|deny"[:64]}]]
    messages = notifier.send_with_buttons(OWNER, text, buttons)
    req_path.write_text(json.dumps({
        "id": req_id, "module": MODULE, "tool_name": tool_name, "input": tool_input,
        "what": what, "created": time.time(), "messages": messages,
    }, ensure_ascii=False), encoding="utf-8")
    log(f"yêu cầu {req_id}: {what} (gửi {len(messages)} tin)")
    if not messages:
        return {"behavior": "deny", "message": "Không gửi được yêu cầu xin quyền lên Telegram; đã từ chối. "
                                               "Hãy làm cách khác hoặc ghi câu hỏi vào state.json."}

    deadline = time.time() + TIMEOUT
    while time.time() < deadline:
        if res_path.exists():
            try:
                res = json.loads(res_path.read_text(encoding="utf-8"))
            except ValueError:
                time.sleep(1)
                continue
            log(f"yêu cầu {req_id}: {res.get('decision')} bởi {res.get('by')}")
            if res.get("decision") == "allow":
                return {"behavior": "allow", "updatedInput": tool_input}
            return {"behavior": "deny",
                    "message": f"{res.get('by', 'Người trong nhóm')} đã từ chối qua Telegram. "
                               "Không thử lại thao tác này; làm cách khác hoặc ghi câu hỏi vào state.json."}
        time.sleep(2)

    log(f"yêu cầu {req_id}: hết {minutes}, tự từ chối")
    res_path.write_text(json.dumps({"decision": "deny", "by": "timeout"}), encoding="utf-8")
    notify.Notifier.edit(messages, f"⌛ <b>[{esc(MODULE)}]</b> hết {minutes} không ai trả lời, "
                                   f"đã TỪ CHỐI:\n<code>{esc(what)}</code>")
    return {"behavior": "deny",
            "message": f"Không ai duyệt trong {minutes} nên đã từ chối. Không thử lại; làm cách khác "
                       "hoặc ghi câu hỏi vào state.json."}


def reply(msg_id, result=None, error=None) -> None:
    out = {"jsonrpc": "2.0", "id": msg_id}
    if error:
        out["error"] = error
    else:
        out["result"] = result
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        method, msg_id = msg.get("method"), msg.get("id")
        if msg_id is None:  # notification (vd notifications/initialized): không trả lời
            continue
        if method == "initialize":
            version = (msg.get("params") or {}).get("protocolVersion", "2025-06-18")
            reply(msg_id, {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
                           "serverInfo": {"name": "flowperm", "version": "1.0.0"}})
        elif method == "tools/list":
            reply(msg_id, {"tools": [TOOL]})
        elif method == "tools/call":
            params = msg.get("params") or {}
            args = params.get("arguments") or {}
            if params.get("name") != "approve":
                reply(msg_id, error={"code": -32602, "message": "tool không tồn tại"})
                continue
            try:
                decision = decide(str(args.get("tool_name", "?")), args.get("input") or {})
            except Exception as exc:  # noqa: BLE001 - lỗi bất kỳ = từ chối, không làm treo Claude
                log(f"lỗi: {exc!r}")
                decision = {"behavior": "deny", "message": f"Lỗi khi xin quyền ({exc}); đã từ chối."}
            reply(msg_id, {"content": [{"type": "text", "text": json.dumps(decision, ensure_ascii=False)}]})
        elif method == "ping":
            reply(msg_id, {})
        else:
            reply(msg_id, error={"code": -32601, "message": f"không hỗ trợ {method}"})


if __name__ == "__main__":
    main()
