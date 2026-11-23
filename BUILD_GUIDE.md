# BUILD_GUIDE.md - how this was built and how to rebuild or extend it

## Architecture (three pieces, only one is code)
1. **Caller (this repo).** Gates the contact, writes four GHL contact fields, reads the value back, later fetches the call log. Code files: `config.py` (env settings, shadow default), `ghl_api.py` (minimal client: retry, the disguised 401 timeout, 5 requests/second), `gates.py` (pure pre-call checks), `ledger.py` (JSON-lines audit and counters), `request.py` (request + unique reference), `service.py` (write path and fetch), `analysis.py` (rule-based readings of the transcript), `scenarios.py` (three fictional examples), `cli.py`.
2. **Workflow (GHL, built by hand).** Trigger: contact custom field `call_facts` changes. First step: exit if Call DND is on or an opt-out tag is present (Voice AI is not known to honour DND). Action: Voice AI Outbound Call using the agent below. A stop-request branch adds the do-not-call tag. Limit it to the test contact(s) until the test passes.
3. **Voice agent (GHL, built by hand).** "Enterprise Outbound Caller v1". Prompt and opening line: `agent_prompt.md`. It speaks only; it never starts calls.

## Build steps in GHL (in order)
1. Create four contact custom fields (Contact object): `call_organization` (single line), `call_purpose`, `call_script`, `call_facts` (all Multi line). The key must equal the name; check in the merge-field picker. (Done 2026-11-22, verified read-only.)
2. Create the voice agent by hand; paste the opening line and prompt from `agent_prompt.md`. Keep the confirmation sentence unchanged.
3. Create the workflow as above; publish it. Check the workflow's execution log after any test.
4. Enable outbound calling under AI Agents, Voice AI (terms or verification may be required). Check the wallet and the per-minute rate in billing: reported $0.06 to $0.215 a minute plus about $0.02 phone (unconfirmed).

## Build the caller from scratch
Python 3.11+ and `httpx`; no other dependency. Keep the package free of imports from the Cora app. Order: config, client, ledger, gates, request, service, analysis, scenarios, CLI, tests. Every write path is shadow by default; live needs two switches and an allowlist. Tests use `httpx.MockTransport`; they never call GHL.

## Settings (environment or the gitignored `.env`; see `.env.example`)
`GHL_API_KEY`, `GHL_LOCATION_ID` (required); `SVC_WRITE_MODE`, `SVC_SHADOW_LOG_ONLY`, `SVC_ALLOWED_CONTACT_IDS` (live gate); field names; window hours; opt-out tags; limits; `SVC_LEDGER_PATH`. Never print or commit values.

## Running a test call
From `C:\Users\keset`: shadow first (`python -m sharedvoiceagent request --scenario doctor --contact-id <ID> --first-name <name>`), then live with the switches set for that run only (`run`, `--expect happy|wrong_person|voicemail|stop`). One call per phone number per day. The 2026-11-23 9 AM Central run is a Windows scheduled task (`SharedVoiceAgent-Test1-Doctor`, script and log in `C:\Users\keset\svc_scheduled\`, outside this repo). Check the log, then compare the transcript with the checklist in Cora's `directives/spec/53_shared_voice_agent_test_plan.md`.

## Extending to a new calling agent
Build a `CallRequest` (contact id, purpose, organization, script steps, facts; `sensitive_phrases` for the wrong-person and voicemail checks), call `request_call(req, idempotency_key=...)` then `fetch_result`. Keep facts short and complete: anything not in the facts is unknown to the voice agent. Add a scenario only as an example; real use is the calling agent's own code.

## Known gaps
No content scan on facts (open question for Ali: suggested his side). No human approval hold (Ali's apps add it in front). One process at a time (local ledger). Voice AI call-log field names, field length limit and DND behaviour unverified until a live call completes.
