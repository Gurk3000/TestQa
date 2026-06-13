"""Explicit-wait helpers built exclusively on WebDriverWait.

Centralizes all synchronization logic so Page Objects never call time.sleep()
and never duplicate wait code. Includes "wait-for-state" helpers (not only
element presence) to combat flaky async UI behavior.
"""
from __future__ import annotations

from typing import Callable, Optional, Tuple

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config.config import settings

Locator = Tuple[str, str]


class Waiter:
    """Thin wrapper around WebDriverWait with project defaults."""

    def __init__(self, driver: WebDriver, timeout: Optional[int] = None, poll: float = 0.5):
        self._driver = driver
        self._timeout = timeout if timeout is not None else settings.explicit_wait
        self._poll = poll

    def _wait(self, timeout: Optional[int] = None) -> WebDriverWait:
        return WebDriverWait(
            self._driver,
            timeout if timeout is not None else self._timeout,
            poll_frequency=self._poll,
            ignored_exceptions=(StaleElementReferenceException,),
        )

    def presence(self, locator: Locator, timeout: Optional[int] = None) -> WebElement:
        return self._wait(timeout).until(EC.presence_of_element_located(locator))

    def visible(self, locator: Locator, timeout: Optional[int] = None) -> WebElement:
        return self._wait(timeout).until(EC.visibility_of_element_located(locator))

    def clickable(self, locator: Locator, timeout: Optional[int] = None) -> WebElement:
        return self._wait(timeout).until(EC.element_to_be_clickable(locator))

    def all_visible(self, locator: Locator, timeout: Optional[int] = None):
        return self._wait(timeout).until(EC.visibility_of_all_elements_located(locator))

    def invisible(self, locator: Locator, timeout: Optional[int] = None) -> bool:
        return self._wait(timeout).until(EC.invisibility_of_element_located(locator))

    def text_present(self, locator: Locator, text: str, timeout: Optional[int] = None) -> bool:
        return self._wait(timeout).until(EC.text_to_be_present_in_element(locator, text))

    def url_contains(self, fragment: str, timeout: Optional[int] = None) -> bool:
        return self._wait(timeout).until(EC.url_contains(fragment))

    def title_contains(self, fragment: str, timeout: Optional[int] = None) -> bool:
        return self._wait(timeout).until(EC.title_contains(fragment))

    def is_present(self, locator: Locator, timeout: int = 3) -> bool:
        """Non-throwing presence probe (for optional / negative checks)."""
        try:
            self.presence(locator, timeout=timeout)
            return True
        except TimeoutException:
            return False

    def is_visible(self, locator: Locator, timeout: int = 3) -> bool:
        try:
            self.visible(locator, timeout=timeout)
            return True
        except TimeoutException:
            return False

    def until(self, condition: Callable, timeout: Optional[int] = None):
        """Wait for an arbitrary custom condition (wait-for-state)."""
        return self._wait(timeout).until(condition)

    def for_state(self, predicate: Callable[[WebDriver], bool], timeout: Optional[int] = None) -> bool:
        """Wait until a boolean predicate over the driver becomes true."""
        return self._wait(timeout).until(lambda d: bool(predicate(d)))

    def document_ready(self, timeout: Optional[int] = None) -> bool:
        """Wait until document.readyState == 'complete'."""
        return self._wait(timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
