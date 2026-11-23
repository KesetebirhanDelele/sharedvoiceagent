# sharedvoiceagent

Stand-alone package (imports nothing from the Cora app) that lets one agent ask the shared GHL outbound voice agent to
place a call, then reads the result back. Terms: the **voice agent** is the GHL Voice AI agent that talks; the **workflow**
in GHL starts it when `call_facts` changes; this package is the **caller** that gates, writes the four fields and fetches the
call. Full rules and acceptance criteria: [SPEC.md](SPEC.md). Prompt for the GHL agent: [agent_prompt.md](agent_prompt.md). GHL workflow that starts the call: [WORKFLOW.md](WORKFLOW.md).

## What it does
1. Checks the contact may be called (Call DND, opt-out tags, 8 AM to 8 PM local, one call a day, 14 in 14 days, test allowlist).
2. Writes `call_purpose`, `call_organization`, `call_script`, `call_facts` in one update, `call_facts` last, with a unique
   reference appended so the value changes every time. Reads the value back to prove it landed.
3. Finds the Voice AI call log for that contact after the write and returns transcript, summary, duration and rule-based readings.

## Safe by default
SHADOW mode: nothing is written to GHL and no call is made. Live needs `SVC_WRITE_MODE=live` **and**
`SVC_SHADOW_LOG_ONLY=false` **and** the contact id in `SVC_ALLOWED_CONTACT_IDS`. Secrets come from the environment or the
gitignored `.env`; they and phone numbers are never printed. Pin the GHL workflow to the test contact too.

## Use
```
cp sharedvoiceagent/.env.example sharedvoiceagent/.env      # fill GHL_API_KEY, GHL_LOCATION_ID
python -m sharedvoiceagent scenarios
python -m sharedvoiceagent request --scenario doctor --contact-id <TEST_CONTACT_ID> --first-name Kes     # shadow: shows what it would write
# live test (after the GHL agent + workflow exist and the contact is allowlisted):
python -m sharedvoiceagent run --scenario doctor --contact-id <TEST_CONTACT_ID> --expect happy
python -m sharedvoiceagent run --scenario course --contact-id <TEST_CONTACT_ID> --expect wrong_person
python -m sharedvoiceagent run --scenario vacation --contact-id <TEST_CONTACT_ID> --expect voicemail
python -m sharedvoiceagent fetch --contact-id <ID> --since 2026-11-23T15:00:00+00:00 --scenario doctor
```
Test: `python -m pytest sharedvoiceagent/tests -q` (no network, no calls).

## Limits (read before relying on it)
- One process at a time (the ledger is a local file). Not a multi-worker service.
- Readings from the transcript are rules, not judgement; a person checks the transcript against the checklist.
- UNVERIFIED until a live call: the exact call-log field names for a Voice AI call started by a workflow, the maximum length of a
  Multi line field, and whether Voice AI honours Call DND (it may not; the workflow must check it, see SPEC section 6).
- Each of the three scenarios is an example of how another agent would call this package; the examples use fictional organizations.
