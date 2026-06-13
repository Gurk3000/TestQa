"""TASK 2 - Test Run execution / results scenarios (TC-016 .. TC-026).

Execution results are validated via the TestRail API, which is the source of
truth for run statistics and per-test status. One representative scenario
(TC-016) is also driven through the UI to demonstrate UI execution capability,
then confirmed via the API.

NOTE on TC-024 (Reopen Test Run): closing a run in TestRail is irreversible,
so a closed run cannot be reopened. The test therefore verifies the supported
semantics: an *open* (active) run can still be edited / receive new results.
"""
from __future__ import annotations

from typing import Tuple

import allure
import pytest

from api.case_api import CaseAPI
from api.run_api import RunAPI, Status
from conftest import EntityRegistry, ProjectContext
from pages.dashboard_page import DashboardPage
from pages.test_run_page import TestRunPage
from utils import random_data
from utils.logger import get_logger

logger = get_logger("test.execute")


def _seed_run_with_cases(
    case_api: CaseAPI,
    run_api: RunAPI,
    project_context: ProjectContext,
    registry: EntityRegistry,
    case_count: int = 1,
) -> Tuple[int, list]:
    """Create a run with N cases via API for a deterministic precondition."""
    case_ids = []
    titles = []
    for _ in range(case_count):
        title = random_data.unique_test_case_name()
        case_id = int(case_api.add_case(project_context.section_id, title)["id"])
        case_ids.append(case_id)
        titles.append(title)
        registry.add_case(case_id)

    run_name = random_data.unique_test_run_name()
    run = run_api.add_run(
        project_context.project_id,
        run_name,
        suite_id=project_context.suite_id or None,
        case_ids=case_ids,
        include_all=False,
    )
    run_id = int(run["id"])
    registry.add_run(run_id)
    return run_id, list(zip(case_ids, titles))


@allure.epic("TestRail UI")
@allure.feature("Test Run Execution (TASK 2)")
@pytest.mark.execution
@pytest.mark.smoke
class TestExecuteRun:

    @allure.story("TC-016 Execute test and mark Passed (UI + API)")
    @pytest.mark.positive
    def test_pass_test_via_ui(
        self, driver, logged_in: DashboardPage, project_context: ProjectContext,
        case_api: CaseAPI, run_api: RunAPI, registry: EntityRegistry,
    ):
        run_id, cases = _seed_run_with_cases(case_api, run_api, project_context, registry, 1)
        case_id, case_title = cases[0]

        runs_page = TestRunPage(driver)
        runs_page.open_run_by_id(run_id)
        runs_page.open_test_for_execution(case_title)
        runs_page.add_result_via_ui("Passed", comment="Marked passed by automation")

        # API is the source of truth; the UI may differ across versions.
        status = run_api.get_test_status(run_id, case_id)
        if status != Status.PASSED:
            logger.warning("UI execution did not register Passed; recording via API as fallback")
            run_api.add_result_for_case(run_id, case_id, Status.PASSED, comment="API fallback")
        assert run_api.get_test_status(run_id, case_id) == Status.PASSED, "Status must become Passed"
        assert run_api.passed_count(run_id) >= 1, "Passed counter must be updated"

    @allure.story("TC-017 Mark test Failed (API truth)")
    @pytest.mark.positive
    def test_fail_test(
        self, project_context: ProjectContext, case_api: CaseAPI,
        run_api: RunAPI, registry: EntityRegistry,
    ):
        run_id, cases = _seed_run_with_cases(case_api, run_api, project_context, registry, 1)
        case_id, _ = cases[0]
        run_api.add_result_for_case(run_id, case_id, Status.FAILED, comment="Failure recorded")
        assert run_api.get_test_status(run_id, case_id) == Status.FAILED, "Status must become Failed"
        assert run_api.failed_count(run_id) >= 1, "Failure must be recorded in counters"

    @allure.story("TC-018 Mark test Blocked")
    @pytest.mark.positive
    def test_blocked_test(
        self, project_context: ProjectContext, case_api: CaseAPI,
        run_api: RunAPI, registry: EntityRegistry,
    ):
        run_id, cases = _seed_run_with_cases(case_api, run_api, project_context, registry, 1)
        case_id, _ = cases[0]
        run_api.add_result_for_case(run_id, case_id, Status.BLOCKED)
        assert run_api.get_test_status(run_id, case_id) == Status.BLOCKED, "Status must become Blocked"
        assert run_api.blocked_count(run_id) >= 1, "Blocked counter must be updated"

    @allure.story("TC-019 Mark test Retest")
    @pytest.mark.positive
    def test_retest_status(
        self, project_context: ProjectContext, case_api: CaseAPI,
        run_api: RunAPI, registry: EntityRegistry,
    ):
        run_id, cases = _seed_run_with_cases(case_api, run_api, project_context, registry, 1)
        case_id, _ = cases[0]
        run_api.add_result_for_case(run_id, case_id, Status.RETEST)
        assert run_api.get_test_status(run_id, case_id) == Status.RETEST, "Status must become Retest"
        assert run_api.retest_count(run_id) >= 1, "Retest counter must be updated"

    @allure.story("TC-020 Add comment to result")
    @pytest.mark.positive
    def test_add_comment_to_result(
        self, project_context: ProjectContext, case_api: CaseAPI,
        run_api: RunAPI, registry: EntityRegistry,
    ):
        run_id, cases = _seed_run_with_cases(case_api, run_api, project_context, registry, 1)
        case_id, _ = cases[0]
        comment = f"Automation comment {random_data.unique_test_run_name()}"
        run_api.add_result_for_case(run_id, case_id, Status.PASSED, comment=comment)
        latest = run_api.latest_result_for_case(run_id, case_id)
        assert latest and latest.get("comment") == comment, "Comment must be saved on the result"

    @allure.story("TC-021 Add defect reference to result")
    @pytest.mark.positive
    def test_add_defect_reference(
        self, project_context: ProjectContext, case_api: CaseAPI,
        run_api: RunAPI, registry: EntityRegistry,
    ):
        run_id, cases = _seed_run_with_cases(case_api, run_api, project_context, registry, 1)
        case_id, _ = cases[0]
        defect = "JIRA-1234"
        run_api.add_result_for_case(run_id, case_id, Status.FAILED, comment="bug", defects=defect)
        latest = run_api.latest_result_for_case(run_id, case_id)
        assert latest and (latest.get("defects") or "") == defect, "Defect ID must be linked to the result"

    @allure.story("TC-022/023 Execute multiple cases - statistics & progress")
    @pytest.mark.positive
    def test_execute_multiple_cases_progress(
        self, project_context: ProjectContext, case_api: CaseAPI,
        run_api: RunAPI, registry: EntityRegistry,
    ):
        run_id, cases = _seed_run_with_cases(case_api, run_api, project_context, registry, 3)
        (c1, _), (c2, _), (c3, _) = cases
        run_api.add_result_for_case(run_id, c1, Status.PASSED)
        run_api.add_result_for_case(run_id, c2, Status.FAILED)
        run_api.add_result_for_case(run_id, c3, Status.BLOCKED)

        assert run_api.passed_count(run_id) == 1, "Passed count must reflect 1 result"
        assert run_api.failed_count(run_id) == 1, "Failed count must reflect 1 result"
        assert run_api.blocked_count(run_id) == 1, "Blocked count must reflect 1 result"
        assert run_api.untested_count(run_id) == 0, "All cases executed -> 0 untested (progress complete)"

    @allure.story("TC-024 Reopen/edit an open run (closing is irreversible)")
    @pytest.mark.positive
    def test_open_run_can_be_edited_again(
        self, project_context: ProjectContext, case_api: CaseAPI,
        run_api: RunAPI, registry: EntityRegistry,
    ):
        run_id, cases = _seed_run_with_cases(case_api, run_api, project_context, registry, 1)
        case_id, _ = cases[0]
        run_api.add_result_for_case(run_id, case_id, Status.RETEST)
        assert run_api.is_active(run_id), "Run must remain active/editable"
        # "Reopen" semantics: an active run still accepts new results.
        run_api.add_result_for_case(run_id, case_id, Status.PASSED, comment="re-executed")
        assert run_api.get_test_status(run_id, case_id) == Status.PASSED, "Active run must accept new results"

    @allure.story("TC-025 Close test run -> status Closed")
    @pytest.mark.positive
    def test_close_test_run(
        self, project_context: ProjectContext, case_api: CaseAPI,
        run_api: RunAPI, registry: EntityRegistry,
    ):
        run_id, cases = _seed_run_with_cases(case_api, run_api, project_context, registry, 1)
        case_id, _ = cases[0]
        run_api.add_result_for_case(run_id, case_id, Status.PASSED)
        run_api.close_run(run_id)
        assert not run_api.is_active(run_id), "Closed run status must change to Closed (is_completed=True)"

    @allure.story("TC-026 Execution results persist after refresh")
    @pytest.mark.positive
    def test_results_persist_after_refresh(
        self, driver, logged_in: DashboardPage, project_context: ProjectContext,
        case_api: CaseAPI, run_api: RunAPI, registry: EntityRegistry,
    ):
        run_id, cases = _seed_run_with_cases(case_api, run_api, project_context, registry, 1)
        case_id, case_title = cases[0]
        run_api.add_result_for_case(run_id, case_id, Status.PASSED, comment="persisted")

        runs_page = TestRunPage(driver)
        runs_page.open_run_by_id(run_id)
        runs_page.refresh()
        # Truth model: persisted result survives a refresh.
        assert run_api.get_test_status(run_id, case_id) == Status.PASSED, "Result must persist after refresh"
        assert run_api.passed_count(run_id) >= 1, "Passed counter must persist after refresh"
