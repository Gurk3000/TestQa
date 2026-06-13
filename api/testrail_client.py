"""Low-level TestRail API v2 client.

Wraps the HTTP transport, Basic Auth, retries and JSON (de)serialization.
Acts as the transport layer for the higher-level CaseAPI / RunAPI resource
clients. The API is used as the *source of truth* for validating and cleaning
up entities created through the UI.

TestRail API reference: https://www.gurock.com/testrail/docs/api
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.config import settings
from utils.logger import get_logger

logger = get_logger("api.client")


class TestRailAPIError(RuntimeError):
    """Raised when the TestRail API returns a non-success status code."""

    def __init__(self, status_code: int, message: str, url: str):
        self.status_code = status_code
        self.url = url
        super().__init__(f"TestRail API error {status_code} for {url}: {message}")


class TestRailClient:
    """Authenticated, retrying HTTP client for the TestRail REST API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self._api_base = (base_url or settings.base_url).rstrip("/") + "/index.php?/api/v2"
        self._auth = (email or settings.email, password or settings.api_password)
        self._session = self._build_session()

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.6,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({"Content-Type": "application/json"})
        return session

    def _url(self, endpoint: str) -> str:
        # TestRail endpoints use the form: index.php?/api/v2/<endpoint>
        return f"{self._api_base}/{endpoint.lstrip('/')}"

    def _request(self, method: str, endpoint: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        url = self._url(endpoint)
        logger.debug("API %s %s payload=%s", method, endpoint, payload)
        response = self._session.request(
            method=method,
            url=url,
            json=payload,
            auth=self._auth,
            timeout=30,
        )
        if not response.ok:
            message = response.text[:500]
            logger.error("API %s %s -> %s: %s", method, endpoint, response.status_code, message)
            raise TestRailAPIError(response.status_code, message, url)

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    def get(self, endpoint: str) -> Any:
        return self._request("GET", endpoint)

    def post(self, endpoint: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        return self._request("POST", endpoint, payload or {})

    # --- Pagination (bulk GET endpoints) -------------------------------------
    # Per the TestRail API: bulk GETs (get_cases, get_runs, get_tests,
    # get_results*) return at most 250 records and expose `_links.next` plus
    # `limit`/`offset`. We follow the offset chain so callers always get the
    # FULL collection (otherwise validation could silently miss records > 250).
    PAGE_SIZE = 250

    def get_collection(self, endpoint: str, key: str, page_size: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch every record of a paginated bulk-GET endpoint by walking offsets.

        Falls back gracefully to a single request for older TestRail versions
        that return a bare list or that do not support `limit`/`offset`.
        """
        size = page_size or self.PAGE_SIZE
        items: List[Dict[str, Any]] = []
        offset = 0
        while True:
            paged = f"{endpoint}&limit={size}&offset={offset}"
            try:
                data = self.get(paged)
            except TestRailAPIError:
                # limit/offset unsupported (pre-6.7) or bad page -> single shot.
                if offset == 0:
                    data = self.get(endpoint)
                    if isinstance(data, dict):
                        return data.get(key, []) or []
                    return data or []
                break

            if isinstance(data, list):  # older API: bare list, no pagination
                return data
            if not isinstance(data, dict):
                break

            batch = data.get(key, []) or []
            items.extend(batch)

            links = data.get("_links") or {}
            has_next = bool(links.get("next"))
            # Stop on: explicit end-of-links, empty/short page (final records).
            if not has_next or not batch or len(batch) < size:
                break
            offset += size
        return items

    # --- Generic resource helpers shared by resource clients -----------------

    def get_project(self, project_id: int) -> Dict[str, Any]:
        return self.get(f"get_project/{project_id}")

    def get_projects(self) -> List[Dict[str, Any]]:
        # Newer TestRail paginates projects (250/page); walk all pages.
        return self.get_collection("get_projects", "projects")

    def find_project_id_by_name(self, name: str) -> Optional[int]:
        for project in self.get_projects():
            if project.get("name") == name:
                return int(project["id"])
        return None

    def get_suites(self, project_id: int) -> List[Dict[str, Any]]:
        # get_suites is not offset-paginated, but tolerate both shapes.
        data = self.get(f"get_suites/{project_id}")
        if isinstance(data, dict):
            return data.get("suites", [])
        return data or []

    def get_sections(self, project_id: int, suite_id: Optional[int] = None) -> List[Dict[str, Any]]:
        endpoint = f"get_sections/{project_id}"
        if suite_id:
            endpoint += f"&suite_id={suite_id}"
        # Sections are paginated (250/page) in current TestRail.
        return self.get_collection(endpoint, "sections")

    def add_section(self, project_id: int, name: str, suite_id: Optional[int] = None) -> Dict[str, Any]:
        """Create a section so test cases have a place to be added."""
        payload: Dict[str, Any] = {"name": name}
        if suite_id:
            payload["suite_id"] = suite_id
        logger.info("API add_section project=%s suite=%s name=%s", project_id, suite_id, name)
        return self.post(f"add_section/{project_id}", payload)

    def close(self) -> None:
        self._session.close()
