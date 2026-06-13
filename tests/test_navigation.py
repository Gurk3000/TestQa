"""Project navigation scenarios: positive + invalid project."""
from __future__ import annotations

import allure
import pytest

from config.config import settings
from conftest import ProjectContext
from pages.dashboard_page import DashboardPage
from pages.project_page import ProjectPage


@allure.epic("TestRail UI")
@allure.feature("Project Navigation")
class TestNavigation:

    @allure.story("TC-002 Positive: navigate to target project")
    @pytest.mark.positive
    @pytest.mark.smoke
    def test_navigate_to_project(self, logged_in: DashboardPage, project_context: ProjectContext, driver):
        logged_in.go_to_dashboard_via_logo()
        assert logged_in.is_project_present(settings.project_name, project_context.project_id), (
            f"Project '{settings.project_name}' must be reachable from the dashboard"
        )
        logged_in.open_project(settings.project_name, project_id=project_context.project_id)
        project = ProjectPage(driver)
        assert project.is_loaded(), "Project overview page must load"
        assert str(project_context.project_id) in project.current_url(), "URL must contain resolved project id"
        assert project.is_project_name_displayed(settings.project_name), (
            f"Project page must display the correct project name '{settings.project_name}'"
        )
        assert project.is_test_cases_section_available(), "Test Cases section must be available in the sidebar"

    @allure.story("Negative: navigate to non-existent project")
    @pytest.mark.negative
    def test_invalid_project_navigation(self, logged_in: DashboardPage, driver):
        project = ProjectPage(driver)
        # An obviously invalid project id should not render a valid project overview.
        project.open_by_id(99999999)
        assert project.has_error() or "/projects/overview" not in project.current_url() or not project.title_text(), (
            "Invalid project navigation must not render a valid project"
        )
