"""What another agent supplies to ask for a call, and the unique reference that makes every attempt start the workflow."""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class CallRequest:
    contact_id: str          # the GHL contact to call (the caller never takes a raw phone number)
    purpose: str             # what the call is about, in one short sentence
    organization: str        # who the AI assistant says it is calling on behalf of
    script: str              # extra per-call steps. It can add steps, never override the agent's locked rules
    facts: str               # the facts the agent may state. Anything not here -> "a team member will reach out"
    requested_by: str = ""   # which calling agent asked (for the audit trail)
    sensitive_phrases: tuple[str, ...] = field(default=(), compare=False)  # used only to check wrong-person/voicemail leaks

    def problems(self, max_chars: int) -> list[str]:
        out: list[str] = []
        for name in ("contact_id", "purpose", "organization", "facts"):
            if not getattr(self, name).strip():
                out.append(f"{name} is required")
        for name in ("purpose", "organization", "script", "facts"):
            if len(getattr(self, name)) > max_chars:
                out.append(f"{name} is longer than {max_chars} characters")
        return out


def new_reference(now: datetime | None = None) -> str:
    """A short unique code. Appended to `facts` so the field value differs on every attempt (that change starts the
    workflow). The agent's locked prompt must never read it aloud."""
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d%H%M%S")
    return f"SVC-{stamp}-{secrets.token_hex(3)}"


def facts_with_reference(facts: str, ref: str) -> str:
    return f"{facts.rstrip()}\n\n(Internal reference, never read aloud: {ref})"
