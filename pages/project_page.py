"""Project page object: project-scoped overview and navigation hub."""
from __future__ import annotations

import allure
from selenium.webdriver.common.by import By

from components.header_component import HeaderComponent
from components.sidebar_component import SidebarComponent
from config.config import settings
from pages.base_page import BasePage


class ProjectPage(BasePage):
    """TestRail project overview with sidebar navigation."""

    url_fragment = "/projects/overview"

    _PROJECT_TITLE = (By.CSS_SELECTOR, "#content-header .content-header-title, h1, .title")
    _CONTENT = (By.CSS_SELECTOR, "#content, .content")
    _ERROR_PAGE = (By.CSS_SELECTOR, ".message-error, .error, #error")

    def __init__(self, driver):
        super().__init__(driver)
        self.sidebar = SidebarComponent(driver)
        self.header = HeaderComponent(driver)

    @allure.step("Open project by id={project_id}")
    def open_by_id(self, project_id: int) -> "ProjectPage":
        self.log.info("Opening project overview id=%s", project_id)
        self.open(f"{settings.base_url}/index.php?/projects/overview/{project_id}")
        self.wait.document_ready()
        return self

    def is_loaded(self) -> bool:
        return self.is_present(self._CONTENT, timeout=10) and "/projects/overview" in self.current_url()

    def title_text(self) -> str:
        if self.is_visible(self._PROJECT_TITLE, 5):
            return self.get_text(self._PROJECT_TITLE)
        return ""

    def displayed_project_name(self) -> str:
        return self.title_text()

    def is_project_name_displayed(self, name: str) -> bool:
        return name.lower() in self.title_text().lower()

    def is_test_cases_section_available(self) -> bool:
        return self.sidebar.is_test_cases_available()

    def has_error(self) -> bool:
        return self.is_visible(self._ERROR_PAGE, 4)

    @allure.step("Navigate to Test Cases")
    def go_to_test_cases(self) -> None:
        self.sidebar.open_test_cases()
        self.wait.document_ready()

    @allure.step("Navigate to Test Runs & Results")
    def go_to_test_runs(self) -> None:
        self.sidebar.open_test_runs()
        self.wait.document_ready()
