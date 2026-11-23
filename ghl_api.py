"""Minimal, self-contained GoHighLevel client (no imports from the Cora app). Only the calls this package needs."""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from .config import Config

logger = logging.getLogger(__name__)
_RETRYABLE = frozenset({429, 500, 502, 503, 504})
_MIN_INTERVAL = 0.2  # about 5 requests per second, the rate found safe elsewhere


class GhlError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _disguised_timeout(resp: httpx.Response) -> bool:
    """GHL sometimes reports its own timeout as HTTP 401 with body 'Command timed out'. Only that shape is retried."""
    try:
        body = resp.json()
    except ValueError:
        return False
    return isinstance(body, dict) and body.get("statusCode") == 401 and "timed out" in str(body.get("message", "")).lower()


class GhlApi:
    def __init__(self, cfg: Config, http: httpx.Client | None = None, sleep=time.sleep):
        self.cfg = cfg
        self._sleep = sleep
        self._last = 0.0
        self._http = http or httpx.Client(base_url=cfg.base_url, timeout=cfg.timeout_seconds)

    def _request(self, method: str, path: str, **kw: Any) -> Any:
        headers = {"Authorization": f"Bearer {self.cfg.api_key}", "Content-Type": "application/json",
                   "Accept": "application/json", "Version": "2021-07-28"}
        for attempt in range(self.cfg.retry_max + 1):
            gap = _MIN_INTERVAL - (time.monotonic() - self._last)
            if gap > 0:
                self._sleep(gap)
            self._last = time.monotonic()
            try:
                resp = self._http.request(method, path, headers=headers, **kw)
            except httpx.TimeoutException as exc:
                if attempt < self.cfg.retry_max:
                    self._sleep(2 ** attempt)
                    continue
                raise GhlError(f"GHL timed out: {method} {path}") from exc
            if resp.status_code in _RETRYABLE or (resp.status_code == 401 and _disguised_timeout(resp)):
                if attempt < self.cfg.retry_max:
                    logger.warning("GHL transient error status=%s path=%s attempt=%s", resp.status_code, path, attempt + 1)
                    self._sleep(2 ** attempt)
                    continue
                raise GhlError(f"GHL failed after retries: HTTP {resp.status_code} {path}", resp.status_code)
            if resp.status_code >= 400:
                raise GhlError(f"GHL HTTP {resp.status_code} {path} | {resp.text[:200]}", resp.status_code)
            return resp.json() if resp.content else {}
        raise GhlError(f"GHL retries exhausted: {method} {path}")

    def get_contact(self, contact_id: str) -> dict:
        result = self._request("GET", f"/contacts/{contact_id}")
        return result.get("contact", result)

    def search_contact_by_phone(self, phone: str) -> dict | None:
        """Look up by E.164 phone. Phone numbers are never logged."""
        result = self._request("GET", "/contacts/", params={"locationId": self.cfg.location_id, "query": phone})
        contacts = result.get("contacts", [])
        return contacts[0] if contacts else None

    def get_location_fields(self) -> list[dict]:
        return self._request("GET", f"/locations/{self.cfg.location_id}/customFields").get("customFields", [])

    def update_custom_fields(self, contact_id: str, fields: list[dict]) -> dict:
        """fields: ordered list of {"id": uuid, "value": str}. The order is the order sent."""
        return self._request("PUT", f"/contacts/{contact_id}", json={"customFields": fields})

    def list_voice_call_logs(self, contact_id: str, page_size: int = 10) -> list[dict]:
        """GHL Voice AI call logs for one contact, newest first. Each has id, createdAt, duration, summary and a
        transcript string whose lines start 'human:' or 'bot:' (confirmed in the Cora repo, spec/35)."""
        result = self._request("GET", "/voice-ai/dashboard/call-logs", params={
            "locationId": self.cfg.location_id, "contactId": contact_id, "page": 1, "pageSize": page_size})
        return result.get("callLogs", [])
