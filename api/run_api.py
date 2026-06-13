"""Test Run resource client (thin domain layer over TestRailClient)."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from api.testrail_client import TestRailClient
from utils.logger import get_logger

logger = get_logger("api.run")


class Status:
    """TestRail built-in result status ids."""

    PASSED = 1
    BLOCKED = 2
    UNTESTED = 3
    RETEST = 4
    FAILED = 5

    NAMES = {
        PASSED: "Passed",
        BLOCKED: "Blocked",
        UNTESTED: "Untested",
        RETEST: "Retest",
        FAILED: "Failed",
    }


class RunAPI:
    """CRUD-ish helpers for TestRail test runs and their tests/results."""

    def __init__(self, client: TestRailClient):
        self._client = client

    def get_runs(self, project_id: int) -> List[Dict[str, Any]]:
        # Bulk GET: max 250/page -> follow offsets for the FULL list.
        return self._client.get_collection(f"get_runs/{project_id}", "runs")

    def get_run(self, run_id: int) -> Dict[str, Any]:
        return self._client.get(f"get_run/{run_id}")

    def add_run(
        self,
        project_id: int,
        name: str,
        suite_id: Optional[int] = None,
        case_ids: Optional[List[int]] = None,
        include_all: bool = False,
        **fields: Any,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"name": name, "include_all": include_all, **fields}
        if suite_id:
            payload["suite_id"] = suite_id
        if case_ids is not None:
            payload["case_ids"] = case_ids
        logger.info("API add_run project=%s name=%s cases=%s", project_id, name, case_ids)
        return self._client.post(f"add_run/{project_id}", payload)

    def find_run_by_name(self, project_id: int, name: str) -> Optional[Dict[str, Any]]:
        for run in self.get_runs(project_id):
            if run.get("name") == name:
                return run
        return None

    def wait_for_run_by_name(
        self,
        project_id: int,
        name: str,
        *,
        timeout_seconds: float = 30.0,
        interval_seconds: float = 0.35,
    ) -> Optional[Dict[str, Any]]:
        """Poll API until a run with the exact name appears (UI redirect can lag)."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            found = self.find_run_by_name(project_id, name)
            if found:
                logger.info("wait_for_run_by_name: found run id=%s name=%r", found.get("id"), name)
                return found
            time.sleep(interval_seconds)
        logger.warning("wait_for_run_by_name: timeout name=%r", name)
        return None

    def run_exists(self, project_id: int, name: str) -> bool:
        return self.find_run_by_name(project_id, name) is not None

    def get_tests(self, run_id: int) -> List[Dict[str, Any]]:
        """Tests are the case instances included in a run (paginated, 250/page)."""
        return self._client.get_collection(f"get_tests/{run_id}", "tests")

    def get_results(self, test_id: int) -> List[Dict[str, Any]]:
        return self._client.get_collection(f"get_results/{test_id}", "results")

    def run_contains_case(self, run_id: int, case_id: int) -> bool:
        return any(test.get("case_id") == case_id for test in self.get_tests(run_id))

    def tests_count(self, run_id: int) -> int:
        return len(self.get_tests(run_id))

    def get_test_id_for_case(self, run_id: int, case_id: int) -> Optional[int]:
        for test in self.get_tests(run_id):
            if test.get("case_id") == case_id:
                return int(test["id"])
        return None

    def get_test_status(self, run_id: int, case_id: int) -> Optional[int]:
        for test in self.get_tests(run_id):
            if test.get("case_id") == case_id:
                return test.get("status_id")
        return None

    # --- Execution / results -------------------------------------------------

    def add_result_for_case(
        self,
        run_id: int,
        case_id: int,
        status_id: int,
        comment: Optional[str] = None,
        defects: Optional[str] = None,
        **fields: Any,
    ) -> Dict[str, Any]:
        """Record an execution result for a case inside a run."""
        payload: Dict[str, Any] = {"status_id": status_id, **fields}
        if comment is not None:
            payload["comment"] = comment
        if defects is not None:
            payload["defects"] = defects
        logger.info(
            "API add_result_for_case run=%s case=%s status=%s(%s)",
            run_id, case_id, status_id, Status.NAMES.get(status_id, "?"),
        )
        return self._client.post(f"add_result_for_case/{run_id}/{case_id}", payload)

    def get_results_for_case(self, run_id: int, case_id: int) -> List[Dict[str, Any]]:
        # Bulk GET: max 250/page. Results are newest-first; the first page holds
        # the latest result, but we page through for completeness.
        return self._client.get_collection(f"get_results_for_case/{run_id}/{case_id}", "results")

    def latest_result_for_case(self, run_id: int, case_id: int) -> Optional[Dict[str, Any]]:
        results = self.get_results_for_case(run_id, case_id)
        return results[0] if results else None

    def is_active(self, run_id: int) -> bool:
        """A run is active while it is not completed (closed)."""
        return not bool(self.get_run(run_id).get("is_completed"))

    def passed_count(self, run_id: int) -> int:
        return int(self.get_run(run_id).get("passed_count", 0))

    def failed_count(self, run_id: int) -> int:
        return int(self.get_run(run_id).get("failed_count", 0))

    def blocked_count(self, run_id: int) -> int:
        return int(self.get_run(run_id).get("blocked_count", 0))

    def retest_count(self, run_id: int) -> int:
        return int(self.get_run(run_id).get("retest_count", 0))

    def untested_count(self, run_id: int) -> int:
        return int(self.get_run(run_id).get("untested_count", 0))

    def close_run(self, run_id: int) -> Dict[str, Any]:
        """Close a run. NOTE: closing is irreversible in TestRail."""
        logger.info("API close_run id=%s", run_id)
        return self._client.post(f"close_run/{run_id}")

    def delete_run(self, run_id: int) -> None:
        logger.info("API delete_run id=%s", run_id)
        self._client.post(f"delete_run/{run_id}")
