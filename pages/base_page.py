"""BasePage: shared behavior for every Page Object.

Encapsulates the driver, the Waiter (explicit waits only), logging and the
most common interactions so concrete pages stay declarative and DRY.
"""
from __future__ import annotations

from typing import Optional, Tuple

import allure
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from config.config import settings
from utils.logger import get_logger
from utils.waits import Waiter

Locator = Tuple[str, str]


class BasePage:
    """Common foundation for all pages."""

    # Optional URL fragment used by `is_loaded` of concrete pages.
    url_fragment: str = ""

    def __init__(self, driver: WebDriver):
        self.driver = driver
        self.wait = Waiter(driver)
        self.log = get_logger(self.__class__.__name__)

    # --- Navigation ----------------------------------------------------------

    def open(self, path: str = "") -> "BasePage":
        url = path if path.startswith("http") else f"{settings.base_url}{path}"
        self.log.info("Open URL: %s", url)
        self.driver.get(url)
        self.wait.document_ready()
        return self

    def current_url(self) -> str:
        return self.driver.current_url

    def refresh(self) -> None:
        self.log.info("Refreshing page")
        self.driver.refresh()
        self.wait.document_ready()

    # --- Interactions --------------------------------------------------------

    def find(self, locator: Locator) -> WebElement:
        return self.wait.visible(locator)

    def find_clickable(self, locator: Locator) -> WebElement:
        return self.wait.clickable(locator)

    @allure.step("Click {locator}")
    def click(self, locator: Locator) -> None:
        self.log.debug("Click %s", locator)
        element = self.wait.clickable(locator)
        try:
            element.click()
        except (ElementClickInterceptedException, StaleElementReferenceException):
            # Fallback for overlays / re-rendered nodes.
            self.driver.execute_script("arguments[0].click();", self.wait.clickable(locator))

    @allure.step("Type into {locator}")
    def type(self, locator: Locator, text: str, clear: bool = True) -> None:
        self.log.debug("Type %r into %s", text, locator)
        element = self.wait.visible(locator)
        if clear:
            element.clear()
        try:
            element.send_keys(text)
        except WebDriverException as exc:
            # ChromeDriver rejects some Unicode (e.g. emoji) via the W3C input endpoint.
            if "only supports characters" not in str(exc) and "BMP" not in str(exc):
                raise
            self.log.warning("send_keys rejected text; applying JS value + events (%s)", exc)
            self.driver.execute_script(
                """
                const el = arguments[0];
                const val = arguments[1];
                el.focus();
                el.value = val;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                """,
                element,
                text,
            )

    def get_text(self, locator: Locator) -> str:
        return self.wait.visible(locator).text.strip()

    def get_attribute(self, locator: Locator, attribute: str) -> Optional[str]:
        return self.wait.presence(locator).get_attribute(attribute)

    def is_visible(self, locator: Locator, timeout: int = 5) -> bool:
        return self.wait.is_visible(locator, timeout=timeout)

    def is_present(self, locator: Locator, timeout: int = 5) -> bool:
        return self.wait.is_present(locator, timeout=timeout)

    def scroll_into_view(self, locator: Locator) -> None:
        element = self.wait.presence(locator)
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)

    def js_click(self, locator: Locator) -> None:
        self.driver.execute_script("arguments[0].click();", self.wait.presence(locator))

    # --- State -------------------------------------------------------------

    def is_loaded(self) -> bool:
        if not self.url_fragment:
            return True
        return self.wait.is_present(("xpath", "//body")) and self.url_fragment in self.current_url()

    def wait_until_loaded(self) -> "BasePage":
        if self.url_fragment:
            self.wait.url_contains(self.url_fragment)
        self.wait.document_ready()
        return self
