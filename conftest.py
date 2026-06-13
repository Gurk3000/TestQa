"""Pytest fixtures, WebDriver lifecycle, reporting and API-based cleanup.

This module wires together:
  * WebDriver creation (Chrome/Firefox/Edge) via Selenium Manager.
  * Explicit-wait based, headless-capable browser sessions.
  * Screenshot-on-failure + Allure attachment (screenshot, page source, logs).
  * TestRail API clients (source of truth for validation + cleanup).
  * Project context resolution (project/suite/section ids via API).
  * An entity registry that deletes UI-created cases/runs through the API.
"""
from __future__ import annotations

from datetime import datetime
import os
import platform
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Iterator, List

import allure
import pytest
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver

from api.case_api import CaseAPI
from api.run_api import RunAPI
from api.testrail_client import TestRailClient
from config.config import settings
from pages.dashboard_page import DashboardPage
from pages.login_page import LoginPage
from utils import report_selector
from utils import screenshot as screenshot_util
from utils import failure_diagnostics
from utils.logger import get_logger, log_file_path

logger = get_logger("conftest")


def _first_section_id(api_client: TestRailClient, project_id: int, preferred_suite_id: int) -> int:
    """Pick a valid section for add_case; walk suites if the default suite has no sections."""
    suite_order: List[int] = []
    if preferred_suite_id:
        suite_order.append(preferred_suite_id)
    for suite in api_client.get_suites(project_id):
        sid = int(suite["id"])
        if sid not in suite_order:
            suite_order.append(sid)
    # Last resort: master project (no suite filter) — some deployments return root sections only here.
    suite_order.append(-1)

    for sid in suite_order:
        sections = api_client.get_sections(project_id, None if sid == -1 else sid)
        if sections:
            chosen = int(sections[0]["id"])
            logger.info("Resolved section_id=%s (suite_id=%s)", chosen, sid if sid != -1 else "default")
            return chosen

    # No section exists yet -> create one so cases have a place to live.
    try:
        created = api_client.add_section(
            project_id,
            "Automation",
            suite_id=preferred_suite_id or None,
        )
        new_id = int(created["id"])
        logger.info("Auto-created section_id=%s ('Automation') for the project", new_id)
        return new_id
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to auto-create a section via API: %s", exc)
    return 0


# --------------------------------------------------------------------------- #
# CLI options
# --------------------------------------------------------------------------- #
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--browser", action="store", default=None, help="chrome|firefox|edge")
    parser.addoption("--headless", action="store", default=None, help="true|false")
    parser.addoption(
        "--report",
        action="store",
        default=None,
        choices=["html", "allure"],
        help="Report type. If omitted, an interactive prompt is shown (unless CI / non-interactive).",
    )


def _resolve(option_value, default):
    if option_value is None:
        return default
    return str(option_value).lower() in {"1", "true", "yes", "on"}


# --------------------------------------------------------------------------- #
# Interactive report-type selection (runs once, before collection)
# --------------------------------------------------------------------------- #
def _is_interactive_console() -> bool:
    """True if a real terminal is attached (even when pytest captures ``sys.stdin``)."""
    for stream in (sys.__stdin__, sys.stdin):
        try:
            if stream is not None and stream.isatty():
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _read_console_line() -> str:
    """Read one line from the real console, bypassing pytest's stdin capture.

    Tries the original stdin first, then the OS console device (``CON`` on Windows,
    ``/dev/tty`` elsewhere) so the prompt works under pytest capture.
    """
    try:
        if sys.__stdin__ is not None and sys.__stdin__.isatty():
            line = sys.__stdin__.readline()
            if line != "":
                return line.strip()
    except Exception:  # noqa: BLE001
        pass
    device = "CON" if os.name == "nt" else "/dev/tty"
    try:
        with open(device, "r", encoding="utf-8") as tty:
            return (tty.readline() or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def _prompt_report_type(config: pytest.Config) -> str:
    """Prompt the user in the terminal, safely suspending pytest capture."""
    capman = config.pluginmanager.getplugin("capturemanager")
    if capman is not None:
        capman.suspend_global_capture(in_=True)
    try:
        out = sys.__stdout__ or sys.stdout
        out.write(report_selector.render_menu() + "\n")
        out.write("Enter choice [1/2] (default 1): ")
        out.flush()
        answer = _read_console_line()
        out.write(f"Selected: {report_selector.normalize_choice(answer)}\n\n")
        out.flush()
    except Exception:  # noqa: BLE001 - no usable console -> safe default
        answer = ""
    finally:
        if capman is not None:
            capman.resume_global_capture()
    return report_selector.normalize_choice(answer)


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config) -> None:
    # trylast: interactive report choice runs AFTER pytest-html / allure-pytest have
    # already configured (they only auto-wire when paths are set early). We then set
    # the path and manually register the writer if needed. Running tryfirst broke the
    # normal PowerShell progress output (-v PASSED lines) because the early capture
    # suspend/resume around the menu interfered with pytest's terminal reporter.
    cli_value = config.getoption("--report")
    interactive = _is_interactive_console()

    report_type, reason = report_selector.decide_report_type(
        cli_value=cli_value,
        interactive=interactive,
        prompt_fn=lambda: _prompt_report_type(config),
    )
    logger.info("Report selection: %s (reason: %s)", report_type, reason)

    effective = report_selector.apply_report_config(config, report_type)
    config._report_type = effective  # type: ignore[attr-defined]
    if effective != report_type:
        logger.info("Report selection fell back to: %s", effective)
    config._failure_summary = {}  # type: ignore[attr-defined]  # nodeid -> one-line reason


def pytest_sessionstart(session: pytest.Session) -> None:
    """One-line session banner so log files are self-describing."""
    logger.info(
        "Pytest session | rootdir=%s | platform=%s | python=%s",
        session.config.rootpath,
        platform.platform(),
        platform.python_version(),
    )
    logger.info("Pytest args: %s", " ".join(str(a) for a in session.config.args))


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Log report output paths; write failure summary when any test failed (call phase)."""
    opt = session.config.option
    htmlp = getattr(opt, "htmlpath", None)
    if htmlp:
        try:
            logger.info("pytest-html report file: %s", Path(htmlp).resolve())
        except Exception:  # noqa: BLE001
            logger.info("pytest-html report file: %s", htmlp)
    ard = getattr(opt, "allure_report_dir", None)
    if ard:
        try:
            logger.info("Allure results directory: %s", Path(ard).resolve())
        except Exception:  # noqa: BLE001
            logger.info("Allure results directory: %s", ard)

    # Build static Allure HTML (index.html) when CLI is available — runs even if all tests passed.
    if not hasattr(session.config, "workerinput"):
        if getattr(session.config, "_report_type", None) == "allure" and ard:
            results_dir = Path(ard)
            tr = session.config.pluginmanager.get_plugin("terminalreporter")

            def _echo(msg: str) -> None:
                if tr is not None:
                    tr.write_line(msg, flush=True)

            idx = report_selector.generate_allure_static_html_site(
                results_dir,
                settings.allure_report_html_dir,
                terminal_echo=_echo,
            )
            if idx is not None:
                report_selector.launch_allure_open_browser(
                    settings.allure_report_html_dir,
                    terminal_echo=_echo,
                )

    bucket = getattr(session.config, "_failure_summary", None)
    if not isinstance(bucket, dict) or not bucket:
        return
    from utils import failure_summary as failure_summary_mod

    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    out = settings.reports_dir / "failure_summary.txt"
    failure_summary_mod.write_session_summary(out, bucket, datetime.now().isoformat(timespec="seconds"))
    logger.info("Failure summary: %s (%s failed test(s))", out, len(bucket))


# --------------------------------------------------------------------------- #
# WebDriver factory
# --------------------------------------------------------------------------- #
def _build_driver(browser: str, headless: bool) -> WebDriver:
    browser = browser.lower()
    logger.info("Creating WebDriver: browser=%s headless=%s", browser, headless)

    if browser == "chrome":
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        # Reduce Windows stderr noise (DevTools / GCM / GPU messages are harmless).
        options.add_argument("--log-level=3")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        driver = webdriver.Chrome(options=options)
    elif browser == "firefox":
        options = webdriver.FirefoxOptions()
        if headless:
            options.add_argument("--headless")
        driver = webdriver.Firefox(options=options)
    elif browser == "edge":
        options = webdriver.EdgeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--start-maximized")
        driver = webdriver.Edge(options=options)
    else:
        raise ValueError(f"Unsupported browser: {browser}")

    driver.implicitly_wait(settings.implicit_wait)
    driver.set_page_load_timeout(settings.page_load_timeout)
    try:
        driver.maximize_window()
    except Exception:  # noqa: BLE001 - headless may not support maximize
        pass
    return driver


@pytest.fixture
def driver(request: pytest.FixtureRequest) -> Iterator[WebDriver]:
    browser = request.config.getoption("--browser") or settings.browser
    headless = _resolve(request.config.getoption("--headless"), settings.headless)

    drv = _build_driver(browser, headless)
    # Expose driver on the node so the report hook can grab a screenshot.
    request.node._driver = drv  # type: ignore[attr-defined]
    yield drv
    logger.info("Quitting WebDriver")
    drv.quit()


# --------------------------------------------------------------------------- #
# API clients & project context
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def api_client() -> Iterator[TestRailClient]:
    client = TestRailClient()
    yield client
    client.close()


@pytest.fixture(scope="session")
def case_api(api_client: TestRailClient) -> CaseAPI:
    return CaseAPI(api_client)


@pytest.fixture(scope="session")
def run_api(api_client: TestRailClient) -> RunAPI:
    return RunAPI(api_client)


@dataclass
class ProjectContext:
    project_id: int
    suite_id: int
    section_id: int
    project_name: str


@pytest.fixture(scope="session")
def project_context(api_client: TestRailClient) -> ProjectContext:
    """Resolve project/suite/section ids via API (overridable through env)."""
    name = settings.project_name

    if settings.project_id_override:
        project_id = int(settings.project_id_override)
    else:
        project_id = api_client.find_project_id_by_name(name)
        if project_id is None:
            pytest.skip(f"Project '{name}' not found via API. Set TESTRAIL_PROJECT_ID or check credentials.")

    if settings.suite_id_override:
        suite_id = int(settings.suite_id_override)
    else:
        suites = api_client.get_suites(project_id)
        suite_id = int(suites[0]["id"]) if suites else 0

    if settings.section_id_override:
        section_id = int(settings.section_id_override)
    else:
        section_id = _first_section_id(api_client, project_id, suite_id)

    logger.info(
        "Project context resolved: project_id=%s suite_id=%s section_id=%s",
        project_id, suite_id, section_id,
    )
    if section_id == 0:
        pytest.skip(
            "No TestRail section could be resolved via API. Set TESTRAIL_SECTION_ID in config/credentials.env."
        )
    return ProjectContext(project_id=project_id, suite_id=suite_id, section_id=section_id, project_name=name)


# --------------------------------------------------------------------------- #
# Entity registry for API cleanup (idempotency / no leftover data)
# --------------------------------------------------------------------------- #
@dataclass
class EntityRegistry:
    case_ids: List[int] = field(default_factory=list)
    run_ids: List[int] = field(default_factory=list)

    def add_case(self, case_id: int) -> None:
        if case_id:
            self.case_ids.append(case_id)

    def add_run(self, run_id: int) -> None:
        if run_id:
            self.run_ids.append(run_id)


@pytest.fixture
def registry(case_api: CaseAPI, run_api: RunAPI) -> Iterator[EntityRegistry]:
    reg = EntityRegistry()
    yield reg
    # Teardown: delete runs first, then cases (best-effort, never fails the test).
    for run_id in reversed(reg.run_ids):
        try:
            run_api.delete_run(run_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cleanup: failed to delete run %s: %s", run_id, exc)
    for case_id in reversed(reg.case_ids):
        try:
            case_api.delete_case(case_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cleanup: failed to delete case %s: %s", case_id, exc)


# --------------------------------------------------------------------------- #
# Higher-level UI fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def login_page(driver: WebDriver) -> LoginPage:
    return LoginPage(driver)


@pytest.fixture
def logged_in(driver: WebDriver) -> DashboardPage:
    """Authenticated session (dashboard, onboarding, or other post-login landing)."""
    login = LoginPage(driver)
    login.open_login()
    login.login_expecting_success(settings.email, settings.password)
    dashboard = DashboardPage(driver)
    dashboard.ensure_main_app_landing()
    return dashboard


# --------------------------------------------------------------------------- #
# Reporting: screenshot + page source + logs on failure / skip / rerun
# --------------------------------------------------------------------------- #
def _attach_execution_log_to_allure() -> None:
    try:
        path = log_file_path()
        if path.exists():
            allure.attach.file(str(path), name="execution.log", attachment_type=allure.attachment_type.TEXT)
    except Exception:  # noqa: BLE001
        pass


def _attach_screenshot_to_html(item: pytest.Item, report: pytest.TestReport, drv, label: str) -> None:
    """Embed a screenshot into the pytest-html report (self-contained base64 PNG)."""
    if drv is None:
        return
    pytest_html = item.config.pluginmanager.getplugin("html")
    if pytest_html is None:
        return
    b64 = screenshot_util.capture_b64(drv)
    if not b64:
        return
    extras = list(getattr(report, "extras", []) or [])
    try:
        extras.append(pytest_html.extras.png(b64, name=label))
    except Exception:  # noqa: BLE001 - older pytest-html API
        try:
            extras.append(pytest_html.extras.image(b64, mime_type="image/png"))
        except Exception:  # noqa: BLE001
            return
    report.extras = extras


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Iterator[None]:
    outcome = yield
    report = outcome.get_result()

    drv = getattr(item, "_driver", None)

    if getattr(report, "skipped", False):
        failure_diagnostics.log_skip_report(item, report)

    if report.failed:
        failure_diagnostics.log_pytest_report(item, report, driver=drv)
        if report.when == "call":
            bucket = getattr(item.config, "_failure_summary", None)
            if isinstance(bucket, dict):
                from utils import failure_summary as failure_summary_mod

                bucket[item.nodeid] = failure_summary_mod.one_line_reason(report)

    if report.failed:
        if drv is not None:
            logger.error("Capturing screenshot / page source for: %s", item.nodeid)
            phase_name = f"{item.name}_{report.when}"
            screenshot_util.capture(drv, phase_name)
            screenshot_util.attach_to_allure(drv, name=f"failure_{phase_name}")
            screenshot_util.attach_page_source(drv, name=f"page_source_{phase_name}")
            _attach_screenshot_to_html(item, report, drv, f"failure_{phase_name}")
        _attach_execution_log_to_allure()

    # Visual evidence for PASSED tests too (senior-grade reporting): one screenshot
    # at the end of the call phase, embedded into both Allure and pytest-html.
    elif (
        report.when == "call"
        and getattr(report, "passed", False)
        and settings.screenshot_on_success
        and drv is not None
    ):
        label = f"passed_{item.name}"
        screenshot_util.capture(drv, label)
        screenshot_util.attach_to_allure(drv, name=label)
        _attach_screenshot_to_html(item, report, drv, label)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """pytest-rerunfailures sets ``outcome='rerun'`` only here (after makereport for that attempt)."""
    if getattr(report, "outcome", None) != "rerun":
        return
    item = getattr(report, "node", None)
    drv = getattr(item, "_driver", None) if item is not None else None
    failure_diagnostics.log_rerun_report(item, report, driver=drv)
    if report.when == "call" and drv is not None:
        logger.warning("Capturing screenshot / page source for RERUN: %s", report.nodeid)
        ridx = getattr(report, "rerun", 0)
        safe = (item.name if item is not None else report.nodeid.replace("::", "_"))[:100]
        base = f"{safe}_rerun{ridx}"
        screenshot_util.capture(drv, base)
        screenshot_util.attach_to_allure(drv, name=base)
        screenshot_util.attach_page_source(drv, name=f"page_source_{base}")
        if item is not None:
            _attach_screenshot_to_html(item, report, drv, base)
        _attach_execution_log_to_allure()


def pytest_exception_interact(node: pytest.Node, call: pytest.CallInfo, report: pytest.TestReport) -> None:
    """Emit a full traceback as soon as pytest handles an exception (best signal for debugging).

    The `report` parameter name must match the pytest hookspec exactly.
    """
    del report  # name required by hookspec; diagnostics come from `call.excinfo`
    failure_diagnostics.log_interactive_exception(node, call)
