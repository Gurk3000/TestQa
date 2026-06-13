"""Test Case resource client (thin domain layer over TestRailClient)."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from api.testrail_client import TestRailClient
from utils.logger import get_logger

logger = get_logger("api.case")


class CaseAPI:
    """CRUD-ish helpers for TestRail test cases."""

    def __init__(self, client: TestRailClient):
        self._client = client

    def get_cases(self, project_id: int, suite_id: Optional[int] = None) -> List[Dict[str, Any]]:
        endpoint = f"get_cases/{project_id}"
        if suite_id:
            endpoint += f"&suite_id={suite_id}"
        # Bulk GET: returns max 250/page -> follow offsets for the FULL list.
        return self._client.get_collection(endpoint, "cases")

    def find_case_by_title_via_filter(
        self, project_id: int, title: str, suite_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Server-side title filter (get_cases &filter=) to avoid scanning all pages.

        TestRail's `filter` matches a substring in the title, so we still verify
        an exact match locally. Falls back silently to None on unsupported builds.
        """
        from urllib.parse import quote

        endpoint = f"get_cases/{project_id}"
        if suite_id:
            endpoint += f"&suite_id={suite_id}"
        endpoint += f"&filter={quote(title)}"
        try:
            for case in self._client.get_collection(endpoint, "cases"):
                if case.get("title") == title:
                    return case
        except Exception as exc:  # noqa: BLE001 - filter is an optimization only
            logger.debug("get_cases filter lookup failed (%s); will scan pages", exc)
        return None

    def get_case(self, case_id: int) -> Dict[str, Any]:
        return self._client.get(f"get_case/{case_id}")

    def add_case(self, section_id: int, title: str, **fields: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"title": title, **fields}
        logger.info("API add_case section=%s title=%s", section_id, title)
        return self._client.post(f"add_case/{section_id}", payload)

    def find_case_by_title(
        self, project_id: int, title: str, suite_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        # Fast path: server-side title filter (cheap even with >250 cases).
        hit = self.find_case_by_title_via_filter(project_id, title, suite_id)
        if hit:
            return hit
        # Fallback: full paginated scan (handles builds without `filter`).
        if suite_id:
            for case in self.get_cases(project_id, suite_id):
                if case.get("title") == title:
                    return case
        for case in self.get_cases(project_id, None):
            if case.get("title") == title:
                return case
        return None

    def wait_for_case_by_title(
        self,
        project_id: int,
        title: str,
        suite_id: Optional[int] = None,
        *,
        timeout_seconds: float = 30.0,
        interval_seconds: float = 0.35,
    ) -> Optional[Dict[str, Any]]:
        """Poll API until a case with the given title appears (UI save can lag)."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            found = self.find_case_by_title(project_id, title, suite_id)
            if found:
                logger.info("wait_for_case_by_title: found case id=%s title=%r", found.get("id"), title)
                return found
            time.sleep(interval_seconds)
        logger.warning("wait_for_case_by_title: timeout title=%r", title)
        return None

    def case_exists(self, project_id: int, title: str, suite_id: Optional[int] = None) -> bool:
        return self.find_case_by_title(project_id, title, suite_id) is not None

    def delete_case(self, case_id: int) -> None:
        logger.info("API delete_case id=%s", case_id)
        self._client.post(f"delete_case/{case_id}")
