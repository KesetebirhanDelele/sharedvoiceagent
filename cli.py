"""Command line: `python -m sharedvoiceagent ...`. Shadow by default. Never prints secrets or phone numbers."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import Config
from .ghl_api import GhlApi
from .ledger import Ledger
from .scenarios import SCENARIOS, build
from .service import Attempt, CallResult, VoiceCallService


def _load_dotenv(path: Path) -> None:
    """Tiny .env reader (optional, so the package needs no extra dependency). Existing environment wins."""
    import os
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _print_attempt(a: Attempt) -> None:
    print(f"status: {a.status}")
    if a.reasons:
        print("reasons: " + "; ".join(a.reasons))
    if a.payload_preview:
        print("fields (characters): " + ", ".join(f"{k}={v}" for k, v in a.payload_preview.items()))
    if a.reference:
        print(f"reference: {a.reference}")
    if a.verified_written is not None:
        print(f"value read back from GHL matches what was written: {a.verified_written}")


def _print_result(r: CallResult, expect: str) -> None:
    if not r.found:
        print(f"no call found: {r.note}")
        return
    a = r.analysis
    print(f"call id: {r.call_id}  at: {r.created_at}  duration: {r.duration_seconds}s")
    print(f"summary: {r.summary}")
    print("--- transcript ---")
    for sp, tx in r.transcript:
        print(f"{sp}: {tx}")
    print("--- readings (check the transcript; these are rules, not judgement) ---")
    print(f"outcome: {a.outcome}")
    print(f"AI disclosed in first agent line: {a.ai_disclosed_first}")
    print(f"confirmation question asked: {a.confirmation_asked}; plain yes captured: {a.confirmed_yes}")
    print(f"reference read aloud (must be False): {a.reference_read_aloud}")
    print(f"stop requested: {a.stop_requested}; do-not-call now set on contact: {r.contact_do_not_call}")
    print(f"details spoken by the agent: {a.leaked_phrases or 'none'}")
    if expect in ("wrong_person", "voicemail"):
        ok = not a.leaked_phrases
        print(f"{expect} check: {'PASS - no details spoken' if ok else 'FAIL - details were spoken'}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sharedvoiceagent")
    p.add_argument("--env-file", default="sharedvoiceagent/.env")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scenarios", help="list the example scenarios")
    for name in ("request", "run"):
        s = sub.add_parser(name, help="gate + write fields" + (" + wait and fetch the call" if name == "run" else ""))
        s.add_argument("--scenario", choices=SCENARIOS, required=True)
        s.add_argument("--contact-id", required=True)
        s.add_argument("--first-name", default="there")
        s.add_argument("--expect", choices=["happy", "wrong_person", "voicemail", "stop"], default="happy")
        if name == "run":
            s.add_argument("--wait", type=int, default=600, help="seconds to wait for the call log")
    f = sub.add_parser("fetch", help="read the latest call for a contact since a time")
    f.add_argument("--contact-id", required=True)
    f.add_argument("--since", required=True, help="ISO time, e.g. 2026-11-23T15:00:00+00:00")
    f.add_argument("--scenario", choices=SCENARIOS, default=None)
    f.add_argument("--expect", choices=["happy", "wrong_person", "voicemail", "stop"], default="happy")
    args = p.parse_args(argv)

    if args.cmd == "scenarios":
        print("\n".join(SCENARIOS))
        return 0
    _load_dotenv(Path(args.env_file))
    cfg = Config.from_env()
    svc = VoiceCallService(cfg, GhlApi(cfg), Ledger(cfg.ledger_path))
    print(f"mode: {'LIVE' if cfg.live else 'SHADOW (no GHL write, no call)'}")

    if args.cmd in ("request", "run"):
        req = build(args.scenario, args.contact_id, args.first_name)
        att = svc.request_call(req)
        _print_attempt(att)
        if args.cmd == "run" and att.status == "handed_to_ghl":
            _print_result(svc.fetch_result(att, req, wait_seconds=args.wait), args.expect)
        return 0 if att.status in ("handed_to_ghl", "shadow") else 2

    if args.cmd == "fetch":
        req = build(args.scenario, args.contact_id) if args.scenario else None
        att = Attempt("handed_to_ghl", args.contact_id, written_at=args.since)
        _print_result(svc.fetch_result(att, req, wait_seconds=0), args.expect)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
