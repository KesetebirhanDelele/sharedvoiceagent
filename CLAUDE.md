# CLAUDE.md - sharedvoiceagent

Stand-alone Python package that asks the shared GHL (GoHighLevel) outbound voice agent to place a call and reads the result back. It imports nothing from the Cora recap engine (`C:\Users\keset\cora-recap-engine`). Read `PROGRESS.md` at the start of every session, then `SPEC.md`.

## Terms (use them exactly)
- **Voice agent**: the GHL Voice AI agent "Enterprise Outbound Caller v1" that talks on the phone. Its prompt lives in GHL; the copy is `agent_prompt.md`.
- **Workflow**: the GHL automation that starts the call when `call_facts` changes. It talks to nobody.
- **Caller**: this package. Not an "agent" and not an "app": it checks, writes four fields and fetches the call.

## How it works
Gate the contact, write `call_purpose`, `call_organization`, `call_script`, `call_facts` (facts last, unique reference appended), read the value back, later fetch the Voice AI call log. The field write IS the call, so every write passes the gates.

## Run (from `C:\Users\keset`, not from inside this folder)
```
python -m pytest sharedvoiceagent/tests -q
python -m sharedvoiceagent scenarios
python -m sharedvoiceagent request --scenario doctor --contact-id <ID> --first-name <name>   # shadow: no write, no call
```

## Rules
- **Shadow by default.** Live needs `SVC_WRITE_MODE=live` AND `SVC_SHADOW_LOG_ONLY=false` AND the contact id in `SVC_ALLOWED_CONTACT_IDS`.
- **Never print or store secrets, field text or phone numbers.** Check a secret only by "is it non-empty". The ledger holds contact ids only.
- **Fail closed:** unknown timezone or phone, Call DND, opt-out tag, outside 8 AM to 8 PM local, one call per day, 14 in 14 days: no write.
- **No live write without Kes's explicit go and a named test contact.** Do not widen the calling window or the daily limit without Kes saying so for that single run, and record it in `PROGRESS.md`.
- **Keep the confirmation sentence unchanged** ("Can you confirm you got this information? Please just say yes."): Ali's system finds the answer by that wording.
- Pre-ship: debrief files changed and verification, wait for Kes's "go ahead" before commit, push or any live call.
- Tests never touch the network or place calls. Update `SPEC.md`, `README.md` and `PROGRESS.md` in the same change as behaviour changes.
- `.env` and `ledger.jsonl` are gitignored; never commit them.

## Unverified until a live call completes
Voice AI call-log field names for a workflow-started call; the real stored-length limit of a Multi line field; whether Voice AI honours Call DND (the workflow must stop those contacts first); whether the call log appears within 10 minutes.
