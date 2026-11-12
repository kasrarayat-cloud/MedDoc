# FINAL-V2 amendment 1: the refutation, judged

**What this is.** The judge's record for the refutation of FINAL-V2 amendment 1 (`AMENDMENT-1.md`), written 2026-11-12.
Three lenses (races and duplicates: `refute-races.md`; truth, staleness, approval and export: `refute-truth.md`; legacy,
cost and compatibility: `refute-legacy.md`) reported 30 findings. Each was verified against the code before it was
decided. The owner's words (`gemini-migration/owner-autorecheck-20261112-verbatim.md`) and D184 governed every decision;
where the amendment disagreed with them, the amendment was wrong.

**Inputs.**
- The amendment as refuted: `AMENDMENT-1-pre-refutation.md`, byte-identical to the file the lenses read (sha256
  `fd8167ac6a1b9a13172a63d94b8c7c514d25098da0882c7931a4aabb9448895d`).
- The code: branch `feat/cpt-studio-gemini-interpreter-20261109` at `c0d6d52a7f7066d77382fe9576a8e1a4de5b2eab` (the
  worktree `/opt/meddoc-pro/.worktrees/cpt-gemini-20261109`, read only); the installed release's `studio/answers.py` read
  with `git show c2e53f8e:` (read only).
- D184 in `docs/gemini-migration/DECISIONS.md` and FINAL-V2 6.2 (MO-1), 8.0 and 8.1.

**Method.** For every finding: read the cited code, confirm or refute the sequence's premises and its wrong outcome, then
decide. Nothing was built, run, sent or changed outside `design-v2/amend1/`. No sealed set, `acceptance-a1/`, `g1-stage`,
walk or docs directory of c6 or c7 was opened.

**Result.** 30 accepted, 0 accepted in part, 0 rejected. Every finding's wrong outcome holds against the code. In
three cases the fix differs from the lens's hint, and the reason is given (R3/L6, R4/R5, L7). One finding's secondary
detail is inaccurate without affecting its substance (R6(c)). Applying the fixes surfaced one more defect, in the judge's
own fix, which the revision also closes (J1 below). The revised amendment tags every change `[R:<lens>-<id>]`.

**New decisions the revision adds** (to be recorded in DECISIONS with the amendment's adoption):
- **A16** an installation-wide provider hold for Corti, Astra and Fable on authentication, permission, payment and quota
  refusals (R2, L2);
- **A17** while an update is pending, an assessment that is not final is recorded but never made current and withdraws
  nothing of the earlier codes (R3, L6, T6);
- **A18** a context save is refused while a member-act stage runs on the current context; a withdrawal is refused while an
  update is pending (R4, R5, T12).

Amended: A1, A3, A4, A6, A9, A10, A12.

---

## Summary

| id | lens | severity | decision | where the amendment changed |
|---|---|---|---|---|
| R1 | races | critical | accepted (with T1, L1) | A9; 4.3; 5.1 item 4; 5.4; 8.2; 8.3; U13; W2; W6 |
| R2 | races | critical | accepted (with L2) | A10, A16; 2.2; 2.6; 3.6; 3.9; 7.1; 7.2; 7.3; 10; U12, U20; W8 |
| R3 | races | high | accepted, fix differs from hint (with L6) | A3, A17; vocabulary; 2.5; 4.1 (+J1); 4.4; 4.5; 9.1; 10; U8, U15 |
| R4 | races | high | accepted, fix is the hint's second option | A1, A18; vocabulary; 1.3; 1.4; 2.5; 2.7; 3.1; 3.10; U18 |
| R5 | races | medium | accepted (same fix as R4) | A1, A18; vocabulary; 1.4; 3.1; U18 |
| R6 | races | medium | accepted (detail of (c) inaccurate) | A4; 2.3; 2.7; 3.3; 3.4; 3.6; 3.10; U5 |
| T1 | truth | critical | accepted (with R1, L1) | as R1 |
| T2 | truth | high | accepted | vocabulary (progress jobs); 5.1 (`update.started_at`); 5.2; 4.3; 10; U16 |
| T3 | truth | high | accepted | 4.3; 5.1 item 3; 5.2; 10; U19 |
| T4 | truth | medium | accepted | 5.1 items 2 and 4; 5.3; 10; U21 |
| T5 | truth | medium | accepted | 5.1 (results section); 10; U21 |
| T6 | truth | medium | accepted | A17; 4.3; 5.1 item 2; 10; U21 |
| T7 | truth | medium | accepted | A12; 1.4; 2.4; 2.5; 5.1 (`update.kind`); 7.1 (case C texts); 7.5; 9.5; 10; U14 |
| T8 | truth | medium | accepted | vocabulary; 2.5; 4.3; 4.5; 8.1; U8 |
| T9 | truth | medium | accepted | 5.1 (JSON); 6.2 step 4; U11 |
| T10 | truth | medium | accepted | 5.4; U11 |
| T11 | truth | medium | accepted, fix is the hint's second option | 5.1 (JSON); 6.2 steps 1 and 5; U11 |
| T12 | truth | medium | accepted | A18; 1.4; 5.1 item 3; 5.3; 10; U18 |
| T13 | truth | low | accepted | 1.3; 2.5; 10; U1 |
| T14 | truth | low | accepted | 5.4; 6.2 step 3; 8.3; U11 |
| T15 | truth | low | accepted | 4.3; 5.3; 10; U10 |
| L1 | legacy | critical | accepted (with R1, T1) | as R1 |
| L2 | legacy | critical | accepted (with R2) | as R2, plus the Corti adapter's recorded token status (7.3, 10) |
| L3 | legacy | high | accepted | 9.5; 10 |
| L4 | legacy | high | accepted | A6; 2.2; 2.7; 7.1; 7.2; U12 |
| L5 | legacy | high | accepted | A6; 3.2; 7.1; 7.2; U12 |
| L6 | legacy | high | accepted (with R3) | as R3, plus 9.1 and U8's legacy Stop case |
| L7 | legacy | medium | accepted, fix extends the hint | 9.4; 10; U17 |
| L8 | legacy | low | accepted | 9.5; 10 |
| L9 | legacy | low | accepted | 3.8; 7.3 |

---

## The findings

### R1 (critical), T1 (critical), L1 (critical): a case-B update leaves the pre-save export "current"

**Claim.** A case-B save (a legacy revision, or a v2 revision whose inventory is of an older version) stores the values in
`Encounter.user_values` and keeps the context, the assessment, the decisions and the answers, so `customer_marker` is
unchanged; the approved export made before the save is listed and served as current, with no banner, for the whole
update and indefinitely after a failure, hold or Stop.

**Verified.** `reports.py:customer_marker` (lines 2057-2070) digests the live assessment, `encounter.current_context_id`,
the current decisions and the standing answers, and no member value. `review.py:live_assessment` checks only the
revision. `reports.py:customer_artifact_current` compares that digest; `customer_api.py:_reports` lists by it;
`api.py:download_report` serves a current artifact as stored. The amendment's 2.3 step 2 keeps the context in case B, and
its 8.3 treated the gap as a momentary race. All three lenses describe the same defect; the wrong outcome holds.

**Decision: accepted.** T1's variant of the fix is taken: currency becomes "the marker matches AND no update is pending"
in `customer_artifact_current`, `_reports` and so `download_report`. R1's alternative (member values in the marker) is
rejected as a fix: every stored artifact's `snapshot_sha256` was computed without them, so it would turn every export made
before the install non-current at once. With the update in the test, a restore makes the export current again by itself.

**Revision.** A9; 4.3 (a row for the three readers); 5.1 item 4; 5.4; 8.2 (the marker never gains the values, and why);
8.3 (the rule, and the race bullet narrowed to the moment before the save commits); U13 (the case-B download in four
states, then after a restore); W2 and W6 (the download during the update).

### R2 (critical), L2 (critical): after a quota, payment or authentication refusal, Corti and the participants are asked again

**Claim.** After Corti answers 402 (or 401, 403, 429), the refused text invites a date change, which makes a new request
that is sent; every other encounter's update sends too; the participants behave the same; and (L2) a token refusal is
recorded not sent, which the failed-before door never holds, so every save re-posts the credentials. 7.3 declared this a
"stated limit".

**Verified.** `jobs.py:_failed_before` (641) matches the encounter, provider, adapter and request sha256, FAILED and
`sent=True` only. `stage_predict` (1074-1186) sends whenever no stored answer, no unknown outcome and no failed-before run
exists. `providers/corti.py:send` and `_authenticate` (128-190) turn every token refusal into `not_sent(...)` with no
status (`providers/base.py:not_sent`). `jobs.py:_finish_run` records it NOT_SENT. The pre-refutation 7.1 refused row
said "Change the date of service, add documentation, or restore the earlier details." The owner: "Handle quota and
payment failures without repeated requests"; D184: "quota, authentication and payment failures hold without repeated
requests". The amendment's own rule makes the disagreement its defect.

**Decision: accepted.** L2's sequence (b) (every legacy edit sends Corti and the peers) describes the cost of the owner's
own directive (the automatic recheck applies to legacy encounters) and is not a defect by itself; the hold bounds it
after a refusal.

**Revision.** A16, a provider hold modelled on the interpreter's: `ProviderHold`/`ProviderHoldRelease` (1d, additive in
0015), `studio/provider_holds.py` (5b), `manage.py provider_hold` (6b). It is set by a Corti 401, 402, 403 or 429, by a
token refusal (Corti's adapter now records that status on its not-sent run, so the hold reads a field, never error text),
and by an Astra or Fable exchange answering 401, 402, 403 or 429. Every send door reads it after the reuse door. A held
Corti pauses the update (resumable after an operator's release). A held participant blocks only itself (I10).
`_failed_before` leaves a hold-setting run out (as `_interpretation_failed_before` does), so after the release one send
is made. `retry_update` is refused while held. The refused row of 7.1 became a paused row with no date-change advice.
Also A10, 2.2, 2.6, 3.6, 3.9, 7.2, 7.3 (the "stated limit" replaced), 10 (FINAL-V2 4.12 amended), U12, U20, W8.
Recorded limit: a participant's 429 holds fail-closed, because their 429 bodies are not classified finer. A finer
classification, as the interpreter has, is a later refinement that needs evidence.

### R3 (high), L6 (high): "restore the earlier details" after the update's assess #1 is not a restore

**Claim.** Once the update's assess #1 (non-final) is current, 2.5 turned a restore into an ordinary change. On a legacy
encounter that is a new v2 update: peer requests on the new reading are sent (a Stop cancelled the abandoned ones, and the
legacy ones carry the legacy heading), and its final invalidates every legacy approval (D7). This contradicts 2.5's "no
provider call; decisions carry" and the stopped text that offered the restore.

**Verified.** `review.py:persist_assessment` (1166-1256) sets `current_assessment = assessment` for every assessment and
carries only when `is_final`. `jobs.py:_peer_reading_heading` (2390) gives the events engine's assessment a different
heading (D9). `_carry_decisions` (1090-1124) invalidates across engines. The wrong outcome holds.

**Decision: accepted. The fix differs from R3's hint (a).** Setting `current_assessment` back to B on a restore is not
enough. `persist_assessment` runs `_withdraw_superseded` (910-936) for every assessment, final or not. That withdraws
every earlier open clarification the new assessment does not raise again, and on a legacy B that is every
proposal-scoped one (the fingerprint changed). B would come back with its questions WITHDRAWN.
`_assessment_blockers` (1328-1430) and the overlay read open Clarification rows, so B could read ready, or lose its
encounter-scoped "Open clarification" blocker. The hint's (b) (stop offering the restore after assess #1) is safe but
removes the member's way back from a stalled legacy update.

The revision takes a third route. **A17**: while an update is pending, a non-final assessment is recorded (its own rows,
`_close_answered` over its own questions), never made current, and withdraws nothing. The final does everything persist
does today. Verified compatible with the chain: the peer stages and assess #2 read `_newest_assessment` /
`_first_assessment` (by creation), never `current_assessment` (jobs.py 321-330, 3118, 3212). So B stays current with its
questions until the update's final, the restore applies at every point before it, and T6's intermediate-state display
goes away too.

**Revision.** A3, A17; the vocabulary (`earlier`); 2.5 (rewritten, with the reason the naive fix fails); 4.1 (the persist
step and J1 below); 4.4; 4.5; 5.1's A14 rationale; 9.1 (legacy); 9.4's note; 10 (`persist_assessment`,
`_newest_assessment`; and a row in the superseded table for HARNESS.md 12.1's behaviour); U8 (a legacy Stop-then-restore
case, B's clarifications still OPEN, no peer sent), U15.

### R4 (high), R5 (medium): a restore over a member act a context save superseded

**Claim (R4).** A withdrawal queues a recompute J. A context save made while J runs is accepted (A1) and supersedes J. A
restore then makes E fresh again, still reading the withdrawn answer, with STALE_ANSWER_BLOCKER standing for good: J is
no target job, there is no Resume, the retry is refused and a second withdrawal is ALREADY_WITHDRAWN. If X was recorded
rather than withdrawn, E stays with X applied by the overlay alone. **Claim (R5).** The same race loses a second review:
superseded at its start, its key is used (SECOND_REVIEW_ASKED); superseded after sending, its paid answer is never
assessed.

**Verified.** `answers.py:_revoke_answer` (937-962) refuses only while busy and calls `recompute_after_answers`.
`jobs.py:recompute_after_answers` (4614-4655) returns None unless the final is on the current context.
`review.py:_reads_a_withdrawn_answer` (1314) and `_assessment_blockers` (1346-1347) raise STALE_ANSWER_BLOCKER. The
`CONTEXT_VERSION` comment (jobs.py 60-83) records "a member's answer applied to the stored assessment with no recompute
(a false 'reviewed' with an approved export)" as a regression class. `_second_review_key` and `_second_review_blocker`
(3364-3386) refuse once the key is used. `_second_review_bounds` (3389-3464) refuses "already made" once a run exists.
Today the race is impossible only because every context save is refused while busy; A1 lifted that.

**Decision: accepted, both.** Fix: the hint's second option. **A18**: a context save is refused (the existing busy
sentence) while a member-act stage (an AGAIN assess `:c:`, which covers the answer recompute, the re-assessment after a
confirmation and `reassess_retained`; a `review2` and its `:review2:` follow-up) is queued or running on the current
context. Rapid successive edits are untouched (saves following saves). The hint's first option (re-queue on restore) was
not taken: it needs a catalogue of superseded acts to replay, and a replayed second review could send again.

**Revision.** A1, A18; the vocabulary (member-act stage); 1.3 (the order); 1.4 ("Kept for member acts"); 2.5; 2.7; 3.1;
3.10 item 7; U18.

### R6 (medium): coalescing into a running reading stage that never reaches analyze

**Claim.** 2.3 coalesced a save with a QUEUED or RUNNING reading stage. (a) A Stop recorded on a running stage survives
`clear_stop`, so it ends CANCELLED and the save is never read. (b) A running stage may already have decided "superseded"
from a restored state just before the save. (c) A dead worker's stage stays RUNNING for up to 600 s. In each case the
update flips to stopped and needs a manual Resume.

**Verified.** `jobs.py:clear_stop` (126) clears only `Encounter.stopped_at`. `stop_encounter` (3985) sets
`Job.stop_requested_at` on running jobs. `_stop_requested` (1336) reads that flag. `claim_next` (3603) locks Job rows
(`skip_locked`), not the encounter, so a start check can read the state before a concurrent save commits.
`settings.STALE_RUNNING_SECONDS = 600`.

**Decision: accepted.** (c)'s display detail is inaccurate. After `WORKER_SILENT_SECONDS` (120 s) without a heartbeat,
`progress.encounter_progress` reads `paused`, not "Changes saved—updating codes" (jobs.py 3905; 7.1's last row). The
substance holds: the save is not rechecked until a manual Resume.

**Revision.** 2.3 coalesces only with a QUEUED reading stage. A running one gets the owed stage queued beside it under
`:after-save:<uuid>`; its doors reuse what the running one stores, so nothing is sent twice. `_superseded` reads the
encounter under its row lock at the start check and the successor gate, so a coalesced QUEUED stage reads the save. Also
A4, 2.7, 3.3, 3.4, 3.6, 3.10 item 5, U5 (a)-(c).

### T2 (high): "target jobs" make the progress steps and times false

**Claim.** Folding progress over target jobs drops the context-free stages once the reading is no longer owed (an
addendum's or a legacy update's reading flips to "Not needed" and the timer resets). It pulls the original legacy chain
in before analyze (the elapsed time counts from the upload). It gives every upload "Not started" reading steps after
analyze. It restarts the timer at every rapid save. It leaves a completed document with no finished time.

**Verified.** `jobs.py:start_pipeline` (135), `_after_extract` (797) and `_queue_analyze` (2073) enqueue with no context.
`progress.py:_runs` (157-174), `_steps` (278-303) and `encounter_progress` (562-640) fold every job of the revision into
runs, and today's run cutting handles all six shapes correctly. The amendment's vocabulary is what breaks them.

**Decision: accepted.** **Revision.** A new vocabulary row, **progress jobs**: the revision's jobs minus superseded ones,
cut by today's run rule (overlapping chains form one run). Progress folds them for the steps and the times; target jobs
still decide busy, the phase, the state, Resume and Retry. `started_at` while pending is `update.started_at` (the first
save after the earlier codes or the newest restore). `finished_at` is kept. Also 5.1, 5.2, 4.3, 10, U16.

### T3 (high): case B keeps the context, and the date block, detail rows and date hold keep reading it

**Claim.** After "Use document date" on a legacy encounter held on a member conflict (case B), `date_held` still reads the
legacy context, so the phase stays `action_needed`. A failure or a pause is then never shown, nor its Retry, and
re-choosing is a no-op. Without a conflict, the old date shows as entered.

**Verified.** `progress.py:date_held` (326-332) reads `encounter.current_context`, and `encounter_progress` (578-579)
decides `action_needed` before anything else, computing no error there. `answers.py:service_date_block` (251-270) and
`_rows` (539-575) read the context's facts and `user_values`. `_save_details` compares with `Encounter.user_values`.

**Decision: accepted.** **Revision.** While `values(encounter) != values(current context)` (case B pending), the date
block and the rows read the saved values (the document date and quote still from the context), no member conflict is
asserted until a context derives one, and `date_held`, `customer_state` and `list_row` let the update's own state decide.
4.3 (two rows), 5.1 item 3, 5.2, 10, U19.

### T4 (medium): "being updated" while nothing runs

**Verified** against the amendment's own texts (5.1 items 2 and 4, 5.3): unconditional, while `update.state` includes
failed, stopped, paused and being_confirmed. **Decision: accepted.** **Revision.** The earlier codes' line is true in
every state. UPDATE_EXPORT_NOTE and the customer UPDATE_BLOCKER are chosen by `update.state`. UPDATE_DECISION and
UPDATE_EXPORT no longer promise the update finishes. U21.

### T5 (medium): the results section says no codes were suggested

**Verified.** `app.js:emptyResults` (959-968): the lookup has no `updating`, and the failed, stopped and paused sentences
say nothing was suggested. `tallyText` (454-467) returns "No codes yet". `resultsSection` draws the bar when reports exist.
**Decision: accepted.** **Revision.** 5.1's "results section while pending" (true sentences pointing to the earlier codes;
the tally prefixed "Before your change: "), 10, U21.

### T6 (medium): other assessment-derived keys read the update's unfinished assess #1

**Verified.** `customer_api.py:encounter_json` (1036-1071) derives `other_codes`, `not_separately_coded`, `unresolved`,
`limitations`, `details_needed` and `earlier_answers` from `review.live_assessment`, which under the pre-refutation design
was the update's assess #1 during the peer phase. **Decision: accepted.** **Revision.** A17 removes the state (the
update's assess #1 is never current). The revision also requires that these keys come from `earlier(encounter)` while
pending, and that the page draws them inside the earlier codes' section (4.3, 5.1 item 2). U21.

### T7 (medium): case-C texts offer an impossible restore, and an addendum can start an update that never finishes

**Verified.** `api.py:addenda` (325-370) checks only the 20,000-character addendum and `MAX_PASTE_CHARS` (400,000) for the
combined text. `settings.INTERPRET_MAX_CHARS = 20_000` (`jobs._size_bound`). `stage_extract` (754-795) carries the
parent's pages to an addendum. 2.5's restore requires the same revision. **Decision: accepted.** **Revision.** A12
extended to addenda: refused under the row lock before the revision is recorded or any decision invalidated, using the
`combined` length `addenda` already computes (ADDENDUM_TOO_LONG, ADDENDUM_UNPREPARED). `update.kind` distinguishes case C.
7.1 gained case-C wording with no restore. Also 1.4, 2.4, 2.5, 7.5, 9.5 (reported to the owner with the live maximum),
10, U14.

### T8 (medium): a save during a first processing's assess #1 is not an update

**Verified.** `persist_assessment` makes a non-final assess #1 current. `customer_api.readiness` gives `draft` whenever an
assessment is live. `api.py:create_report` gates only the approved kind. The scenario is reachable today after a Stop,
and while busy once A1 lifted the refusal. **Decision: accepted.** **Revision.** `earlier()` and
`earlier_for_new_context` gain a branch: a first processing's unfinished assessment that a save made stale is the earlier
codes. The update block, the export refusal and "what changed" then apply. A restore needs a final B, so a save back to
its values is an ordinary change. The vocabulary, 2.5, 4.3, 4.5, 8.1, U8.

### T9 (medium): "what changed" lists a revoked approval as cleared, and a later-cleared carry as kept

**Verified.** `review.py:current_decisions` (224-232) ends a decision at a REVOKE row, and `_carry_decisions` acts only on
current decisions, so a revoked approval has neither a carry nor an invalidation. 6.2 step 4 picked "the latest Decision
that is not a revoke". A carried approval later invalidated by a same-context final (`_carry_decisions` with
`by_context` the unchanged context) still had a `carried_from` row. **Decision: accepted.** **Revision.** Step 4 lists a
decision only when E's latest decision for the proposal is not a revoke. "Kept" requires the carried chain to reach a
decision current on N. A new outcome, "kept by the update, then cleared". The JSON `outcome` field. U11.

### T10 (medium): Earlier decisions attributes every same-revision clearing to a details change

**Verified.** `_carry_decisions` (1114) invalidates `by_context=context`, the new final's context, which for an answer
recompute, a re-check follow-up or `reassess_retained` is the decision's own assessment's context. **Decision:
accepted.** **Revision.** 5.4 gains a rows-only rule: `by_context` equal to the decision's own assessment's context gives
"Cleared when the codes were checked again with the same details". This also labels the installed release's existing
clearings truthfully. U11.

### T11 (medium): "what changed" compares stored rows while the member saw overlay statuses

**Verified.** `jobs.py:recompute_after_answers` (4634-4637) never recomputes an answer on a legacy context after the
install ("stands on its overlay"). `customer_api._status` shows the overlay. 6.2 read stored rows. **Decision: accepted**,
with the hint's second option. Recomputing each side's overlay at a recorded point would need historical decisions and
answers and the legacy reader, against 6.2's rows-only determinism. **Revision.** 6.2 step 1 says it compares the
suggestions as made, before any answer or decision. A new step 5 (rows only: `MemberAnswer`, `MemberAnswerRevocation`,
N's clarifications and answered markers) adds one line when an answer is not applied to N, pointing to "Earlier answers,
not applied". JSON `answers`. U11.

### T12 (medium): a withdrawal during an idle update, then a restore, keeps the withdrawn answer in effect

**Verified** as for R4: `_revoke_answer` is refused only while busy, and `recompute_after_answers` returns None while the
final is off the current context. **Decision: accepted.** **Revision.** A18: a withdrawal is refused while an update is
pending (UPDATE_ANSWER_WITHDRAW), as a new answer is, and the Withdraw link is hidden then. 1.4, 5.1 item 3, 5.3, 10,
U18.

### T13 (low): a restore answers "updating": true

**Verified.** `answers.py:_save_details` (909-910) returns `'reassessing': bool(changed) or ...`. `app.js:saveDetails`
(1625) toasts "The results are being updated." **Decision: accepted.** **Revision.** A restore answers `updating: false,
restored: true`; `reassessing` comes from the `ContextSave`; the toast is worded from it. 1.3, 2.5, 10, U1.

### T14 (low): the earlier label, banner and removal reason claim changes that did not happen

**Verified.** The marker changes with a new context, assessment or carried decision row even when no code or decision
changed visibly. `customer_api._exclusion_reason` (485-491) falls back to "A documentation check excluded this code.",
while `code_rows` (683-684) words an alternative "Listed as an alternative only; not suggested for approval."
**Decision: accepted.** **Revision.** The label is "it may not show the current codes". The banner is "EARLIER EXPORT —
MAY NOT SHOW THE CURRENT CODES … This document has changed since (its details, its documentation, its codes or its
decisions)". The removal reason is the other-codes expression applied to N's stored row. 5.4, 6.2 step 3, 8.3, U11.

### T15 (low): the re-check is offered on the earlier codes during an idle case-B update

**Verified.** `_second_review_bounds` (3389-3464) checks busy, the context's identity, legacy and earlier context
versions, never the saved values. A case-B save on a v2 revision whose inventory is of an older version keeps the
context. Live legacy contexts are refused by the legacy bound, as the lens says. **Decision: accepted.** **Revision.**
`_second_review_bounds` refuses while an update is pending (UPDATE_DECISION's wording). 4.3, 5.3, 10, U10.

### L3 (high): the install-stop count trips on every install after v2 has run

**Verified.** `ops/install.py:phase_app` (4874-4935) serves fix releases, re-installs and same-revision re-runs (D83's
provider-mode switch). The comment at 4917 records the round-7c8 skeptic's sk:2: refusing on a persistent data state
refused exactly those. FINAL-V2 6.2 [R:MO-1] records the same class. `intake.py:_create` (92-96) stores an upload's date
in `Encounter.user_values` before any context exists. **Decision: accepted.** **Revision.** The count is defined over
encounters with a current context of the current revision. It is printed on every install and never refuses. On the
first install over `c2e53f8e` (no v2 row) a non-zero count is reported to the owner before the switch. 9.5, 10.

### L4 (high): when E's own Corti run failed, no update that leaves Corti's request unchanged can complete

**Verified.** `jobs.py:_decide_after_save` (4466-4491) re-checks today with any run in use that answers the request.
The pre-refutation 2.2 step 5 restricted that to SUCCEEDED runs during an update, and 7.2 then ended the stage FAILED on
the not-resent run `_failed_before` (641) produces. `review.is_final` has no provider condition. The legacy variant pays
both Gemini passes first. The owner: "Rerun only stages whose inputs changed." **Decision: accepted.** **Revision.** A6
compares with E: re-check with the run in use when it succeeded OR is E's own run. In `stage_predict`, an outcome on a
request byte-identical to E's own run's, or one unbuildable where E's was too, goes on with E's outcome. Nothing is
re-sent for a request E's run sent and failed. A request E's run never sent goes once, as its first attempt. 2.2, 2.7,
7.1, 7.2, U12.

### L5 (high): a Corti run recorded NOT_SENT with its request is not in 7.2's list

**Verified.** `providers/corti.py:send` (128-148) returns `not_sent` for an unreadable credentials file, a session
failure, a token refusal, an unreachable service and a deadline before sending. `jobs.py:_send` (1188-1290) records them
NOT_SENT carrying the request. `stage_predict` (1183-1184) calls `next_assess(run)` after `_send` whatever the state.
`persist_assessment`'s final carries or invalidates. **Decision: accepted.** **Revision.** 7.2's list is now exhaustive,
in this order: the provider hold (a hold-setting run pauses); succeeded or reused; E's own outcome (L4); unknown; coding
service disabled; every other outcome, including NOT_SENT with its request, ends the stage FAILED. A not-sent run has a
retry that needs no release (`predict:<context>:retry:<run>`), and a 7.1 row. A6, 3.2, U12.

### L7 (medium): on the rollback image a re-entered pending value is silently not saved

**Verified** with `git show c2e53f8e:cpt-studio/studio/answers.py`. `save_details` (807-808) computes `changed` against
`Encounter.user_values`, while the panel (246, 559) shows the context's values. A re-entered pending value is
"unchanged" and `change_context` is not called. **Decision: accepted, with a fix that extends the hint.** Reporting the
encounters alone would still leave the old image unable to apply the re-entered value. Refusing the switch-back on it
would repeat sk:2 on the incident path. **Revision.** For the "pending, before analyze" row, the undo (in CLOSE_STAGES'
step, under the row lock) reverts `Encounter.user_values` to the legacy context's values. It records the fields in a
`context.rollback_reverted` audit row, and the fields and both values in its answer. The switch-back note lists the
encounters so the members save the change again on the old image, where it then takes effect. 9.4, 10, U17. **For the
adoption:** this is an operator act that overwrites a member's unapplied input, though it records the input. The
adoption's DECISIONS entry should record it explicitly. If the owner reads it as class d, it goes to him.

### L8 (low): the SAVE_UNPREPARED class is not counted before the install

**Verified** against A12/1.4 (the framing refusal) and 9.5 bullet 1 (size bounds only). **Decision: accepted.**
**Revision.** 9.5 counts live current revisions with no inventory whose text fails the framing check, reported with the
size count (class b). 10.

### L9 (low): 3.8 says a hold-setting answer is never re-sent; the door excludes holds by design

**Verified.** `jobs.py:_interpretation_failed_before` (1995-2009): "never a hold, which an operator's release ends".
`retry_target` (4114-4135) releases only FAILED and TOO_LONG effects. W4 expects one send after a release.
**Decision: accepted.** **Revision.** 3.8 and 7.3: not sent while the hold stands; after the release the next member act
sends it once; refused again, it sets a new hold.

---

## J1: a defect in the judge's own fix, found while applying it

**What.** A17 records an update's assess #1 without making it current. After a restore, that abandoned assess #1 stays
the revision's newest assessment by creation. `jobs._newest_assessment` (321) is read by `recompute_after_answers` (4640:
newest must be the final), `reassess_retained` (4728: RETAINED_NOT_NEWEST), and the AGAIN and second-review-follow-up
basis checks of `_assess_events` (3118) and `stage_assess` (3212: ASSESS_MOVED). So every act on the restored codes would
refuse or skip: an answer never recomputed, a withdrawal leaving STALE_ANSWER_BLOCKER. This is R4's outcome by another
door.

**Fix (in 4.1, tagged with R3).** `_newest_assessment` returns the newest assessment that is the encounter's current
assessment or is on its current context. An abandoned one's context never becomes current again: contexts are never
deduplicated, and a restore makes B's own context current. While an update runs, its own assess #1 is on the current
context and stays the newest for its peer stages and assess #2. `progress.py`'s own newest-assessment lookup (556) uses the
same helper. U8 checks an answer's recompute and `reassess_retained` after such a restore.

---

## For the adoption

- Record A16, A17 and A18 as DECISIONS entries. Record the amended A1, A3, A4, A6, A9, A10 and A12. Record FINAL-V2 4.12's
  amendment (A16), and HARNESS.md 12.1's behaviour during an update (A17).
- Owner-facing items (class b, via 9.5's report): documents whose details cannot be changed after the install (size or
  framing); addenda that would take a document over the bound are refused; a non-zero pending count on the first install.
- L7's undo revert, recorded explicitly in the adoption, and taken to the owner if read as class d.
- Builders: the participants' 429 hold is fail-closed (A16). `studio/providers/corti.py` gains an owner (5b) for one change
  (the token refusal's recorded status).
