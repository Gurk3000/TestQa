"""Short human-readable failure reasons for a post-run summary file."""
from __future__ import annotations

import re
from typing import Any


def one_line_reason(report: Any, max_len: int = 220) -> str:
    """Derive a single-line explanation from a failed pytest ``TestReport``."""
    raw = ""
    try:
        lr = getattr(report, "longrepr", None)
        if lr is not None:
            raw = str(lr)
    except Exception:  # noqa: BLE001
        raw = ""

    blob = raw.replace("\r\n", "\n")

    if "NoSuchElementException" in blob or "no such element" in blob.lower():
        m = re.search(r"Message:\s*([^\n]+)", blob, re.I)
        if m:
            return f"Element not found: {m.group(1).strip()[:max_len]}"
        return "Element not found (locator / timeout)."

    if "TimeoutException" in blob:
        # Selenium's TimeoutException message is usually empty; point at the action that
        # timed out by scanning our own frames (pages/ or tests/) for the failing call.
        action = ""
        for line in blob.split("\n"):
            s = line.strip()
            if (".py:" in s and " in " in s) and ("pages" in s or "tests" in s):
                action = s.split(" in ", 1)[-1].strip()
            mc = re.search(r"self\.(click|wait\.\w+|type|js_click)\(([^)]*)\)", s)
            if mc:
                action = f"{mc.group(1)}({mc.group(2)})"
        if action:
            return f"Wait timeout in {action[:max_len]} (element not clickable/visible or URL not reached)."
        return "Wait timeout (element not clickable/visible or URL did not stabilize)."

    if "only supports characters in the BMP" in blob or "ChromeDriver only supports char" in blob:
        return "ChromeDriver rejected a character in send_keys (non-BMP / emoji); JS input fallback applies."

    if "AttributeError" in blob:
        m = re.search(r"AttributeError:\s*([^\n]+)", blob)
        if m:
            return f"AttributeError: {m.group(1).strip()[:max_len]}"

    if "AssertionError" in blob:
        for line in blob.split("\n"):
            s = line.strip()
            if s.startswith("AssertionError") or s.startswith("assert "):
                return s[:max_len]

    if "StaleElementReferenceException" in blob:
        return "Stale element (DOM re-rendered before interaction)."

    if "ElementClickInterceptedException" in blob:
        return "Click intercepted (overlay / another element on top)."

    if "ElementNotInteractableException" in blob:
        return "Element not interactable (hidden, disabled, or off-screen)."

    # Last non-empty line of traceback / message
    for line in reversed(blob.split("\n")):
        s = line.strip()
        if len(s) > 12 and not s.startswith("="):
            return s[:max_len]

    return "See pytest longrepr / screenshots."


def write_session_summary(path: Any, entries: dict[str, str], session_start: str) -> None:
    """Write ``nodeid -> reason`` map as a UTF-8 text report."""
    lines = [
        f"Session: {session_start}",
        f"Failed tests (last failure per test): {len(entries)}",
        "",
        "nodeid\tsummary",
    ]
    for nodeid in sorted(entries.keys()):
        lines.append(f"{nodeid}\t{entries[nodeid]}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
