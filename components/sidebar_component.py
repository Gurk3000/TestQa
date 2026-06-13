"""Project sidebar navigation component.

Reusable across project-scoped pages to switch between Overview, Test Cases,
Test Runs & Results, Milestones, etc.
"""
from __future__ import annotations

from selenium.webdriver.common.by import By

from components.base_component import BaseComponent


class SidebarComponent(BaseComponent):
    """Left-hand project navigation sidebar."""

    root_locator = (By.CSS_SELECTOR, "#sidebar, .sidebar")

    _TEST_CASES = (
        By.CSS_SELECTOR,
        "[data-testid='navigateToCasesButton'], #navigation-suites-dropdown, "
        "a[href*='/suites/view'], a[href*='/suites/overview']",
    )
    _TEST_RUNS = (
        By.CSS_SELECTOR,
        "[data-testid='navigateToRunsButton'], #navigation-runs-dropdown, a[href*='/runs/overview']",
    )
    _OVERVIEW = (By.CSS_SELECTOR, "a[href*='/projects/overview'], #navigation-overview")
    _MILESTONES = (By.CSS_SELECTOR, "a[href*='/milestones/overview']")
    _LINK_BY_TEXT = "//*[@id='sidebar' or contains(@class,'sidebar')]//a[normalize-space()=\"{text}\"]"

    def open_test_cases(self) -> None:
        self.log.info("Sidebar -> Test Cases")
        self._open(self._TEST_CASES, "Test Cases")

    def open_test_runs(self) -> None:
        self.log.info("Sidebar -> Test Runs & Results")
        self._open(self._TEST_RUNS, "Test Runs & Results")

    def open_overview(self) -> None:
        self.log.info("Sidebar -> Overview")
        self._open(self._OVERVIEW, "Overview")

    def open_milestones(self) -> None:
        self.log.info("Sidebar -> Milestones")
        self._open(self._MILESTONES, "Milestones")

    def is_test_cases_available(self) -> bool:
        if self.is_present(self._TEST_CASES, 5):
            return True
        return self.is_present((By.XPATH, self._LINK_BY_TEXT.format(text="Test Cases")), 3)

    def is_test_runs_available(self) -> bool:
        if self.is_present(self._TEST_RUNS, 5):
            return True
        return self.is_present((By.XPATH, self._LINK_BY_TEXT.format(text="Test Runs & Results")), 3)

    def _open(self, primary: tuple, text_fallback: str) -> None:
        if self.is_present(primary, 4):
            self.click(primary)
            return
        # Fallback by visible link text inside the sidebar.
        self.click((By.XPATH, self._LINK_BY_TEXT.format(text=text_fallback)))
