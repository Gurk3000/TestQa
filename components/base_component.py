"""BaseComponent: foundation for reusable Page Components.

A component is scoped to a root WebElement (or the whole document when no root
is given) and exposes the same explicit-wait based interaction helpers as
BasePage, but relative to its own subtree. This implements the Page Component
Pattern and keeps shared UI widgets (sidebar, header, modal) reusable across
pages without duplicating locators.
"""
from __future__ import annotations

from typing import Optional, Tuple

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from utils.logger import get_logger
from utils.waits import Waiter

Locator = Tuple[str, str]


class BaseComponent:
    """Foundation for reusable, scoped UI components."""

    # Locator of the component root; concrete components should override.
    root_locator: Optional[Locator] = None

    def __init__(self, driver: WebDriver, root: Optional[WebElement] = None):
        self.driver = driver
        self.wait = Waiter(driver)
        self.log = get_logger(self.__class__.__name__)
        self._root = root

    @property
    def root(self) -> Optional[WebElement]:
        if self._root is not None:
            return self._root
        if self.root_locator is not None:
            self._root = self.wait.presence(self.root_locator)
        return self._root

    # --- Scoped interactions ------------------------------------------------

    def click(self, locator: Locator) -> None:
        self.log.debug("Component click %s", locator)
        self.wait.clickable(locator).click()

    def type(self, locator: Locator, text: str, clear: bool = True) -> None:
        element = self.wait.visible(locator)
        if clear:
            element.clear()
        element.send_keys(text)

    def get_text(self, locator: Locator) -> str:
        return self.wait.visible(locator).text.strip()

    def is_visible(self, locator: Locator, timeout: int = 5) -> bool:
        return self.wait.is_visible(locator, timeout=timeout)

    def is_present(self, locator: Locator, timeout: int = 5) -> bool:
        return self.wait.is_present(locator, timeout=timeout)

    def is_displayed(self) -> bool:
        if self.root_locator is not None:
            return self.is_visible(self.root_locator)
        return self._root is not None and self._root.is_displayed()
