# WORKFLOW.md - the GHL workflow that starts the call

The caller (this package) never dials. It writes four contact fields; a GHL **workflow** notices that `call_facts` changed and starts the **voice agent** call. If the workflow is missing, unpublished or paused, the write succeeds and nothing happens (this is what happened on the 2026-11-22 8:00 PM attempt; see PROGRESS.md).

This workflow is built by hand in GHL (Automation, Workflows). It cannot be created from this repo. Reference: the "Voice interview_notification" workflow used by the interview agent is the pattern; this one is the same idea with different fields, an added safety check and a stricter scope.

## Summary
| Item | Value |
|---|---|
| Name | `Voice shared_outbound_call` |
| Type | Contact workflow |
| Trigger | Contact Changed: custom field `call_facts` **has changed** |
| First step | If/Else: exit when Call DND is on or an opt-out tag is present |
| Action | Voice AI Outbound Call, agent "Enterprise Outbound Caller v1", from the location's outbound number |
| Status | Draft while testing; publish only when pinned to the test contact (see Scope) |

## Why the trigger is `call_facts`
The caller writes the fields in a fixed order: `call_purpose`, `call_organization`, `call_script`, then `call_facts` **last**. The workflow starts on the `call_facts` change, so by the time the call is queued the voice agent can already read all four values. Triggering on any other field would start the call with stale or empty content.

Every `call_facts` value ends with a unique reference (e.g. `SVC-20261123020024-96b981`). That guarantees the value is different each time, so "has changed" fires even when the same person is called twice with the same facts.

## Build steps
1. **Create workflow** > Start from scratch > name `Voice shared_outbound_call`.
2. **Add trigger: Contact Changed.** Filter: Custom Field `call_facts` > "has changed". Do not add other filters on the trigger. Confirm the field is `call_facts` and not a similarly named field.
3. **Scope while testing.** Add a trigger filter or first If/Else so only the test contact enters (for example, tag `test`, or contact id equals the id in `SVC_ALLOWED_CONTACT_IDS`). Remove the scope only when Kes and Ali say so. This second lock matters because the field write IS the call.
4. **Add If/Else (safety check).** Branch 1 (exit): Call DND is on, OR contact has any of the tags `do not call`, `do not call again`, `do not contact`, `not interested`, `dnc`, `stop` (these match `DEFAULT_OPT_OUT_TAGS` in `config.py`; keep both lists identical). Leave branch 1 empty, which ends the workflow for that contact. Branch 2 ("None"): continue.
   Why: it is **unverified** whether Voice AI honours Call DND on its own. The caller also checks these before writing, but the workflow is the last line of defence if someone edits the fields by hand or another system changes them.
5. **Add action: Voice AI Outbound Call.** Agent: "Enterprise Outbound Caller v1". From number: the location's outbound number. Do not hard-code purpose, organization, script or facts here; the agent reads them from the contact fields (the prompt in `agent_prompt.md` explains how).
6. **Workflow settings.**
   - Allow multiple enrollments: **On** (each new `call_facts` value must be able to start a new call).
   - Allow multiple opportunity enrollments: On.
   - Stop on response: **Off**.
   - Auto-mark messages as read: Off.
   - Timezone: account timezone for workflow timing (the call itself follows the contact's timezone window, below).
7. **Stop-request branch (optional, add after the first test passes).** After the call, a branch on the call outcome that adds the tag `do not call` when the person asked to stop. The caller never changes DND; the workflow does this.
8. **Save, then Publish.** A draft workflow does nothing. Check the toggle says Published.

## What GHL does with the call (from the Voice AI calling guidelines on the action)
Re-check these on the action's help text; limits and dates change.
- Calls only between 8:00 AM and 8:00 PM in the **contact's** timezone (derived from the phone number). Outside the window the call is queued.
- One call per contact per day; further attempts queue to the next day.
- Calls are queued at roughly 10 a minute, so dialing can start a few minutes after the trigger.
- Contacts who opted out of AI calls, or have DND, are skipped (UNVERIFIED for Voice AI: keep the If/Else in step 4).
- Daily location cap applies (the example showed 1,000 a day rising to 5,000 later; confirm for this location).
- Each location calls numbers in its own country only.

The caller mirrors the first two rules in its own gates (8 AM to 8 PM local, one call a day, 14 in 14 days) and refuses to write when they are not met, so the workflow should rarely have to queue anything.

## How to check it worked
1. Run a shadow request first: `python -m sharedvoiceagent request --scenario doctor --contact-id <ID> --first-name <name>` (no write, no call).
2. For a live test (needs Kes's explicit go and a named test contact): `python -m sharedvoiceagent run --scenario doctor --contact-id <ID> --expect happy`, from `C:\Users\keset`.
3. In GHL open the workflow > Execution Logs (or Enrollment History). Expected: one enrollment for the test contact within a minute of the write, passing the If/Else, then the Voice AI action marked executed.
4. In AI Agents > Voice AI > Call Logs, expect a call within a few minutes (inside the calling window). Compare the transcript with the checklist in Cora's `directives/spec/53_shared_voice_agent_test_plan.md`.

## If the write worked but no call came
Check in this order:
1. Is the workflow **Published** (not Draft or Paused)?
2. Is there an enrollment in the execution log for that contact? No enrollment: the trigger did not fire (wrong field selected, test-contact scope excluding the contact, or the value did not change).
3. Enrolled but stopped at the If/Else: the contact has Call DND or an opt-out tag (the tag `test` is not an opt-out tag; `stop` is).
4. Enrolled and the action ran but no call: outside the contact's 8 AM to 8 PM window, already called that day, outbound calling or wallet not enabled under Voice AI, or the call is still in the queue.
5. Voice AI call log empty after 10 minutes: record it as an open item (the call-log field names for a workflow-started call are still unverified).

## Changing it
Any change to the trigger field, the tag list or the scope is a behaviour change: update this file, `SPEC.md` section 6, `BUILD_GUIDE.md` and `PROGRESS.md` in the same change, and keep `DEFAULT_OPT_OUT_TAGS` in `config.py` in step with the tag list in step 4.

## Status
Not confirmed to exist as of 2026-11-23. A read-only listing of the account's 61 workflows on 2026-11-22 showed none that looked like this one. Update this section with the date and the result once Kes has built and published it.
