"""Turn a GHL Voice AI call log into a plain result. Rules only, no AI. Every field is a READING of the transcript, so a
person still checks the transcript lines for the test-call checklist; these flags tell you where to look."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_SPEAKER = re.compile(r"^\s*(human|bot)\s*:\s*(.*)$", re.IGNORECASE)
_AI_WORDS = re.compile(r"\b(ai|a\.i\.|artificial intelligence|virtual assistant|automated)\b", re.IGNORECASE)
_YES = re.compile(r"\b(yes|yeah|yep|yup|correct|sure|i did|i do|i got it|got it)\b", re.IGNORECASE)
_STOP = re.compile(
    r"\b(stop calling|don'?t call|do not call|take me off|remove me|unsubscribe|never call|quit calling)\b", re.IGNORECASE)
_REF = re.compile(r"\bSVC-\d{8,14}-[0-9a-f]{4,}\b", re.IGNORECASE)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def parse_transcript(raw: str | None) -> list[tuple[str, str]]:
    """'human: hi\\nbot: hello' -> [('human','hi'),('bot','hello')]. Lines with no speaker continue the previous line."""
    lines: list[tuple[str, str]] = []
    for line in (raw or "").splitlines():
        m = _SPEAKER.match(line)
        if m:
            lines.append((m.group(1).lower(), m.group(2).strip()))
        elif line.strip() and lines:
            sp, txt = lines[-1]
            lines[-1] = (sp, f"{txt} {line.strip()}".strip())
    return lines


@dataclass
class CallAnalysis:
    outcome: str = "no_conversation"   # confirmed | stop_request | no_confirmation | no_answer_or_voicemail | no_conversation
    human_spoke: bool = False
    ai_disclosed_first: bool = False
    confirmation_asked: bool = False
    confirmed_yes: bool = False
    stop_requested: bool = False
    reference_read_aloud: bool = False
    leaked_phrases: list[str] = field(default_factory=list)
    candidate_confirmation_line: str = ""
    bot_line_count: int = 0
    human_line_count: int = 0


def analyze(transcript: list[tuple[str, str]], *, confirm_marker: str, sensitive_phrases: tuple[str, ...] = (),
            reference: str = "") -> CallAnalysis:
    a = CallAnalysis()
    bot = [t for s, t in transcript if s == "bot"]
    human = [t for s, t in transcript if s == "human" and t.strip()]
    a.bot_line_count, a.human_line_count = len(bot), len(human)
    a.human_spoke = bool(human)
    if not transcript:
        return a
    first_bot = next((t for s, t in transcript if s == "bot"), "")
    a.ai_disclosed_first = bool(_AI_WORDS.search(first_bot))
    marker = _norm(confirm_marker)
    asked_at = next((i for i, (s, t) in enumerate(transcript) if s == "bot" and marker and marker in _norm(t)), None)
    a.confirmation_asked = asked_at is not None
    if asked_at is not None:
        reply = next((t for s, t in transcript[asked_at + 1:] if s == "human" and t.strip()), "")
        if reply and _YES.search(reply):
            a.confirmed_yes = True
            a.candidate_confirmation_line = reply
    a.stop_requested = any(_STOP.search(t) for t in human)
    bot_text = " ".join(bot)
    a.reference_read_aloud = bool(_REF.search(bot_text)) or (bool(reference) and reference.lower() in bot_text.lower())
    low = bot_text.lower()
    a.leaked_phrases = [p for p in sensitive_phrases if p and p.lower() in low]
    if a.stop_requested:
        a.outcome = "stop_request"
    elif a.confirmed_yes:
        a.outcome = "confirmed"
    elif not a.human_spoke:
        a.outcome = "no_answer_or_voicemail"
    else:
        a.outcome = "no_confirmation"
    return a
