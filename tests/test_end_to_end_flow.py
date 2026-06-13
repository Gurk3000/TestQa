"""End-to-end flow: login -> project -> case -> run -> verify -> logout.

Mirrors the assignment exactly and validates each step via the API as the
source of truth in addition to UI assertions.
"""
from __future__ import annotations

import allure
import pytest

from api.case_api import CaseAPI
from api.run_api import RunAPI
from config.config import settings
from conftest import EntityRegistry, ProjectContext
from pages.dashboard_page import DashboardPage
from pages.login_page import LoginPage
from pages.project_page import ProjectPage
from pages.test_case_page import TestCasePage
from pages.test_run_page import TestRunPage
from tests.helpers import resolve_case_id_after_ui_create, resolve_run_id_after_ui_create
from utils import random_data
from utils.logger import get_logger

logger = get_logger("e2e")


@allure.epic("TestRail UI")
@allure.feature("End-to-End")
@pytest.mark.e2e
class TestEndToEndFlow:

    @allure.story("Full assignment flow with UI + API verification")
    @pytest.mark.positive
    def test_full_flow(
        self,
        driver,
        project_context: ProjectContext,
        case_api: CaseAPI,
        run_api: RunAPI,
        registry: EntityRegistry,
    ):
        case_title = random_data.unique_test_case_name()
        run_name = random_data.unique_test_run_name()

        with allure.step("1. Login"):
            logger.info("E2E step: login")
            login = LoginPage(driver)
            login.open_login()
            login.login_expecting_success(settings.email, settings.password)

        with allure.step("2. Dashboard via logo, then suites (Test Cases)"):
            logger.info("E2E step: dashboard + Test Cases quick link")
            dashboard = DashboardPage(driver)
            dashboard.ensure_main_app_landing()
            dashboard.go_to_dashboard_via_logo()
            assert "/dashboard" in dashboard.current_url().lower(), "Logo must lead to the dashboard URL"
            dashboard.open_test_cases_quick_link_from_dashboard(project_context.project_id)

        with allure.step("3-4. Create test case + verify"):
            logger.info("E2E step: create test case")
            cases_page = TestCasePage(driver)
            cases_page.create_case_inline(case_title, section_id=project_context.section_id)
            case_id = resolve_case_id_after_ui_create(cases_page, case_api, project_context, case_title)
            assert case_id is not None, "Case ID must be generated"
            registry.add_case(case_id)
            assert case_api.get_case(case_id).get("title") == case_title, "API must confirm the case"

        with allure.step("5-6. Create test run with the case + verify"):
            logger.info("E2E step: create test run")
            dashboard.go_to_dashboard_via_logo()
            dashboard.open_test_runs_quick_link_from_dashboard(project_context.project_id)
            runs_page = TestRunPage(driver)
            runs_page.create_run(run_name, case_title=case_title, case_id=case_id, project_id=project_context.project_id)
            run_id = resolve_run_id_after_ui_create(runs_page, run_api, project_context, run_name)
            assert run_id is not None, "Run ID must be generated"
            registry.add_run(run_id)
            runs_page.open_run_by_id(run_id)
            assert run_api.get_run(run_id).get("name") == run_name, "API must confirm the run"

        with allure.step("7-8. Verify the case is inside the run (API truth)"):
            logger.info("E2E step: verify case inside run")
            assert run_api.run_contains_case(run_id, case_id), "Case must be inside the run (API)"
            assert run_api.tests_count(run_id) == 1, "Run must contain exactly one test"

        with allure.step("9. Logout"):
            logger.info("E2E step: logout")
            ProjectPage(driver).header.logout()
            assert "/auth/login" in driver.current_url or LoginPage(driver).is_on_login_page()
