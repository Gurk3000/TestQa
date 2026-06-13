"""Interactive report-type selection logic.

Keeps all report-decision logic in one place (clean architecture). The conftest
hooks call into these pure-ish helpers, so the policy is easy to unit-test and
reason about:

  * CLI flag (--report=html|allure) always wins and suppresses the prompt.
  * CI environments never prompt and always use pytest-html.
  * A non-interactive stdin (piped / captured) never prompts -> pytest-html.
  * Otherwise an interactive terminal menu is shown.
  * Allure is only enabled when BOTH the allure-pytest plugin and the Allure
    CLI are available; otherwise we log a fallback to pytest-html.
"""
from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Tuple

from config.config import settings
from utils.logger import get_logger

logger = get_logger("report")

HTML = "html"
ALLURE = "allure"

# Environment variables commonly set by CI providers.
_CI_ENV_VARS = (
    "CI",
    "CONTINUOUS_INTEGRATION",
    "GITHUB_ACTIONS",
    "GITLAB_CI",
    "JENKINS_URL",
    "TF_BUILD",
    "BUILDKITE",
    "TEAMCITY_VERSION",
)


def is_ci() -> bool:
    """True if running inside a CI environment."""
    for var in _CI_ENV_VARS:
        value = os.getenv(var, "").strip().lower()
        if value and value not in {"0", "false", "no"}:
            return True
    return False


def allure_cli_available() -> bool:
    """True if the Allure command-line tool is on PATH."""
    return shutil.which("allure") is not None


def allure_plugin_available() -> bool:
    """True if the allure-pytest plugin is importable."""
    try:
        import allure_pytest  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def allure_available() -> bool:
    return allure_plugin_available() and allure_cli_available()


def render_menu() -> str:
    return (
        "\n"
        "==================================================\n"
        " Select report type:\n"
        "   1 - pytest-html (default)\n"
        "   2 - Allure (only if installed)\n"
        "=================================================="
    )


def normalize_choice(raw: str) -> str:
    """Map raw terminal input to a canonical report type."""
    raw = (raw or "").strip().lower()
    if raw in {"2", "allure", "a"}:
        return ALLURE
    return HTML


def _configure_pytest_html_path(config, html_path) -> None:
    """Set ``htmlpath`` / self-contained flag and ensure the HTML writer is registered."""
    if not hasattr(config.option, "htmlpath"):
        return
    config.option.htmlpath = str(html_path)
    if hasattr(config.option, "self_contained_html"):
        config.option.self_contained_html = True
    _ensure_pytest_html_report(config, str(html_path))


def apply_report_config(config, report_type: str) -> str:
    """Configure pytest plugin options for the chosen report type.

    Returns the *effective* report type after applying availability fallbacks.

    When **Allure** is selected successfully, a **companion pytest-html** file is still
    written under ``reports/html/`` so a full-suite run always has a double-clickable
    report without needing ``allure serve`` (Allure CLI remains optional for the rich UI).
    """
    settings.ensure_dirs()
    html_dir = settings.reports_dir / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    session_html = html_dir / f"report_{datetime.now():%Y%m%d_%H%M%S}.html"

    if report_type == ALLURE:
        if allure_available():
            if hasattr(config.option, "allure_report_dir"):
                _clean_allure_dir()
                config.option.allure_report_dir = str(settings.allure_results_dir)
                if _ensure_allure_listener(config, settings.allure_results_dir):
                    logger.info("Reporting: Allure ENABLED (results -> %s)", settings.allure_results_dir)
                    # Always pair Allure with a browseable HTML report (same as --report=html).
                    _configure_pytest_html_path(config, session_html)
                    logger.info("Reporting: companion pytest-html (-> %s)", session_html)
                    return ALLURE
                logger.warning("Could not register Allure listener; falling back to pytest-html")
            logger.warning("allure-pytest option not registered; falling back to pytest-html")
        else:
            missing = []
            if not allure_plugin_available():
                missing.append("allure-pytest plugin")
            if not allure_cli_available():
                missing.append("Allure CLI")
            logger.warning(
                "Allure selected but unavailable (%s). Falling back to pytest-html.",
                ", ".join(missing),
            )
        report_type = HTML

    # pytest-html branch (default + Allure fallback).
    if hasattr(config.option, "htmlpath"):
        _configure_pytest_html_path(config, session_html)
        logger.info("Reporting: pytest-html ENABLED (-> %s)", session_html)
    else:
        logger.warning("pytest-html not installed; no structured report will be generated.")

    return HTML


def _pytest_html_writer_active(config) -> bool:
    """True if pytest-html's Report writer (not just the entry-point module) is registered."""
    try:
        from pytest_html.report import Report
        from pytest_html.selfcontained_report import SelfContainedReport

        for _name, plugin in config.pluginmanager.list_name_plugin():
            if isinstance(plugin, (Report, SelfContainedReport)):
                return True
    except Exception:  # noqa: BLE001
        pass
    return False


def _ensure_pytest_html_report(config, html_path: str) -> bool:
    """Register pytest-html if the path was set after the plugin's own ``pytest_configure``.

    pytest-html only wires its writer when ``htmlpath`` is already set during its
    configure hook. Our interactive ``--report`` choice runs later (``trylast``),
    so we mirror the plugin's registration here when needed.
    """
    if _pytest_html_writer_active(config):
        return True
    if hasattr(config, "workerinput"):
        return True
    try:
        import os
        from pathlib import Path

        import pytest_html
        from pytest_html.report import Report
        from pytest_html.report_data import ReportData
        from pytest_html.selfcontained_report import SelfContainedReport
        from pytest_html.util import _process_css, _read_template

        extra_css = [
            Path(os.path.expandvars(css)).expanduser()
            for css in getattr(config.option, "css", []) or []
        ]
        resources_path = Path(pytest_html.__file__).resolve().parent.joinpath("resources")
        default_css = resources_path / "style.css"
        template = _read_template([resources_path])
        processed_css = _process_css(default_css, extra_css)
        report_data = ReportData(config)
        if getattr(config.option, "self_contained_html", False):
            html_plugin = SelfContainedReport(html_path, config, report_data, template, processed_css)
        else:
            html_plugin = Report(html_path, config, report_data, template, processed_css)
        config.pluginmanager.register(html_plugin)
        logger.info("Reporting: pytest-html writer registered manually")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to register pytest-html writer manually: %s", exc)
        return False


def _ensure_allure_listener(config, report_dir) -> bool:
    """Register Allure listener + file logger if the plugin skipped them (path set too late)."""
    if config.pluginmanager.hasplugin("allure_listener"):
        return True
    try:
        import os

        import allure_commons
        from allure_commons.logger import AllureFileLogger
        from allure_pytest.listener import AllureListener

        abs_dir = os.path.abspath(str(report_dir))
        listener = AllureListener(config)
        config.pluginmanager.register(listener, "allure_listener")
        allure_commons.plugin_manager.register(listener)

        file_logger = AllureFileLogger(abs_dir, clean=False)
        allure_commons.plugin_manager.register(file_logger)

        def _cleanup() -> None:
            try:
                allure_commons.plugin_manager.unregister(
                    name=allure_commons.plugin_manager.get_name(file_logger)
                )
                allure_commons.plugin_manager.unregister(
                    name=allure_commons.plugin_manager.get_name(listener)
                )
            except Exception:  # noqa: BLE001
                pass

        config.add_cleanup(_cleanup)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to register Allure listener manually: %s", exc)
        return False


def _clean_allure_dir() -> None:
    """Remove previous Allure results to avoid mixing historical runs."""
    try:
        target = settings.allure_results_dir
        if target.exists():
            for item in target.glob("*"):
                if item.is_file():
                    item.unlink()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not clean Allure results dir: %s", exc)


def generate_allure_static_html_site(
    results_dir: Path,
    output_dir: Path,
    *,
    timeout_seconds: int = 100,
    terminal_echo: Optional[Callable[[str], None]] = None,
) -> Optional[Path]:
    """Run ``allure generate`` to produce browsable HTML at ``output_dir/index.html``."""
    import subprocess

    def _echo(msg: str) -> None:
        if terminal_echo is not None:
            terminal_echo(msg)

    exe = shutil.which("allure")
    if not exe:
        logger.warning("Allure CLI not on PATH; cannot generate static HTML report")
        _echo("Allure static HTML skipped: Allure CLI not on PATH.")
        return None
    if not results_dir.is_dir():
        logger.warning("Allure results dir missing: %s", results_dir)
        _echo(f"Allure static HTML skipped: results dir missing ({results_dir}).")
        return None
    if not any(results_dir.glob("*.json")):
        logger.warning("No Allure *.json in %s; skip allure generate", results_dir)
        _echo(f"Allure static HTML skipped: no *.json under {results_dir}.")
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    # Windows: running a .bat/.cmd shim via CreateProcess often fails; route through cmd.exe.
    results_s = str(results_dir.resolve())
    output_s = str(output_dir.resolve())
    if os.name == "nt":
        argv = ["cmd", "/c", exe, "generate", results_s, "-o", output_s, "--clean"]
    else:
        argv = [exe, "generate", results_s, "-o", output_s, "--clean"]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        logger.warning("Allure executable not found: %s", exe)
        _echo(f"Allure static HTML skipped: cannot run {exe!r}.")
        return None
    except subprocess.TimeoutExpired:
        logger.error("allure generate timed out after %ss", timeout_seconds)
        _echo(f"Allure static HTML failed: allure generate timed out ({timeout_seconds}s).")
        return None
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:800]
        logger.warning("allure generate failed (exit %s): %s", proc.returncode, err)
        hint = err.splitlines()[0][:240] if err else "no stderr"
        _echo(f"Allure static HTML failed (exit {proc.returncode}): {hint}")
        return None
    index = output_dir / "index.html"
    if not index.is_file():
        logger.warning("allure generate finished but index.html missing under %s", output_dir)
        _echo(f"Allure static HTML failed: index.html missing under {output_dir}.")
        return None
    try:
        resolved = index.resolve()
    except Exception:  # noqa: BLE001
        resolved = index
    logger.info("Allure static HTML report: %s", resolved)
    logger.info(
        "Do not open Allure index.html via file:// (shows Failed to fetch). "
        "Use: allure open %s",
        output_dir.resolve(),
    )
    return resolved


def _allure_open_after_generate_enabled() -> bool:
    raw = os.getenv("TESTRAIL_ALLURE_OPEN", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def launch_allure_open_browser(
    output_dir: Path,
    *,
    terminal_echo: Optional[Callable[[str], None]] = None,
) -> None:
    """Spawn ``allure open <output_dir>`` in the background (non-blocking). Skipped in CI or when disabled."""
    import subprocess

    def _echo(msg: str) -> None:
        if terminal_echo is not None:
            terminal_echo(msg)

    if is_ci():
        logger.info("Allure open skipped (CI environment)")
        return
    if not _allure_open_after_generate_enabled():
        logger.info("Allure open skipped (TESTRAIL_ALLURE_OPEN is disabled)")
        return
    exe = shutil.which("allure")
    if not exe:
        return
    output_s = str(output_dir.resolve())
    if os.name == "nt":
        # New console process tree; returns immediately so pytest can finish.
        argv = ["cmd", "/c", "start", "", exe, "open", output_s]
        popen_kwargs: dict = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
        }
    else:
        argv = [exe, "open", output_s]
        popen_kwargs = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
            "start_new_session": True,
        }
    try:
        subprocess.Popen(argv, **popen_kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not launch allure open: %s", exc)
        _echo(f"Allure open failed: {exc}")
        return
    logger.info("Launched Allure viewer (background): allure open %s", output_s)
    _echo(f"Opening Allure report in browser: allure open {output_s}")


def decide_report_type(cli_value, interactive: bool, prompt_fn) -> Tuple[str, str]:
    """Decide which report type to use.

    Returns a tuple of (report_type, reason) for logging/traceability.
    """
    if cli_value:
        return normalize_choice(cli_value), f"CLI flag --report={cli_value}"
    if is_ci():
        return HTML, "CI environment detected"
    if not interactive:
        return HTML, "non-interactive stdin"
    return prompt_fn(), "interactive selection"
