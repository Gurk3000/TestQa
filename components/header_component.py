"""Header / top navigation bar component."""
from __future__ import annotations

from selenium.webdriver.common.by import By

from components.base_component import BaseComponent


class HeaderComponent(BaseComponent):
    """Top navigation bar: user menu, logout, global links."""

    # TestRail modern layout uses #top as chrome root (there is no #navigation wrapper).
    root_locator = (By.ID, "top")

    _USER_MENU = (By.ID, "navigation-user")
    _USER_MENU_BY_TESTID = (By.CSS_SELECTOR, '[data-testid="userDropdown"]')
    _USER_MENU_FALLBACK = (By.CSS_SELECTOR, "a#navigation-user, .navigation-user, .user-menu")
    _LOGOUT_LINK = (By.CSS_SELECTOR, '[data-testid="logoutButton"], #navigation-user-logout, a[href*="/auth/logout"]')
    _USERNAME_LABEL = (By.CSS_SELECTOR, ".navigation-username")
    _DASHBOARD_LINK = (By.CSS_SELECTOR, "a[href*='/dashboard']")

    def is_logged_in(self) -> bool:
        """A logged-in session exposes the user menu and/or a logout control (see staging DOM)."""
        return (
            self.is_present(self._USER_MENU, 5)
            or self.is_present(self._USER_MENU_BY_TESTID, 3)
            or self.is_present(self._LOGOUT_LINK, 3)
            or self.is_present(self._USER_MENU_FALLBACK, 3)
        )

    def username(self) -> str:
        if self.is_present(self._USERNAME_LABEL, 2):
            try:
                return self.get_text(self._USERNAME_LABEL)
            except Exception:  # noqa: BLE001
                pass
        for locator in (self._USER_MENU, self._USER_MENU_BY_TESTID, self._USER_MENU_FALLBACK):
            if self.is_present(locator, 3):
                try:
                    return self.get_text(locator)
                except Exception:  # noqa: BLE001
                    continue
        return ""

    def open_user_menu(self) -> None:
        self.log.info("Open user menu")
        locator = self._USER_MENU if self.is_present(self._USER_MENU, 3) else self._USER_MENU_FALLBACK
        self.click(locator)

    def logout(self) -> None:
        self.log.info("Logout via header")
        # Logout link can be a direct href even if hidden in a dropdown.
        if self.is_present(self._USER_MENU, 2) or self.is_present(self._USER_MENU_FALLBACK, 2):
            try:
                self.open_user_menu()
            except Exception:  # noqa: BLE001 - dropdown may be optional
                pass
        logout = self.wait.presence(self._LOGOUT_LINK)
        self.driver.get(logout.get_attribute("href"))

    def go_to_dashboard(self) -> None:
        self.log.info("Navigate to dashboard via header")
        self.click(self._DASHBOARD_LINK)
