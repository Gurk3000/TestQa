"""Generic modal / dialog component.

Encapsulates the common TestRail dialog (#dialog) behavior: waiting for it to
appear, confirming, cancelling and reading its messages.
"""
from __future__ import annotations

from selenium.webdriver.common.by import By

from components.base_component import BaseComponent


class ModalComponent(BaseComponent):
    """Reusable confirmation / form dialog."""

    root_locator = (By.CSS_SELECTOR, "#dialog, .dialog, .modal")

    _CONFIRM_BTN = (By.CSS_SELECTOR, "#dialog .button-positive, #dialog input[type='submit'], .dialog .button-positive")
    _CANCEL_BTN = (By.CSS_SELECTOR, "#dialog .button-link.cancel, .dialog .cancel, #dialog a.button-link")
    _MESSAGE = (By.CSS_SELECTOR, "#dialog .message, .dialog .message")

    def wait_until_open(self) -> "ModalComponent":
        self.log.info("Waiting for modal to open")
        self.wait.visible(self.root_locator)
        return self

    def wait_until_closed(self) -> None:
        self.log.info("Waiting for modal to close")
        self.wait.invisible(self.root_locator)

    def confirm(self) -> None:
        self.log.info("Confirm modal")
        self.click(self._CONFIRM_BTN)

    def cancel(self) -> None:
        self.log.info("Cancel modal")
        self.click(self._CANCEL_BTN)

    def message(self) -> str:
        if self.is_visible(self._MESSAGE, 3):
            return self.get_text(self._MESSAGE)
        return ""

    def is_open(self) -> bool:
        return self.is_visible(self.root_locator, 3)
