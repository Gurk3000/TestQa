"""Test Run creation scenarios with UI + API validation."""
from __future__ import annotations

import allure
import pytest

from api.case_api import CaseAPI
from api.run_api import RunAPI
from conftest import EntityRegistry, ProjectContext
from pages.dashboard_page import DashboardPage
from pages.test_run_page import TestRunPage
from tests.helpers import open_test_cases_page, resolve_case_id_after_ui_create, resolve_run_id_after_ui_create
from utils import random_data


def _open_test_runs(driver, dashboard: DashboardPage, project_context: ProjectContext) -> TestRunPage:
    dashboard.open_test_runs_quick_link_from_dashboard(project_context.project_id)
    return TestRunPage(driver)


@allure.epic("TestRail UI")
@allure.feature("Test Run Management")
class TestCreateTestRun:

    @allure.story("TC-005/006/013 Positive: create a test run including a test case")
    @pytest.mark.positive
    @pytest.mark.smoke
    def test_create_test_run_success(
        self,
        driver,
        logged_in: DashboardPage,
        project_context: ProjectContext,
        case_api: CaseAPI,
        run_api: RunAPI,
        registry: EntityRegistry,
    ):
        # TASK 1: create the test case in the UI first, then attach it to the new run.
        case_title = random_data.unique_test_case_name()
        cases_page = open_test_cases_page(driver, logged_in, project_context)
        cases_page.create_case_inline(case_title, section_id=project_context.section_id)
        with allure.step("Precondition: test case created via UI"):
            assert cases_page.created_case_confirmed(case_title), (
                "UI must confirm case creation before adding it to a run"
            )
            case_id = resolve_case_id_after_ui_create(cases_page, case_api, project_context, case_title)
            assert case_id is not None, "Case ID must be resolved (URL or API after UI save)"
        registry.add_case(case_id)

        run_name = random_data.unique_test_run_name()
        runs_page = _open_test_runs(driver, logged_in, project_context)
        runs_page.create_run(run_name, case_title=case_title, case_id=case_id, project_id=project_context.project_id)

        with allure.step("TC-005: run created + visible in run view (UI)"):
            run_id = resolve_run_id_after_ui_create(runs_page, run_api, project_context, run_name)
            assert run_id is not None, "Run ID must be resolved (URL /runs/view/<id> or API by name)"
            registry.add_run(run_id)
            runs_page.open_run_by_id(run_id)
            assert runs_page.run_title() == run_name or runs_page.included_cases_count() >= 1, (
                "Run view must show the run name / included tests"
            )

        with allure.step("TC-006: selected case present inside the run (UI)"):
            assert runs_page.is_case_in_run(case_title), "Selected case must be visible inside the run"

        with allure.step("TC-005/006/013: validate via API (source of truth)"):
            api_run = run_api.get_run(run_id)
            assert api_run.get("name") == run_name, "API run name must match"
            assert run_api.run_contains_case(run_id, case_id), "Run must contain the selected case via API"
            assert run_api.tests_count(run_id) == 1, "Included test count must be exactly 1 (TC-013)"

    @allure.story("TC-014 Newly created run status is Active")
    @pytest.mark.positive
    def test_run_status_active(
        self, driver, logged_in: DashboardPage, project_context: ProjectContext,
        case_api: CaseAPI, run_api: RunAPI, registry: EntityRegistry,
    ):
        case_title = random_data.unique_test_case_name()
        case_id = int(case_api.add_case(project_context.section_id, case_title)["id"])
        registry.add_case(case_id)

        run_name = random_data.unique_test_run_name()
        runs_page = _open_test_runs(driver, logged_in, project_context)
        runs_page.create_run(run_name, case_title=case_title, case_id=case_id, project_id=project_context.project_id)
        run_id = resolve_run_id_after_ui_create(runs_page, run_api, project_context, run_name)
        assert run_id is not None
        registry.add_run(run_id)
        runs_page.open_run_by_id(run_id)
        assert run_api.is_active(run_id), "A newly created run must be Active (not completed)"

    @allure.story("TC-015 Created run appears in the list after refresh")
    @pytest.mark.positive
    def test_run_appears_in_list_after_refresh(
        self, driver, logged_in: DashboardPage, project_context: ProjectContext,
        case_api: CaseAPI, run_api: RunAPI, registry: EntityRegistry,
    ):
        case_title = random_data.unique_test_case_name()
        case_id = int(case_api.add_case(project_context.section_id, case_title)["id"])
        registry.add_case(case_id)

        run_name = random_data.unique_test_run_name()
        runs_page = _open_test_runs(driver, logged_in, project_context)
        runs_page.create_run(run_name, case_title=case_title, case_id=case_id, project_id=project_context.project_id)
        run_id = resolve_run_id_after_ui_create(runs_page, run_api, project_context, run_name)
        assert run_id is not None, "Run must be created (URL or API)"

        # Go to the runs overview, refresh, and verify the run persists.
        # Return to runs overview the same way as from dashboard (stable vs sidebar state).
        DashboardPage(driver).open_test_runs_quick_link_from_dashboard(project_context.project_id)
        runs_list = TestRunPage(driver)
        runs_list.refresh()
        assert runs_list.is_run_visible(run_name) or run_api.run_exists(
            project_context.project_id, run_name
        ), "Run must be visible in the list after a refresh"

    @allure.story("Negative: empty test run name")
    @pytest.mark.negative
    def test_create_test_run_empty_name(self, driver, logged_in: DashboardPage, project_context: ProjectContext):
        runs_page = _open_test_runs(driver, logged_in, project_context)
        runs_page.open_add_run_form(project_id=project_context.project_id)
        runs_page.set_name("")
        runs_page.submit()
        assert runs_page.has_validation_error() or runs_page.is_on_form(), (
            "Empty run name must trigger validation or keep the form open"
        )

    @allure.story("Negative: create run without any test case selected")
    @pytest.mark.negative
    def test_create_run_without_case(
        self,
        driver,
        logged_in: DashboardPage,
        project_context: ProjectContext,
        run_api: RunAPI,
        registry: EntityRegistry,
    ):
        run_name = random_data.unique_test_run_name()
        runs_page = _open_test_runs(driver, logged_in, project_context)
        runs_page.open_add_run_form(project_id=project_context.project_id)
        runs_page.set_name(run_name)
        # Explicitly switch to custom selection but pick nothing.
        runs_page.switch_to_custom_selection()
        runs_page.submit()

        run_id = runs_page.get_created_run_id()
        if run_id:
            # If TestRail permits an empty run, it must contain zero tests (API truth).
            registry.add_run(run_id)
            assert run_api.tests_count(run_id) == 0, "A run created without cases must contain zero tests"
        else:
            assert runs_page.has_validation_error() or runs_page.is_on_form(), (
                "Run creation without cases must be blocked or produce an empty run"
            )
