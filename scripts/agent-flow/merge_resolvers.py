"""Giải tự động các xung đột merge đã biết trước (dùng cho integrate.py).

Chỉ xử lý những trường hợp mà cách giải là hiển nhiên; còn lại trả None để agent `integrator` giải:
- `backend/app/api/v1/router.py`: mỗi module thêm một tên vào dòng import và một dòng `include_router`
  (doc 05 §9.4), nên kết quả là hợp của hai phía, sắp theo bảng chữ cái;
- hai phía cùng thêm một file với nội dung giống hệt nhau.
"""

from __future__ import annotations

import re

ROUTER_PATH = "backend/app/api/v1/router.py"
IMPORT_RE = re.compile(r"^from app\.api\.v1\.endpoints import (\([^)]*\)|[^\n]*)$", re.M)
INCLUDE_RE = re.compile(r"^api_v1_router\.include_router\((\w+)\.router\b.*$", re.M)
MARKER_RE = re.compile(r"^(<{7}|>{7})( |$)", re.M)  # bỏ qua "=======" vì Markdown dùng làm gạch tiêu đề
MAX_IMPORT_LINE = 99


def has_conflict_markers(text: str) -> bool:
    return bool(MARKER_RE.search(text))


def parse_router(text: str) -> tuple[set[str], dict[str, str], str] | None:
    """(tên module import, {tên: dòng include_router}, phần còn lại của file) hoặc None nếu lạ."""
    imports = IMPORT_RE.findall(text)
    if len(imports) != 1:
        return None
    names = {n.strip() for n in imports[0].strip("()").replace("\n", " ").split(",") if n.strip()}
    includes = {m.group(1): m.group(0) for m in INCLUDE_RE.finditer(text)}
    rest = INCLUDE_RE.sub("", IMPORT_RE.sub("", text))
    return names, includes, "\n".join(line for line in rest.splitlines() if line.strip())


def render_import(names: set[str]) -> str:
    line = "from app.api.v1.endpoints import " + ", ".join(sorted(names))
    if len(line) <= MAX_IMPORT_LINE:
        return line
    return "from app.api.v1.endpoints import (\n" + "".join(f"    {n},\n" for n in sorted(names)) + ")"


def merge_router(ours: str, theirs: str) -> str | None:
    """Hợp router.py của hai phía; None nếu hai phía khác nhau ở chỗ khác ngoài import/include."""
    left, right = parse_router(ours), parse_router(theirs)
    if left is None or right is None or left[2] != right[2]:
        return None
    includes = {**right[1], **left[1]}
    if any(left[1][k] != right[1][k] for k in left[1].keys() & right[1].keys()):
        return None  # cùng một module nhưng dòng include khác nhau: để agent xem
    names = left[0] | right[0]
    if set(includes) - names:
        return None
    text = IMPORT_RE.sub(lambda _: render_import(names), ours, count=1)
    first = INCLUDE_RE.search(text)
    if first is None:
        return None
    head, tail = text[: first.start()], INCLUDE_RE.sub("", text[first.start():])
    body = "\n".join(includes[k] for k in sorted(includes))
    return head + body + "\n" + tail.lstrip("\n")


def resolve(path: str, ours: str | None, theirs: str | None) -> str | None:
    """Nội dung đã giải cho một file xung đột, hoặc None nếu không giải tự động được."""
    if ours is not None and ours == theirs:
        return ours
    if path == ROUTER_PATH and ours is not None and theirs is not None:
        return merge_router(ours, theirs)
    return None
