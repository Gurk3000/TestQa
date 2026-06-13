"""Screenshot capture and Allure attachment helpers."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import allure
from selenium.webdriver.remote.webdriver import WebDriver

from config.config import settings
from utils.logger import get_logger

logger = get_logger("screenshot")


def _safe(name: str) -> str:
    keep = "-_."
    return "".join(c if c.isalnum() or c in keep else "_" for c in name)[:120]


def capture(driver: WebDriver, name: str) -> Optional[Path]:
    """Save a PNG screenshot to /screenshots and return its path."""
    settings.screenshots_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_safe(name)}_{datetime.now():%Y%m%d_%H%M%S}.png"
    path = settings.screenshots_dir / filename
    try:
        driver.save_screenshot(str(path))
        logger.info("Screenshot saved: %s", path)
        return path
    except Exception as exc:  # noqa: BLE001 - screenshots must never break a run
        logger.error("Failed to capture screenshot '%s': %s", name, exc)
        return None


def capture_b64(driver: WebDriver) -> Optional[str]:
    """Return a live screenshot as a base64 PNG string (for pytest-html embedding)."""
    try:
        return driver.get_screenshot_as_base64()
    except Exception as exc:  # noqa: BLE001 - screenshots must never break a run
        logger.error("Failed to capture base64 screenshot: %s", exc)
        return None


def attach_to_allure(driver: WebDriver, name: str = "screenshot") -> None:
    """Attach a live screenshot directly to the Allure report."""
    try:
        allure.attach(
            driver.get_screenshot_as_png(),
            name=name,
            attachment_type=allure.attachment_type.PNG,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to attach screenshot to Allure: %s", exc)


def attach_page_source(driver: WebDriver, name: str = "page_source") -> None:
    try:
        allure.attach(
            driver.page_source,
            name=name,
            attachment_type=allure.attachment_type.HTML,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to attach page source to Allure: %s", exc)
