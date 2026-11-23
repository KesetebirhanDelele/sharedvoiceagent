# Spec: shared voice caller (stand-alone package)

Status: built 2026-11-23, NOT yet run against a live GHL account. Related: `directives/spec/53_shared_voice_agent_test_plan.md` (the GHL-side test plan and the call checklist).

## 1. Problem statement
Ali's enterprise agents (admissions, scheduling, travel offers and others) need to place an outbound AI voice call to a person
for their own purpose. One shared GHL Voice AI agent does the talking. This package is the part that asks for the call and
reads the outcome. Inputs: a `CallRequest` (GHL contact id, purpose, organization, script, facts). Outputs: an `Attempt`
(shadow / refused / handed_to_ghl / error) and later a `CallResult` (transcript, summary, duration, readings).
Out of scope: the GHL agent prompt (lives in GHL; copy in `agent_prompt.md`), content scanning of facts, an approval hold for
a human (Ali's apps add that in front of this), multi-process locking, anything touching Cora's campaigns.

## 2. Acceptance criteria
| # | Behaviour | Proof |
|---|---|---|
| 1 | Default mode writes nothing and returns `shadow` with character counts only | test_shadow_writes_nothing_and_records_it |
| 2 | Live needs both switches AND an allowlisted contact | config tests, test_live_refuses_a_contact_outside_the_allowlist |
| 3 | Live write sends four fields in one update with `call_facts` last, then reads it back | test_live_writes_four_fields_with_facts_last_and_verifies |
| 4 | A cut-short value is reported (`verified_written` false) | test_truncated_write_is_detected |
| 5 | Call DND, opt-out tag, no phone, unknown timezone, outside 8-20 local, second call same day, 14-in-14: no write | gate tests |
| 6 | Replaying the same idempotency key writes nothing | same test as 3 |
| 7 | A missing GHL field or unknown contact is an `error`, never a write | two tests |
| 8 | Fetch only returns a call created after the write | test_fetch_ignores_calls_from_before_the_write |
| 9 | Readings: AI disclosure, confirmation asked, plain yes, reference read aloud, stop request, details spoken (wrong person / voicemail) | analysis tests |
| 10 | The three example scenarios are valid requests | scenario tests |

## 3. Constraints
Musts: shadow by default; fail closed on unknown timezone or phone; only the four fields are written; secrets and phone numbers never
printed or stored; ledger stores contact ids only; the write is the call, so every write passes the gates.
Must-nots: no raw phone numbers as the target; no import from the Cora app; no call to any contact outside the allowlist in live mode;
no GHL DND changes (the workflow adds the do-not-call tag on a stop request).
Escalation (stop and tell Ali/Kes): a gate is bypassed; `verified_written` false (length limit?); the reference is read aloud; details are
spoken to a wrong person or on a voicemail; the workflow fires for any other contact.

## 4. How another agent uses it
```python
from sharedvoiceagent import ...  # (import path: sharedvoiceagent.service / .request / .config / .ghl_api / .ledger)
cfg = Config.from_env(); svc = VoiceCallService(cfg, GhlApi(cfg), Ledger(cfg.ledger_path))
att = svc.request_call(CallRequest(contact_id=..., purpose=..., organization=..., script=..., facts=...), idempotency_key="appt-123")
result = svc.fetch_result(att, wait_seconds=600)
```
Three worked examples (doctor appointment confirmation, AI course offer, vacation destination offers) are in `scenarios.py`.

## 5. Decomposition
(1) config + client + ledger; (2) gates; (3) request + reference; (4) service write path; (5) fetch + analysis; (6) CLI + scenarios;
(7) GHL-side setup by Kes (fields, agent, workflow pinned to the test contact); (8) live test calls 1 to 3 plus a stop request.

## 6. Open items (UNVERIFIED until a live call)
1. Exact field names in the Voice AI call log for a workflow-started call (the code expects `id`, `createdAt`, `duration`, `summary`, `transcript` as the Cora repo's spec/35 observed).
2. Maximum stored length of a Multi line custom field (default limit here is 4,000 characters; `verified_written` catches truncation).
3. Whether Voice AI honours Call DND. Do not assume it. Put an If/Else at the start of the workflow that exits on Call DND or an opt-out tag, and test it.
4. Whether the call log appears within the 10-minute default wait.
5. Custom-field value matching: the field is found by name or key `call_*`; confirm the keys match exactly after creation.
6. Two GHL limits are enforced from our own ledger (1 a day, 14 in 14 days); GHL's own counters are separate and not read.
