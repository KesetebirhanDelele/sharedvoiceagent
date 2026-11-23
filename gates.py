"""Pre-call checks. Pure functions: given the contact record, the request, the config and the ledger, return the reasons a
call must NOT be made (empty list = clear). GHL does not run these for a field write, so this package must.
Fails CLOSED: anything unknown (no phone, no timezone) blocks the call."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Config
from .ledger import Ledger, days_ago


def _tags(contact: dict) -> set[str]:
    return {str(t).strip().lower() for t in (contact.get("tags") or [])}


def dnd_blocks_calls(contact: dict) -> bool:
    call = (contact.get("dndSettings") or {}).get("Call") or {}
    return str(call.get("status", "")).lower() == "active" or contact.get("dnd") is True


def local_now(contact: dict, cfg: Config, now: datetime) -> datetime | None:
    name = contact.get("timezone") or cfg.default_timezone
    if not name:
        return None
    try:
        return now.astimezone(ZoneInfo(name))
    except (ZoneInfoNotFoundError, ValueError):
        return None


def check(contact: dict, contact_id: str, cfg: Config, ledger: Ledger, now: datetime) -> list[str]:
    """Reasons this call is refused. Each is a short stable code."""
    reasons: list[str] = []
    if cfg.live and contact_id not in cfg.allowed_contact_ids:
        reasons.append("contact_not_in_test_allowlist")
    if not (contact.get("phone") or "").strip():
        reasons.append("no_phone_number")
    if dnd_blocks_calls(contact):
        reasons.append("call_dnd_active")
    hit = _tags(contact) & {t.lower() for t in cfg.opt_out_tags}
    if hit:
        reasons.append("opt_out_tag:" + ",".join(sorted(hit)))
    local = local_now(contact, cfg, now)
    if local is None:
        reasons.append("timezone_unknown")
    elif not (cfg.window_start_hour <= local.hour < cfg.window_end_hour):
        reasons.append("outside_calling_hours")
    if local is not None:
        start_of_day = local.replace(hour=0, minute=0, second=0, microsecond=0)
        if ledger.live_attempts(contact_id, start_of_day) >= cfg.max_calls_per_day:
            reasons.append("daily_limit_reached")
    if ledger.live_attempts(contact_id, days_ago(now, 14)) >= cfg.max_calls_14_days:
        reasons.append("limit_14_in_14_days_reached")
    return reasons
