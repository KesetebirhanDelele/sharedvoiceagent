"""The shared voice caller: (1) check the contact may be called, (2) write the four GHL fields, (3) read the call back.

The field write IS the call (a GHL workflow reacts to a change in `call_facts`), so every write passes the gates and, in
live mode, is limited to the allowlisted test contacts. A successful write means "handed to GHL", not "the call happened"."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from .analysis import CallAnalysis, analyze, parse_transcript
from .config import Config
from .gates import check, dnd_blocks_calls
from .ghl_api import GhlApi, GhlError
from .ledger import Ledger, utcnow
from .request import CallRequest, facts_with_reference, new_reference

logger = logging.getLogger(__name__)


@dataclass
class Attempt:
    status: str                       # handed_to_ghl | shadow | refused | invalid | error
    contact_id: str
    reference: str = ""
    written_at: str = ""              # ISO time of the write; the call log search starts here
    reasons: list[str] = field(default_factory=list)
    payload_preview: dict = field(default_factory=dict)   # field labels -> character counts (never the text)
    verified_written: bool | None = None


@dataclass
class CallResult:
    found: bool
    call_id: str = ""
    created_at: str = ""
    duration_seconds: int | None = None
    summary: str = ""
    transcript: list[tuple[str, str]] = field(default_factory=list)
    analysis: CallAnalysis = field(default_factory=CallAnalysis)
    contact_do_not_call: bool = False   # tag or Call DND present AFTER the call (the stop-request check)
    note: str = ""


class VoiceCallService:
    def __init__(self, cfg: Config, api: GhlApi, ledger: Ledger, *, clock: Callable[[], datetime] = utcnow,
                 sleep: Callable[[float], None] = time.sleep):
        self.cfg, self.api, self.ledger, self._clock, self._sleep = cfg, api, ledger, clock, sleep

    # -- 1 + 2: gate, then write ---------------------------------------------------------------------------
    def request_call(self, req: CallRequest, *, idempotency_key: str = "") -> Attempt:
        now = self._clock()
        bad = req.problems(self.cfg.max_field_chars)
        if bad:
            return self._record(Attempt("invalid", req.contact_id, reasons=bad), req, now)
        if idempotency_key and self.ledger.has_key(idempotency_key):
            return Attempt("refused", req.contact_id, reasons=["duplicate_request"])
        try:
            self.cfg.validate_for_reads()
            contact = self.api.get_contact(req.contact_id)
            reasons = check(contact, req.contact_id, self.cfg, self.ledger, now)
            if reasons:
                return self._record(Attempt("refused", req.contact_id, reasons=reasons), req, now)
            ids = self._resolve_field_ids()
        except (GhlError, ValueError) as exc:
            return self._record(Attempt("error", req.contact_id, reasons=[f"{type(exc).__name__}: {exc}"[:200]]), req, now)

        ref = new_reference(now)
        values = {"purpose": req.purpose, "organization": req.organization, "script": req.script,
                  "facts": facts_with_reference(req.facts, ref)}
        order = ["purpose", "organization", "script", "facts"]          # facts LAST: it starts the workflow
        payload = [{"id": ids[k], "value": values[k]} for k in order]
        preview = {self.cfg.field_labels[k]: len(values[k]) for k in order}

        if not self.cfg.live:
            logger.info("SHADOW: would write %s to contact %s (no GHL write)", preview, req.contact_id)
            return self._record(Attempt("shadow", req.contact_id, ref, payload_preview=preview), req, now)
        try:
            self.cfg.validate_for_live()
            written_at = self._clock()
            self.api.update_custom_fields(req.contact_id, payload)
            verified = self._verify(req.contact_id, ids["facts"], values["facts"])
        except (GhlError, ValueError) as exc:
            return self._record(Attempt("error", req.contact_id, ref, reasons=[f"{type(exc).__name__}: {exc}"[:200]]), req, now)
        att = Attempt("handed_to_ghl", req.contact_id, ref, written_at.isoformat(), payload_preview=preview,
                      verified_written=verified)
        return self._record(att, req, now, idempotency_key=idempotency_key)

    def _resolve_field_ids(self) -> dict[str, str]:
        fields = self.api.get_location_fields()
        ids: dict[str, str] = {}
        missing = []
        for key, label in self.cfg.field_labels.items():
            found = next((f.get("id") for f in fields if label in (f.get("name"), f.get("fieldKey"),
                          str(f.get("fieldKey", "")).split(".")[-1])), None)
            if found:
                ids[key] = found
            else:
                missing.append(label)
        if missing:
            raise ValueError("custom fields not found in GHL: " + ", ".join(missing))
        return ids

    def _verify(self, contact_id: str, facts_field_id: str, expected: str) -> bool:
        """Read the contact back: a 200 from the write is not proof that the value landed (or was not cut short)."""
        contact = self.api.get_contact(contact_id)
        for f in contact.get("customFields", []):
            if f.get("id") == facts_field_id:
                return str(f.get("value", "")) == expected
        return False

    def _record(self, att: Attempt, req: CallRequest, now: datetime, idempotency_key: str = "") -> Attempt:
        self.ledger.append({
            "at": now.isoformat(), "contact_id": att.contact_id, "status": att.status, "reference": att.reference,
            "reasons": att.reasons, "requested_by": req.requested_by, "purpose_chars": len(req.purpose),
            "idempotency_key": idempotency_key, "verified_written": att.verified_written,
        })
        return att

    # -- 3: read the call back -----------------------------------------------------------------------------
    def fetch_result(self, att: Attempt, req: CallRequest | None = None, *, wait_seconds: int = 600,
                     poll_seconds: int = 15) -> CallResult:
        """Find the Voice AI call logged for this contact after the write. Polls until it appears or time runs out."""
        if att.status != "handed_to_ghl" or not att.written_at:
            return CallResult(False, note=f"nothing to fetch: attempt status is {att.status}")
        since = datetime.fromisoformat(att.written_at) - timedelta(seconds=5)
        deadline = self._clock() + timedelta(seconds=wait_seconds)
        while True:
            log = self._find_log(att.contact_id, since)
            if log is not None:
                return self._build_result(log, att, req)
            if self._clock() >= deadline:
                return CallResult(False, note="no call log yet; the call may not have started, or GHL is slow. Fetch again later.")
            self._sleep(poll_seconds)

    def _find_log(self, contact_id: str, since: datetime) -> dict | None:
        for log in self.api.list_voice_call_logs(contact_id):
            try:
                created = datetime.fromisoformat(str(log.get("createdAt", "")).replace("Z", "+00:00"))
            except ValueError:
                continue
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created >= since:
                return log
        return None

    def _build_result(self, log: dict, att: Attempt, req: CallRequest | None) -> CallResult:
        lines = parse_transcript(log.get("transcript"))
        analysis = analyze(lines, confirm_marker=self.cfg.confirm_marker,
                           sensitive_phrases=req.sensitive_phrases if req else (), reference=att.reference)
        dnc = False
        try:
            c = self.api.get_contact(att.contact_id)
            tags = {str(t).lower() for t in (c.get("tags") or [])}
            dnc = dnd_blocks_calls(c) or bool(tags & {t.lower() for t in self.cfg.opt_out_tags})
        except GhlError:
            pass
        dur = log.get("duration")
        return CallResult(True, str(log.get("id", "")), str(log.get("createdAt", "")),
                          int(dur) if isinstance(dur, (int, float)) else None, str(log.get("summary") or ""),
                          lines, analysis, dnc)
