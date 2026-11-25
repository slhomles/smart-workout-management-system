"""Plugin pytest cho agent flow: ghi lại kết quả của từng test case (TC) trong spec module.

Test gắn TC bằng marker:

    @pytest.mark.tc("EXC-01")
    async def test_list_exercises_default_returns_page(client): ...

Nạp plugin bằng `-p tc_plugin` (thư mục này phải có trong PYTHONPATH) và
`--tc-report=<file.json>`. `check_done.py` làm việc này tự động.

Một test chỉ được tính là "passed" khi pha call pass và setup/teardown không lỗi.
skip, xfail, xpass đều KHÔNG được tính là pass.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_tcs_by_nodeid: dict[str, list[str]] = {}
_outcome: dict[str, str] = {}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--tc-report",
        default=None,
        help="Đường dẫn file JSON ghi kết quả theo test case ID (agent flow).",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "tc(*ids): gắn test với test case ID trong spec module (docs/features/*.md)",
    )


def pytest_collection_modifyitems(
    session: pytest.Session, config: pytest.Config, items: list[pytest.Item]
) -> None:
    for item in items:
        ids: list[str] = []
        for mark in item.iter_markers(name="tc"):
            ids.extend(str(a) for a in mark.args)
        if ids:
            _tcs_by_nodeid[item.nodeid] = sorted(set(ids))


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    nid = report.nodeid
    current = _outcome.get(nid)
    if report.failed:
        _outcome[nid] = "failed" if report.when == "call" else "error"
    elif report.skipped:
        if current not in ("failed", "error"):
            _outcome[nid] = "xfailed" if hasattr(report, "wasxfail") else "skipped"
    elif report.passed and report.when == "call":
        if current is None:
            _outcome[nid] = "xpassed" if hasattr(report, "wasxfail") else "passed"


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    path = session.config.getoption("--tc-report")
    if not path:
        return
    by_tc: dict[str, list[dict[str, str]]] = {}
    for nid, ids in _tcs_by_nodeid.items():
        outcome = _outcome.get(nid, "not_run")
        for tc in ids:
            by_tc.setdefault(tc, []).append({"nodeid": nid, "outcome": outcome})
    data = {
        "exitstatus": int(exitstatus),
        "by_tc": by_tc,
        "total_tests": len(_outcome),
    }
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
