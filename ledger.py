"""Append-only record of every request: an audit trail, the one-call-a-day / 14-in-14-days counters, and the dedupe key.
A plain JSON-lines file, so the package needs no database. Single process: run one caller at a time (documented limit).
Stores contact ids, never phone numbers, never field text."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path


class Ledger:
    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = threading.Lock()

    def _rows(self) -> list[dict]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue  # a torn line must not break the gate
        return rows

    def append(self, row: dict) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, sort_keys=True) + "\n")

    def live_attempts(self, contact_id: str, since: datetime) -> int:
        """Calls actually handed to GHL (status 'handed_to_ghl') for this contact at or after `since`.
        Shadow and refused requests never count."""
        n = 0
        for r in self._rows():
            if r.get("contact_id") != contact_id or r.get("status") != "handed_to_ghl":
                continue
            try:
                t = datetime.fromisoformat(r["at"])
            except (KeyError, ValueError):
                continue
            if t >= since:
                n += 1
        return n

    def seen_reference(self, ref: str) -> bool:
        return any(r.get("reference") == ref for r in self._rows())

    def has_key(self, idempotency_key: str) -> bool:
        return bool(idempotency_key) and any(
            r.get("idempotency_key") == idempotency_key and r.get("status") == "handed_to_ghl" for r in self._rows())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def days_ago(now: datetime, days: int) -> datetime:
    return now - timedelta(days=days)
