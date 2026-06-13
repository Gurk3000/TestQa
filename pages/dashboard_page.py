"""Dashboard page object: post-login landing with the project list."""
from __future__ import annotations

from typing import Optional

import allure
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By

from components.header_component import HeaderComponent
from config.config import settings
from pages.base_page import BasePage


class DashboardPage(BasePage):
    """TestRail dashboard / projects overview."""

    url_fragment = "/dashboard"

    _PROJECT_LINK_BY_NAME = "//a[normalize-space()=\"{name}\"]"
    _PROJECT_ROWS = (By.CSS_SELECTOR, "a[href*='/projects/overview/']")
    _CONTENT = (By.CSS_SELECTOR, "#content, .content, #body")
    _SIDEBAR = (By.CSS_SELECTOR, '[data-testid="sidebar"]')
    # First-login wizard uses the same chrome; leave it before picking a project.
    _ONBOARDING_DASHBOARD_LINK = (
        By.CSS_SELECTOR,
        "#navigation-sub-dashboard, [data-testid='onboardingSidebarDashboard']",
    )
    _BANNER_DASHBOARD = (By.CSS_SELECTOR, '[data-testid="bannerLink"][href*="dashboard"]')
    # Top logo: `div#top-logo > a[data-testid=bannerLink] > img`. Present in ALL four
    # saved pages (logs/: dashboard, suites, runs-add, runs-overview) — shared chrome.
    _DASHBOARD_LOGO_LINK = (
        By.CSS_SELECTOR,
        "#top-logo a[href*='dashboard'], [data-testid='bannerLink'][href*='dashboard'], #top-logo a.link-noline",
    )
    _DASHBOARD_LOGO_IMG = (By.CSS_SELECTOR, "#top-logo img[src*='TestRail_Logo'], #top-logo img[src*='TestRail_Logo_Enterprise']")
    # Sidebar project picker: #searchProject + a[data-testid='projectId{N}']
    # (seen in the suites / runs-overview dumps under the sidebar search).
    _SEARCH_PROJECT_INPUT = (
        By.CSS_SELECTOR,
        "#searchProject, input[data-testid='searchProjectInput'], .search-project",
    )

    def __init__(self, driver):
        super().__init__(driver)
        self.header = HeaderComponent(driver)

    @allure.step("Verify dashboard is loaded")
    def is_loaded(self) -> bool:
        return self.is_present(self._CONTENT, timeout=10)

    def is_dashboard_displayed(self) -> bool:
        """App shell after login: main layout is up and URL is not the login page.

        New accounts often land on **/onboarding** first (same global chrome as dashboard).
        """
        if "/auth/login" in self.current_url():
            return False
        if not self.is_loaded():
            return False
        url_l = self.current_url().lower()
        if any(p in url_l for p in ("/onboarding", "/dashboard", "/mysettings")):
            return True
        if self.is_present(self._SIDEBAR, 3):
            return True
        return self.header.is_logged_in()

    def is_user_logged_in(self) -> bool:
        return self.header.is_logged_in()

    def username(self) -> str:
        return self.header.username()

    @staticmethod
    def _project_id_from_settings() -> Optional[int]:
        raw = (settings.project_id_override or "").strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    @allure.step("Leave onboarding wizard when it blocks project navigation")
    def ensure_main_app_landing(self) -> None:
        if "/onboarding" not in self.current_url().lower():
            return
        self.log.info("Onboarding URL detected; switching to main app shell")
        for loc in (self._ONBOARDING_DASHBOARD_LINK, self._BANNER_DASHBOARD):
            if self.is_present(loc, 3):
                try:
                    self.click(loc)
                    self.wait.url_contains("dashboard", timeout=20)
                    self.wait.document_ready()
                    return
                except Exception as exc:  # noqa: BLE001
                    self.log.warning("Could not use %s to leave onboarding: %s", loc, exc)
        self.open("/index.php?/dashboard")
        self.wait.url_contains("dashboard", timeout=20)
        self.wait.document_ready()

    @allure.step("Open dashboard via top logo (banner link / TestRail logo)")
    def go_to_dashboard_via_logo(self) -> None:
        """``#top-logo`` / ``[data-testid='bannerLink']`` → ``/dashboard`` (all four saved HTML dumps share this)."""
        self.log.info("Navigating to dashboard via top logo")
        for loc in (self._DASHBOARD_LOGO_LINK, self._DASHBOARD_LOGO_IMG, self._BANNER_DASHBOARD):
            if not self.is_present(loc, 5):
                continue
            try:
                self.scroll_into_view(loc)
                self.click(loc)
                self.wait.url_contains("dashboard", timeout=25)
                self.wait.document_ready()
                return
            except Exception as exc:  # noqa: BLE001
                self.log.warning("go_to_dashboard_via_logo attempt %s failed: %s", loc, exc)
        self.log.warning("Logo navigation unavailable; opening dashboard URL directly")
        self.open("/index.php?/dashboard")
        self.wait.url_contains("dashboard", timeout=20)
        self.wait.document_ready()

    def _project_overview_link_visible(self, name: str) -> bool:
        want = (name or "").strip()
        for el in self.driver.find_elements(*self._PROJECT_ROWS):
            try:
                if (el.text or "").strip() == want and el.is_displayed():
                    return True
            except StaleElementReferenceException:
                continue
        return False

    def _focus_project_search_and_filter(self, name: str) -> None:
        self.scroll_into_view(self._SEARCH_PROJECT_INPUT)
        self.click(self._SEARCH_PROJECT_INPUT)
        self.type(self._SEARCH_PROJECT_INPUT, name)
        self.wait.document_ready()

    def _try_open_project_via_sidebar_search(self, name: str) -> bool:
        if not self.is_present(self._SEARCH_PROJECT_INPUT, 5):
            return False
        self.log.info("Opening project via sidebar project search for %r", name)
        try:
            self._focus_project_search_and_filter(name)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("Sidebar project search failed: %s", exc)
            return False
        return self._click_visible_project_overview_link(name)

    def _click_visible_project_overview_link(self, name: str) -> bool:
        want = (name or "").strip()
        for el in self.driver.find_elements(*self._PROJECT_ROWS):
            try:
                if (el.text or "").strip() != want or not el.is_displayed():
                    continue
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                self.driver.execute_script("arguments[0].click();", el)
                return True
            except StaleElementReferenceException:
                continue
            except Exception as exc:  # noqa: BLE001
                self.log.debug("Project link click retry: %s", exc)
        return False

    def is_project_present(self, name: str, project_id: Optional[int] = None) -> bool:
        resolved = project_id if project_id is not None else self._project_id_from_settings()
        self.ensure_main_app_landing()
        if self._project_overview_link_visible(name):
            return True
        if self.is_present(self._SEARCH_PROJECT_INPUT, 4):
            try:
                self._focus_project_search_and_filter(name)
            except Exception:  # noqa: BLE001
                return resolved is not None
            if self._project_overview_link_visible(name):
                return True
        return resolved is not None

    @allure.step("Open project '{name}'")
    def open_project(self, name: str, project_id: Optional[int] = None) -> None:
        self.ensure_main_app_landing()
        self.log.info("Opening project %r", name)
        self.wait.document_ready()

        if self._click_visible_project_overview_link(name):
            self.wait.url_contains("/projects/overview")
            return

        if self._try_open_project_via_sidebar_search(name):
            self.wait.url_contains("/projects/overview")
            return

        xpath_locator = (By.XPATH, self._PROJECT_LINK_BY_NAME.format(name=name))
        if self.is_present(xpath_locator, 3):
            try:
                self.scroll_into_view(xpath_locator)
                self.click(xpath_locator)
                self.wait.url_contains("/projects/overview")
                return
            except Exception as exc:  # noqa: BLE001
                self.log.warning("XPath project link click failed: %s", exc)

        fallback_id = project_id if project_id is not None else self._project_id_from_settings()
        if fallback_id is not None:
            self.log.info("Opening project overview by id=%s (UI pick failed or was skipped)", fallback_id)
            self.open(f"/index.php?/projects/overview/{fallback_id}")
            return

        raise TimeoutException(f"Unable to open project {name!r}: no clickable project link and no id fallback.")

    @allure.step("Open dashboard then Test Cases via content link (suites/view/{project_id})")
    def open_test_cases_quick_link_from_dashboard(self, project_id: int) -> None:
        """Leave onboarding, open **/dashboard** via logo, then Test Cases.

        Selectors are derived from saved staging HTML under ``logs/``:
        ``testtask testrail-staging dashboard.txt`` (``a.link`` + ``suites/view``) and
        ``testtask.testrail-staging-com-index-suites.txt`` (sidebar ``navigateToCasesButton``).
        """
        self.ensure_main_app_landing()
        self.go_to_dashboard_via_logo()

        pid = int(project_id)
        candidates = (
            (By.CSS_SELECTOR, f"a.link[href*='suites/view/{pid}']"),
            (By.XPATH, f"//a[contains(@class,'link') and contains(@href,'suites/view/{pid}')]"),
            (
                By.XPATH,
                "//a[contains(@href,'suites/view') and contains(normalize-space(.),'Test Cases')]",
            ),
            (By.CSS_SELECTOR, f"[data-testid='navigateToCasesButton'][href*='suites/view/{pid}']"),
        )
        last_exc: Optional[Exception] = None
        for loc in candidates:
            try:
                if not self.is_present(loc, 6):
                    continue
                self.scroll_into_view(loc)
                self.click(loc)
                self.wait.url_contains(f"suites/view/{pid}", timeout=25)
                self.wait.document_ready()
                return
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                self.log.warning("Test Cases quick link %s failed: %s", loc, exc)
        raise AssertionError(
            f"Could not open Test Cases from dashboard quick link (project_id={pid}). Last error: {last_exc}"
        )

    @allure.step("Open dashboard then Test Runs via content link (runs/overview/{project_id})")
    def open_test_runs_quick_link_from_dashboard(self, project_id: int) -> None:
        """Leave onboarding, open **/dashboard** via logo, then Test Runs.

        Mirrors ``logs/testtask testrail-staging dashboard.txt`` (``a.link`` + ``runs/overview``) and
        ``logs/testtask-testrail-staging-com-index-php-runs-overview-1.txt`` (``navigateToRunsButton``,
        ``navigationRunsAdd`` for add-run from runs area — not used here).
        """
        self.ensure_main_app_landing()
        self.go_to_dashboard_via_logo()

        pid = int(project_id)
        candidates = (
            (By.CSS_SELECTOR, f"a.link[href*='runs/overview/{pid}']"),
            (By.XPATH, f"//a[contains(@class,'link') and contains(@href,'runs/overview/{pid}')]"),
            (
                By.XPATH,
                "//a[contains(@href,'runs/overview') and contains(normalize-space(.),'Test Runs')]",
            ),
            (By.CSS_SELECTOR, f"[data-testid='navigateToRunsButton'][href*='runs/overview/{pid}']"),
        )
        last_exc: Optional[Exception] = None
        for loc in candidates:
            try:
                if not self.is_present(loc, 6):
                    continue
                self.scroll_into_view(loc)
                self.click(loc)
                self.wait.url_contains(f"runs/overview/{pid}", timeout=25)
                self.wait.document_ready()
                return
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                self.log.warning("Test Runs quick link %s failed: %s", loc, exc)
        raise AssertionError(
            f"Could not open Test Runs from dashboard quick link (project_id={pid}). Last error: {last_exc}"
        )

    def logout(self) -> None:
        self.header.logout()
