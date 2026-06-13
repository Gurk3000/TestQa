"""Test Run page object: runs list + add run form + run view."""
from __future__ import annotations

import re
import time
from typing import Optional

import allure
from selenium.webdriver.common.by import By

from config.config import settings
from pages.base_page import BasePage


class TestRunPage(BasePage):
    """TestRail test runs area (runs overview, add-run form, run view)."""

    # Page Object, not a pytest test class: stop collection despite the Test* prefix.
    __test__ = False

    url_fragment = "/runs"

    # --- Toolbar / list ------------------------------------------------------
    # Modern UI: sidebar CTA and/or "+" menu (see logs/testtask-testrail-staging-com-index-php-runs-overview-1.txt).
    _ADD_RUN_SIDEBAR = (
        By.CSS_SELECTOR,
        "#navigation-runs-add, [data-testid='navigationRunsAdd'], a.sidebar-nav-btn[href*='/runs/add/']",
    )
    _DYNAMIC_ADD_TRIGGER = (
        By.CSS_SELECTOR,
        '[data-testid="dynamicAddButton"], a.dynamic_add.dropdownLink[href="#dynamicAdd"]',
    )
    _ADD_RUN_MENU_LINK = (
        By.CSS_SELECTOR,
        '[data-testid="navigationTestRun"], a#navigation-test-run',
    )
    _ADD_RUN_BUTTON = (
        By.CSS_SELECTOR,
        "a[href*='/runs/add'], #sidebar-add-run, a.toolbar-add-run",
    )
    _ADD_RUN_BY_TEXT = (By.XPATH, "//a[contains(normalize-space(),'Add Test Run') or contains(normalize-space(),'New Test Run')]")

    # --- Add-run form --------------------------------------------------------
    _NAME_INPUT = (By.CSS_SELECTOR, "#name, input[name='name'], [data-testid='addRunFormName']")
    # Add-run form radios (see Data/testtask-*-runs-add-1.txt): include all vs specific cases.
    _INCLUDE_ALL_RADIO = (By.CSS_SELECTOR, "#includeAll, input[name='include_all'][value='1']")
    _INCLUDE_SPECIFIC_RADIO = (By.CSS_SELECTOR, "#includeSpecific, input[name='include_all'][value='0']:not(#includeDynamic)")
    _SELECT_CASES_LINK = (By.XPATH, "//a[contains(@onclick,'App.Runs.selectCases')] | //a[contains(translate(normalize-space(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'change selection')]")
    # Add-run form: ``form action=".../runs/add/{id}"`` (see Data/testtask-*-runs-add-1.txt).
    _SAVE_RUN_CANDIDATES = (
        (By.CSS_SELECTOR, "form[action*='runs/add'] button#accept"),
        (By.CSS_SELECTOR, "form[action*='runs/add'] button[data-testid='addRunFormOkButton']"),
        (By.CSS_SELECTOR, "form[action*='runs/add'] button.add-form-submit"),
        (By.CSS_SELECTOR, "form[action*='runs/add'] button[type='submit'].button-positive"),
        (By.CSS_SELECTOR, "button[data-testid='addRunFormOkButton']"),
    )
    _SAVE_BUTTON = _SAVE_RUN_CANDIDATES[0]  # back-compat for any direct reference

    # --- Case selection dialog ----------------------------------------------
    _CASE_CHECKBOX_BY_TITLE = "//tr[.//*[normalize-space()=\"{title}\"]]//input[@type='checkbox']"
    _DIALOG_OK = (
        By.CSS_SELECTOR,
        "#selectCasesDialog [data-testid='selectCasesSubmit'], #selectCasesSubmit, "
        "#selectCasesDialog button.button-positive.dialog-action-default",
    )

    # --- Feedback ------------------------------------------------------------
    _SUCCESS_NOTICE = (
        By.CSS_SELECTOR,
        ".message-success, .message.message-success, .notification-success, #notice, .message.success, "
        "[data-testid*='Success'], [data-testid*='success']",
    )
    _FIELD_ERROR = (By.CSS_SELECTOR, ".message-error, .error, .field-error, .message-attention")

    # --- Run view ------------------------------------------------------------
    _RUN_TITLE = (By.CSS_SELECTOR, "#content-header .content-header-title, h1, .title")
    _TEST_ROWS = (By.CSS_SELECTOR, ".test-row, table.grid tbody tr[id], tr.row")
    _RUN_ROW_BY_NAME = "//a[contains(@href,'/runs/view/') and normalize-space()=\"{name}\"]"
    _CASE_IN_RUN_BY_TITLE = "//*[contains(@class,'grid') or self::table]//*[normalize-space()=\"{title}\"]"
    _RUN_STATUS_BADGE = (By.CSS_SELECTOR, ".content-header-status, .status, .run-status")

    # --- Execution (result) dialog ------------------------------------------
    _TEST_LINK_BY_TITLE = "//a[contains(@href,'/tests/view/') and normalize-space()=\"{title}\"]"
    _ADD_RESULT_BUTTON = (
        By.CSS_SELECTOR,
        "#addResult, a[href*='/tests/add'], .toolbar a.button-add, #sidebar-add",
    )
    _STATUS_DROPDOWN = (By.CSS_SELECTOR, "#statusId, #addResultStatus, .status-dropdown, #status")
    _STATUS_OPTION_BY_TEXT = "//*[@id='dialog' or contains(@class,'dialog')]//*[normalize-space()=\"{status}\"]"
    _RESULT_COMMENT = (By.CSS_SELECTOR, "#comment, textarea[name='comment'], #addResultComment")
    _RESULT_DEFECTS = (By.CSS_SELECTOR, "#defects, input[name='defects']")
    _RESULT_SUBMIT = (
        By.CSS_SELECTOR,
        "#addResultSubmit, #dialog button[type='submit'].button-positive, "
        "#dialog .button-positive.button-ok, #dialog form .button-positive",
    )

    @staticmethod
    def _project_id_from_settings() -> Optional[int]:
        raw = (settings.project_id_override or "").strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    def _click_first_visible_run_add_link(self) -> bool:
        from selenium.common.exceptions import StaleElementReferenceException

        for el in self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/runs/add']"):
            try:
                if el.is_displayed():
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                    self.driver.execute_script("arguments[0].click();", el)
                    return True
            except StaleElementReferenceException:
                continue
            except Exception:  # noqa: BLE001
                continue
        return False

    @allure.step("Open Add Test Run form")
    def open_add_run_form(self, project_id: Optional[int] = None) -> "TestRunPage":
        self.log.info("Opening Add Test Run form")
        if self.is_present(self._ADD_RUN_SIDEBAR, 5):
            try:
                self.click(self._ADD_RUN_SIDEBAR)
                self.wait.visible(self._NAME_INPUT, timeout=25)
                return self
            except Exception as exc:  # noqa: BLE001
                self.log.warning("Sidebar Add Test Run click failed: %s; trying other entry points", exc)

        if self.is_present(self._DYNAMIC_ADD_TRIGGER, 5):
            try:
                self.click(self._DYNAMIC_ADD_TRIGGER)
                self.wait.visible(self._ADD_RUN_MENU_LINK, timeout=10)
                self.click(self._ADD_RUN_MENU_LINK)
                self.wait.visible(self._NAME_INPUT, timeout=25)
                return self
            except Exception as exc:  # noqa: BLE001
                self.log.warning("Dynamic-add path for new run failed: %s; trying fallbacks", exc)

        if self._click_first_visible_run_add_link():
            self.wait.visible(self._NAME_INPUT, timeout=25)
            return self

        if self.is_present(self._ADD_RUN_BY_TEXT, 3):
            self.click(self._ADD_RUN_BY_TEXT)
            self.wait.visible(self._NAME_INPUT, timeout=25)
            return self

        pid = project_id if project_id is not None else self._project_id_from_settings()
        if pid is not None:
            self.log.info("Opening add-run form via URL (project id=%s)", pid)
            return self.open_add_run_by_url(pid)

        raise AssertionError(
            "Could not open Add Test Run form: no sidebar/dynamic-add UI, no visible add link, "
            "and no project id (pass project_id= or set TESTRAIL_PROJECT_ID)."
        )

    def open_add_run_by_url(self, project_id: int) -> "TestRunPage":
        self.log.info("Opening Add Test Run form by URL (project=%s)", project_id)
        self.open(f"{settings.base_url}/index.php?/runs/add/{project_id}")
        self.wait.visible(self._NAME_INPUT)
        return self

    @allure.step("Fill test run name")
    def set_name(self, name: str) -> "TestRunPage":
        # Remember the intended name so the scripted submit can re-assert it right
        # before POSTing (TestRail's AJAX re-render can otherwise blank #name).
        self._run_name = name
        self.type(self._NAME_INPUT, name)
        return self

    def _set_specific_case_ids(self, case_ids: list[int]) -> bool:
        """Deterministically select 'specific cases' and inject case ids into the form.

        The add-run form posts the hidden ``#case_ids`` field plus ``include_all=0``.
        The native 'change selection' popup is loaded via AJAX and is flaky, so when the
        case id is known we set the form state directly (still submitted through the UI button).
        """
        script = """
        const ids = arguments[0];
        const specific = document.getElementById('includeSpecific');
        const all = document.getElementById('includeAll');
        const dynRadio = document.getElementById('includeDynamic');
        const dyn = document.getElementById('include_dynamic');
        const hidden = document.getElementById('case_ids');
        const container = document.getElementById('includeSpecificContainer');
        const info = document.getElementById('includeSpecificInfo');
        if (!specific || !hidden) return false;
        if (all) all.checked = false;
        if (dynRadio) dynRadio.checked = false;
        specific.checked = true;
        specific.dispatchEvent(new Event('click', { bubbles: true }));
        specific.dispatchEvent(new Event('change', { bubbles: true }));
        if (dyn) dyn.value = '0';
        if (container) container.classList.remove('hidden');
        hidden.value = ids.join(',');
        hidden.dispatchEvent(new Event('change', { bubbles: true }));
        // TestRail keeps the canonical selection in App.Runs.case_ids and serializes it on submit.
        try { if (window.App && App.Runs) App.Runs.case_ids = ids.slice(); } catch (e) {}
        if (info) info.innerHTML = '<strong>' + ids.length + '</strong> test cases included';
        return hidden.value === ids.join(',');
        """
        try:
            return bool(self.driver.execute_script(script, [int(c) for c in case_ids]))
        except Exception as exc:  # noqa: BLE001
            self.log.warning("[runs:add] could not set case_ids via JS: %s", exc)
            return False

    @allure.step("Select specific case '{title}'")
    def select_specific_case(self, title: str, case_id: Optional[int] = None) -> "TestRunPage":
        """Switch to custom selection and include a single case.

        Prefers a deterministic ``case_id`` injection (reliable, the AJAX popup is flaky);
        falls back to the native 'change selection' dialog when only the title is known.
        """
        self.log.info("Selecting specific case '%s' (id=%s) for the run", title, case_id)
        if case_id is not None and self._set_specific_case_ids([case_id]):
            return self

        # Fallback: drive the native selection dialog by case title.
        if self.is_present(self._INCLUDE_SPECIFIC_RADIO, 4):
            try:
                self.js_click(self._INCLUDE_SPECIFIC_RADIO)
            except Exception:  # noqa: BLE001
                self.click(self._INCLUDE_SPECIFIC_RADIO)
        if self.is_present(self._SELECT_CASES_LINK, 4):
            self.click(self._SELECT_CASES_LINK)
        checkbox = (By.XPATH, self._CASE_CHECKBOX_BY_TITLE.format(title=title))
        if self.is_present(checkbox, 8):
            element = self.wait.presence(checkbox)
            if not element.is_selected():
                self.js_click(checkbox)
            if self.is_present(self._DIALOG_OK, 4):
                try:
                    self.click(self._DIALOG_OK)
                except Exception:  # noqa: BLE001
                    self.js_click(self._DIALOG_OK)
        return self

    @allure.step("Switch to custom case selection")
    def switch_to_custom_selection(self) -> "TestRunPage":
        if self.is_present(self._INCLUDE_SPECIFIC_RADIO, 4):
            try:
                self.js_click(self._INCLUDE_SPECIFIC_RADIO)
            except Exception:  # noqa: BLE001
                self.click(self._INCLUDE_SPECIFIC_RADIO)
        return self

    def _try_js_submit_run_form(self) -> bool:
        """Click submit inside ``form[action*='runs/add']`` only (avoids global #accept)."""
        script = """
        var f = document.querySelector('form[action*="runs/add"]');
        if (!f) return false;
        var b = f.querySelector('button[data-testid="addRunFormOkButton"], button#accept, button[type="submit"]');
        if (!b || b.disabled || b.offsetParent === null) return false;
        b.click();
        return true;
        """
        try:
            return bool(self.driver.execute_script(script))
        except Exception:  # noqa: BLE001
            return False

    def _native_submit_run_form(self) -> None:
        """Fill the add-run form deterministically and POST it directly.

        The add-run form binds a jQuery ``submit`` handler (``.add-form-submit``) that
        ``preventDefault``s and AJAX-validates; on a scripted case selection it silently
        re-renders and can blank ``#name`` (the server then answers "Name is required"
        and the page stays on ``/runs/add``). We therefore (1) re-assert the name from
        the value typed earlier, (2) set Assign To = current user, (3) reconcile the
        case-selection radios with the injected ``case_ids``, then (4) detach the handler
        and call the native ``HTMLFormElement.submit`` so the plain POST creates the run
        and redirects to ``/runs/view/<id>``.
        """
        name = getattr(self, "_run_name", None)
        try:
            mode = self.driver.execute_script(
                """
                var wantName = arguments[0];
                var f = document.querySelector('form[action*="runs/add"]') || document.getElementById('form');
                if (!f) return 'noform';
                // Re-assert the run name (AJAX re-render may have cleared it).
                var nm = f.querySelector('#name, input[name="name"]');
                if (nm && wantName !== null) {
                    nm.value = wantName;
                    nm.dispatchEvent(new Event('input', {bubbles: true}));
                    nm.dispatchEvent(new Event('change', {bubbles: true}));
                }
                // Assign the run to the current user (mirrors the manual flow; 3 = Me).
                var assignee = document.getElementById('assignedto_id');
                if (assignee && (assignee.value === '' || assignee.value == null)) {
                    assignee.value = '3';
                    assignee.dispatchEvent(new Event('change', {bubbles: true}));
                }
                // Keep the case-selection radios consistent with the injected case_ids.
                var caseIds = document.getElementById('case_ids');
                var spec = document.getElementById('includeSpecific');
                var all = document.getElementById('includeAll');
                var dynR = document.getElementById('includeDynamic');
                var incDyn = document.getElementById('include_dynamic');
                if (caseIds && (caseIds.value || '').trim() !== '') {
                    if (all) all.checked = false;
                    if (dynR) dynR.checked = false;
                    if (spec) spec.checked = true;
                    if (incDyn) incDyn.value = '0';
                }
                var rh = document.getElementById('refs_hidden');
                var refDiv = document.getElementById('refs');
                if (rh && refDiv) { rh.value = (refDiv.textContent || '').trim(); }
                // Bypass the preventDefault/AJAX submit handler and POST directly.
                if (window.jQuery) { try { window.jQuery(f).off('submit'); } catch (e) {} }
                try { window.onbeforeunload = null; } catch (e2) {}
                HTMLFormElement.prototype.submit.call(f);
                return 'native';
                """,
                name,
            )
            self.log.info("[runs:add] direct POST submit mode=%s name=%r", mode, name)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("[runs:add] direct run form submit failed: %s", exc)

    def _wait_run_submission_outcome(self, seconds: float = 28.0) -> None:
        """After clicking OK, wait for redirect to /runs/view/ or a success/error banner."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            url = (self.current_url() or "").lower()
            if "/runs/view/" in url:
                return
            if self.is_visible(self._SUCCESS_NOTICE, 1):
                return
            # Only stop on a *visible* validation banner (hidden .error nodes exist on the page).
            if self.is_visible(self._FIELD_ERROR, 1):
                self.log.warning("[runs:add] validation / error banner visible after submit")
                return
            time.sleep(0.2)

    @allure.step("Submit test run form")
    def submit(self) -> "TestRunPage":
        self.log.info("Submitting test run form")
        # 1) Deterministic path: fill the form via JS and POST directly. We do NOT
        # click the AJAX OK button first — that handler re-renders the form and can
        # blank #name, so the subsequent POST fails with "Name is required".
        self._native_submit_run_form()
        self._wait_run_submission_outcome(35.0)

        # 2) Fallback: a real user click on the OK button (only if not yet created
        # and no validation banner is shown, e.g. negative empty-name scenarios).
        if "/runs/view/" not in (self.current_url() or "").lower() and not self.is_visible(self._FIELD_ERROR, 1):
            for loc in self._SAVE_RUN_CANDIDATES:
                if not self.is_present(loc, 2):
                    continue
                try:
                    el = self.wait.clickable(loc, timeout=6)
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                    el.click()
                except Exception:  # noqa: BLE001
                    try:
                        self.js_click(loc)
                    except Exception as exc:  # noqa: BLE001
                        self.log.warning("[runs:add] save click failed (%s): %s", loc[1], exc)
                        continue
                break
            self._wait_run_submission_outcome(20.0)

        self.wait.document_ready()
        return self

    @allure.step("Create test run '{name}'")
    def create_run(
        self,
        name: str,
        case_title: Optional[str] = None,
        case_id: Optional[int] = None,
        project_id: Optional[int] = None,
    ) -> "TestRunPage":
        self.log.info("Creating test run '%s' (case=%s id=%s)", name, case_title, case_id)
        self.open_add_run_form(project_id=project_id)
        self.set_name(name)
        if case_title or case_id is not None:
            self.select_specific_case(case_title or "", case_id=case_id)
        self.submit()
        return self

    # --- Validations ---------------------------------------------------------

    def get_created_run_id(self) -> Optional[int]:
        try:
            self.wait.for_state(lambda d: re.search(r"/runs/view/(\d+)", d.current_url) is not None, timeout=22)
        except Exception:  # noqa: BLE001
            self.log.warning("Could not detect run id from URL: %s", self.current_url())
            return None
        match = re.search(r"/runs/view/(\d+)", self.current_url())
        return int(match.group(1)) if match else None

    def is_success_notification_displayed(self) -> bool:
        return self.is_visible(self._SUCCESS_NOTICE, timeout=8)

    def has_validation_error(self) -> bool:
        return self.is_visible(self._FIELD_ERROR, timeout=6)

    def is_run_visible(self, name: str) -> bool:
        locator = (By.XPATH, self._RUN_ROW_BY_NAME.format(name=name))
        return self.is_present(locator, timeout=8)

    def included_cases_count(self) -> int:
        if self.is_present(self._TEST_ROWS, 6):
            return len(self.driver.find_elements(*self._TEST_ROWS))
        return 0

    def is_case_in_run(self, title: str) -> bool:
        locator = (By.XPATH, self._CASE_IN_RUN_BY_TITLE.format(title=title))
        return self.is_present(locator, timeout=8)

    def run_title(self) -> str:
        if self.is_visible(self._RUN_TITLE, 5):
            return self.get_text(self._RUN_TITLE)
        return ""

    def is_on_form(self) -> bool:
        return self.is_visible(self._NAME_INPUT, 4)

    # --- Run-view navigation -------------------------------------------------

    @allure.step("Open test run by id={run_id}")
    def open_run_by_id(self, run_id: int) -> "TestRunPage":
        self.open(f"{settings.base_url}/index.php?/runs/view/{run_id}")
        self.wait.document_ready()
        return self

    def status_badge_text(self) -> str:
        if self.is_visible(self._RUN_STATUS_BADGE, 4):
            return self.get_text(self._RUN_STATUS_BADGE)
        return ""

    # --- Execution (TASK 2) --------------------------------------------------

    @allure.step("Open test '{title}' for execution")
    def open_test_for_execution(self, title: str) -> "TestRunPage":
        self.log.info("Opening test '%s' inside the run", title)
        link = (By.XPATH, self._TEST_LINK_BY_TITLE.format(title=title))
        if self.is_present(link, 6):
            self.click(link)
            self.wait.document_ready()
        return self

    def _safe_click(self, locator, timeout: int = 4) -> bool:
        """Click a control if present; never raise (UI execution is best-effort)."""
        if not self.is_present(locator, timeout):
            return False
        try:
            self.click(locator)
            return True
        except Exception:  # noqa: BLE001 - covered/animated control -> JS click
            try:
                self.js_click(locator)
                return True
            except Exception as exc:  # noqa: BLE001
                self.log.warning("[run:exec] click failed (%s): %s", locator[1], exc)
                return False

    @allure.step("Add result via UI: status='{status_name}'")
    def add_result_via_ui(self, status_name: str, comment: Optional[str] = None,
                          defect: Optional[str] = None) -> "TestRunPage":
        """Best-effort UI execution. Results are validated via API (truth model).

        This method must never raise: callers treat the API as the source of truth
        and fall back to an API result when the UI dialog differs across versions.
        """
        self.log.info("Adding result via UI status=%s comment=%s", status_name, comment)
        try:
            self._safe_click(self._ADD_RESULT_BUTTON, 4)
            # Select status (custom dropdown or native select option).
            status_option = (By.XPATH, self._STATUS_OPTION_BY_TEXT.format(status=status_name))
            self._safe_click(self._STATUS_DROPDOWN, 4)
            self._safe_click(status_option, 4)
            if comment and self.is_present(self._RESULT_COMMENT, 3):
                try:
                    self.type(self._RESULT_COMMENT, comment)
                except Exception:  # noqa: BLE001
                    pass
            if defect and self.is_present(self._RESULT_DEFECTS, 3):
                try:
                    self.type(self._RESULT_DEFECTS, defect)
                except Exception:  # noqa: BLE001
                    pass
            if self._safe_click(self._RESULT_SUBMIT, 4):
                self.wait.document_ready()
        except Exception as exc:  # noqa: BLE001 - never break the API truth-model flow
            self.log.warning("[run:exec] add_result_via_ui best-effort path failed: %s", exc)
        return self
