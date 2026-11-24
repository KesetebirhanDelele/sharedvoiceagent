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

## 2026-11-23 - workflow documentation
- Added `WORKFLOW.md`: the GHL workflow that starts the call when `call_facts` changes (trigger, scope to the test contact, Call DND and opt-out check, Voice AI action, settings, how to check it ran, troubleshooting). Modelled on the interview agent's "Voice interview_notification" workflow; its agent id, field id and phone number were not copied. Linked from `README.md` and `BUILD_GUIDE.md`. Docs only; code unchanged.
- Not done: the workflow itself still has to be built and published by hand in GHL (still unconfirmed to exist).

## 2026-11-23 - second live attempt (override)
- The 9:00 AM Central scheduled write (reference SVC-20261123150005-cbb7ca) produced no call; the workflow was not yet published. Kes then published the workflow and asked for one more test call to his own number, about 5 minutes later (about 10:35 AM Central). The daily limit was raised to 2 for that single run only (`SVC_MAX_CALLS_PER_DAY=2` in a one-off script outside the repo); not a saved setting. Result: see the next entry.
- Result of the second attempt (ran 10:47 AM Central, reference SVC-20261123164727-bde6bb): write accepted, read-back matched, no call log found within the 10-minute wait. Whether a call reached the phone is not known to the caller; Kes to confirm, and check the workflow execution log.

## 2026-11-24 - day 1 confirmed, day 2 started
- Day 1 (doctor, happy path): Kes confirmed on 2026-11-23 that the call arrived from the doctor's office via the shared voice agent in GHL, after the workflow was published. This is Kes's report; the transcript and call-log fields were not read by the caller (it found no call log within its 10-minute wait), so those readings remain unverified. The Nov 23 attempts were the 9:00 AM write (no workflow yet) and the 10:47 AM write (call came). The daily limit of 2 was an override for that one run only.
- Day 2 (course, wrong person): Kes asked for the call 5 minutes after about 9:44 AM Central. No limit override. Kes will say "wrong number" on the call. Result: see the next entry.
- Correction: the clock reading "3:44 PM Central" was wrong (a shell timezone setting was ignored and showed UTC). The real time was 9:44 AM Central; the write ran at 9:49:56 AM Central (reference SVC-20261124154956-cd8ad3), read-back matched. The caller again found no call log, even though GHL's conversation shows a completed call at 9:57 AM (41 seconds). So the caller's fetch of the Voice AI call log does not find workflow-started calls yet: cause unverified. Which of the two completed calls in the conversation belong to which write is not yet established.
- Kes listened to the 9:57 AM Central recording on 2026-11-24: it is the mock doctor's office call, NOT the course call (corrects the earlier assumption). Day 2 (course, written 9:49 AM Central) has therefore not been heard yet. Likely, unconfirmed: the 9:57 call was the 2026-11-23 10:47 AM doctor write, held in GHL's queue (Waiting) and delivered a day late, and the course call is queued behind the one-call-a-day limit. To confirm from the workflow Execution logs. No further writes today.

## 2026-11-24 - call log read for the first time (read-only)
- Pulled the Voice AI call log for the test contact with our own client (same endpoint and contact filter the caller already uses). It returns 9 logs. VERIFIED field names: id, agentId, contactId, createdAt, duration, summary, transcript, messageId, fromNumber, extractedData, executedCallActions, trialCall and others. Transcript format: lines starting "bot:" and "human:".
- Day 1 (doctor) call: logged 2026-11-24 14:57 UTC (8:57 AM Central; GHL shows it as 9:57 in Eastern), 38 s, shared voice agent. It was the delayed result of the 2026-11-23 writes (15:00 and 16:47 UTC), about 22 hours late. The 2026-11-23 14:17 UTC call (shown as 9:17 AM Eastern) was the interview agent, not ours: it used up that day's one call for this contact, so our two writes were queued to the next day. This fits GHL's one-call-per-contact-per-day limit; it is an inference from the timestamps, not stated by GHL.
- Day 2 (course, written 15:49:56 UTC on 2026-11-24, after the doctor call): no course call exists yet; most likely queued behind today's already-used call. Not heard, not verified.
- Doctor transcript against the checklist: AI disclosure first and stop-calling line: yes. Appointment details spoken (doctor, time, clinic, arrive early, photo ID): yes. Confirmation sentence asked and plain "yes" received: yes, read by a person. Reference not read aloud: yes. Contact opened with "Am I speaking with Kes?": yes.
- BUG found: the sentence "Can you confirm you got this information? Please just say yes." arrives split across two bot lines ("...Can you confirm" / "you got this information? ..."). `analysis.py` therefore reports confirmation_asked=False and outcome=no_confirmation for a call that did confirm. Fix (join consecutive bot lines before matching) not yet made; wait for Kes's go.
- Open: whether queued calls speak the field values from write time or from call time (the course write may change what a still-queued doctor call says). Unverified.

## 2026-11-24 - confirmation reading fixed
- Fixed `analysis.py`: the confirmation sentence is now found even when the live transcript splits it across bot lines with a person's "Yes." in between (it joins the agent's own lines in order). Added two tests (split sentence found; half a sentence not counted). 36 tests pass (34 before). The real doctor call re-read as outcome "confirmed".
- GHL execution log (Kes's screenshot, Central time): the 2026-11-23 10:47 AM enrollment's Voice AI action executed 2026-11-24 8:57:20 AM; the 2026-11-24 9:50:00 AM enrollment (course) shows the Voice AI action "Waiting". This confirms the call is held, matching the one-call-a-day inference. The 9:00 AM 2026-11-23 write has no enrollment (workflow not yet published then).
- SPEC section 6 items 1 and 4 and the README updated. Not committed: analysis.py, tests, SPEC.md, README.md, PROGRESS.md await Kes's go.
- Note: a commit made outside this session (442e033) removed `.env.example`, which BUILD_GUIDE.md still refers to. Awaiting Kes's decision to restore it.
- Still to do: day 2 (course, wrong person) once GHL places the held call; day 3 (voicemail); stop-request test.
