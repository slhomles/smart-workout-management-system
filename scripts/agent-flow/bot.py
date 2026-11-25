#!/usr/bin/env python3
"""Bot Telegram điều khiển agent flow smart_workout (chạy trên máy có Claude Code + Tailscale).

    python scripts/agent-flow/bot.py [--model opus] [--runner-args "--max-iterations 60"]

Lệnh (gửi trong group cho bot chung, hoặc nhắn riêng bot của bạn):
  /help                     hướng dẫn
  /modules                  danh sách module, owner, trạng thái
  /run <module> [--respec]  soạn spec (nếu chưa có hoặc --respec) rồi chạy flow; mỗi lúc chạy một flow
  /status                   flow đang chạy, hàng đợi, kết quả gần nhất
  /stop <module>            dừng flow đang chạy hoặc bỏ khỏi hàng đợi
  /answer <module> <nội dung>  trả lời câu hỏi của agent (flow đang bị chặn sẽ chạy tiếp)
  /owner <module> <thành viên> đổi người phụ trách module (key trong team.json)

Chỉ nhận lệnh/nút bấm từ tài khoản Telegram của thành viên trong team.json.
Nút ✅/⛔ xin quyền do perm_mcp.py gửi; bot ghi câu trả lời để agent chạy tiếp.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
import check_done  # noqa: E402
import notify  # noqa: E402
import run_flow as rf  # noqa: E402
import team  # noqa: E402
from notify import _call, esc  # noqa: E402

MODULES_FILE = HERE / "modules.json"
DOCX = REPO / "Mô tả dự án.docx"
SPEC_RE = re.compile(r"<<<SPEC\s*\n(.*?)\n\s*SPEC>>>", re.S)
EXIT_TEXT = {0: "✅ xong", 1: "❌ lỗi", 2: "⛔ bị chặn, chờ trả lời", 3: "🧱 kẹt",
             4: "⌛ hết iteration", 5: "❌ môi trường chưa sẵn sàng", -1: "⏹ đã dừng"}
HELP = __doc__.split("Lệnh", 1)[1].split("Chỉ nhận", 1)[0]


API_DOC = REPO / "docs" / "architecture" / "Claude_api_respone.md"
CODE_IN_TC_RE = re.compile(r"error\.code\s*[=:]\s*[`'\"]?([a-z][a-z0-9_]*)")


def registered_error_codes() -> set[str]:
    """Mã lỗi trong bảng Claude_api_respone.md §10 (nguồn duy nhất được phép dùng)."""
    text = API_DOC.read_text(encoding="utf-8")
    section = text.split("## 10.", 1)[1].split("\n## ", 1)[0] if "## 10." in text else ""
    return set(re.findall(r"^\|\s*`([a-z][a-z0-9_]*)`\s*\|", section, re.M))


def unregistered_codes(tcs: list[dict]) -> list[str]:
    allowed = registered_error_codes()
    used = {c for tc in tcs for c in CODE_IN_TC_RE.findall(tc["desc"])}
    return sorted(c for c in used if c not in allowed and not re.fullmatch(r"http_\d{3}", c))


def load_modules() -> dict:
    return json.loads(MODULES_FILE.read_text(encoding="utf-8"))


def save_modules(data: dict) -> None:
    MODULES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def docx_text(out: Path) -> Path:
    """Trích text 'Mô tả dự án.docx' (agent không đọc được .docx)."""
    if out.exists() and DOCX.exists() and out.stat().st_mtime >= DOCX.stat().st_mtime:
        return out
    xml = zipfile.ZipFile(DOCX).read("word/document.xml").decode("utf-8")
    paras = []
    for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
        text = re.sub(r"<[^>]+>", "", p).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        if text.strip():
            paras.append(text.strip())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(paras) + "\n", encoding="utf-8")
    return out


class Bot:
    def __init__(self, args) -> None:
        self.args = args
        self.root = Path(args.flow_root) if args.flow_root else REPO.parent / f"{REPO.name}-flow"
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_file = self.root / "bot-state.json"
        self.log = rf.Logger()
        self.log.file = self.root / "bot.log"
        cfg, err = team.load()
        if err:
            raise SystemExit(f"team.json lỗi: {err}")
        self.cfg = cfg
        self.notifier = notify.Notifier(cfg, self.log)
        self.users = {}  # telegram user id -> key thành viên
        for key, m in (cfg.get("members") or {}).items():
            if not team.is_blank(m.get("telegram_chat_id")):
                self.users[int(str(m["telegram_chat_id"]).strip())] = key
        tokens = [m.get("telegram_token") for m in (cfg.get("members") or {}).values()]
        tokens.append(self.notifier.common().get("token"))
        self.tokens = sorted({str(t).strip() for t in tokens if not team.is_blank(t)})
        self.updates: queue.Queue = queue.Queue()
        self.lock = threading.RLock()
        self.state = rf.read_json(self.state_file, {"queue": [], "current": None, "last": {}})
        self.proc: subprocess.Popen | None = None
        self.spec_proc: subprocess.Popen | None = None
        self.started = time.time()
        self.stop_event = threading.Event()

    # ------------------------------------------------------------------ tiện ích
    def save(self) -> None:
        with self.lock:
            rf.write_json(self.state_file, self.state)

    def name(self, key: str | None) -> str:
        return self.notifier.member_name(key)

    def reply(self, token: str, chat_id, text: str) -> None:
        self.notifier.send_one("reply", token, str(chat_id), text)

    def announce(self, owner: str | None, text: str) -> None:
        """Tin về một module: bot riêng của owner + nhóm chung."""
        try:
            self.notifier.send(owner, text)
        except Exception as exc:  # noqa: BLE001
            self.log(f"CẢNH BÁO: gửi thông báo lỗi: {exc}")

    def module_status(self, key: str) -> str:
        with self.lock:
            cur = self.state.get("current")
            if cur and cur["module"] == key:
                return "🔄 đang soạn spec" if cur["phase"] == "spec" else "🔄 đang chạy"
            if any(j["module"] == key for j in self.state["queue"]):
                return "⏳ đang xếp hàng"
            last = self.state["last"].get(key)
        return EXIT_TEXT.get(last["code"], f"exit {last['code']}") if last else "chưa chạy"

    # ------------------------------------------------------------------ nhận update
    def poll(self, token: str) -> None:
        offset = 0
        while not self.stop_event.is_set():
            try:
                res = _call(token, "getUpdates", {"timeout": 25, "offset": offset,
                                                  "allowed_updates": ["message", "callback_query"]},
                            timeout=40)
            except (OSError, ValueError) as exc:
                self.log(f"getUpdates lỗi ({notify.mask(token)}): {exc}")
                time.sleep(5)
                continue
            if not res.get("ok"):
                self.log(f"getUpdates lỗi ({notify.mask(token)}): {res.get('description')}")
                time.sleep(10)
                continue
            for upd in res.get("result", []):
                offset = upd["update_id"] + 1
                self.updates.put((token, upd))

    def handle(self, token: str, upd: dict) -> None:
        if "callback_query" in upd:
            cq = upd["callback_query"]
            who = self.users.get(cq.get("from", {}).get("id"))
            if not who:
                _call(token, "answerCallbackQuery", {"callback_query_id": cq["id"],
                                                     "text": "Bạn không thuộc nhóm, không có quyền."})
                return
            self.on_permission(token, cq, who)
            return
        msg = upd.get("message") or {}
        text = (msg.get("text") or "").strip()
        if not text.startswith("/") or msg.get("date", 0) < self.started - 5:
            return  # bỏ tin thường và lệnh cũ gửi trước khi bot bật
        chat_id = msg["chat"]["id"]
        who = self.users.get(msg.get("from", {}).get("id"))
        if not who:
            self.reply(token, chat_id, "⛔ Chỉ thành viên nhóm (có trong team.json) mới ra lệnh được.")
            return
        parts = text.split(maxsplit=2)
        cmd = parts[0].split("@", 1)[0].lower()
        self.log(f"lệnh từ {who}: {text[:200]}")
        handler = {
            "/start": self.cmd_help, "/help": self.cmd_help, "/modules": self.cmd_modules,
            "/run": self.cmd_run, "/status": self.cmd_status, "/stop": self.cmd_stop,
            "/answer": self.cmd_answer, "/owner": self.cmd_owner,
        }.get(cmd)
        if not handler:
            self.reply(token, chat_id, "Lệnh không rõ. Gõ /help để xem danh sách lệnh.")
            return
        try:
            handler(token, chat_id, who, parts[1:])
        except Exception as exc:  # noqa: BLE001 - một lệnh lỗi không được làm sập bot
            self.log(f"lỗi xử lý {cmd}: {exc!r}")
            self.reply(token, chat_id, f"❌ Lỗi khi xử lý {esc(cmd)}: {esc(exc)}")

    # ------------------------------------------------------------------ lệnh
    def module_arg(self, token, chat_id, args: list[str]) -> str | None:
        modules = load_modules()["modules"]
        key = args[0].strip().lower() if args else ""
        if key not in modules:
            self.reply(token, chat_id, "Module không có trong danh mục. Có: "
                       + ", ".join(f"<code>{k}</code>" for k in modules))
            return None
        return key

    def cmd_help(self, token, chat_id, who, args) -> None:
        self.reply(token, chat_id, f"🤖 <b>Bot agent flow smart_workout</b>\n<pre>{esc(HELP.strip())}</pre>")

    def cmd_modules(self, token, chat_id, who, args) -> None:
        lines = ["📦 <b>Danh mục module</b>"]
        for key, m in load_modules()["modules"].items():
            owner = self.name(m.get("owner")) if m.get("owner") else "⚠️ chưa có owner"
            lines.append(f"• <code>{key}</code>: {esc(m['title'])}\n   {esc(owner)} · {self.module_status(key)}")
        self.reply(token, chat_id, "\n".join(lines))

    def cmd_run(self, token, chat_id, who, args) -> None:
        key = self.module_arg(token, chat_id, args)
        if not key:
            return
        entry = load_modules()["modules"][key]
        if not entry.get("owner") or entry["owner"] not in (self.cfg.get("members") or {}):
            self.reply(token, chat_id, f"⚠️ <code>{key}</code> chưa có owner hợp lệ. Gán bằng "
                       f"<code>/owner {key} &lt;thành viên&gt;</code> (có: {', '.join(self.cfg['members'])}).")
            return
        respec = len(args) > 1 and "--respec" in args[1]
        with self.lock:
            cur = self.state.get("current")
            if (cur and cur["module"] == key) or any(j["module"] == key for j in self.state["queue"]):
                self.reply(token, chat_id, f"<code>{key}</code> đang chạy hoặc đã trong hàng đợi.")
                return
            self.state["queue"].append({"module": key, "by": who, "respec": respec, "resume": False})
            pos = len(self.state["queue"]) + (1 if cur else 0)
            self.save()
        warn = ""
        core_last = self.state["last"].get("core")
        if key != "core" and not (core_last and core_last["code"] == 0):
            warn = "\n⚠️ Module <code>core</code> chưa xong; flow có thể bị chặn vì thiếu phần nền."
        self.announce(entry["owner"], f"📥 {esc(self.name(who))} yêu cầu chạy <b>[{key}]</b> "
                      f"({esc(entry['title'])}). Vị trí hàng đợi: {pos}.{warn}")

    def cmd_status(self, token, chat_id, who, args) -> None:
        with self.lock:
            cur, q, last = self.state.get("current"), list(self.state["queue"]), dict(self.state["last"])
        lines = ["📊 <b>Trạng thái</b>"]
        if cur:
            mins = int((time.time() - cur["started"]) / 60)
            lines.append(f"Đang chạy: <b>[{cur['module']}]</b> ({'soạn spec' if cur['phase'] == 'spec' else 'flow'}"
                         f", {mins} phút)")
            if cur["phase"] == "run":
                sdir = self.root / cur["module"] / "state"
                run_info, gate = rf.read_json(sdir / "run.json", {}), rf.read_json(sdir / "gate-runner.json", {})
                st = rf.read_json(sdir / "state.json", {})
                done = sum(1 for t in st.get("tasks", []) if t.get("status") == "done")
                lines.append(f"   iteration {run_info.get('iterations_done', 0)} · "
                             f"{esc(gate.get('gates', {}).get('tc', {}).get('summary', 'chưa có kết quả cổng'))} · "
                             f"task {done}/{len(st.get('tasks', []))}")
                pending = [p for p in (sdir / "perm").glob("*.req.json")
                           if not p.with_name(p.name.replace(".req", ".res")).exists()]
                if pending:
                    lines.append(f"   🔐 đang chờ duyệt {len(pending)} yêu cầu quyền")
        else:
            lines.append("Không có flow nào đang chạy.")
        lines.append("Hàng đợi: " + (", ".join(j["module"] for j in q) if q else "trống"))
        if last:
            lines.append("Gần nhất:")
            lines += [f"• {k}: {EXIT_TEXT.get(v['code'], v['code'])} ({v['at']})" for k, v in last.items()]
        self.reply(token, chat_id, "\n".join(lines))

    def cmd_stop(self, token, chat_id, who, args) -> None:
        key = self.module_arg(token, chat_id, args)
        if not key:
            return
        owner = load_modules()["modules"][key].get("owner")
        with self.lock:
            before = len(self.state["queue"])
            self.state["queue"] = [j for j in self.state["queue"] if j["module"] != key]
            if len(self.state["queue"]) != before:
                self.save()
                self.announce(owner, f"🗑 {esc(self.name(who))} đã bỏ <b>[{key}]</b> khỏi hàng đợi.")
                return
            cur = self.state.get("current")
            if not cur or cur["module"] != key:
                self.reply(token, chat_id, f"<code>{key}</code> không chạy cũng không xếp hàng.")
                return
            cur["stopped_by"] = who
            self.save()
        for proc in (self.spec_proc, self.proc):
            if proc and proc.poll() is None:
                rf.kill_tree(proc)
        if cur.get("pid") and rf.pid_alive(cur["pid"]):
            rf.kill_pid_tree(cur["pid"])
        (self.root / key / "state" / "runner.lock").unlink(missing_ok=True)
        self.announce(owner, f"⏹ {esc(self.name(who))} đã dừng <b>[{key}]</b>. "
                      f"Chạy lại bằng <code>/run {key}</code> (tiếp tục từ chỗ dừng).")

    def cmd_answer(self, token, chat_id, who, args) -> None:
        key = self.module_arg(token, chat_id, args)
        if not key:
            return
        if len(args) < 2 or not args[1].strip():
            self.reply(token, chat_id, f"Cách dùng: <code>/answer {key} &lt;nội dung trả lời&gt;</code>")
            return
        answers = self.root / key / "state" / "ANSWERS.md"
        answers.parent.mkdir(parents=True, exist_ok=True)
        with answers.open("a", encoding="utf-8") as fh:
            fh.write(f"\n## {rf.now()} — {self.name(who)} (qua Telegram)\n\n{args[1].strip()}\n")
        owner = load_modules()["modules"][key].get("owner")
        resumed = ""
        with self.lock:
            last = self.state["last"].get(key)
            cur = self.state.get("current")
            busy = (cur and cur["module"] == key) or any(j["module"] == key for j in self.state["queue"])
            if last and last["code"] == 2 and not busy:
                self.state["queue"].append({"module": key, "by": who, "respec": False, "resume": True})
                self.save()
                resumed = "\n▶️ Flow đang bị chặn nên đã được xếp hàng chạy tiếp."
        self.announce(owner, f"💬 {esc(self.name(who))} trả lời <b>[{key}]</b>:\n{esc(args[1].strip()[:1500])}"
                      f"{resumed}")

    def cmd_owner(self, token, chat_id, who, args) -> None:
        key = self.module_arg(token, chat_id, args)
        if not key:
            return
        members = self.cfg.get("members") or {}
        member = args[1].strip() if len(args) > 1 else ""
        if member not in members:
            self.reply(token, chat_id, f"Cách dùng: <code>/owner {key} &lt;thành viên&gt;</code>, "
                       f"thành viên là một trong: {', '.join(members)}")
            return
        data = load_modules()
        data["modules"][key]["owner"] = member
        save_modules(data)
        self.announce(member, f"👤 {esc(self.name(who))} gán <b>[{key}]</b> cho {esc(self.name(member))}. "
                      "Commit của module sẽ mang tên người này (rotation=owner).")

    # ------------------------------------------------------------------ nút xin quyền
    def on_permission(self, token: str, cq: dict, who: str) -> None:
        parts = (cq.get("data") or "").split("|")
        if len(parts) != 4 or parts[0] != "perm":
            _call(token, "answerCallbackQuery", {"callback_query_id": cq["id"]})
            return
        _, module, req_id, decision = parts
        perm_dir = self.root / module / "state" / "perm"
        req_path, res_path = perm_dir / f"{req_id}.req.json", perm_dir / f"{req_id}.res.json"
        if not req_path.exists():
            _call(token, "answerCallbackQuery", {"callback_query_id": cq["id"], "text": "Không tìm thấy yêu cầu."})
            return
        if res_path.exists():
            prev = rf.read_json(res_path, {})
            _call(token, "answerCallbackQuery", {"callback_query_id": cq["id"],
                                                 "text": f"Đã xử lý trước đó: {prev.get('decision')}"})
            return
        allow = decision == "allow"
        rf.write_json(res_path, {"decision": "allow" if allow else "deny", "by": self.name(who), "at": rf.now()})
        _call(token, "answerCallbackQuery", {"callback_query_id": cq["id"],
                                             "text": "Đã cho phép" if allow else "Đã từ chối"})
        req = rf.read_json(req_path, {})
        verdict = f"✅ {self.name(who)} đã CHO PHÉP" if allow else f"⛔ {self.name(who)} đã TỪ CHỐI"
        notify.Notifier.edit(req.get("messages", []), f"🔐 <b>[{esc(module)}]</b> xin quyền:\n"
                             f"<code>{esc(req.get('what', ''))}</code>\n{esc(verdict)}")
        self.log(f"quyền {module}/{req_id}: {decision} bởi {who}")

    # ------------------------------------------------------------------ chạy job
    def scheduler_tick(self) -> None:
        with self.lock:
            if self.state.get("current") or not self.state["queue"]:
                return
            job = self.state["queue"].pop(0)
            self.state["current"] = {"module": job["module"], "phase": "spec", "by": job["by"],
                                     "started": time.time(), "pid": None}
            self.save()
        threading.Thread(target=self.run_job, args=(job,), daemon=True).start()

    def finish_job(self, module: str, code: int) -> None:
        with self.lock:
            cur = self.state.get("current") or {}
            if cur.get("stopped_by"):
                code = -1
            self.state["last"][module] = {"code": code, "at": rf.now()}
            self.state["current"] = None
            self.save()
        self.proc = self.spec_proc = None
        self.log(f"[{module}] kết thúc: {EXIT_TEXT.get(code, code)}")

    def run_job(self, job: dict) -> None:
        key = job["module"]
        entry = load_modules()["modules"][key]
        owner = entry.get("owner")
        spec_path = REPO / "docs" / "features" / f"{key}.md"
        try:
            if job.get("respec") or not spec_path.exists():
                if not self.write_spec(key, entry, spec_path):
                    self.finish_job(key, 1)
                    return
            else:
                errors = check_done.parse_spec(spec_path)["errors"]
                if errors:
                    self.announce(owner, f"❌ <b>[{key}]</b> spec hiện có bị lỗi: {esc('; '.join(errors))}\n"
                                  f"Soạn lại bằng <code>/run {key} --respec</code>.")
                    self.finish_job(key, 1)
                    return
            with self.lock:
                if (self.state.get("current") or {}).get("stopped_by"):
                    self.finish_job(key, -1)
                    return
                self.state["current"]["phase"] = "run"
                self.save()
            cmd = [sys.executable, str(HERE / "run_flow.py"), str(spec_path.relative_to(REPO)),
                   "--ask-permissions", "--flow-root", str(self.root)]
            if job.get("resume"):
                cmd.append("--resume-blocked")
            cmd += shlex.split(self.args.runner_args, posix=os.name != "nt") if self.args.runner_args else []
            console = (self.root / key / "runner-console.log")
            console.parent.mkdir(parents=True, exist_ok=True)
            flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            with console.open("a", encoding="utf-8") as out:
                self.proc = subprocess.Popen(cmd, cwd=REPO, stdout=out, stderr=subprocess.STDOUT,
                                             stdin=subprocess.DEVNULL, creationflags=flags)
                with self.lock:
                    self.state["current"]["pid"] = self.proc.pid
                    self.save()
                self.log(f"[{key}] runner pid {self.proc.pid}")
                code = self.proc.wait()
            self.finish_job(key, code)
        except Exception as exc:  # noqa: BLE001
            self.log(f"[{key}] job lỗi: {exc!r}")
            self.announce(owner, f"❌ <b>[{key}]</b> bot gặp lỗi khi chạy: {esc(exc)}")
            self.finish_job(key, 1)

    def write_spec(self, key: str, entry: dict, spec_path: Path) -> bool:
        owner = entry["owner"]
        self.announce(owner, f"📝 <b>[{key}]</b> đang soạn spec từ Mô tả dự án + tài liệu… (vài phút)")
        shared = self.root / "_shared"
        txt = docx_text(shared / "mo-ta-du-an.txt")
        errors: list[str] = []
        for attempt in range(1, 4):
            prompt = (
                f"Soạn spec cho module `{key}`.\n"
                f"Mục trong danh mục (scripts/agent-flow/modules.json): {json.dumps(entry, ensure_ascii=False)}\n"
                f"owner = `{owner}` · module = `{key}`\n"
                f"Bản text của 'Mô tả dự án.docx': `{txt}`"
                + (f" (mục tính năng số {entry['feature']})" if entry.get("feature") else "")
                + "\nLàm đúng hướng dẫn agent spec-writer; trả lời đúng định dạng <<<SPEC … SPEC>>>."
                + (f"\nLần soạn trước bị lỗi, hãy sửa: {'; '.join(errors)}" if errors else "")
            )
            cmd = [rf.find_claude(), "-p", "--agent", "spec-writer", "--tools", "Read,Grep,Glob",
                   "--permission-mode", "dontAsk", "--permission-prompts", "none",
                   "--settings", str(rf.SETTINGS), "--output-format", "json",
                   "--model", self.args.model, "--add-dir", str(shared)]
            self.spec_proc = subprocess.Popen(cmd, cwd=REPO, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                              errors="replace")
            try:
                out, err = self.spec_proc.communicate(prompt, timeout=1800)
            except subprocess.TimeoutExpired:
                rf.kill_tree(self.spec_proc)
                out, err = "", "quá 30 phút"
            if (self.state.get("current") or {}).get("stopped_by"):
                return False
            (self.root / key).mkdir(parents=True, exist_ok=True)
            (self.root / key / f"spec-writer-{attempt}.log").write_text(out + "\n---\n" + err, encoding="utf-8")
            data = {}
            for line in reversed(out.strip().splitlines()):
                try:
                    data = json.loads(line)
                    break
                except ValueError:
                    continue
            match = SPEC_RE.search(str(data.get("result", "")))
            if not match:
                errors = ["không thấy spec giữa <<<SPEC và SPEC>>>"
                          + (f" ({str(data.get('result', err))[:200]})" if not data or data.get("is_error") else "")]
                continue
            text = match.group(1).strip() + "\n"
            with tempfile.TemporaryDirectory() as tmp:
                probe = Path(tmp) / f"{key}.md"
                probe.write_text(text, encoding="utf-8")
                parsed = check_done.parse_spec(probe)
            errors = list(parsed["errors"])
            if parsed.get("module") != key:
                errors.append(f"frontmatter module phải là '{key}'")
            if parsed.get("owner") != owner:
                errors.append(f"frontmatter owner phải là '{owner}'")
            bad_codes = unregistered_codes(parsed["tcs"])
            if bad_codes:
                errors.append(f"test case dùng error.code chưa đăng ký ở Claude_api_respone.md §10: "
                              f"{', '.join(bad_codes)}. Chỉ dùng mã có trong §10; mã cần thêm thì ghi "
                              "vào mục 6 'Câu hỏi mở' và KHÔNG viết test case phụ thuộc mã đó")
            if errors:
                self.log(f"[{key}] spec lần {attempt} lỗi: {errors}")
                continue
            spec_path.parent.mkdir(parents=True, exist_ok=True)
            spec_path.write_text(text, encoding="utf-8")
            tcs = parsed["tcs"]
            lines = [f"📝 <b>[{key}]</b> spec xong: {len(tcs)} test case · nhánh "
                     f"<code>{esc(parsed['branch'])}</code> · owner {esc(self.name(owner))}"]
            lines += [f"• <b>{esc(t['id'])}</b> {esc(t['desc'][:110])}" for t in tcs[:20]]
            if len(tcs) > 20:
                lines.append(f"… và {len(tcs) - 20} ca khác")
            lines.append(f"File: <code>docs/features/{key}.md</code>. Bắt đầu chạy flow.")
            self.announce(owner, "\n".join(lines))
            return True
        self.announce(owner, f"❌ <b>[{key}]</b> soạn spec thất bại sau 3 lần: {esc('; '.join(errors))[:1500]}")
        return False

    # ------------------------------------------------------------------ khởi động
    def recover(self) -> None:
        """Bot khởi động lại: nhận lại flow đang chạy (nếu tiến trình còn sống)."""
        cur = self.state.get("current")
        if not cur:
            return
        if cur.get("phase") == "run" and cur.get("pid") and rf.pid_alive(cur["pid"]):
            self.log(f"nhận lại flow [{cur['module']}] pid {cur['pid']}")
            threading.Thread(target=self.watch_pid, args=(cur["module"], cur["pid"]), daemon=True).start()
        else:
            self.log(f"flow [{cur['module']}] không còn chạy sau khi bot khởi động lại")
            self.finish_job(cur["module"], self.exit_from_report(cur["module"]))

    def watch_pid(self, module: str, pid: int) -> None:
        while rf.pid_alive(pid):
            time.sleep(10)
        self.finish_job(module, self.exit_from_report(module))

    def exit_from_report(self, module: str) -> int:
        report = self.root / module / "RUN-REPORT.md"
        match = re.search(r"\(exit (\d+)\)", report.read_text(encoding="utf-8")) if report.exists() else None
        return int(match.group(1)) if match else 1

    def serve(self) -> None:
        lock = self.root / "bot.lock"
        if lock.exists():
            try:
                old = int(lock.read_text().split()[0])
            except (ValueError, IndexError):
                old = 0
            if rf.pid_alive(old):
                raise SystemExit(f"bot khác đang chạy (pid {old}). Tắt nó trước.")
        lock.write_text(f"{os.getpid()} {rf.now()}")
        if not self.tokens:
            raise SystemExit("team.json chưa có token bot nào")
        rf.keep_awake(True)
        self.recover()
        for token in self.tokens:
            threading.Thread(target=self.poll, args=(token,), daemon=True).start()
        self.log(f"bot bật: {len(self.tokens)} bot, {len(self.users)} thành viên được phép ra lệnh")
        self.notifier.send(None, "🤖 Bot điều khiển agent flow đã bật. Gõ /help để xem lệnh.")
        try:
            while True:
                try:
                    token, upd = self.updates.get(timeout=1)
                    self.handle(token, upd)
                except queue.Empty:
                    pass
                self.scheduler_tick()
        except KeyboardInterrupt:
            self.log("tắt bot (Ctrl+C); flow đang chạy (nếu có) vẫn tiếp tục")
            self.notifier.send(None, "🤖 Bot điều khiển đã tắt. Flow đang chạy (nếu có) vẫn tiếp tục.")
        finally:
            self.stop_event.set()
            rf.keep_awake(False)
            lock.unlink(missing_ok=True)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--model", default="opus", help="model cho spec-writer")
    ap.add_argument("--flow-root", help="thư mục worktree + state (mặc định ../<repo>-flow)")
    ap.add_argument("--runner-args", default="", help='tham số thêm cho run_flow.py, vd "--max-iterations 60"')
    Bot(ap.parse_args()).serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
