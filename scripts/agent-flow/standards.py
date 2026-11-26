"""Cổng `standards`: đo các ngưỡng của docs/guides/coding-standards.md bằng `ast`.

Chỉ dùng thư viện chuẩn (check_done.py được run_flow.py import). Đây là cổng CẢNH BÁO:
module trả `ok: True` kèm danh sách `file:dòng`, orchestrator phải sửa hoặc giải thích trong REPORT.md.
"""

from __future__ import annotations

import ast
from pathlib import Path

MAX_FUNCTION_LINES = 40
MAX_FILE_LINES = 300
MAX_PARAMETERS = 4
MAX_NESTING = 3
MAX_COMPLEXITY = 10

# FastAPI tiêm các tham số này vào route handler, không phải đầu vào do người gọi chọn.
INJECTED_MARKERS = {"Depends", "Security"}
SKIPPED_PREFIXES = ("backend/alembic/versions/",)
TEST_PREFIX = "backend/tests/"

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef
NESTING_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith, ast.Match)
BRANCH_NODES = (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler,
                ast.With, ast.AsyncWith, ast.Assert)


def is_checked(path: str) -> bool:
    return path.endswith(".py") and path.startswith("backend/") and not path.startswith(SKIPPED_PREFIXES)


def _calls_injector(node: ast.AST | None) -> bool:
    """`x = Depends(...)` hoặc `x: Annotated[T, Depends(...)]`."""
    return node is not None and any(
        isinstance(child, ast.Call) and _callee_name(child) in INJECTED_MARKERS
        for child in ast.walk(node)
    )


def _callee_name(call: ast.Call) -> str:
    func = call.func
    return func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")


def count_parameters(func: FunctionNode) -> int:
    args = func.args
    positional = [*args.posonlyargs, *args.args]
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    pairs = list(zip(positional, defaults)) + list(zip(args.kwonlyargs, args.kw_defaults))
    counted = [a for a, default in pairs
               if a.arg not in {"self", "cls"}
               and not _calls_injector(default) and not _calls_injector(a.annotation)]
    return len(counted) + (args.vararg is not None) + (args.kwarg is not None)


def _own_nodes(func: FunctionNode):
    """Duyệt thân hàm nhưng không đi vào hàm lồng bên trong (hàm đó được đo riêng)."""
    stack: list[ast.AST] = list(func.body)
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            stack.extend(ast.iter_child_nodes(node))


def complexity(func: FunctionNode) -> int:
    """Xấp xỉ McCabe, cách đếm ghi ở docs/guides/coding-standards.md §6."""
    total = 1
    for node in _own_nodes(func):
        if isinstance(node, BRANCH_NODES):
            total += 1
        elif isinstance(node, ast.BoolOp):
            total += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            total += 1 + len(node.ifs)
    return total


def max_nesting(statements: list[ast.stmt], depth: int = 0) -> int:
    deepest = depth
    for stmt in statements:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(stmt, NESTING_NODES):
            deepest = max(deepest, _nesting_of_block(stmt, depth + 1))
    return deepest


def _nesting_of_block(stmt: ast.stmt, depth: int) -> int:
    deepest = depth
    for body in _child_blocks(stmt):
        deepest = max(deepest, max_nesting(body, depth))
    # `elif` là If nằm trong orelse của If trước: cùng cấp, không lồng thêm.
    if isinstance(stmt, ast.If) and len(stmt.orelse) == 1 and isinstance(stmt.orelse[0], ast.If):
        deepest = max(deepest, _nesting_of_block(stmt.orelse[0], depth))
    return deepest


def _child_blocks(stmt: ast.stmt) -> list[list[ast.stmt]]:
    if isinstance(stmt, ast.Match):
        return [case.body for case in stmt.cases]
    blocks = [getattr(stmt, name, []) for name in ("body", "orelse", "finalbody")]
    blocks += [handler.body for handler in getattr(stmt, "handlers", [])]
    if isinstance(stmt, ast.If) and len(stmt.orelse) == 1 and isinstance(stmt.orelse[0], ast.If):
        blocks.remove(stmt.orelse)
    return blocks


def check_function(path: str, func: FunctionNode) -> list[str]:
    where = f"{path}:{func.lineno} {func.name}"
    length = (func.end_lineno or func.lineno) - func.lineno + 1
    measured = [
        ("dòng", length, MAX_FUNCTION_LINES),
        ("tham số", count_parameters(func), MAX_PARAMETERS),
        ("cấp lồng", max_nesting(func.body), MAX_NESTING),
        ("complexity", complexity(func), MAX_COMPLEXITY),
    ]
    return [f"{where}: {value} {unit} (ngưỡng {limit})" for unit, value, limit in measured if value > limit]


def check_file(root: Path, path: str) -> list[str]:
    try:
        source = (root / path).read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []  # ruff và mypy báo lỗi cú pháp, cổng này không nhắc lại
    warnings = []
    lines = len(source.splitlines())
    if lines > MAX_FILE_LINES and not path.startswith(TEST_PREFIX):
        warnings.append(f"{path}: {lines} dòng (ngưỡng {MAX_FILE_LINES})")
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            warnings += check_function(path, node)
    return warnings


def evaluate(root: Path, changed: list[str]) -> dict:
    warnings: list[str] = []
    for path in sorted({p for p in changed if is_checked(p)}):
        warnings += check_file(root, path)
    return {
        "ok": True,  # cảnh báo, không làm cổng trượt
        "summary": f"{len(warnings)} cảnh báo" if warnings else "trong ngưỡng",
        "details": warnings,
    }
