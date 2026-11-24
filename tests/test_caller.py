"""Tests for the shared voice caller. No network, no real calls: GHL is replaced by httpx.MockTransport."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest

from sharedvoiceagent.analysis import analyze, parse_transcript
from sharedvoiceagent.config import Config
from sharedvoiceagent.ghl_api import GhlApi
from sharedvoiceagent.ledger import Ledger
from sharedvoiceagent.request import CallRequest, facts_with_reference, new_reference
from sharedvoiceagent.scenarios import SCENARIOS, build
from sharedvoiceagent.service import VoiceCallService

NOON_CT = datetime(2026, 11, 23, 18, 0, tzinfo=timezone.utc)   # 12:00 in America/Chicago
NIGHT_CT = datetime(2026, 11, 24, 4, 0, tzinfo=timezone.utc)   # 22:00 in America/Chicago
FIELDS = [{"id": f"id-{k}", "name": k, "fieldKey": f"contact.{k}"}
          for k in ("call_purpose", "call_organization", "call_script", "call_facts")]
MARKER = "Can you confirm you got this information? Please just say yes."


def contact(**over):
    c = {"id": "C1", "phone": "+15125550100", "timezone": "America/Chicago", "tags": [], "customFields": []}
    c.update(over)
    return c


class FakeGhl:
    """Records requests; PUT stores the written custom fields so a later GET reads them back."""

    def __init__(self, contact_data, logs=None, truncate=False):
        self.contact, self.logs, self.truncate, self.requests = contact_data, logs or [], truncate, []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.requests.append((req.method, req.url.path, req.content))
        if req.method == "PUT":
            body = json.loads(req.content)
            fields = body["customFields"]
            if self.truncate:
                fields = [{**f, "value": f["value"][:5]} for f in fields]
            self.contact = {**self.contact, "customFields": fields}
            return httpx.Response(200, json={})
        if req.url.path.endswith("/customFields"):
            return httpx.Response(200, json={"customFields": FIELDS})
        if req.url.path == "/voice-ai/dashboard/call-logs":
            return httpx.Response(200, json={"callLogs": self.logs})
        return httpx.Response(200, json={"contact": self.contact})

    def writes(self):
        return [r for r in self.requests if r[0] == "PUT"]


def make(tmp_path, fake, *, live=False, now=NOON_CT, **cfg_over):
    cfg = Config(api_key="secret-key-value", location_id="L1", retry_max=0,
                 write_mode="live" if live else "shadow", shadow_log_only=not live,
                 allowed_contact_ids=frozenset({"C1"}), ledger_path=str(tmp_path / "ledger.jsonl"), **cfg_over)
    api = GhlApi(cfg, http=httpx.Client(base_url=cfg.base_url, transport=httpx.MockTransport(fake)), sleep=lambda s: None)
    return VoiceCallService(cfg, api, Ledger(cfg.ledger_path), clock=lambda: now, sleep=lambda s: None), cfg


def req(**over):
    base = dict(contact_id="C1", purpose="confirm an appointment", organization="Example Clinic",
                script="Ask if the time works.", facts="Appointment Tuesday 2:30 PM.", requested_by="test")
    base.update(over)
    return CallRequest(**base)


# ---- config safety ---------------------------------------------------------------------------------------------------

def test_default_is_shadow_and_secret_is_not_in_repr():
    cfg = Config(api_key="topsecret")
    assert not cfg.live and "topsecret" not in repr(cfg)


@pytest.mark.parametrize("mode,shadow_only,live", [("live", True, False), ("shadow", False, False), ("live", False, True)])
def test_live_needs_both_switches(mode, shadow_only, live):
    assert Config(write_mode=mode, shadow_log_only=shadow_only).live is live


def test_live_without_allowlist_is_refused():
    with pytest.raises(ValueError):
        Config(api_key="k", location_id="L", write_mode="live", shadow_log_only=False).validate_for_live()


def test_from_env_defaults_to_shadow():
    cfg = Config.from_env({"GHL_API_KEY": "k", "GHL_LOCATION_ID": "L"})
    assert not cfg.live and cfg.write_mode == "shadow" and cfg.shadow_log_only


# ---- request ---------------------------------------------------------------------------------------------------------

def test_reference_is_unique_and_appended_to_facts():
    a, b = new_reference(), new_reference()
    assert a != b
    assert a in facts_with_reference("facts", a) and "never read aloud" in facts_with_reference("facts", a)


def test_request_validation():
    assert req().problems(4000) == []
    assert any("facts" in p for p in req(facts=" ").problems(4000))
    assert any("longer" in p for p in req(script="x" * 50).problems(10))


# ---- shadow mode -----------------------------------------------------------------------------------------------------

def test_shadow_writes_nothing_and_records_it(tmp_path):
    fake = FakeGhl(contact())
    svc, _ = make(tmp_path, fake)
    att = svc.request_call(req())
    assert att.status == "shadow" and fake.writes() == []
    assert set(att.payload_preview) == {"call_purpose", "call_organization", "call_script", "call_facts"}
    assert "Tuesday" not in json.dumps(att.payload_preview)        # character counts only, never the text


# ---- live mode -------------------------------------------------------------------------------------------------------

def test_live_writes_four_fields_with_facts_last_and_verifies(tmp_path):
    fake = FakeGhl(contact())
    svc, _ = make(tmp_path, fake, live=True)
    att = svc.request_call(req(), idempotency_key="k1")
    assert att.status == "handed_to_ghl" and att.verified_written is True
    (_, _, body), = fake.writes()
    ids = [f["id"] for f in json.loads(body)["customFields"]]
    assert ids == ["id-call_purpose", "id-call_organization", "id-call_script", "id-call_facts"]
    assert att.reference in json.loads(body)["customFields"][-1]["value"]
    assert svc.request_call(req(), idempotency_key="k1").reasons == ["duplicate_request"]   # replay is safe
    assert len(fake.writes()) == 1


def test_truncated_write_is_detected(tmp_path):
    svc, _ = make(tmp_path, FakeGhl(contact(), truncate=True), live=True)
    assert svc.request_call(req()).verified_written is False


def test_live_refuses_a_contact_outside_the_allowlist(tmp_path):
    fake = FakeGhl(contact())
    svc, _ = make(tmp_path, fake, live=True)
    att = svc.request_call(req(contact_id="C999"))
    assert att.status == "refused" and "contact_not_in_test_allowlist" in att.reasons and fake.writes() == []


# ---- gates -----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("over,reason", [
    ({"dndSettings": {"Call": {"status": "active"}}}, "call_dnd_active"),
    ({"dnd": True}, "call_dnd_active"),
    ({"tags": ["Do Not Call"]}, "opt_out_tag:do not call"),
    ({"phone": ""}, "no_phone_number"),
    ({"timezone": ""}, "timezone_unknown"),
])
def test_contact_that_must_not_be_called_is_refused(tmp_path, over, reason):
    fake = FakeGhl(contact(**over))
    svc, _ = make(tmp_path, fake, live=True)
    att = svc.request_call(req())
    assert att.status == "refused" and reason in att.reasons and fake.writes() == []


def test_outside_calling_hours_is_refused(tmp_path):
    svc, _ = make(tmp_path, FakeGhl(contact()), live=True, now=NIGHT_CT)
    assert "outside_calling_hours" in svc.request_call(req()).reasons


def test_one_call_per_day(tmp_path):
    fake = FakeGhl(contact())
    svc, _ = make(tmp_path, fake, live=True)
    assert svc.request_call(req()).status == "handed_to_ghl"
    second = svc.request_call(req())
    assert second.status == "refused" and "daily_limit_reached" in second.reasons and len(fake.writes()) == 1


def test_missing_field_in_ghl_is_an_error_not_a_write(tmp_path):
    fake = FakeGhl(contact())
    svc, _ = make(tmp_path, fake, live=True, field_script="not_a_real_field")
    att = svc.request_call(req())
    assert att.status == "error" and "not_a_real_field" in att.reasons[0] and fake.writes() == []


def test_unknown_contact_id_is_an_error(tmp_path):
    def handler(r):
        return httpx.Response(404, json={"message": "no"})
    svc, cfg = make(tmp_path, FakeGhl(contact()), live=True)
    svc.api = GhlApi(cfg, http=httpx.Client(base_url=cfg.base_url, transport=httpx.MockTransport(handler)), sleep=lambda s: None)
    assert svc.request_call(req()).status == "error"


# ---- transcript analysis ---------------------------------------------------------------------------------------------

HAPPY = (f"bot: Hello, this is an AI assistant calling for Example Clinic. Am I speaking with Sam?\nhuman: yes\n"
         f"bot: Your appointment is Tuesday.\nbot: {MARKER}\nhuman: Yes\nbot: Thank you, goodbye.")


def test_parse_transcript_joins_continuation_lines():
    assert parse_transcript("bot: hi\nthere\nhuman: hello") == [("bot", "hi there"), ("human", "hello")]
    assert parse_transcript(None) == []


def test_happy_call_is_confirmed_and_ref_not_leaked():
    a = analyze(parse_transcript(HAPPY), confirm_marker=MARKER, sensitive_phrases=("Tuesday",), reference="SVC-20261123-abc123")
    assert (a.outcome, a.ai_disclosed_first, a.confirmation_asked, a.confirmed_yes) == ("confirmed", True, True, True)
    assert a.reference_read_aloud is False and a.candidate_confirmation_line == "Yes"


def test_confirmation_sentence_split_across_lines_is_still_found():
    # Shape of the real 2026-11-24 call: the sentence is split in two bot lines with a person's "Yes." in between.
    raw = ("bot: Hi, this is Colaberry's AI assistant. Am I speaking with Kes?\nhuman: Yes.\n"
           "bot: Your appointment is Tuesday. Does that time still work for you?\n\nCan you confirm\n"
           "human: Yes. Yes.\n"
           "bot: you got this information? Please just say yes.\nhuman: Yes.\n"
           "bot: Perfect, thanks.\nhuman: No. That's all.")
    a = analyze(parse_transcript(raw), confirm_marker=MARKER)
    assert (a.outcome, a.confirmation_asked, a.confirmed_yes) == ("confirmed", True, True)


def test_half_a_confirmation_sentence_is_not_counted():
    t = parse_transcript("bot: I am an AI assistant. Can you confirm\nhuman: Yes.\nbot: Goodbye.")
    a = analyze(t, confirm_marker=MARKER)
    assert (a.confirmation_asked, a.outcome) == (False, "no_confirmation")


def test_reference_read_aloud_is_flagged():
    t = parse_transcript("bot: AI here. Reference SVC-20261123-abc123.\nhuman: ok")
    assert analyze(t, confirm_marker=MARKER, reference="SVC-20261123-abc123").reference_read_aloud is True


def test_stop_request_wins_over_yes():
    t = parse_transcript(f"bot: I am an AI.\nbot: {MARKER}\nhuman: yes, but stop calling me")
    assert analyze(t, confirm_marker=MARKER).outcome == "stop_request"


def test_wrong_person_leak_is_detected_and_clean_call_passes():
    leak = parse_transcript("bot: I'm an AI calling about your appointment with Dr. Rivera.\nhuman: wrong number")
    clean = parse_transcript("bot: I'm an AI assistant. Am I speaking with Sam?\nhuman: wrong number\nbot: Sorry, goodbye.")
    assert analyze(leak, confirm_marker=MARKER, sensitive_phrases=("Dr. Rivera", "appointment")).leaked_phrases == ["Dr. Rivera", "appointment"]
    assert analyze(clean, confirm_marker=MARKER, sensitive_phrases=("Dr. Rivera", "appointment")).leaked_phrases == []


def test_voicemail_means_no_human_lines():
    a = analyze(parse_transcript("bot: Hi, this is an AI assistant for Example Clinic. Please call us back."),
                confirm_marker=MARKER, sensitive_phrases=("appointment",))
    assert a.outcome == "no_answer_or_voicemail" and a.leaked_phrases == []
    assert analyze([], confirm_marker=MARKER).outcome == "no_conversation"


# ---- fetching the result ---------------------------------------------------------------------------------------------

def test_fetch_finds_call_after_write_and_reads_stop_tag(tmp_path):
    log = {"id": "call-1", "createdAt": "2026-11-23T18:01:00.000Z", "duration": 42, "summary": "ok", "transcript": HAPPY}
    fake = FakeGhl(contact(tags=["do not call"]), logs=[log])
    svc, _ = make(tmp_path, fake, live=True)
    att = svc.request_call(req())            # contact has the tag -> refused; build an attempt manually
    assert att.status == "refused"
    from sharedvoiceagent.service import Attempt
    res = svc.fetch_result(Attempt("handed_to_ghl", "C1", "SVC-x", NOON_CT.isoformat()), req(), wait_seconds=0)
    assert res.found and res.call_id == "call-1" and res.duration_seconds == 42 and res.contact_do_not_call is True
    assert res.analysis.outcome == "confirmed"


def test_fetch_ignores_calls_from_before_the_write(tmp_path):
    old = {"id": "old", "createdAt": "2026-11-20T10:00:00Z", "transcript": "bot: hi"}
    svc, _ = make(tmp_path, FakeGhl(contact(), logs=[old]), live=True)
    from sharedvoiceagent.service import Attempt
    assert svc.fetch_result(Attempt("handed_to_ghl", "C1", "r", NOON_CT.isoformat()), wait_seconds=0).found is False


def test_fetch_of_shadow_attempt_does_nothing(tmp_path):
    svc, _ = make(tmp_path, FakeGhl(contact()))
    att = svc.request_call(req())
    assert svc.fetch_result(att).found is False


# ---- scenarios -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", SCENARIOS)
def test_each_scenario_is_a_valid_request(name):
    r = build(name, "C1", "Sam")
    assert r.problems(4000) == [] and r.sensitive_phrases and "Sam" in r.facts
    assert r.organization.strip()


def test_unknown_scenario_is_rejected():
    with pytest.raises(ValueError):
        build("nope", "C1")
