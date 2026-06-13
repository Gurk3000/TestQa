"""Structured failure diagnostics for pytest + Selenium runs.

Used from conftest hooks so operators see *why* a test failed without digging
through Allure or HTML reports first.
"""
from __future__ import annotations

import traceback
from typing import Any, Optional

from selenium.webdriver.remote.webdriver import WebDriver

from utils.logger import get_logger

logger = get_logger("failure")


def _safe_driver_context(driver: Optional[WebDriver]) -> list[str]:
    if driver is None:
        return ["  browser: <no driver on this node>"]
    lines: list[str] = []
    try:
        lines.append(f"  current_url: {driver.current_url}")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"  current_url: <error reading: {exc}>")
    try:
        lines.append(f"  page_title: {driver.title}")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"  page_title: <error reading: {exc}>")
    try:
        lines.append(f"  window_rect: {driver.get_window_rect()}")
    except Exception:
        pass
    return lines


def log_pytest_report(item: Any, report: Any, driver: Optional[WebDriver] = None) -> None:
    """Log a human-readable block when a test phase failed (setup/call/teardown)."""
    if not getattr(report, "failed", False):
        return

    header = [
        "=" * 78,
        f"TEST FAILURE  phase={report.when!r}  outcome={getattr(report, 'outcome', '?')!r}",
        f"  nodeid: {item.nodeid}",
        f"  location: {getattr(item, 'location', ('?', '?', '?'))}",
    ]
    header.extend(_safe_driver_context(driver))

    longrepr = getattr(report, "longrepr", None)
    if longrepr is not None:
        header.append("--- pytest longrepr ---")
        header.append(str(longrepr).rstrip())

    capout = getattr(report, "capstdout", None) or ""
    caperr = getattr(report, "capstderr", None) or ""
    if capout.strip():
        header.append("--- captured stdout ---")
        header.append(capout.rstrip())
    if caperr.strip():
        header.append("--- captured stderr ---")
        header.append(caperr.rstrip())

    header.append("=" * 78)
    logger.error("\n".join(header))


def log_skip_report(item: Any, report: Any) -> None:
    """Log why a test was skipped (fixtures: pytest.skip, @pytest.mark.skip, etc.)."""
    if not getattr(report, "skipped", False):
        return
    nodeid = getattr(item, "nodeid", None) or getattr(report, "nodeid", "?")
    reason = str(report.longrepr).strip() if getattr(report, "longrepr", None) else "unknown"
    block = [
        "=" * 78,
        "TEST SKIPPED",
        f"  phase: {report.when!r}",
        f"  outcome: {getattr(report, 'outcome', '?')!r}",
        f"  nodeid: {nodeid}",
        f"  location: {getattr(item, 'location', ('?', '?', '?'))}",
        "--- reason (pytest longrepr) ---",
        reason,
        "=" * 78,
    ]
    logger.warning("\n".join(block))


def log_rerun_report(item: Optional[Any], report: Any, driver: Optional[WebDriver] = None) -> None:
    """Log intermediate failure that will trigger pytest-rerunfailures (outcome='rerun').

    Called from ``pytest_runtest_logreport`` because the plugin sets ``outcome='rerun'``
    *after* ``pytest_runtest_makereport`` has already run for that attempt.
    """
    if getattr(report, "outcome", None) != "rerun":
        return
    nodeid = getattr(item, "nodeid", None) if item is not None else getattr(report, "nodeid", "?")
    exec_count = getattr(item, "execution_count", "?") if item is not None else "?"
    rerun_idx = getattr(report, "rerun", "?")
    cfg = getattr(getattr(item, "config", None), "option", None) if item is not None else None
    max_reruns = getattr(cfg, "reruns", None) if cfg is not None else None

    header = [
        "=" * 78,
        "TEST RERUN — intermediate failure (another attempt will run)",
        f"  nodeid: {nodeid}",
        f"  phase: {report.when!r}",
        f"  execution_count: {exec_count}  (report.rerun index: {rerun_idx})",
        f"  configured --reruns: {max_reruns}",
        "  note: pytest_runtest_makereport may have logged the same attempt as FAILURE above;",
        "        this block is the official 'rerun' signal from pytest-rerunfailures.",
        "  hint: fix the root cause below; otherwise reruns will be exhausted.",
    ]
    header.extend(_safe_driver_context(driver))

    longrepr = getattr(report, "longrepr", None)
    if longrepr is not None:
        header.append("--- failure that triggered this rerun ---")
        header.append(str(longrepr).rstrip())

    capout = getattr(report, "capstdout", None) or ""
    caperr = getattr(report, "capstderr", None) or ""
    if capout.strip():
        header.append("--- captured stdout ---")
        header.append(capout.rstrip())
    if caperr.strip():
        header.append("--- captured stderr ---")
        header.append(caperr.rstrip())

    header.append("=" * 78)
    logger.warning("\n".join(header))


def log_interactive_exception(node: Any, call: Any) -> None:
    """Log full traceback from pytest_exception_interact (clearest stack trace)."""
    excinfo = getattr(call, "excinfo", None)
    if excinfo is None or excinfo.value is None:
        return

    tb_text = "".join(
        traceback.format_exception(excinfo.type, excinfo.value, excinfo.tb),
    )
    block = [
        "=" * 78,
        "EXCEPTION (during test / fixture)",
        f"  nodeid: {node.nodeid}",
        f"  exc_type: {excinfo.type.__name__ if excinfo.type else 'Unknown'}",
        f"  exc_msg: {excinfo.value!r}",
        "--- traceback ---",
        tb_text.rstrip(),
        "=" * 78,
    ]
    logger.error("\n".join(block))
