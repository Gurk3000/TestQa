"""Login page object for TestRail authentication.

Includes verbose stage logging and robust field filling so failures show
*whether* credentials actually reached the DOM (common issue: wrong frame,
overlays, React-controlled inputs, or swallowed clicks).
"""
from __future__ import annotations

import time
from typing import List, Optional, Tuple

import allure
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement

from config.config import settings
from pages.base_page import BasePage

Locator = Tuple[str, str]

# Phrases often present in TestRail / SPA login failure copy (English UI).
_LOGIN_FAILURE_TERMS: Tuple[str, ...] = (
    "invalid",
    "incorrect",
    "wrong password",
    "wrong user",
    "could not log",
    "cannot log",
    "login failed",
    "try again",
    "check your",
    "does not match",
    "doesn't match",
    "do not match",
    "not match",
    "unknown user",
    "unrecognized",
    "authentication failed",
    "unable to sign",
    "unable to log",
    "sign in failed",
    "failed to sign",
    "bad credentials",
    "combination",
    "problem signing",
    "attention",
    "oops",
    "sorry",
)


class LoginPage(BasePage):
    """TestRail /auth/login page."""

    url_fragment = "/auth/login"

    def __init__(self, driver):
        super().__init__(driver)
        # Avoid re-probing all iframes on every poll tick while waiting for post-login navigation.
        self._login_iframe_probe_ttl_s = 3.0
        self._login_iframe_last_probe_at = 0.0
        self._login_iframe_cached_idx: Optional[int] = None

    _EMAIL = (By.ID, "name")
    _PASSWORD = (By.ID, "password")
    _SUBMIT = (By.CSS_SELECTOR, "#button_primary, button[name='enter'], input[name='enter']")
    # TestRail Cloud / staging may use different markup — keep a wide net + XPath fallbacks.
    _ERROR_PRIMARY = (
        By.CSS_SELECTOR,
        ".message.message-error, .message-error, .loginpage-message, #message, .message-attention, "
        ".notification, .notification-error, .flash-error, .flash-message, .banner-error, "
        ".text-danger, .validation-error, .field-error, .loginpage-error, .auth-error, #loginError, "
        "#errorMessage, .error-message, p.error, span.error, div.alert, div.alert-danger, "
        "[data-testid*='error'], [class*='error']",
    )
    _ERROR_ROLE_ALERT = (By.XPATH, "//*[@role='alert' and normalize-space()]")
    _ERROR_TOAST = (
        By.XPATH,
        "//*[contains(@class,'toast') or contains(@class,'snackbar') or contains(@class,'Snackbar')]"
        "[normalize-space()]",
    )
    _BODY = (By.TAG_NAME, "body")
    _FORM = (By.CSS_SELECTOR, "form[action*='auth/login'], form#login, form")

    _EMAIL_CANDIDATES: List[Locator] = [
        (By.ID, "name"),
        (By.CSS_SELECTOR, "input#name"),
        (By.CSS_SELECTOR, "input[name='name']"),
        (By.CSS_SELECTOR, "input[type='email']"),
        (By.CSS_SELECTOR, "input[name='user']"),
    ]
    _PASSWORD_CANDIDATES: List[Locator] = [
        (By.ID, "password"),
        (By.CSS_SELECTOR, "input#password"),
        (By.CSS_SELECTOR, "input[name='password']"),
        (By.CSS_SELECTOR, "input[type='password']"),
    ]

    @allure.step("Open login page")
    def open_login(self) -> "LoginPage":
        self.log.info("[login:stage=OPEN] navigating to login URL")
        self._login_iframe_last_probe_at = 0.0
        self._login_iframe_cached_idx = None
        self.open(settings.login_url)
        self._log_page_basics("OPEN_AFTER_NAV")
        # List iframes from top-level *before* switching into a login iframe.
        self._log_iframes("OPEN")
        self._ensure_login_context()
        # Resolve which email locator works in the active context.
        email_el, email_loc = self._resolve_field("email", self._EMAIL_CANDIDATES)
        self.log.info("[login:stage=OPEN] email field resolved via %s (displayed=%s)", email_loc, email_el.is_displayed())
        self.wait.visible(email_loc)
        return self

    @allure.step("Login with email='{email}'")
    def login(self, email: str, password: str) -> None:
        self._ensure_login_context()
        self._log_page_basics("BEFORE_FILL")

        self.log.info("[login:stage=FILL_EMAIL] target_len=%s", len(email or ""))
        email_el, email_loc = self._resolve_field("email", self._EMAIL_CANDIDATES)
        self._fill_text_input(email_el, email_loc, email, secret=False, stage="FILL_EMAIL")

        self.log.info("[login:stage=FILL_PASSWORD] target_len=%s", len(password or ""))
        pwd_el, pwd_loc = self._resolve_field("password", self._PASSWORD_CANDIDATES)
        self._fill_text_input(pwd_el, pwd_loc, password, secret=True, stage="FILL_PASSWORD")

        self.log.info("[login:stage=SUBMIT] clicking primary submit control")
        self.click(self._SUBMIT)
        self._log_page_basics("AFTER_SUBMIT_CLICK")

    def login_expecting_success(self, email: str, password: str) -> None:
        self.login(email, password)
        primary_wait = min(settings.explicit_wait, max(8, settings.login_post_submit_wait_seconds))
        self.log.info(
            "[login:stage=WAIT_RESULT] waiting up to %ss for redirect or error (poll every ~0.15s)",
            primary_wait,
        )

        if not self._wait_for_login_result(timeout=primary_wait, poll_log_s=2.0):
            self.log.warning("[login:stage=FALLBACK_ENTER] submit did not change state; sending ENTER on password")
            self._ensure_login_context()
            _, pwd_loc = self._resolve_field("password", self._PASSWORD_CANDIDATES)
            self.wait.visible(pwd_loc).send_keys(Keys.ENTER)
            self._log_page_basics("AFTER_ENTER_FALLBACK")
            fb = max(5, settings.login_fallback_wait_seconds)
            if not self._wait_for_login_result(timeout=fb, poll_log_s=2.0):
                self.log.warning("[login:stage=FALLBACK_JS_SUBMIT] trying native form submit")
                self._native_form_submit()
                self._log_page_basics("AFTER_JS_SUBMIT")
                self._wait_for_login_result(timeout=fb, poll_log_s=2.0)

        if self.is_on_login_page():
            diagnostics = self.login_diagnostics()
            self.log.error("[login:stage=FAILED] %s", diagnostics)
            try:
                self.driver.switch_to.default_content()
            except Exception:  # noqa: BLE001
                pass
            raise AssertionError(f"Login failed / stayed on login page. Diagnostics: {diagnostics}")

        self.log.info("[login:stage=SUCCESS] user appears logged in (left login URL)")
        self._log_page_basics("SUCCESS")
        # Return driver to top-level document for dashboard / project pages.
        try:
            self.driver.switch_to.default_content()
            self.log.info("[login:stage=SUCCESS] switched to defaultContent for post-login navigation")
        except Exception as exc:  # noqa: BLE001
            self.log.warning("[login:stage=SUCCESS] could not switch to defaultContent: %s", exc)

    # --- Internals -----------------------------------------------------------

    def _log_page_basics(self, stage: str) -> None:
        try:
            self.log.info(
                "[login:%s] url=%s title=%s readyState=%s",
                stage,
                self.current_url(),
                self.driver.title,
                self.driver.execute_script("return document.readyState"),
            )
        except Exception as exc:  # noqa: BLE001
            self.log.warning("[login:%s] could not read page basics: %s", stage, exc)

    def _log_iframes(self, stage: str) -> None:
        try:
            self.driver.switch_to.default_content()
            frames = self.driver.find_elements(By.TAG_NAME, "iframe")
            self.log.info("[login:%s] iframe_count=%s", stage, len(frames))
            for idx, fr in enumerate(frames[:5]):
                fid = fr.get_attribute("id") or ""
                fsrc = (fr.get_attribute("src") or "")[:120]
                self.log.info("[login:%s] iframe[%s] id=%r src=%r", stage, idx, fid, fsrc)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("[login:%s] iframe introspection failed: %s", stage, exc)

    def _ensure_login_context(self) -> None:
        """Use default document unless the login fields only exist inside an iframe."""
        self.driver.switch_to.default_content()
        if self._any_locator_visible(self._EMAIL_CANDIDATES, timeout=1):
            self.log.info("[login:context] using defaultContent (email field visible)")
            self._login_iframe_cached_idx = None
            return

        now = time.monotonic()
        frames = self.driver.find_elements(By.TAG_NAME, "iframe")

        # Cheap path: reuse last iframe index (one switch + visibility) on every poll tick.
        if self._login_iframe_cached_idx is not None:
            idx = self._login_iframe_cached_idx
            if 0 <= idx < len(frames):
                try:
                    self.driver.switch_to.default_content()
                    self.driver.switch_to.frame(frames[idx])
                    if self._any_locator_visible(self._EMAIL_CANDIDATES, timeout=1):
                        return
                except Exception as exc:  # noqa: BLE001
                    self.log.debug("[login:context] cached iframe index=%s failed: %s", idx, exc)
            self._login_iframe_cached_idx = None
            # Stale cache: allow a full rescan even if the TTL window has not elapsed.
            self._login_iframe_last_probe_at = 0.0

        if now - self._login_iframe_last_probe_at < self._login_iframe_probe_ttl_s:
            self.driver.switch_to.default_content()
            return

        self._login_iframe_last_probe_at = now
        for idx, fr in enumerate(frames):
            try:
                self.driver.switch_to.default_content()
                self.driver.switch_to.frame(fr)
                if self._any_locator_visible(self._EMAIL_CANDIDATES, timeout=1):
                    self._login_iframe_cached_idx = idx
                    self.log.info("[login:context] switched to iframe index=%s (email field visible)", idx)
                    return
            except Exception as exc:  # noqa: BLE001
                self.log.warning("[login:context] iframe index=%s probe failed: %s", idx, exc)

        self.driver.switch_to.default_content()
        self._login_iframe_cached_idx = None
        # Benign during post-submit polling: once login succeeds the page leaves the
        # form and the email field is gone. Keep it as a DEBUG trace, not a warning.
        self.log.debug("[login:context] email field not found in default or iframes; staying on defaultContent")

    def _any_locator_visible(self, locators: List[Locator], timeout: int = 2) -> bool:
        for loc in locators:
            if self.is_visible(loc, timeout=timeout):
                return True
        return False

    def _resolve_field(self, role: str, candidates: List[Locator]) -> Tuple[WebElement, Locator]:
        last_exc: Optional[Exception] = None
        for loc in candidates:
            try:
                if self.is_present(loc, timeout=3):
                    el = self.wait.visible(loc)
                    self.log.info("[login:resolve_%s] using locator %s", role, loc)
                    return el, loc
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                self.log.debug("[login:resolve_%s] locator %s failed: %s", role, loc, exc)
        raise AssertionError(f"Could not resolve {role} input. Last error: {last_exc}")

    def _fill_text_input(
        self,
        element: WebElement,
        locator: Locator,
        text: str,
        *,
        secret: bool,
        stage: str,
    ) -> None:
        """Fill an input and verify DOM value; apply JS fallback if needed."""
        self.scroll_into_view(locator)
        self.wait.clickable(locator)
        try:
            ac = "new-password" if secret else "username"
            self.driver.execute_script(
                "arguments[0].setAttribute('autocomplete', arguments[1]);"
                "arguments[0].setAttribute('data-lpignore','true');",
                element,
                ac,
            )
        except Exception:  # noqa: BLE001
            pass
        element.click()

        before = element.get_attribute("value") or ""
        self.log.info(
            "[login:%s] before_clear value_len=%s preview=%r",
            stage,
            len(before),
            self._mask_value(before, secret),
        )

        # Robust clear (React-friendly): focus + CTRL+A + BACKSPACE
        element.send_keys(Keys.CONTROL, "a")
        element.send_keys(Keys.BACKSPACE)
        element.send_keys(text)

        after_keys = element.get_attribute("value") or ""
        self.log.info(
            "[login:%s] after_send_keys value_len=%s matches_target=%s preview=%r",
            stage,
            len(after_keys),
            (after_keys == text),
            self._mask_value(after_keys, secret),
        )

        if after_keys != text:
            self.log.warning("[login:%s] send_keys did not set expected value; applying JS value + events", stage)
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
            after_js = element.get_attribute("value") or ""
            self.log.info(
                "[login:%s] after_js value_len=%s matches_target=%s preview=%r",
                stage,
                len(after_js),
                (after_js == text),
                self._mask_value(after_js, secret),
            )
            if after_js != text:
                raise AssertionError(
                    f"[login:{stage}] Could not populate input {locator}: "
                    f"expected_len={len(text)} actual_len={len(after_js)} "
                    f"actual_preview={self._mask_value(after_js, secret)!r}"
                )

    @staticmethod
    def _mask_value(value: str, secret: bool) -> str:
        if not value:
            return ""
        if secret:
            return f"<redacted len={len(value)}>"
        if len(value) <= 6:
            return value
        return f"{value[:3]}...{value[-3:]} (len={len(value)})"

    def _wait_for_login_result(self, timeout: int, poll_log_s: float = 2.0) -> bool:
        """Wait until URL leaves login, an error appears, or email field disappears."""
        deadline = time.monotonic() + float(timeout)
        last_log = 0.0
        while time.monotonic() < deadline:
            try:
                # One context resolve per tick; hot-path error checks must not re-scan all iframes.
                self._ensure_login_context()
                url = self.current_url()
                on_login_url = "/auth/login" in url
                err = (
                    self._error_visible_now()
                    or self.has_login_failure_keywords()
                    or self._credential_field_aria_invalid()
                )
                email_gone = not self._any_locator_visible(self._EMAIL_CANDIDATES, timeout=1)
                if not on_login_url or err or email_gone:
                    self.log.info(
                        "[login:wait_poll] done on_login_url=%s error_visible=%s email_gone=%s url=%s",
                        on_login_url,
                        err,
                        email_gone,
                        url,
                    )
                    return True
            except Exception as exc:  # noqa: BLE001
                self.log.debug("[login:wait_poll] transient read error: %s", exc)

            now = time.monotonic()
            if now - last_log >= poll_log_s:
                try:
                    self.log.info(
                        "[login:wait_poll] still waiting url=%s title=%s",
                        self.current_url(),
                        self.driver.title,
                    )
                except Exception:
                    pass
                last_log = now

            time.sleep(0.12)

        self.log.error("[login:wait_poll] timeout after %ss url=%s", timeout, self.current_url())
        return False

    def _native_form_submit(self) -> None:
        self._ensure_login_context()
        form = self.wait.presence(self._FORM)
        self.driver.execute_script("HTMLFormElement.prototype.submit.call(arguments[0]);", form)

    @staticmethod
    def _looks_like_auth_error_text(text: str) -> bool:
        tl = (text or "").strip().lower()
        if len(tl) < 4:
            return False
        needles = (
            "invalid",
            "incorrect",
            "wrong",
            "failed",
            "unable",
            "unknown",
            "not match",
            "doesn't",
            "does not",
            "try again",
            "check your",
            "check the",
            "problem",
            "attention",
            "oops",
            "credentials",
            "denied",
            "refused",
        )
        return any(n in tl for n in needles)

    def _error_visible_now(self) -> bool:
        """Fast DOM scan for visible auth error / alert / toast in the *current* document."""
        for loc in (self._ERROR_PRIMARY, self._ERROR_ROLE_ALERT, self._ERROR_TOAST):
            try:
                for el in self.driver.find_elements(*loc)[:28]:
                    try:
                        if not el.is_displayed():
                            continue
                        role = (el.get_attribute("role") or "").lower()
                        txt = (el.text or "").strip()
                        if role == "alert" and len(txt) >= 2:
                            return True
                        if self._looks_like_auth_error_text(txt):
                            return True
                    except Exception:  # noqa: BLE001
                        continue
            except Exception:  # noqa: BLE001
                continue
        return False

    def _body_inner_lower(self) -> str:
        """Lowercased body text in the *active* document (default or iframe)."""
        try:
            body = self.driver.find_element(By.TAG_NAME, "body")
            return (body.get_attribute("innerText") or body.text or "").lower()
        except Exception:  # noqa: BLE001
            return ""

    def has_login_failure_keywords(self) -> bool:
        try:
            if "/auth/login" not in (self.current_url() or "").lower():
                return False
        except Exception:  # noqa: BLE001
            return False
        blob = self._body_inner_lower()
        return any(term in blob for term in _LOGIN_FAILURE_TERMS)

    def _credential_field_aria_invalid(self) -> bool:
        for loc in list(self._EMAIL_CANDIDATES) + list(self._PASSWORD_CANDIDATES):
            try:
                for el in self.driver.find_elements(*loc)[:3]:
                    try:
                        if el.is_displayed() and (el.get_attribute("aria-invalid") or "").lower() == "true":
                            return True
                    except Exception:  # noqa: BLE001
                        continue
            except Exception:  # noqa: BLE001
                continue
        return False

    def wait_for_failed_login_feedback(self, timeout: int = 12) -> bool:
        """Poll until an error control appears or known failure wording is in the page."""
        deadline = time.monotonic() + float(timeout)
        while time.monotonic() < deadline:
            self._ensure_login_context()
            if self._error_visible_now():
                self.log.info("[login:neg] detected visible error / alert / toast")
                return True
            if self.has_login_failure_keywords():
                self.log.info("[login:neg] detected auth-failure keywords in body text")
                return True
            if self._credential_field_aria_invalid():
                self.log.info("[login:neg] credential field marked aria-invalid=true")
                return True
            time.sleep(0.2)
        self.log.warning("[login:neg] no failure feedback after %ss url=%s", timeout, self.current_url())
        return False

    @allure.step("Expect failed login feedback")
    def expect_failed_login(self, timeout: int = 12) -> None:
        if self.wait_for_failed_login_feedback(timeout):
            return
        diag = self.login_diagnostics()
        self.log.error("[login:neg] expect_failed_login context: %s", diag)
        raise AssertionError(f"Expected authentication error on login page. Diagnostics: {diag}")

    def has_error(self) -> bool:
        self._ensure_login_context()
        if self._error_visible_now():
            return True
        if self.has_login_failure_keywords():
            return True
        return self._credential_field_aria_invalid()

    def error_text(self) -> str:
        self._ensure_login_context()
        for loc in (self._ERROR_PRIMARY, self._ERROR_ROLE_ALERT, self._ERROR_TOAST):
            try:
                for el in self.driver.find_elements(*loc):
                    try:
                        if el.is_displayed():
                            t = (el.text or "").strip()
                            if t:
                                return t
                    except Exception:  # noqa: BLE001
                        continue
            except Exception:  # noqa: BLE001
                continue
        return ""

    def login_diagnostics(self) -> dict:
        self._ensure_login_context()
        body_text = ""
        if self.is_present(self._BODY, timeout=2):
            body_text = self.get_text(self._BODY)

        email_val = ""
        pwd_val = ""
        try:
            _, eloc = self._resolve_field("email", self._EMAIL_CANDIDATES)
            email_el = self.wait.presence(eloc)
            email_val = email_el.get_attribute("value") or ""
        except Exception as exc:  # noqa: BLE001
            email_val = f"<unreadable:{exc}>"

        try:
            _, ploc = self._resolve_field("password", self._PASSWORD_CANDIDATES)
            pwd_el = self.wait.presence(ploc)
            pwd_val = pwd_el.get_attribute("value") or ""
        except Exception as exc:  # noqa: BLE001
            pwd_val = f"<unreadable:{exc}>"

        return {
            "url": self.current_url(),
            "title": self.driver.title,
            "error_text": self.error_text(),
            "email_value_len": len(email_val) if isinstance(email_val, str) and not email_val.startswith("<") else email_val,
            "email_value_preview": self._mask_value(email_val, secret=False) if isinstance(email_val, str) else email_val,
            "password_value_len": len(pwd_val) if isinstance(pwd_val, str) and not pwd_val.startswith("<") else pwd_val,
            "submit_visible": self.is_visible(self._SUBMIT, timeout=2),
            "body_excerpt": body_text[:800],
        }

    def is_on_login_page(self) -> bool:
        if "/auth/login" in self.current_url():
            return True
        return self._any_locator_visible(self._EMAIL_CANDIDATES, timeout=2)
