# PROGRESS.md - sharedvoiceagent

Append a new dated section at the end of each work session. Do not rewrite history.

## 2026-11-22 / 2026-11-23: built, first live attempt, second scheduled
**Context.** Ali confirmed the shared outbound voice agent proposal (spec 53 in the Cora repo holds the GHL-side plan and checklist). Kes asked for a stand-alone caller that writes the GHL fields, triggers the call and fetches the conversation, with three example scenarios showing how Ali's other agents would use it.

**Built (commit 0640925 + the commit after it):** config (shadow default), a minimal GHL client (retry, the disguised 401 timeout, rate limit), gates, ledger, request with unique reference, service (write four fields, facts last, read-back, fetch call log), transcript readings, CLI, three scenarios (doctor appointment for "Example Family Clinic", AI course for "Tech Bros", vacation offers for "Example Travel Co"), agent prompt, spec, README. 34 offline tests pass.

**GHL facts checked read-only (2026-11-22):** the four custom fields exist with the right keys (`call_organization` TEXT; `call_purpose`, `call_script`, `call_facts` LARGE_TEXT). Test contact is Kes's own (contact id nggGZQByw53cbL8ws9Xg, time zone US/Central, tag "test", Call DND off). Shadow runs of all three scenarios cleared every gate.

**First live attempt (2026-11-22, 8:00 PM Central, doctor scenario):** write accepted, value read back matched (reference SVC-20261123020024-96b981). No call came and no call log appeared in 8 minutes. Cause not confirmed; most likely there is no published workflow reacting to `call_facts` (a listing of the account's 61 workflows showed none that looks like it). The calling window was widened to 10 PM for that single run because Kes was the recipient and asked for it; not a saved setting.

**Decision on the three tests:** GHL and this package allow one call per phone number per day, so the three scenarios run on three separate days on Kes's number: day 1 doctor (happy path), day 2 course (wrong person: say "wrong number"), day 3 vacation (voicemail: let it ring out). A stop-request test comes after.

**Scheduled:** Windows task `SharedVoiceAgent-Test1-Doctor` runs once at 10:00 AM Eastern (9:00 AM Central) on 2026-11-23, scripts and log in `C:\Users\keset\svc_scheduled\` (outside this repo; log is `run_doctor_test.log`). It reads credentials from the Cora `.env` at run time. Cancel with `schtasks /Delete /TN "SharedVoiceAgent-Test1-Doctor" /F`.

**NOT done / unverified**
- The GHL workflow (trigger: `call_facts` changes; action: Voice AI Outbound Call; start with a Call DND / opt-out check) is not confirmed to exist.
- No call has been completed, so the transcript readings and the call-log field names are untested against a real call.
- Outbound Voice AI billing: reported at about $0.06 to $0.215 a minute plus about $0.02 phone (third-party and HighLevel help pages, unconfirmed in Kes's billing page); building the agent was not found to cost anything.
- Open questions from Ali: who builds the content scan (suggested: his side); confirmation wording stays unchanged.

**Next steps (in order)**
1. Kes checks the workflow and its execution log; fix whatever stopped the 8:00 PM write from starting a call.
2. Read `run_doctor_test.log` after the 9 AM run; check the transcript against the checklist in spec 53.
3. Day 2 (course, wrong person) and day 3 (vacation, voicemail), then a stop-request test.
4. Report results with transcript lines to Ali; record the real per-minute cost.

## 2026-11-23 - documentation pass
- Added `BUILD_GUIDE.md` (architecture, GHL build steps, rebuild from scratch, settings, running a test, extending, known gaps) and this entry. Code unchanged since commit 9c74e01.
- State: no live call has completed yet. The 2026-11-22 8:00 PM write reached GHL but no call followed (workflow not confirmed). The one-time scheduled test for 9:00 AM Central 2026-11-23 is set; read `C:\Users\keset\svc_scheduled\run_doctor_test.log` afterwards and append the result here.
- Not done: wrong-person and voicemail tests (days 2 and 3), stop-request test, report to Ali, real per-minute cost.
