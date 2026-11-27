"""Lệnh git/gh dùng chung cho phần tích hợp module vào main (integrate.py, pr_publish.py)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class IntegrationError(Exception):
    """Không đưa được module vào main; nhánh giữ nguyên để người xem."""


def sh(cmd: list[str], cwd: Path, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def git(wt: Path, *args: str) -> str:
    proc = sh(["git", *args], wt)
    if proc.returncode != 0:
        raise IntegrationError(f"git {' '.join(args)}: {(proc.stderr or proc.stdout).strip()[:400]}")
    return proc.stdout.strip()


def git_ok(wt: Path, *args: str) -> bool:
    return sh(["git", *args], wt).returncode == 0


def gh(wt: Path, *args: str) -> subprocess.CompletedProcess:
    """`gh` thật, hoặc script giả khi kiểm thử (biến FLOW_GH trỏ tới file .py)."""
    fake = os.environ.get("FLOW_GH")
    base = ([sys.executable, fake] if fake.endswith(".py") else [fake]) if fake else ["gh"]
    return sh([*base, *args], wt, timeout=300)
