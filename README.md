# TestRail UI Automation Framework

Production-ready UI automation for TestRail using Python, Selenium, Pytest, Page Object
and Page Component patterns, explicit waits, logging, Allure and pytest-html reporting,
screenshots, and an API-backed truth model with API cleanup.

---

## 1. 

### 1.1 Risk analysis — weakest points of the TestRail UI flow

| # | Risk area | Why it is risky | Mitigation in this framework |
|---|-----------|-----------------|------------------------------|
| R1 | Login redirect timing | Auth redirect is async; asserting too early gives false negatives | `login_expecting_success` waits for URL state change, not a sleep |
| R2 | Dialog / modal rendering | TestRail uses `#dialog` overlays that animate in/out | `ModalComponent.wait_until_open/closed` waits for visibility/invisibility |
| R3 | Case/Run save → redirect | The `/cases/view/{id}` URL appears only after the server round-trip | `get_created_case_id` waits for the URL regex (wait-for-state) |
| R4 | Element re-render (stale) | Grid rows re-render after AJAX updates | `Waiter` ignores `StaleElementReferenceException`; JS-click fallback |
| R5 | Click intercepted by overlay | Sticky headers / toasts intercept clicks | `BasePage.click` falls back to JS click |
| R6 | Locator drift across TestRail versions | UI markup varies between releases | Resilient multi-selector locators + text-based fallbacks |
| R7 | Duplicate data between runs | Re-runs collide on names | Timestamp + random suffix unique names; API cleanup |
| R8 | Case-selection sub-dialog in Add Run | Two-step async widget | `select_specific_case` handles radio → dialog → checkbox → confirm |

### 1.2 Async / race conditions

- Post-submit navigation (case/run id only known after redirect) → URL wait-for-state.
- AJAX grid refresh after entity creation → presence/visibility waits, never `sleep`.
- Modal open/close animation → explicit visibility/invisibility waits.
- Double-submit on slow networks → covered by the rapid-clicks edge test + idempotency assertion.

### 1.3 Flaky UI behaviors and mitigations

- Stale elements → `WebDriverWait` with ignored stale exceptions + clickable re-fetch.
- Intercepted clicks → JS-click fallback.
- Transient network/server hiccups → API `Retry` and explicit waits (no automatic pytest reruns).
- Non-deterministic preconditions → seeded via API for stable starting state.

---

## 2. Test strategy — coverage matrix

Priority legend: **P0** critical path, **P1** important, **P2** edge/secondary.

| Feature | Risk | Test case | Type | Priority |
|---------|------|-----------|------|----------|
| Auth | R1 | `test_00_tc001_valid_login` | Positive/Smoke | P0 |
| Auth | R1 | `test_invalid_login` | Negative | P1 |
| Auth | R1 | `test_empty_login` | Negative | P1 |
| Auth | R1 | `test_empty_password` | Negative | P1 |
| Navigation | R6 | `test_navigate_to_project` | Positive/Smoke | P0 |
| Navigation | R6 | `test_invalid_project_navigation` | Negative | P2 |
| Test Case | R3,R5 | `test_create_test_case_success` | Positive/Smoke | P0 |
| Test Case | R3 | `test_create_test_case_empty_name` | Negative | P1 |
| Test Case | R7 | `test_create_test_case_duplicate_name` | Negative | P1 |
| Test Run | R8,R3 | `test_create_test_run_success` | Positive/Smoke | P0 |
| Test Run | R3 | `test_create_test_run_empty_name` | Negative | P1 |
| Test Run | R8 | `test_create_run_without_case` | Negative | P1 |
| E2E | R1-R8 | `test_full_flow` | E2E/Positive | P0 |
| Edge | R3 | `test_very_long_name` | Edge | P2 |
| Edge | R3 | `test_special_characters` | Edge | P2 |
| Edge | R3 | `test_unicode_characters` | Edge | P2 |
| Edge | R4 | `test_rapid_multiple_clicks` | Edge | P2 |
| Edge | R2 | `test_browser_refresh_during_creation` | Edge | P2 |

---

## 3. Stability engineering

- **No `sleep()`** anywhere — only `WebDriverWait` via the `Waiter` helper.
- **Wait-for-state**, not just presence: URL regex waits, `document.readyState`,
  modal visibility/invisibility, custom predicates.
- **Retry mechanism**: HTTP `Retry` with backoff for the API layer (UI tests do not use automatic reruns).
- **Self-healing interactions**: stale-exception tolerance + JS-click fallback.

---

## 4. Data strategy

- **Idempotency**: unique names `TestCase_YYYYMMDD_HHMMSS_xxxx` / `TestRun_YYYYMMDD_HHMMSS_xxxx`.
- **No duplicate conflicts**: timestamp + random suffix guarantees uniqueness even within the same second.
- **API cleanup**: every UI-created entity is registered and deleted via API in teardown
  (runs first, then cases), best-effort and never failing the test.
- **Deterministic preconditions**: where a case must pre-exist (run/duplicate tests),
  it is seeded through the API rather than the UI.

---

## 5. UI vs API truth model

UI actions are validated against the **TestRail API as the source of truth**:

- After UI creation, the test case is validated via `get_case` / `get_cases`.
- After UI creation, the test run is validated via `get_run`.
- Case-in-run membership is validated via `get_tests` (`run_contains_case`, `tests_count`).

**Suite grid (staging):** the section **Add Case** action uses `data-testid="suiteAddCaseLink"`.
To open a case from the list, click the **title** cell link (`href` contains `/cases/view/`).
The **Edit Test Case** screen is `/cases/edit/<id>`; the main form uses `id="form"` and
`action` containing `cases/edit` (reference dump: `data/testtask-testrail-staging-com-index-php-cases-edit.txt`).

---

## 6. Project structure

```
project/
├── pages/            # Page Objects (BasePage + login/dashboard/project/case/run)
├── components/       # Page Components (BaseComponent + sidebar/header/modal)
├── tests/            # test_00_tc001_valid_login / test_navigation / test_create_test_case
│                     # test_create_test_run / test_execute_run (TASK 2)
│                     # test_end_to_end_flow / test_edge_cases
├── api/              # TestRail API client + Case/Run resource wrappers (+ Status, results)
├── utils/            # logger, waits, screenshot, random_data, report_selector
├── config/           # config.py + credentials.env
├── reports/          # pytest-html + Allure results + allure-report (static HTML) + failure_summary.txt
├── screenshots/      # Failure screenshots
├── logs/             # Execution logs
├── conftest.py       # Fixtures, driver lifecycle, report selection, reporting, cleanup
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## 7. Setup

### Prerequisites

- Python 3.9+
- Google Chrome / Firefox / Edge (drivers via Selenium Manager)
- Allure CLI (optional, for Allure reports): https://allurereport.org/docs/install/

### Install (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Configure

Copy `config/credentials.env.example` to `config/credentials.env` and fill in real values.
The `credentials.env` file is **gitignored** and must never be committed.

Project/suite/section IDs are resolved automatically via the API. Override with
`TESTRAIL_PROJECT_ID`, `TESTRAIL_SUITE_ID`, `TESTRAIL_SECTION_ID` if needed.

Optional tuning:

- `TESTRAIL_API_POLL_AFTER_UI_SECONDS` (default `28`) — poll `get_cases` after UI create when the URL has no `/cases/view/<id>` yet.
- `LOGIN_POST_SUBMIT_WAIT` (default `15`), `LOGIN_FALLBACK_WAIT` (default `8`) — login redirect / fallback timing.
- `TESTRAIL_CONSOLE_LOG_LEVEL` (default `WARNING`) — console verbosity; full `DEBUG` is always in `logs/run_*.log`.
- `TESTRAIL_ALLURE_OPEN` (default enabled) — after Allure static HTML is built, spawn `allure open` in the background. Set `false` to disable locally. Skipped in CI.
- `TESTRAIL_SCREENSHOT_ON_SUCCESS` — attach screenshots for passed tests too (`true`/`false`).

---

## 8. Running tests (Windows PowerShell)

The module `tests/test_00_tc001_valid_login.py` is collected **before** other `tests/test_*.py`
files so **TC-001** runs first in that module, then other login tests, then the rest.

```powershell
# Full suite (interactive report menu unless --report is set; see section 9)
pytest

# By marker
pytest -m smoke
pytest -m positive
pytest -m negative
pytest -m edge
pytest -m e2e
pytest -m execution      # TASK 2 execution / results only

pytest --browser chrome --headless true
pytest -n auto -m smoke
```

### 8.1 Smoke (`TASK 1` + `TASK 2`)

The `smoke` marker includes **TASK 1** (four UI tests: login, project navigation, create case,
create run with that UI-created case) and **TASK 2** (all tests in `tests/test_execute_run.py`,
TC-016 .. TC-026). The `execution` marker remains on the same class so you can run
`pytest -m execution` without the TASK 1 quartet.

**Report type** uses the same rules as a full run (section 9): `--report=html` or `--report=allure`.

```powershell
pytest -m smoke --report=html
pytest -m smoke --report=allure
```

| Area | Tests |
|------|-------|
| TASK 1 (4) | `test_00_tc001_valid_login`, `test_navigate_to_project`, `test_create_test_case_success`, `test_create_test_run_success` |
| TASK 2 (10) | `TestExecuteRun` in `test_execute_run.py` (also marked `execution`) |

---

## 9. Interactive report selection

1. **CLI wins** — `pytest --report=html` or `pytest --report=allure` (works with any selection, e.g. `-m smoke`).
2. **CI** — if `CI`, `GITHUB_ACTIONS`, `JENKINS_URL`, etc. are set, no prompt; **pytest-html** is used.
3. **Non-interactive stdin** — no prompt; **pytest-html**.
4. **Interactive terminal** — menu before tests: `1` pytest-html, `2` Allure (if plugin + CLI available).

Implementation: `pytest_addoption` and `pytest_configure` in `conftest.py`; policy in `utils/report_selector.py`.

---

## 10. Where is my pytest-html report?

- Path pattern: `reports/html/report_YYYYMMDD_HHMMSS.html` (new file each run).
- Logs at session start: `Reporting: pytest-html ENABLED` / `companion pytest-html` when Allure is active.
- At session end: `pytest-html report file: <path>`.
- Screenshots: embedded for failures and (by default) passed `call` when `TESTRAIL_SCREENSHOT_ON_SUCCESS=true`.

---

## 11. Allure (optional)

Install **allure-pytest** (in `requirements.txt`) and the **Allure CLI** on `PATH`.

When Allure mode is active and the CLI is available, the session ends with **`allure generate`**
into `reports/allure-report/`, then **`allure open`** in the background (unless CI or `TESTRAIL_ALLURE_OPEN=false`).

**Do not open `index.html` via `file://`** — the Allure SPA loads JSON with `fetch()`; browsers block that from `file://`, producing **Failed to fetch**. Use `allure open reports/allure-report` or serve the folder over `http://127.0.0.1`.

```powershell
allure serve reports/allure-results
allure open reports/allure-report
```

The directory `reports/allure-report/` may exist empty until generation succeeds; see terminal
lines `Allure static HTML skipped` / `failed` and `logs/run_*.log`.

---

## 12. Reporting and logging

- **Reports**: pytest-html under `reports/html/`, optional Allure under `reports/allure-results/`
  plus static `reports/allure-report/` when the CLI runs `generate`.
- **Failure summary**: if any test fails in the `call` phase, `reports/failure_summary.txt` lists nodeids and short reasons.
- **Failure diagnostics** and `pytest_exception_interact` print trace context to console and log files.
- Locators live in Page Objects / components only — tests stay free of raw selectors.

---

## 13. TASK 2 — extra automation (Test Runs → View → Execute)

Creating a run is only the start; execution and trustworthy results matter. `tests/test_execute_run.py`
covers Passed/Failed/Blocked/Retest, comments, defects, multi-case progress, closing a run, and
persistence after refresh. Most steps use the API for deterministic assertions; TC-016 and TC-026
also exercise the run UI.

**TC-024 note:** closing a run in TestRail is irreversible; the test checks that an *active* run
still accepts new results.

---

## 14. Coverage summary

| Area | Test IDs | Files |
|------|----------|-------|
| Login | TC-001, 007, 008, 009 | `test_00_tc001_valid_login.py` |
| Navigation | TC-002 | `test_navigation.py` |
| Test Case | TC-003, 004, 010, 011, 012 | `test_create_test_case.py` |
| Test Run | TC-005, 006, 013, 014, 015 | `test_create_test_run.py` |
| End-to-end | E2E | `test_end_to_end_flow.py` |
| Execution (TASK 2) | TC-016 … TC-026 | `test_execute_run.py` |
| Edge cases | long/special/unicode/rapid/refresh | `test_edge_cases.py` |

---

## 15. Locators

TestRail markup can differ between releases. Locators use resilient multi-selector CSS and
text-based XPath fallbacks. Adjust them in the relevant Page Object or component if your instance differs.
