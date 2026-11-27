"""Hồ sơ theo target của một module: thư mục, cổng mặc định, file bảo vệ, test.

Spec module ghi `target: backend | ai-services | frontend` trong frontmatter, mặc định `backend`
để các spec cũ chạy y nguyên. check_done.py, run_flow.py và standards.py đọc hồ sơ ở đây
thay vì viết cứng `backend/`. Chỉ dùng thư viện chuẩn.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PYTHON_GATES = ["spec", "protected", "clean", "pytest", "tc", "coverage", "ruff", "mypy", "standards"]
NODE_GATES = ["spec", "protected", "clean", "tsc", "eslint", "jest", "tc", "coverage", "standards"]
ALL_GATES = list(dict.fromkeys(PYTHON_GATES + NODE_GATES))
TEST_RUN_GATES = {"pytest", "jest", "tc", "coverage"}


@dataclass(frozen=True)
class Target:
    name: str
    root: str  # thư mục con của repo, chạy lệnh tại đây
    kind: str  # "python" | "node"
    gates: list[str]
    core: list[str] = field(default_factory=list)  # chỉ sửa khi spec cho allow_core_changes
    deps: list[str] = field(default_factory=list)  # chỉ sửa khi spec cho allow_new_dependencies
    test_prefixes: tuple[str, ...] = ()  # xoá file ở đây = xoá test
    test_suffixes: tuple[str, ...] = ()
    cov_package: str = "app"
    venv: str = ""  # venv python trong repo chính, rỗng = dùng chung venv backend

    def is_test(self, path: str) -> bool:
        return path.startswith(self.test_prefixes) or path.endswith(self.test_suffixes)


TARGETS: dict[str, Target] = {
    "backend": Target(
        name="backend", root="backend", kind="python", gates=PYTHON_GATES,
        core=["backend/app/core/", "backend/app/middleware/", "backend/app/schemas/base.py",
              "backend/app/main.py", "backend/tests/conftest.py", "backend/alembic/env.py",
              "backend/alembic.ini"],
        deps=["backend/requirements.txt"],
        test_prefixes=("backend/tests/",), venv="backend/.venv",
    ),
    "ai-services": Target(
        name="ai-services", root="ai-services", kind="python", gates=PYTHON_GATES,
        core=["ai-services/app/core/", "ai-services/app/main.py", "ai-services/app/contracts.py",
              "ai-services/tests/conftest.py"],
        deps=["ai-services/requirements.txt", "ai-services/requirements-ml.txt"],
        test_prefixes=("ai-services/tests/",), venv="ai-services/.venv",
    ),
    "frontend": Target(
        name="frontend", root="frontend", kind="node", gates=NODE_GATES,
        core=["frontend/src/app/_layout.tsx", "frontend/src/app/(tabs)/_layout.tsx",
              "frontend/src/services/api/", "frontend/src/styles/theme.ts", "frontend/jest.config.js",
              "frontend/jest.setup.ts", "frontend/eslint.config.js", "frontend/tsconfig.json",
              "frontend/app.config.ts"],
        deps=["frontend/package.json", "frontend/package-lock.json"],
        test_prefixes=("frontend/__tests__/",), test_suffixes=(".test.ts", ".test.tsx"),
    ),
}
DEFAULT_TARGET = "backend"


def get(name: str | None) -> Target | None:
    return TARGETS.get(name or DEFAULT_TARGET)


def venv_python(repo: Path, target: Target) -> Path:
    """Python của venv dùng cho cổng (ruff, mypy, pytest) của target python."""
    sub = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
    return repo / (target.venv or "backend/.venv") / sub[0] / sub[1]
