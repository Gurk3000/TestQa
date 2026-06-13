"""Test Case creation scenarios with UI + API validation.

UI vs API truth model: every UI action is validated against the TestRail API,
which is treated as the source of truth.
"""
from __future__ import annotations

import allure
import pytest

from api.case_api import CaseAPI
from conftest import EntityRegistry, ProjectContext
from pages.dashboard_page import DashboardPage
from tests.helpers import open_test_cases_page, resolve_case_id_after_ui_create
from utils import random_data


@allure.epic("TestRail UI")
@allure.feature("Test Case Management")
class TestCreateTestCase:

    @allure.story("TC-003 Positive: create a test case (UI + API validated)")
    @pytest.mark.positive
    @pytest.mark.smoke
    def test_create_test_case_success(
        self,
        driver,
        logged_in: DashboardPage,
        project_context: ProjectContext,
        case_api: CaseAPI,
        registry: EntityRegistry,
    ):
        title = random_data.unique_test_case_name()
        cases_page = open_test_cases_page(driver, logged_in, project_context)

        # Inline section quick-add: "Add Case" link -> title -> Enter (per TestRail UI).
        cases_page.create_case_inline(title, section_id=project_context.section_id)

        with allure.step("TC-003: success message + ID generated"):
            assert cases_page.created_case_confirmed(title), (
                "UI must confirm creation (grid row / success notice / case view)"
            )
            case_id = resolve_case_id_after_ui_create(cases_page, case_api, project_context, title)
            assert case_id is not None, "Case ID must be generated (URL or API after save)"
            registry.add_case(case_id)

        with allure.step("Validate via API (source of truth)"):
            api_case = case_api.get_case(case_id)
            assert api_case.get("title") == title, "API case title must match the created title"
            assert case_api.case_exists(
                project_context.project_id, title, project_context.suite_id or None
            ), "Created case must be discoverable via API in the project"

        with allure.step("TC-003: case appears in the list"):
            assert case_api.find_case_by_title(
                project_context.project_id, title, project_context.suite_id or None
            ) is not None, "Created case must appear in the project case list (API)"

    @allure.story("TC-011 Verify generated ID is not empty")
    @pytest.mark.positive
    def test_verify_generated_case_id(
        self, driver, logged_in: DashboardPage, project_context: ProjectContext,
        case_api: CaseAPI, registry: EntityRegistry,
    ):
        title = random_data.unique_test_case_name()
        cases_page = open_test_cases_page(driver, logged_in, project_context)
        # Same fast path as TC-003 smoke; TC-011 only requires a non-empty id (URL or API).
        cases_page.create_case_inline(title, section_id=project_context.section_id)
        case_id = resolve_case_id_after_ui_create(cases_page, case_api, project_context, title)
        assert case_id, "Generated test case ID must not be empty"
        registry.add_case(case_id)
        assert case_api.get_case(case_id).get("id") == case_id, "API must confirm the same case ID"

    @allure.story("TC-004 Verify created test case: name + description match")
    @pytest.mark.positive
    def test_verify_created_test_case(
        self, driver, logged_in: DashboardPage, project_context: ProjectContext,
        case_api: CaseAPI, registry: EntityRegistry,
    ):
        title = random_data.unique_test_case_name()
        description = f"Description for {title}"
        cases_page = open_test_cases_page(driver, logged_in, project_context)
        cases_page.create_case(title, references=description, section_id=project_context.section_id)
        case_id = resolve_case_id_after_ui_create(cases_page, case_api, project_context, title)
        assert case_id is not None, "Case must be created"
        registry.add_case(case_id)

        with allure.step("Open created case and verify name (UI)"):
            cases_page.open_case_by_id(case_id)
            assert title in cases_page.displayed_title() or cases_page.displayed_title() == title, (
                "Opened case must display the entered name"
            )

        with allure.step("Verify name + description via API (source of truth)"):
            api_case = case_api.get_case(case_id)
            assert api_case.get("title") == title, "Name must match the entered value"
            # `refs` is the verifiable description proxy set through the form.
            assert (api_case.get("refs") or "") == description, "Description/refs must match the entered value"

    @allure.story("TC-012 Verify created test case is found through search")
    @pytest.mark.positive
    def test_verify_test_case_search(
        self, driver, logged_in: DashboardPage, project_context: ProjectContext,
        case_api: CaseAPI, registry: EntityRegistry,
    ):
        title = random_data.unique_test_case_name()
        cases_page = open_test_cases_page(driver, logged_in, project_context)
        cases_page.create_case_inline(title, section_id=project_context.section_id)
        case_id = resolve_case_id_after_ui_create(cases_page, case_api, project_context, title)
        assert case_id is not None, "Case must be created before search"
        registry.add_case(case_id)

        # Project sidebar state may differ; return to case list via dashboard quick link.
        DashboardPage(driver).open_test_cases_quick_link_from_dashboard(project_context.project_id)
        with allure.step("Search and verify visibility (UI)"):
            assert cases_page.search_case(title), "Created case must be found through search / in the list"

    @allure.story("TC-010 / Negative: empty test case name")
    @pytest.mark.negative
    def test_create_test_case_empty_name(
        self, driver, logged_in: DashboardPage, project_context: ProjectContext,
    ):
        cases_page = open_test_cases_page(driver, logged_in, project_context)
        cases_page.open_add_case_form(section_id=project_context.section_id)
        cases_page.set_title("")
        cases_page.submit()
        assert cases_page.has_validation_error() or cases_page.is_on_form(), (
            "Empty title must trigger validation or keep the form open"
        )

    @allure.story("Negative: duplicate test case name")
    @pytest.mark.negative
    def test_create_test_case_duplicate_name(
        self,
        driver,
        logged_in: DashboardPage,
        project_context: ProjectContext,
        case_api: CaseAPI,
        registry: EntityRegistry,
    ):
        # Seed the first case via API for determinism, then create a duplicate via UI.
        title = random_data.unique_test_case_name()
        seeded = case_api.add_case(project_context.section_id, title)
        registry.add_case(int(seeded["id"]))

        cases_page = open_test_cases_page(driver, logged_in, project_context)
        cases_page.create_case_inline(title, section_id=project_context.section_id)

        # TestRail allows duplicate titles by design, so the duplicate must get
        # its own distinct ID. We assert the API now reports two cases with the
        # same title (no silent overwrite / data loss).
        new_id = resolve_case_id_after_ui_create(cases_page, case_api, project_context, title)
        if new_id:
            registry.add_case(new_id)
        matches = [c for c in case_api.get_cases(project_context.project_id, project_context.suite_id or None)
                   if c.get("title") == title]
        assert len(matches) >= 2, "Duplicate-titled case must be created as a separate entity"
