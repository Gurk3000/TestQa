"""Edge-case scenarios for test case creation."""
from __future__ import annotations

import allure
import pytest

from api.case_api import CaseAPI
from conftest import EntityRegistry, ProjectContext
from pages.dashboard_page import DashboardPage
from pages.test_case_page import TestCasePage
from tests.helpers import resolve_case_id_after_ui_create
from utils import random_data


def _open_test_cases(driver, dashboard: DashboardPage, project_context: ProjectContext) -> TestCasePage:
    dashboard.open_test_cases_quick_link_from_dashboard(project_context.project_id)
    return TestCasePage(driver)


def _register_if_created(
    cases_page: TestCasePage,
    registry: EntityRegistry,
    case_api: CaseAPI,
    project_context: ProjectContext,
    title: str,
) -> int | None:
    """Resolve the new case id (URL first, then API by title) and register it for cleanup."""
    case_id = resolve_case_id_after_ui_create(cases_page, case_api, project_context, title)
    if case_id:
        registry.add_case(case_id)
    return case_id


@allure.epic("TestRail UI")
@allure.feature("Test Case Edge Cases")
@pytest.mark.edge
class TestEdgeCases:

    @allure.story("Edge: very long test case name")
    def test_very_long_name(
        self, driver, logged_in: DashboardPage, project_context: ProjectContext,
        case_api: CaseAPI, registry: EntityRegistry,
    ):
        title = random_data.long_name(250)
        cases_page = _open_test_cases(driver, logged_in, project_context)
        cases_page.create_case(title, section_id=project_context.section_id)
        case_id = _register_if_created(cases_page, registry, case_api, project_context, title)
        # Either it is accepted (and stored, possibly truncated) or rejected gracefully.
        if case_id:
            stored = case_api.get_case(case_id).get("title", "")
            assert stored, "A created case must have a stored title"
        else:
            assert cases_page.has_validation_error() or cases_page.is_on_form()

    @allure.story("Edge: special characters in name")
    def test_special_characters(
        self, driver, logged_in: DashboardPage, project_context: ProjectContext,
        case_api: CaseAPI, registry: EntityRegistry,
    ):
        title = random_data.special_chars_name()
        cases_page = _open_test_cases(driver, logged_in, project_context)
        cases_page.create_case_inline(title, section_id=project_context.section_id)
        case_id = _register_if_created(cases_page, registry, case_api, project_context, title)
        assert case_id is not None, "Special characters should be accepted in a title"
        assert case_api.get_case(case_id).get("title") == title, "Special-char title must be stored verbatim"

    @allure.story("Edge: unicode characters in name")
    def test_unicode_characters(
        self, driver, logged_in: DashboardPage, project_context: ProjectContext,
        case_api: CaseAPI, registry: EntityRegistry,
    ):
        title = random_data.unicode_name()
        cases_page = _open_test_cases(driver, logged_in, project_context)
        cases_page.create_case_inline(title, section_id=project_context.section_id)
        case_id = _register_if_created(cases_page, registry, case_api, project_context, title)
        assert case_id is not None, "Unicode characters should be accepted in a title"
        assert case_api.get_case(case_id).get("title") == title, "Unicode title must be stored verbatim"

    @allure.story("Edge: rapid multiple clicks on save must not duplicate")
    def test_rapid_multiple_clicks(
        self, driver, logged_in: DashboardPage, project_context: ProjectContext,
        case_api: CaseAPI, registry: EntityRegistry,
    ):
        title = random_data.unique_test_case_name()
        cases_page = _open_test_cases(driver, logged_in, project_context)
        cases_page.open_add_case_form(section_id=project_context.section_id)
        cases_page.set_title(title)
        cases_page.rapid_submit(5)
        case_id = _register_if_created(cases_page, registry, case_api, project_context, title)

        matches = [c for c in case_api.get_cases(project_context.project_id, project_context.suite_id or None)
                   if c.get("title") == title]
        # Track any extras for cleanup, then assert idempotency of a single submit.
        for case in matches:
            registry.add_case(int(case["id"]))
        assert len(matches) <= 1, "Rapid double submit must not create duplicate cases"

    @allure.story("Edge: browser refresh during creation")
    def test_browser_refresh_during_creation(
        self, driver, logged_in: DashboardPage, project_context: ProjectContext,
        case_api: CaseAPI, registry: EntityRegistry,
    ):
        title = random_data.unique_test_case_name()
        cases_page = _open_test_cases(driver, logged_in, project_context)
        cases_page.open_add_case_form(section_id=project_context.section_id)
        cases_page.set_title(title)
        # Refresh before submitting: unsaved data must NOT create an entity.
        cases_page.refresh()
        exists = case_api.case_exists(project_context.project_id, title, project_context.suite_id or None)
        if exists:  # defensive cleanup if the platform persisted a draft
            case = case_api.find_case_by_title(project_context.project_id, title, project_context.suite_id or None)
            if case:
                registry.add_case(int(case["id"]))
        assert not exists, "Refreshing before submit must not persist an unsaved test case"
