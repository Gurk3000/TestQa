"""Centralized, immutable configuration loaded from environment / .env file.

Single source of truth for runtime settings. All other modules import the
`settings` singleton instead of reading environment variables directly,
keeping the rest of the framework decoupled from the configuration source.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Resolve project root (one level above this /config package).
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]

# Load environment variables from credentials.env (does not override real env).
_ENV_FILE = PROJECT_ROOT / "config" / "credentials.env"
load_dotenv(dotenv_path=_ENV_FILE, override=False)


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _get_bool(key: str, default: bool = False) -> bool:
    raw = _get(key, str(default)).lower()
    return raw in {"1", "true", "yes", "y", "on"}


def _get_int(key: str, default: int) -> int:
    raw = _get(key, "")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings."""

    base_url: str = field(default_factory=lambda: _get("TESTRAIL_BASE_URL").rstrip("/"))
    email: str = field(default_factory=lambda: _get("TESTRAIL_EMAIL"))
    password: str = field(default_factory=lambda: _get("TESTRAIL_PASSWORD"))
    api_key: str = field(default_factory=lambda: _get("TESTRAIL_API_KEY"))
    project_name: str = field(default_factory=lambda: _get("TESTRAIL_PROJECT_NAME"))

    project_id_override: str = field(default_factory=lambda: _get("TESTRAIL_PROJECT_ID"))
    suite_id_override: str = field(default_factory=lambda: _get("TESTRAIL_SUITE_ID"))
    section_id_override: str = field(default_factory=lambda: _get("TESTRAIL_SECTION_ID"))

    browser: str = field(default_factory=lambda: _get("BROWSER", "chrome").lower())
    headless: bool = field(default_factory=lambda: _get_bool("HEADLESS", False))
    implicit_wait: int = field(default_factory=lambda: _get_int("IMPLICIT_WAIT", 0))
    explicit_wait: int = field(default_factory=lambda: _get_int("EXPLICIT_WAIT", 20))
    page_load_timeout: int = field(default_factory=lambda: _get_int("PAGE_LOAD_TIMEOUT", 40))
    ui_retry_count: int = field(default_factory=lambda: _get_int("UI_RETRY_COUNT", 2))
    # After login submit: max wait for redirect / error (separate from global EXPLICIT_WAIT).
    login_post_submit_wait_seconds: int = field(default_factory=lambda: _get_int("LOGIN_POST_SUBMIT_WAIT", 15))
    # ENTER / JS-submit fallbacks after the primary wait.
    login_fallback_wait_seconds: int = field(default_factory=lambda: _get_int("LOGIN_FALLBACK_WAIT", 8))
    # Max seconds to poll get_cases after UI create when URL has no /cases/view/<id> yet.
    api_poll_after_ui_seconds: int = field(
        default_factory=lambda: _get_int("TESTRAIL_API_POLL_AFTER_UI_SECONDS", 28)
    )
    # Console (PowerShell) log level; full DEBUG trace always goes to the log file.
    console_log_level: str = field(
        default_factory=lambda: _get("TESTRAIL_CONSOLE_LOG_LEVEL", "WARNING")
    )
    # Capture + attach a screenshot for PASSED tests too (not only failures), so the
    # report shows visual evidence for every test. Disable with =false to speed runs.
    screenshot_on_success: bool = field(
        default_factory=lambda: _get_bool("TESTRAIL_SCREENSHOT_ON_SUCCESS", True)
    )

    # Derived directories (created lazily by callers that need them).
    reports_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "reports")
    screenshots_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "screenshots")
    logs_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "logs")
    allure_results_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "reports" / "allure-results")
    # Static HTML produced by ``allure generate`` (``index.html``) after an Allure run.
    allure_report_html_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "reports" / "allure-report")

    @property
    def api_password(self) -> str:
        """Credential used for TestRail API Basic Auth (API key preferred)."""
        return self.api_key or self.password

    @property
    def login_url(self) -> str:
        return f"{self.base_url}/index.php?/auth/login/"

    @property
    def api_base(self) -> str:
        return f"{self.base_url}/index.php?/api/v2"

    def ensure_dirs(self) -> None:
        for directory in (
            self.reports_dir,
            self.screenshots_dir,
            self.logs_dir,
            self.allure_results_dir,
            self.allure_report_html_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


# Importable singleton.
settings = Settings()
settings.ensure_dirs()
