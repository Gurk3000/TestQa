"""Shared helpers for tests (no locators — keeps tests thin)."""
from __future__ import annotations

from typing import Any, Optional

from api.case_api import CaseAPI
from api.run_api import RunAPI
from config.config import settings
from pages.dashboard_page import DashboardPage
from pages.test_case_page import TestCasePage
from pages.test_run_page import TestRunPage


def open_test_cases_page(driver: Any, dashboard: DashboardPage, project_context: Any) -> TestCasePage:
    """Open the project Test Cases view from the dashboard (shared by case/run tests)."""
    dashboard.open_test_cases_quick_link_from_dashboard(project_context.project_id)
    return TestCasePage(driver)


def resolve_case_id_after_ui_create(
    cases_page: TestCasePage,
    case_api: CaseAPI,
    project_context: Any,
    title: str,
) -> Optional[int]:
    """Prefer URL id; if TestRail is slow to redirect, poll API by unique title."""
    cid = cases_page.get_created_case_id()
    if cid:
        return cid
    # Wrong-page submit (e.g. mis-clicked global button) — do not burn a full minute.
    url = (cases_page.current_url() or "").lower()
    if "/post" in url or "about:blank" in url:
        return None
    row = case_api.wait_for_case_by_title(
        project_context.project_id,
        title,
        project_context.suite_id or None,
        timeout_seconds=settings.api_poll_after_ui_seconds,
    )
    return int(row["id"]) if row else None


def resolve_run_id_after_ui_create(
    runs_page: TestRunPage,
    run_api: RunAPI,
    project_context: Any,
    run_name: str,
) -> Optional[int]:
    """Prefer URL id; if TestRail is slow to redirect, poll API by unique run name."""
    rid = runs_page.get_created_run_id()
    if rid:
        return rid
    url = (runs_page.current_url() or "").lower()
    if "/post" in url or "about:blank" in url:
        return None
    row = run_api.wait_for_run_by_name(
        project_context.project_id,
        run_name,
        timeout_seconds=float(settings.api_poll_after_ui_seconds),
    )
    return int(row["id"]) if row else None
