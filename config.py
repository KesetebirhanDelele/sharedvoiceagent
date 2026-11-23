"""Settings for the shared voice caller. Read from environment variables only; nothing is hard-coded and no secret is ever
printed. Safe by default: SHADOW mode (no GHL write, no call) unless BOTH live switches are set and the contact is allowed."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping

DEFAULT_OPT_OUT_TAGS = (
    "do not call", "do not call again", "do not contact", "not interested", "dnc", "stop",
)


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv(value: str | None) -> tuple[str, ...]:
    return tuple(p.strip() for p in (value or "").split(",") if p.strip())


@dataclass(frozen=True)
class Config:
    api_key: str = field(default="", repr=False)  # secret: never shown in repr/logs
    location_id: str = ""
    base_url: str = "https://services.leadconnectorhq.com"
    timeout_seconds: float = 30.0
    retry_max: int = 3
    write_mode: str = "shadow"          # "shadow" | "live"
    shadow_log_only: bool = True        # live needs write_mode == "live" AND this False
    allowed_contact_ids: frozenset[str] = frozenset()  # live writes only ever go to these contacts
    field_purpose: str = "call_purpose"
    field_organization: str = "call_organization"
    field_script: str = "call_script"
    field_facts: str = "call_facts"     # written LAST: its change is what starts the GHL workflow
    opt_out_tags: tuple[str, ...] = DEFAULT_OPT_OUT_TAGS
    window_start_hour: int = 8          # local time of the contact
    window_end_hour: int = 20
    default_timezone: str = ""          # used only when the contact has no timezone; blank = block (fail closed)
    max_calls_per_day: int = 1          # per phone number (GHL limit: 1/day)
    max_calls_14_days: int = 14         # GHL limit: 14 in 14 days
    max_field_chars: int = 4000         # UNVERIFIED: GHL's real limit for a Multi line field is not confirmed
    ledger_path: str = "sharedvoiceagent/ledger.jsonl"
    confirm_marker: str = "Can you confirm you got this information? Please just say yes."

    @property
    def live(self) -> bool:
        return self.write_mode == "live" and not self.shadow_log_only

    @property
    def field_labels(self) -> dict[str, str]:
        return {
            "purpose": self.field_purpose,
            "organization": self.field_organization,
            "script": self.field_script,
            "facts": self.field_facts,
        }

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Config":
        e = os.environ if env is None else env
        d = cls()
        return cls(
            api_key=e.get("GHL_API_KEY", ""),
            location_id=e.get("GHL_LOCATION_ID", ""),
            base_url=e.get("GHL_BASE_URL", d.base_url),
            timeout_seconds=float(e.get("SVC_TIMEOUT_SECONDS", d.timeout_seconds)),
            retry_max=int(e.get("SVC_RETRY_MAX", d.retry_max)),
            write_mode=e.get("SVC_WRITE_MODE", d.write_mode).strip().lower(),
            shadow_log_only=_bool(e.get("SVC_SHADOW_LOG_ONLY"), True),
            allowed_contact_ids=frozenset(_csv(e.get("SVC_ALLOWED_CONTACT_IDS"))),
            field_purpose=e.get("SVC_FIELD_PURPOSE", d.field_purpose),
            field_organization=e.get("SVC_FIELD_ORGANIZATION", d.field_organization),
            field_script=e.get("SVC_FIELD_SCRIPT", d.field_script),
            field_facts=e.get("SVC_FIELD_FACTS", d.field_facts),
            opt_out_tags=tuple(t.lower() for t in _csv(e.get("SVC_OPT_OUT_TAGS"))) or d.opt_out_tags,
            window_start_hour=int(e.get("SVC_WINDOW_START_HOUR", d.window_start_hour)),
            window_end_hour=int(e.get("SVC_WINDOW_END_HOUR", d.window_end_hour)),
            default_timezone=e.get("SVC_DEFAULT_TIMEZONE", d.default_timezone),
            max_calls_per_day=int(e.get("SVC_MAX_CALLS_PER_DAY", d.max_calls_per_day)),
            max_calls_14_days=int(e.get("SVC_MAX_CALLS_14_DAYS", d.max_calls_14_days)),
            max_field_chars=int(e.get("SVC_MAX_FIELD_CHARS", d.max_field_chars)),
            ledger_path=e.get("SVC_LEDGER_PATH", d.ledger_path),
            confirm_marker=e.get("SVC_CONFIRM_MARKER", d.confirm_marker),
        )

    def validate_for_reads(self) -> None:
        if not self.api_key or not self.location_id:
            raise ValueError("GHL_API_KEY and GHL_LOCATION_ID must be set (values are never printed)")

    def validate_for_live(self) -> None:
        self.validate_for_reads()
        if not self.live:
            raise ValueError("live writes need SVC_WRITE_MODE=live AND SVC_SHADOW_LOG_ONLY=false")
        if not self.allowed_contact_ids:
            raise ValueError("live writes need SVC_ALLOWED_CONTACT_IDS (the test contact ids)")
