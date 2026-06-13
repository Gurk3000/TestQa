"""Test Case page object: list view + add/edit case form."""
from __future__ import annotations

import re
from typing import Optional

import allure
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from config.config import settings
from pages.base_page import BasePage


class TestCasePage(BasePage):
    """TestRail test cases area (suite/case list and add-case form)."""

    # Page Object, not a pytest test class: stop collection despite the Test* prefix.
    __test__ = False

    url_fragment = "/suites"

    # --- Toolbar / list locators --------------------------------------------
    # Modern UI: "+" opens #dynamicAdd; the real link is [data-testid="navigationTestCase"] (often not clickable until the menu opens).
    _DYNAMIC_ADD_TRIGGER = (
        By.CSS_SELECTOR,
        '[data-testid="dynamicAddButton"], a.dynamic_add.dropdownLink[href="#dynamicAdd"]',
    )
    _ADD_CASE_MENU_LINK = (
        By.CSS_SELECTOR,
        '[data-testid="navigationTestCase"], a#navigation-test-case',
    )
    _ADD_CASE_BUTTON = (
        By.CSS_SELECTOR,
        "a[href*='/cases/add'], #sidebar-add, a.toolbar-add-case, #addCase",
    )
    _ADD_CASE_BY_TEXT = (By.XPATH, "//a[contains(normalize-space(),'Add Test Case') or contains(normalize-space(),'Add Case')]")

    # --- Add/edit form locators ---------------------------------------------
    # Add page + Edit page (`cases/edit`) share #title; edit uses data-testid (see data/*cases-edit*.txt).
    _TITLE_INPUT = (By.CSS_SELECTOR, "#title, input[name='title'], [data-testid='addEditCaseTitle']")
    # The "References" field is a simple text input present across templates and
    # maps to the API field `refs`; used here as the verifiable description proxy.
    _REFS_INPUT = (By.CSS_SELECTOR, "#refs, input[name='refs']")
    # Full "Add Test Case" page: never use a global `.button-positive` (dialogs share it).
    # Staging uses ``form[action*='cases/add']``; legacy builds use ``#caseForm`` (Data/*.txt).
    _CASE_FORM = (By.CSS_SELECTOR, "form#caseForm, form[id='caseForm']")
    _SAVE_BUTTON_CANDIDATES = (
        (By.CSS_SELECTOR, "form[action*='cases/edit'] button#accept"),
        (By.CSS_SELECTOR, "form[action*='cases/edit'] button.add-form-submit"),
        (By.CSS_SELECTOR, "form[action*='cases/edit'] button[type='submit'].button-positive"),
        (By.CSS_SELECTOR, "form[action*='cases/add'] button#accept"),
        (By.CSS_SELECTOR, "form[action*='cases/add'] button[data-testid='addCaseFormOkButton']"),
        (By.CSS_SELECTOR, "form[action*='cases/add'] button.add-form-submit"),
        (By.CSS_SELECTOR, "form[action*='cases/add'] button[type='submit'].button-positive"),
        (By.CSS_SELECTOR, "form#caseForm button#accept, form[id='caseForm'] button#accept"),
        (
            By.CSS_SELECTOR,
            "form#caseForm button.add-form-submit, form#caseForm button[type='submit'].button-positive",
        ),
        (By.CSS_SELECTOR, "form#caseForm input[type='submit']"),
        (
            By.XPATH,
            "//form[@id='caseForm']//button[contains(@class,'button-positive')]"
            " | //form[@id='caseForm']//input[@type='submit']",
        ),
        (
            By.XPATH,
            "//form[@id='caseForm']//*[self::button or self::a][contains(@class,'button')]"
            "[contains(normalize-space(.),'Add Test Case')]",
        ),
    )
    _SAVE_BUTTON = _SAVE_BUTTON_CANDIDATES[0]
    _FORM = (By.CSS_SELECTOR, "form#caseForm, form[action*='cases'], #content form")

    # --- Inline "quick add" within the suite grid ----------------------------
    # Staging: section footer link uses data-testid suiteAddCaseLink (user screenshots + DevTools).
    _SUITE_INLINE_ADD_CASE = (By.CSS_SELECTOR, "a[data-testid='suiteAddCaseLink'], [data-testid='suiteAddCaseLink']")
    _GRID_GROUPS = (By.CSS_SELECTOR, "#groups, [data-testid='sectionCaseGridGroups']")
    _INLINE_ADD_CASE_LINK = (
        By.XPATH,
        "//*[@id='groups']//a[normalize-space()='Add Case']"
        " | //a[contains(@onclick,'App.Cases.add(') and normalize-space()='Add Case']",
    )
    _INLINE_TITLE_INPUT = (
        By.CSS_SELECTOR,
        "#groups form input[type='text'], #groups input.inline-add-title, #groups input[name='title']",
    )

    # --- Search / filter -----------------------------------------------------
    _SEARCH_INPUT = (
        By.CSS_SELECTOR,
        "#sidebar-filter, input[name='filter'], input[type='search'], #filterText, .toolbar input[type='text']",
    )

    # --- Feedback locators ---------------------------------------------------
    _SUCCESS_NOTICE = (
        By.CSS_SELECTOR,
        ".message-success, .message.message-success, .notification-success, #notice, .message.success, "
        ".grid-success, [data-testid*='Success'], [data-testid*='success'], "
        ".automate-ai-success-notification, #automationAddedSuccessNotification",
    )
    _FIELD_ERROR = (By.CSS_SELECTOR, ".message-error, .error, .field-error, .message-attention")

    _CASE_ROW_BY_TITLE = "//*[contains(@class,'grid') or self::table]//*[normalize-space()=\"{title}\"]"

    # Row title opens case view (`/cases/view/<id>`); prefer JS click to avoid XPath quoting issues.
    _ROW_EDIT_ICON = (By.CSS_SELECTOR, "[data-testid='addSubsectionEditIcon']")
    _CASE_VIEW_EDIT = (
        By.CSS_SELECTOR,
        "#content a[href*='/cases/edit/'], .toolbar a[href*='/cases/edit/'], "
        "a.link[href*='/cases/edit/']",
    )

    @staticmethod
    def _section_id_from_settings() -> Optional[int]:
        raw = (settings.section_id_override or "").strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    def _probe(self, label: str, locator, timeout: int = 4) -> bool:
        """Presence probe with explicit FOUND / NOT FOUND step logging."""
        ok = self.is_present(locator, timeout)
        self.log.info("[create_case] %-26s %-9s (%s)", label, "FOUND" if ok else "NOT FOUND", locator[1])
        return ok

    def _click_first_visible_case_add_link(self) -> bool:
        from selenium.common.exceptions import StaleElementReferenceException

        for el in self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/cases/add']"):
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

    @allure.step("Open Add Test Case form")
    def open_add_case_form(self, section_id: Optional[int] = None) -> "TestCasePage":
        self.log.info("[create_case] STEP 1: open the 'Add Test Case' page")
        if self._probe("toolbar '+' dynamic add", self._DYNAMIC_ADD_TRIGGER, 5):
            try:
                self.click(self._DYNAMIC_ADD_TRIGGER)
                self.wait.visible(self._ADD_CASE_MENU_LINK, timeout=10)
                self.log.info("[create_case] STEP 1: dynamic-add menu opened; clicking 'Test Cases'")
                self.click(self._ADD_CASE_MENU_LINK)
                self.wait.visible(self._TITLE_INPUT, timeout=25)
                self.log.info("[create_case] STEP 1: reached add page (url=%s)", self.current_url())
                return self
            except Exception as exc:  # noqa: BLE001
                self.log.warning("[create_case] STEP 1: dynamic-add path failed: %s; trying fallbacks", exc)

        if self._click_first_visible_case_add_link():
            self.log.info("[create_case] STEP 1: opened via visible 'cases/add' link")
            self.wait.visible(self._TITLE_INPUT, timeout=25)
            return self

        if self._probe("'Add Test Case' text link", self._ADD_CASE_BY_TEXT, 3):
            self.click(self._ADD_CASE_BY_TEXT)
            self.wait.visible(self._TITLE_INPUT, timeout=25)
            self.log.info("[create_case] STEP 1: opened via text link")
            return self

        sid = section_id if section_id is not None else self._section_id_from_settings()
        if sid is not None:
            self.log.info("[create_case] STEP 1: opening add-case page via URL (section id=%s)", sid)
            return self.open_add_case_by_url(sid)

        raise AssertionError(
            "Could not open Add Test Case form: no working dynamic-add UI, no visible add link, "
            "and no section id (pass section_id= or set TESTRAIL_SECTION_ID)."
        )

    def open_add_case_by_url(self, suite_or_section_id: int) -> "TestCasePage":
        self.log.info("Opening Add Test Case form by URL (id=%s)", suite_or_section_id)
        self.open(f"{settings.base_url}/index.php?/cases/add/{suite_or_section_id}")
        self.wait.visible(self._TITLE_INPUT)
        return self

    @allure.step("Fill test case title")
    def set_title(self, title: str) -> "TestCasePage":
        self.type(self._TITLE_INPUT, title)
        return self

    @allure.step("Fill test case references / description")
    def set_references(self, references: str) -> "TestCasePage":
        """Set the References field (verifiable description proxy -> API `refs`).

        Staging renders refs as a ``contenteditable`` div plus a hidden ``#refs_hidden``
        input that is what actually gets POSTed, so set both via JS (``send_keys`` can't
        clear a contenteditable and the hidden input is not interactable).
        """
        applied = self.driver.execute_script(
            """
            const val = arguments[0];
            const hidden = document.getElementById('refs_hidden')
                || document.querySelector("input[type='hidden'][name='refs']");
            const editable = document.querySelector("div[name='refs'], [contenteditable='true'][name='refs']");
            let ok = false;
            if (hidden) { hidden.value = val; ok = true; }
            if (editable) { editable.textContent = val; editable.dispatchEvent(new Event('input', {bubbles: true})); ok = true; }
            return ok;
            """,
            references,
        )
        if applied:
            return self
        # Fallback: a plain text input variant on some templates.
        if self.is_present((By.CSS_SELECTOR, "input[name='refs']:not([type='hidden'])"), 3):
            self.type((By.CSS_SELECTOR, "input[name='refs']:not([type='hidden'])"), references)
        else:
            self.log.warning("References field not found on case form; skipping")
        return self

    def _ensure_required_case_selects(self) -> None:
        """Pre-select the first real option for any *required* empty select.

        The full Add Test Case form marks Section/Template/Type/Priority as required;
        a freshly opened form can leave one without a value, which makes the POST
        bounce back to ``/cases/add`` without creating the case.
        """
        try:
            self.driver.execute_script(
                """
                const ids = ['section_id', 'template_id', 'type_id', 'priority_id'];
                for (const id of ids) {
                    const sel = document.getElementById(id);
                    if (!sel || sel.disabled) continue;
                    if (sel.value === '' || sel.value == null) {
                        for (const opt of sel.options) {
                            if (opt.value !== '' && !opt.disabled) { sel.value = opt.value; break; }
                        }
                        sel.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                }
                """
            )
        except Exception as exc:  # noqa: BLE001
            self.log.warning("[create_case] could not pre-fill required selects: %s", exc)

    def _submit_succeeded(self, timeout: int = 5) -> bool:
        """A save is confirmed by a redirect to /cases/view/<id> or a success notice."""
        try:
            self.wait.for_state(lambda d: "/cases/view/" in d.current_url, timeout=timeout)
            return True
        except Exception:  # noqa: BLE001
            return self.is_visible(self._SUCCESS_NOTICE, timeout=2)

    def _try_js_click_case_form_submit(self) -> bool:
        """Click the first enabled submit control inside ``#caseForm`` (never global dialogs)."""
        script = """
        var f = document.querySelector('form[action*="cases/add"]')
            || document.querySelector('form[action*="cases/edit"]')
            || document.getElementById('caseForm')
            || document.getElementById('form');
        if (!f) return false;
        var sel = 'button.add-form-submit, button#accept, button[data-testid="addCaseFormOkButton"], '
            + 'button[type="submit"], input[type="submit"]';
        var nodes = f.querySelectorAll(sel);
        for (var i = 0; i < nodes.length; i++) {
          var el = nodes[i];
          if (el.disabled || el.offsetParent === null) continue;
          el.click();
          return true;
        }
        return false;
        """
        try:
            ok = bool(self.driver.execute_script(script))
            if ok:
                self.log.info("[create_case] STEP 3: JS-clicked submit control inside #caseForm")
            return ok
        except Exception as exc:  # noqa: BLE001
            self.log.warning("[create_case] STEP 3: JS case-form submit failed: %s", exc)
            return False

    def _press_save_shortcut(self) -> None:
        """Documented TestRail shortcut: Ctrl/Cmd+S saves the test case (focus kept in-page)."""
        if "/cases/add" not in self.current_url().lower():
            self.log.info("[create_case] STEP 3: skip Ctrl+S (not on cases/add URL)")
            return
        actions = ActionChains(self.driver)
        try:
            el = self.wait.visible(self._TITLE_INPUT, timeout=4)
            actions.move_to_element(el).click()
        except Exception:  # noqa: BLE001 - shortcut still works on document focus
            pass
        actions.key_down(Keys.CONTROL).send_keys("s").key_up(Keys.CONTROL).perform()

    def _click_save_candidate(self, loc) -> bool:
        """Click a save control via a short clickable wait, with a JS-click fallback."""
        try:
            self.wait.clickable(loc, timeout=4).click()
            return True
        except Exception:  # noqa: BLE001 - overlay / re-render -> JS click
            try:
                self.js_click(loc)
                return True
            except Exception as exc:  # noqa: BLE001
                self.log.warning("[create_case] STEP 3: save click %s failed: %s", loc[1], exc)
                return False

    @allure.step("Submit test case form")
    def submit(self) -> "TestCasePage":
        self.log.info("[create_case] STEP 3: submit the 'Add Test Case' form")
        # A required-but-empty select silently rejects the POST; pre-fill defaults first.
        self._ensure_required_case_selects()

        # 1) Real user click on the primary save button (drives TestRail's own AJAX flow).
        for loc in self._SAVE_BUTTON_CANDIDATES[:5]:
            if not self._probe("save control", loc, 2):
                continue
            self.log.info("[create_case] STEP 3: clicking save control (%s)", loc[1])
            # Lock / suite AJAX after save can exceed a few seconds on staging.
            if self._click_save_candidate(loc) and self._submit_succeeded(35):
                self.log.info("[create_case] STEP 3: save CONFIRMED (url=%s)", self.current_url())
                return self
            self.log.info("[create_case] STEP 3: %s did not confirm; trying scripted submit", loc[1])
            break

        # 2) Scripted submit: sync hidden fields, then requestSubmit (fires handlers) or native POST.
        self._native_submit_case_form()
        if self._submit_succeeded(25):
            self.log.info("[create_case] STEP 3: save CONFIRMED after scripted submit (url=%s)", self.current_url())
        return self

    def _native_submit_case_form(self) -> None:
        """Submit the case form in a way the server accepts.

        Staging uses jQuery ``submit`` handlers (``preventDefault`` + AJAX). Plain
        ``HTMLFormElement.submit`` skips listeners and can POST incomplete state.
        Prefer ``requestSubmit(acceptButton)`` so the browser fires ``submit`` events;
        then fall back to ``js_test=1`` + detached handlers + native POST.
        """
        try:
            mode = self.driver.execute_script(
                """
                var f = document.querySelector('form[action*="cases/add"]')
                    || document.querySelector('form[action*="cases/edit"]')
                    || document.getElementById('caseForm')
                    || document.getElementById('form');
                if (!f) return 'noform';
                var fc = f.querySelector('#filter_changed, input[name="filter_changed"]');
                if (fc) fc.value = '1';
                var rh = f.querySelector('#refs_hidden, input[type="hidden"][name="refs"]');
                var refDiv = f.querySelector('#refs[contenteditable="true"], div[name="refs"][contenteditable]');
                if (rh && refDiv) { rh.value = (refDiv.textContent || '').trim(); }
                var t = f.querySelector('#title, input[name="title"]');
                if (t) { t.dispatchEvent(new Event('change', {bubbles: true})); }
                var jt = f.querySelector('#js_test, input[name="js_test"]');
                if (jt) jt.value = '1';
                var bc = f.querySelector('#button_clicked, input[name="button_clicked"]');
                if (bc) bc.value = 'accept';
                var btn = f.querySelector('button#accept, button[data-testid="addCaseFormOkButton"]');
                try {
                    if (btn && typeof f.requestSubmit === 'function') {
                        f.requestSubmit(btn);
                        return 'requestSubmit';
                    }
                } catch (e) {}
                if (window.jQuery) { try { window.jQuery(f).off('submit'); } catch (e2) {} }
                try { window.onbeforeunload = null; } catch (e3) {}
                HTMLFormElement.prototype.submit.call(f);
                return 'native';
                """
            )
            self.log.info("[create_case] STEP 3: scripted case submit mode=%s", mode)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("[create_case] STEP 3: scripted case form submit failed: %s", exc)

    def rapid_submit(self, times: int = 5) -> "TestCasePage":
        """Fire multiple saves to probe for double-submit duplication."""
        self.log.info("[create_case] rapid-submitting the form %s times", times)
        for _ in range(times):
            if self._try_js_click_case_form_submit():
                pass
            else:
                try:
                    self.js_click(self._SAVE_BUTTON)
                except Exception:  # noqa: BLE001
                    break
            if self._submit_succeeded(3):
                break
        return self

    def _try_inline_add(self, title: str) -> bool:
        """Inline "quick add" within the section grid (title -> Enter).

        Mirrors the user-reported flow: section "Add Case" link -> inline form
        input -> type title -> confirm. Returns True only once the title is
        entered and submitted; the case is then verifiable via the API by title.
        """
        self.log.info("[create_case] STEP 2a: try inline 'Add Case' on the suite grid")
        if not self._probe("suite grid container", self._GRID_GROUPS, 6):
            return False
        link_candidates = (
            ("suiteAddCaseLink (data-testid)", self._SUITE_INLINE_ADD_CASE),
            ("legacy Add Case xpath", self._INLINE_ADD_CASE_LINK),
        )
        opened = False
        for label, loc in link_candidates:
            if not self._probe(f"inline {label}", loc, 4):
                continue
            try:
                self.click(loc)
                opened = True
                break
            except Exception as exc:  # noqa: BLE001
                self.log.warning("[create_case] STEP 2a: inline %s click failed: %s", label, exc)
        if not opened:
            return False
        if not self._probe("inline title input", self._INLINE_TITLE_INPUT, 6):
            return False
        self.type(self._INLINE_TITLE_INPUT, title)
        self.log.info("[create_case] STEP 2a: typed title %r into inline input", title)
        # Documented: press Enter (or the green icon) to save the inline case.
        self.wait.visible(self._INLINE_TITLE_INPUT).send_keys(Keys.ENTER)
        self.log.info("[create_case] STEP 2a: submitted inline form via ENTER")
        if self.is_case_visible(title):
            self.log.info("[create_case] STEP 2a: inline add CONFIRMED — grid row with title present")
            return True
        self.log.info("[create_case] STEP 2a: no grid row appeared; will use the full Add Test Case page")
        return False

    @allure.step("Create test case '{title}' (inline add, then edit to set references)")
    def create_case(self, title: str, references: Optional[str] = None, section_id: Optional[int] = None) -> "TestCasePage":
        """Create a case following the reliable TestRail flow.

        The full "Add Test Case" page POST is unreliable on staging (it bounces
        back to ``/cases/add`` without creating the case). The flow that mirrors
        the real UI is: inline quick-add a case (unique title) on the suite grid,
        then open it in edit mode (``/cases/edit/<id>``), fill the fields and
        click **Save Test Case** (``button#accept``) which redirects to
        ``/cases/view/<id>``.
        """
        self.log.info("Creating test case '%s' (refs=%s) via inline-add + edit flow", title, references)
        # STEP 1-2: inline quick-add actually creates the case (title only).
        self.create_case_inline(title, section_id=section_id)
        # STEP 3: open the freshly created case in edit mode and set references, then Save.
        if references:
            self._edit_case_set_references_and_save(title, references)
        return self

    def _edit_case_set_references_and_save(self, title: str, references: str) -> None:
        """Open the just-created case in edit mode, fill references and Save.

        Robust to where ``create_case_inline`` left us: the suite grid (inline
        succeeded), ``/cases/view/`` (full-page fallback succeeded) or already on
        ``/cases/edit/``.
        """
        url = (self.current_url() or "").lower()
        if "/cases/edit/" not in url:
            if "/cases/view/" in url:
                self.log.info("[create_case] STEP 3: on case view; following Edit link")
                self.open_case_edit_from_view_toolbar()
            else:
                self.log.info("[create_case] STEP 3: on suite grid; opening case edit via title")
                self.open_case_edit_from_suite_via_title(title)
        self.set_references(references)
        # button#accept on the edit form saves and redirects to /cases/view/<id>.
        self.submit()

    @allure.step("Create test case '{title}' (inline quick-add in section grid)")
    def create_case_inline(self, title: str, section_id: Optional[int] = None) -> "TestCasePage":
        """Create a case using the section "Add Case" quick-add (title + Enter).

        Falls back to the full "Add Test Case" page if the inline form is not
        available, so the scenario stays reliable across UI states.
        """
        self.log.info("Creating test case '%s' via inline quick-add", title)
        if self._try_inline_add(title):
            return self
        self.log.info("[create_case] inline quick-add unavailable; falling back to full Add Test Case page")
        return self._create_case_full_page(title, section_id=section_id)

    @allure.step("Create test case '{title}' (full Add Test Case page fallback)")
    def _create_case_full_page(
        self, title: str, references: Optional[str] = None, section_id: Optional[int] = None
    ) -> "TestCasePage":
        """Last-resort creation via the full "Add Test Case" page.

        Used only when inline quick-add is unavailable; the primary flow is
        :meth:`create_case` (inline add + edit).
        """
        self.log.info("Creating test case '%s' (refs=%s) via full Add Test Case page", title, references)
        self.open_add_case_form(section_id=section_id)
        self.log.info("[create_case] STEP 2: fill the case title")
        self.set_title(title)
        if references:
            self.set_references(references)
        self.submit()
        return self

    @allure.step("Open test case by id={case_id}")
    def open_case_by_id(self, case_id: int) -> "TestCasePage":
        self.open(f"{settings.base_url}/index.php?/cases/view/{case_id}")
        self.wait.document_ready()
        return self

    @allure.step("Open Edit Test Case for id={case_id}")
    def open_case_edit_by_id(self, case_id: int) -> "TestCasePage":
        """Open ``/cases/edit/<id>`` (same main form as add; action contains ``cases/edit``)."""
        self.open(f"{settings.base_url}/index.php?/cases/edit/{case_id}")
        self.wait.visible(self._TITLE_INPUT, timeout=25)
        self.wait.document_ready()
        return self

    @allure.step("Open case view from suite grid by clicking title link")
    def open_case_view_from_suite_by_title(self, title: str) -> "TestCasePage":
        """On ``/suites/view/...``, click the grid link whose text matches ``title`` (``/cases/view/<id>``)."""
        ok = self.driver.execute_script(
            """
            const want = (arguments[0] || '').trim();
            const links = Array.from(document.querySelectorAll("a[href*='cases/view']"));
            const a = links.find(el => (el.textContent || '').trim() === want);
            if (!a) return false;
            a.scrollIntoView({block: 'center'});
            a.click();
            return true;
            """,
            title,
        )
        if not ok:
            raise AssertionError(f"No visible case title link matching {title!r} (href contains cases/view)")
        self.wait.for_state(lambda d: "/cases/view/" in (d.current_url or "").lower(), timeout=25)
        self.wait.document_ready()
        return self

    @allure.step("Click Edit on case view page (navigate to cases/edit)")
    def open_case_edit_from_view_toolbar(self) -> "TestCasePage":
        """When URL is ``/cases/view/<id>``, follow the Edit link to ``/cases/edit/<id>``."""
        if "/cases/view/" not in (self.current_url() or "").lower():
            raise AssertionError("open_case_edit_from_view_toolbar requires /cases/view/ URL")
        self.click(self._CASE_VIEW_EDIT)
        self.wait.for_state(lambda d: "/cases/edit/" in (d.current_url or "").lower(), timeout=25)
        self.wait.visible(self._TITLE_INPUT, timeout=20)
        self.wait.document_ready()
        return self

    @allure.step("Suite: open Edit Test Case for title (grid title → case view → Edit)")
    def open_case_edit_from_suite_via_title(self, title: str) -> "TestCasePage":
        """Prefer title link + **Edit** on the case view (stable) over hover-only icons."""
        self.open_case_view_from_suite_by_title(title)
        return self.open_case_edit_from_view_toolbar()

    @allure.step("Search test cases for '{title}'")
    def search_case(self, title: str) -> bool:
        """Filter the case list (if a filter exists) and report visibility."""
        if self.is_present(self._SEARCH_INPUT, 4):
            self.type(self._SEARCH_INPUT, title)
            # Filtering is client/AJAX driven; wait for the row to settle.
            self.wait.document_ready()
        return self.is_case_visible(title)

    # --- Validations ---------------------------------------------------------

    def get_created_case_id(self) -> Optional[int]:
        """Extract case id from the post-save URL (e.g. /cases/view/123).

        The full "Add Test Case" page redirects to /cases/view/<id>; inline
        quick-add does not change the URL, so callers should resolve the id via
        the API by title when this returns ``None``.
        """
        try:
            self.wait.for_state(lambda d: re.search(r"/cases/view/(\d+)", d.current_url) is not None, timeout=10)
        except Exception:  # noqa: BLE001 - id extraction is best-effort
            self.log.info("[create_case] no /cases/view/<id> in URL (%s); resolve via API by title", self.current_url())
            return None
        match = re.search(r"/cases/view/(\d+)", self.current_url())
        return int(match.group(1)) if match else None

    def is_success_notification_displayed(self) -> bool:
        return self.is_visible(self._SUCCESS_NOTICE, timeout=8)

    def has_validation_error(self) -> bool:
        return self.is_visible(self._FIELD_ERROR, timeout=6)

    def is_case_visible(self, title: str) -> bool:
        row = (By.XPATH, self._CASE_ROW_BY_TITLE.format(title=title))
        if self.is_present(row, timeout=5):
            return True
        try:
            return bool(
                self.driver.execute_script(
                    """
                    const want = (arguments[0]||'').trim();
                    return Array.from(document.querySelectorAll("a[href*='cases/view']")).some(
                        el => (el.textContent||'').trim() === want && el.offsetParent !== null
                    );
                    """,
                    title,
                )
            )
        except Exception:  # noqa: BLE001
            return False

    def created_case_confirmed(self, title: str) -> bool:
        """UI confirmation that works for both flows (full page redirect / notice / grid row)."""
        if "/cases/view/" in self.current_url():
            return True
        if self.is_success_notification_displayed():
            return True
        if self.displayed_title() == title:
            return True
        return self.is_case_visible(title)

    def displayed_title(self) -> str:
        locator = (By.CSS_SELECTOR, "#content-header .content-header-title, h1, .title")
        if self.is_visible(locator, 5):
            return self.get_text(locator)
        return ""

    def is_on_form(self) -> bool:
        return self.is_visible(self._TITLE_INPUT, 4)
