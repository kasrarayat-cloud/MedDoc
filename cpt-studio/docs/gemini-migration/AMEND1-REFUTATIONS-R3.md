# FINAL-V2 amendment 1, third refutation: judged

**What this is.** The judge's record for the bounded third refutation of FINAL-V2 amendment 1, written 2026-11-12. It
covers round 2's revision only: every `[R2:...]` passage, A19, A20, J2, J3, J4 and the amended A3, A4, A10, A16 and A18.
Two lenses reported 13 findings on the twice-revised `AMENDMENT-1.md`:

- binding, restores and holds (`r3/refute3-binding.md`, R3B-1 to R3B-6);
- truth, the screen, exports and confidentiality (`r3/refute3-truth.md`, R3T-1 to R3T-7).

Each finding's premises and wrong outcome were checked against the code before it was decided. The owner's words
(`gemini-migration/owner-autorecheck-20261112-verbatim.md`) governed every judgement. Where the amendment disagreed with
them, the amendment was wrong.

## Inputs

| input | sha256 |
|---|---|
| `AMENDMENT-1.md` as refuted, at the start of this judgement (194,741 bytes, 1,757 lines) | `3ba391192e6b7f763d5185e2a7c69d42daacd08604d48e1ffad8834b0adf07b8` |
| `r3/AMENDMENT-1-r2.md`, its copy, made first (2026-11-12T13:23:49Z) | `3ba391192e6b7f763d5185e2a7c69d42daacd08604d48e1ffad8834b0adf07b8` (equal) |
| `AMENDMENT-1.md` as revised by this judgement (222,209 bytes, 1,928 lines) | `204487df9c50375495d27ed72fef38efcc70723258d25a43b92eddb4675066db` |
| `r3/refute3-binding.md` | `eb90c29984fd24258f959e58ba003adb2fe92af0da92bd0548687960b06a90fb` |
| `r3/refute3-truth.md` | `d10165c6b2eb07add4906c4b55709257aadabce2d60ee53a9c4615971db86fcd` |
| `owner-autorecheck-20261112-verbatim.md` | `65cb0be8ceb1aaf20acb3095f84860a140692f95e0263cfc24102daf5f961c13` |
| `r2/AMEND-REFUTATIONS-R2.md` (the second judgement) | `d11729a31f74871707b04d724e5c5024c3e6802b1b7a24b49acd119bcb34372e` |
| `r2/AMENDMENT-1-r1.md` (the text before round 2) | `2f0699485de0bd85f945c38c3d1296d3caf620f785a6d0959547a096a3edcf1a` |
| `r2/refute2-binding.md`, `r2/refute2-truth.md` | `5787381c…`, `33afdc00…` |
| `AMEND-REFUTATIONS.md` (the first judgement) | `8cbed069c5c7713fe681fa1c8ca6606916b6feef0b2a22bd7b100e452d35e2b0` |
| `docs/gemini-migration/FINAL-V2.md` (worktree) | `9d650797c41091d3ab9ce2f783c1838e5aa394bb926c5d5b2733c2186d733b21` |
| `docs/gemini-migration/DECISIONS.md` (worktree) | `b2828cb58bf90545a812045489f396e6f1fdd5d7817321f88a255780f9e70c9e` |

The diff from `r3/AMENDMENT-1-r2.md` to the revised text: 100 lines removed, 271 added (reflowed paragraphs included).

The code: branch `feat/cpt-studio-gemini-interpreter-20261109` at `c0d6d52a7f7066d77382fe9576a8e1a4de5b2eab` (the worktree
`/opt/meddoc-pro/.worktrees/cpt-gemini-20261109`, read only; HEAD read with `git rev-parse HEAD`).

**The worktree's HEAD moved during this judgement, and nothing read here changed.** Another session committed
`06b9bab30be5ba44ff9cc4532ba3e29207de0cc0` at 2026-11-12T13:38:23Z ("Record the arbiter triage's rulings for build waves 1
and 2 (D185-D207)"). It touches only `docs/gemini-migration/DECISIONS.md`, with engine rulings: object grammar, reasons,
the date fact and the like, none on saves, updates, holds, reconciliation or progress. `git diff` between the two commits
shows `studio/` identical, so every code citation below holds at both. The DECISIONS.md hash in the table is c0d6d52a's
(`b2828cb5…`); at `06b9bab3` it is `2ddd4c93296167310b478ea46d6e6ee811191b86463731df411c81a22266f111`. The adoption numbers
the A-decisions from D208 on.

Read for this judgement:

- `studio/jobs.py`: `_send` (1187), `_finish_run` (924), `_settle_unrecorded` (1321), `_failed_before` (641),
  `_not_resent_run` (724), `_earlier_reading` (1024), `stage_predict` (1074), `_new_path_owed` (1966), `stage_interpret`
  (2169; the after-reconcile settle at 2218), `claim_next` (3603), `run_job` (3643), `reconcile` (4046; the
  already-reconciled refusal at 4070), `_run_answers` (4203), `_run_in_use` (4257), `_attempt_owed`, `change_context`,
  `_save_on_inventory`, `_save_before_reading`, `_decide_after_save` (4466), `recompute_after_answers` (4614), and the
  `CONTEXT_VERSION` comment (60-83);
- `studio/review.py`: `decision_holder` (203), `current_decisions` (224), `invalidate_for_new_revision` (781),
  `_unreconciled_unknown` (1276), `_reads_a_withdrawn_answer` (1314), `_assessment_blockers` (1328), `_failed_stage_state`
  (1602), `_state_and_run` (1742; the assessment's own unknown run at 1779);
- `studio/answers.py`: `_save_details` (780; the answer row at 872, `change_context` at 882, the recompute only
  `if saved_ids and not changed` at 896);
- `studio/progress.py`: `ERRORS`, `_runs` (157), `_step_outcome` (222), `FOLD_ORDER` (255), `_fold` (258), `_steps`,
  `interpreter_paused` (335), `encounter_progress` (589);
- `studio/api.py`: `addenda` (326-377; `invalidate_for_new_revision` at 371);
- `studio/providers/corti.py`: `_authenticate` (159-195; every non-200 token answer a `_NotSent` at 189-190), `_predict`;
  `studio/providers/base.py` (`not_sent`);
- `studio/customer_api.py`: `FORBIDDEN` (97), `KNOWN_ERRORS` (`jobs.RETRY_UNKNOWN` at 160);
- `studio/static/studio/app.js`: `STEP_STATES` (50), `PHASE_TITLES` (57).

## Method

- **Every finding.** The cited code and the current text were read, and the sequence's premises and its wrong outcome
  were confirmed or refuted. Each finding was then accepted, accepted in part or rejected, held to the fixed rubric
  (critical: an older result current, stale codes approvable or exportable as current, a duplicate paid call, a provider
  call after a quota or payment failure, a lost save; then high, medium, low) and to the scope (a round-2 fix that does
  not close its finding, or a defect round 2 introduced).
- **Every accepted finding.** The narrowest change that closes it was made to `AMENDMENT-1.md`, tagged
  `[R3:<lens>-<id>]`. Refusing, holding or failing truthfully was preferred to a new mechanism, and nothing was made
  approvable or exportable that was not before. One new decision: A21.
- **Every changed passage was re-read** against the owner's words, the first round's 30 fixes, J1, and the second round's
  15 fixes and J2-J4. Six defects in this judge's own fixes were found and repaired (J5 to J10, below).
- **Checks run.**
  - The new and changed customer strings (15, the check forms included) were matched in the scratchpad against a verbatim
    copy of `customer_api.FORBIDDEN`: 0 hits.
  - Every table of the revised text was checked for a constant column count: 18 tables, 0 bad rows.
  - The scripted reflows asserted their own counts (expected 1, measured 1, each; the one paragraph rewrapped whole
    asserted that its word sequence was unchanged), and every `[R3:…]` tag was counted: 109 tags, each of the 13
    findings tagged where the text changed.
- **What was not done.**
  - Nothing was built, run against the application, sent to a provider, installed, or run in docker.
  - No git command changed the worktree; `git -C /opt/meddoc-pro` was never used.
  - None of these was opened: a sealed set, `acceptance-a1/`, `g1-stage`, `walk-c6`/`walk-c7`, `docs-c6`/`docs-c7`, or the
    acceptance directory.

## Result

| outcome | count | findings |
|---|---|---|
| accepted | 12 | R3B-1, R3B-2, R3B-3, R3B-5, R3B-6, R3T-1, R3T-2, R3T-3, R3T-4, R3T-5, R3T-6, R3T-7 |
| accepted in part | 1 | R3B-4: the missing state is accepted (as R3T-6); the re-send through the Retry door is only a wording ambiguity |
| rejected | 0 | |

- **Critical findings:** 1, accepted (R3B-1).
- **High findings:** 6. Five were accepted (R3B-2, R3B-3, R3T-1, R3T-2, R3T-3) and R3B-4 in part.
- **Duplicates:** R3B-5 and R3T-4 are one defect, with one fix. R3B-4 and R3T-6 share one fix.
- **New decision:** A21. A reconciliation that releases the current codes' own unknown document review while a reading
  is owed starts an update of those codes, with no save (kind `check`).
- **Amended:** A10, A16, A18, A19, A20.
- **Own-fix defects found and repaired:** 6 (J5 to J10).

## Summary

| id | lens | severity | decision | where the amendment changed |
|---|---|---|---|---|
| R3B-1 | binding | critical | accepted (the hint's two options combined) | A20; 7.3 "Where the hold is recorded"; 7.2 (`jobs.RETRY_UNKNOWN`, J7); 10 (`provider_holds.py`, `jobs.py`, pinned behaviours); U20 |
| R3B-2 | binding | high | accepted (the hint's first option) | A18, A19 (third condition); 2.5 (condition, a third case); 10; U8 |
| R3B-3 | binding | high | accepted; the fix differs from the hint (A21) | vocabulary (`fresh`, `update pending`); A19 and 2.5 (J5); A21; 3.4; 5.1 (title, `kind` `check`, `started_at`); 7.1 (check texts); 7.4; 9.1; 9.4 (J10); 9.5; 10; U17, U21, U22 |
| R3B-4 | binding | high | accepted in part | A10, A20; 7.1 (refused-before row; the no-restore paragraph); 7.2 (never-retried paragraph, RETRY_UPDATE_REFUSED_BEFORE); 7.3 ("Refusals recorded before the install"); 9.5; 10; U20 |
| R3B-5 | binding | medium | accepted (same defect as R3T-4) | A16; 2.2 step 5 (J9); 2.7; 7.2 last paragraph; 7.3 "What a held stage does"; 10; pinned behaviours; U20 |
| R3B-6 | binding | low | accepted | 5.1 (a fixed line in place of an empty `changes`); 10; U21 |
| R3T-1 | truth | high | accepted | 5.2 (the fold's outcome part); 10 (`progress.py`); U16 |
| R3T-2 | truth | high | accepted | 5.2 (the fold's activity part); 10; U16 |
| R3T-3 | truth | high | accepted (the hint) | 6.2 step 4; 10; U11 |
| R3T-4 | truth | medium | accepted (with R3B-5) | as R3B-5 |
| R3T-5 | truth | medium | accepted (the hint's first option) | vocabulary (`earlier`, `update pending`); 4.5 (code, bullets); 6.2 step 4; 8.1; 10; U11, U22 |
| R3T-6 | truth | medium | accepted (with R3B-4) | as R3B-4 |
| R3T-7 | truth | low | accepted (the hint's second option) | 7.1 header and held row; 7.3 "What a held stage does"; 10; U20 |

---

## The findings

### R3B-1 (critical): a token refusal whose outcome record fails is recorded not sent, with no status and no hold

**Claim.** Round 2's fallback sentence says an outcome whose record fails "is recorded unknown, and the unknown-outcome
block holds its encounter". It is false for the token class RT1 added. A token 4xx whose outcome transaction fails is
recorded NOT_SENT with no status, and no hold is recorded. "Try updating again" and every other encounter's predict then
post the refused credentials again. A coding 401-429 on the same path is UNKNOWN but blocks only its own encounter.

**Verified.**
- `_send` calls `_finish_run` inside `try`, and on any exception calls `_settle_unrecorded` and re-raises.
- `_settle_unrecorded` computes `unsent = exchange.outcome == 'not_sent' and not exchange.sent`. For such an exchange it
  writes NOT_SENT, `sent` False and a fixed error, with no `http_status`.
- `corti._authenticate` turns every non-200 token answer into `_NotSent`, so the exchange is a `base.not_sent(...)`.
- R2B-1's fix puts the `ProviderHold` insert into the outcome's own transaction, so a failure of either write rolls back
  both.
- `run_job` ends the stage FAILED on the re-raised exception.
- With no hold row and no status, the run is 7.1's local not-sent class, so `retry_update` queues `:retry:<run>`.
- A coding-endpoint refusal (outcome `failed`) is recorded UNKNOWN, and `_unreconciled_unknown` is per encounter.

The wrong outcome holds. The precondition is rare: the outcome transaction must fail. But that is the path the code and
the sentence exist for, and the outcome (a provider call after a quota or payment refusal, for a token 429 or 402, or for
a coding 402 or 429 sent once more by another encounter) is the rubric's critical class.

**Decision: accepted.** The fix combines the hint's two options:
- the fallback writes the HTTP status among its small fields;
- a run whose exchange carries a status A20 holds is recorded UNKNOWN whatever `sent` says, so its encounter is blocked
  and no member Retry is offered;
- the hold is recorded from those fields right after, in a transaction of its own, so every other encounter is held;
- any other not-sent exchange is recorded not sent, as today.

UNKNOWN was chosen over "not sent, with its status, and the stage ending paused" for two reasons:
- it needs no change to how `_send` ends the stage;
- it stays fail-closed if the hold's own write fails too. The one more request another encounter can then send is the
  limit a killed worker already has (3.7, and the binding lens's own "checked" list).

**Revision.**
- A20: the fallback sentence.
- 7.3: the fallback paragraph, replacing round 2's false sentence.
- 7.2: `jobs.RETRY_UNKNOWN` listed among `retry_update`'s refusals (J7).
- 10: `provider_holds.record` from the fallback; `jobs._settle_unrecorded`; pinned behaviours.
- U20: a token 401 and a coding 402, each with the record failing, then a Retry and another encounter's predict.

### R3B-2 (high): a restore brings back codes that never read an answer the same save recorded

**Claim.** One details save can record a "Not documented" answer and change a detail. The save queues no recompute. A
restore before the update's final then makes E current, with the answer applied only by the overlay: the state 1.4's A18
paragraph says a restore must never bring back.

**Verified.**
- `_save_details` writes the `MemberAnswer` (872), calls `change_context` (882), and queues the recompute only
  `if saved_ids and not changed` (896), because "a context change's own re-assessment reads the answers".
- 1.4's narrowed refusal refuses a save that records an answer only while something is queued or running or an update
  is pending. On an idle, fresh encounter the save is accepted.
- `_reads_a_withdrawn_answer` reads only answers that no longer stand, so A19 passes.
- `_assessment_blockers` skips a `DETAIL_UNAVAILABLE` view with no blocker (1386).
- The `CONTEXT_VERSION` comment (68) records "a member's answer applied to the stored assessment with no recompute (a
  false 'reviewed' with an approved export)" as a regression.
- A legacy B is unaffected: `recompute_after_answers` returns None on a legacy context.

The wrong outcome holds. It is A18's and 3.10.7's claim, and it is R2B-5's class (a details save that changes the
answers, then a restore). The lens's high is kept, as R2B-5's was.

**Decision: accepted.** The fix is the hint's first option, a third A19 condition. On a gemini context, every standing
answer recorded after B was made must have had a re-assessment of B queued after it (an assess on B's context carrying
`jobs.AGAIN_MARK`). Otherwise the save is A19's ordinary change in case A, or RESTORE_REFUSED in case B. `update.restorable`
follows.

The test is "a recompute was queued", not "B's rows read it", so R4's designed shape still works: an answer whose own
recompute was queued and stopped, then a change and a restore, still restores, and Resume runs that recompute. The
recompute-on-restore option was not taken, for round 2's reason with R2B-5: it adds an act to the restore, and the
ordinary change already closes the case with no new act.

**Revision.** A18 and A19; 2.5 (the condition, and a third case bullet); 10 (`review.restorable`,
`jobs._change_context`); U8 (both shapes).

### R3B-3 (high): where a reading is owed while the codes are fresh, 3.4 supersedes the reconciliation's own reading

**Claim.**
- (a) A legacy encounter, fresh, whose E's own Corti run is UNKNOWN: the operator's reconciliation queues the interpret.
  3.4 supersedes it as restored (the codes are fresh). E then reads "being confirmed", with the outcome reconciled and
  nothing pending.
- (b) The same after a save and a restore made before the reconciliation: R2B-4's acts, in another order.

**Verified.**
- `reconcile` queues `interpret:…:after-reconcile:<run>` whenever `_new_path_owed`, which is true for a context that is
  not a gemini context (1966-1972). It refuses an already reconciled run (4070).
- 3.4's predicate 3 supersedes every context-free stage while `review.fresh`. Its start check runs after
  `_settle_from_exchange`, which finds nothing for a Corti run.
- `_state_and_run` reads the assessment's own UNKNOWN run as provider_unknown, reconciled or not (1779).
- `_assessment_blockers` keeps "The provider outcome is unknown" (1351-1352), so E's approved export is blocked for good.
- `_earlier_reading` refuses any stage on a legacy context (1024), so on this image the reading is the only attempt.

Today's code runs that interpret: `stage_interpret` checks only the revision.

**Scope.** Sequence (a) alone comes from the pre-refutation text (3.4 and 7.4 both predate round 1). It is accepted
because:
- (b) is R2B-4's own acts;
- A19, which round 2 wrote to close that class, names this very attempt ("or the interpret stage while a reading is
  owed") and claims that only a restore supersedes it.

So R2B-4's fix does not close its class.

**Decision: accepted, with a fix narrower in mechanism than the hint's (A21).** Under A21, `fresh` is false while a reading
is owed and the current assessment's own document review is an UNKNOWN run a reconciliation released. The consequences
come from rules already in the text:
- 3.4 no longer supersedes the reading;
- it is a target job;
- its analyze records E as the new context's earlier assessment;
- its predict sends the released attempt;
- the final replaces E, and "what changed" is computed against E.

E stays current and read-only meanwhile (A7, A9, A17). No save started this update, so it gets `update.kind` `check`, with
its own forms:
- the title is "Updating codes";
- the texts drop "Your change is saved" and read "from before this update";
- no restore clause is offered;
- `saved_by` is null, and `started_at` is the `provider.reconciled` row.

The hint's route was not taken: exempting `:after-reconcile:` keys from SUPERSEDED_RESTORED and having the chain read as
processing.
- The exemption needs a mark carried through the appraise and analyze keys, and target jobs widened while the codes are
  fresh.
- "Processing" after the analyze needs `earlier()`'s first branch changed, which also changes the switch-back state of
  9.4.
- It would also lose "what changed" and the earlier codes' read-only display. The owner's "While updated coding is
  pending, prevent approval or export of stale codes as current" and "show the updated codes and what changed" favour the
  update.

A participant's reconciliation there still ends superseded. The codes' own review stands, so no false state results, and
the codes go without that check (I10); this is recorded under "For the adoption". A v2 revision at the current versions is
unchanged: the reconciliation's predict runs as a chain re-run (R2B-3).

**Revision.**
- Vocabulary (`fresh`, `update pending`); A21; A19 and 2.5 (J5).
- 3.4 (a note); 5.1 (the title, `kind`, `started_at`, the JSON enum); 7.1 ("Check texts"); 7.4 (a paragraph).
- 9.1; 9.4 (the `update_pending` hazard, J10); 9.5 (a count, expected 0); 10.
- U17, U21, U22.

### R3B-4 (high): a refusal recorded before the install, met during an update, is neither retried, held nor explained — accepted in part

**Claim.**
- A pre-install Corti 402 (R0, no hold row) on a date that is not E's is met again when an update sets that date. The
  stage ends FAILED with a not-resent run.
- As 7.2 is written, no row and no refusal fits: no hold exists for "Resume after the release", and RETRY_UPDATE_NOTHING's
  condition is false.
- Read through A10 and A20, R0 "sets no provider hold", so a member's Retry could re-send it.

**Verified.**
- `_failed_before` holds any FAILED, sent run of the request in the encounter, whatever revision (641-654), and
  `_not_resent_run` carries the failed run's error (724-738). So the stage ends FAILED by 7.2's every-other-outcome bullet.
- 7.1's rows: the held row needs a standing hold or one this request set, and the failure row covers "a 5xx, another
  4xx". Neither fits.
- 7.2's refusals: RETRY_UPDATE_NOTHING ("the latest target job did not fail") is false, and RETRY_UPDATE_HELD needs a
  standing hold. Neither fits.
- 7.2's "They set Corti's provider hold, which an operator releases; then Resume sends once" is false for such a run.

The missing state is confirmed. The re-send is not demonstrated:
- 7.2's release rule reads the status ("other than 401, 402, 403 or 429");
- A10's own second sentence says payment and quota refusals are never retried by a member.

Only A10's first clause ("a failure that sets no provider hold"), read with A20's definition, invites that reading.

**Decision: accepted in part.**
- The state is given a 7.1 row of its own ("refused this same request before, and it is not sent again"; restore where
  A19 allows; no other way suggested, per 7.3's rule against inviting new requests).
- `retry_update` gets a refusal, RETRY_UPDATE_REFUSED_BEFORE.
- 7.2's never-retried paragraph is scoped: from the install on, a hold; before it, held per encounter.
- A10 now reads by status.
- The critical re-send outcome is not accepted as demonstrated.
- The stated limit is written down, and 9.5's report names it for the owner: no operator act releases such a refusal, so
  that update cannot finish for those details on that encounter, as today.

**Revision.** A10, A20; 7.1 (the row; the no-restore paragraph); 7.2; 7.3 ("Refusals recorded before the install"); 9.5;
10; U20.

### R3B-5 (medium) and R3T-4 (medium): a save during a first processing paused by its own refusal makes the final with the refused run

**Claim.**
- A first processing is paused by its own Corti 402, or a token 4xx, as RT6 made it.
- A setting save then re-checks with the refused run: `_decide_after_save` is unchanged in a first processing.
- The final is made with that run and reads provider_failed: "You can upload the document again", with no Resume. After
  the release every other paused upload resumes.
- The participants' first readings are sent for it.

**Verified.**
- `_decide_after_save` re-checks whenever `_run_answers` holds (4466-4491).
- `_run_in_use` leaves out only held runs, reservations the sweep settled and reconciled unknowns (4257-4292). A
  hold-setting run (FAILED and sent, or a token refusal NOT_SENT with its request and `started_at`) stands.
- A setting change leaves Corti's request unchanged (`_run_answers`, 4203).
- `_state_and_run` reads a final whose run did not succeed as provider_failed.

7.3's "never a final made with the refused run" and A16's RT6 sentence are false: RT6's fix does not close.

**Decision: accepted.** One fix closes both findings. No re-check takes a run a `ProviderHold` row names: in a first
processing, during an update (where such a run carrying E's request would otherwise pass as "E's own", J9), and in
`reconcile`'s participant branch. The save queues the predict instead:
- while the hold stands, the hold door pauses it again;
- after the release it sends the identical request once (`_failed_before` leaves that run out, 7.3).

**Revision.** A16; 2.2 step 5; 2.7; 7.2 (last paragraph); 7.3 "What a held stage does"; 10 (`jobs.py`, pinned behaviours);
U20.

### R3B-6 (low): the update A19 makes from the earlier codes' own values names no change

**Claim.** A19's ordinary change (case A) has `values(C2) == values(E.context)`. The panel reads "Changes saved—updating
codes" with an empty list and no reason given.

**Verified.** 5.1 computes `changes` as `values(encounter)` against `values(earlier.context)`, plus the revision when it
differs. The list is truthful but unexplained. The same empty list arises from T8's save back to a first processing's
unfinished codes.

**Decision: accepted.** When `changes` is empty within one revision, the list shows one fixed line chosen from rows:
- for T8's save back, "not finished … being finished for these details";
- for A19's ordinary change, "your answers, or an earlier check, changed since those codes were made";
- for kind `check`, A21's line.

3c words them.

**Revision.** 5.1; 10 (`customer_api.py`, `app.js`); U21.

### R3T-1 (high): a late finisher still colours its step when the newer chain runs no attempt of that kind

**Claim.**
- In W1's three saves, the third save re-checks with E's run, so no predict is queued for it.
- The first save's predict, a late finisher, then answers 500 and ends FAILED. It is the only, so the newest, PREDICT
  progress job, and it colours "Checking suggested codes: Did not finish" beside the update in progress and after it
  completes. With a 402 it reads "Stopped".
- An `:after-save:` twin that expires in a backlog after the running reading read the document makes "Identifying
  procedures: Stopped".

**Verified.**
- `_run_in_use` counts only finished runs, so while the first predict is SENDING the run in use is E's. The second save
  queues a predict, which the third save supersedes. The third save re-checks with E's run.
- 7.2's list ends the late finisher FAILED (StageFailure), and `run_job` writes no `superseded` (3656-3662). So the late
  finisher is a progress job again once it has finished.
- `_runs` joins the third save's chain to its run (157). `_fold` ranks stopped and failed above done (255, 258).
- `claim_next` expires a QUEUED job past its deadline with no `started_at` (3613-3616), and it takes the oldest job
  first. So the twin, queued before the running reading's successor, can expire while that successor runs on.

The judge's round-2 note that the newest-attempt rule covers RT3(b) is false for this shape.

**Decision: accepted.** The fold is read in two parts (5.2). For the outcome, a stage that carries a context colours its
step only while its context is the current context. Of the colouring attempts, and of the context-free ones, only the
newest attempt of each kind that started colours the step. One that never started colours it only when no attempt of its
kind in the run started. Every attempt keeps its row and its times.

The judge's round-2 objection to dropping stages `_superseded` would answer is respected:
- context-free stages are not read through `_superseded`;
- the rule applies only within the current run, so earlier runs' steps (the latest earlier run's state, T2) are read as
  before.

**Revision.** 5.2; 10 (`progress.py`); U16 (W1 with a 500 and a 402, with and without participants; the expired twin).

### R3T-2 (high): the newest-attempt rule makes a running step read "Waiting to start"

**Claim.** A legacy save while pass 1 is RUNNING queues its `:after-save:` twin. The step's newest attempt is the QUEUED
twin, so the step folds to `waiting`: "Identifying procedures: Waiting to start", with no active detail, while pass 1 is
sent for this very update.

**Verified.**
- `_fold` over QUEUED jobs alone returns `waiting` (258-266).
- `app.js` draws `waiting` as "Waiting to start" and the active detail only at an `active` step.
- Round 2's text says the running stage "never colours the step, whatever its outcome", against 5.2's own legacy
  expectation.

**Decision: accepted.** Activity is read from every progress job of the step, as today's fold reads it: one RUNNING job is
in progress; one QUEUED beside a finished one is in progress; only QUEUED ones are waiting. A superseded running job is not
a progress job, so a late finisher in flight never animates a step.

**Revision.** 5.2; 10; U16 (a save beside a running pass 1).

### R3T-3 (high): two addenda before the first one's update finishes, and "what changed" lists no decision

**Claim.** With two addenda, the first invalidates E's approval (`by_revision` R2) and the second finds nothing. J2's step
4 reads only "invalidated for N's revision" (R3), so the cleared approval is never listed.

**Verified.**
- `addenda` calls `invalidate_for_new_revision` for every addendum (371). It invalidates `current_decisions(decision_holder)`
  with `by_revision` the new revision (781-798).
- The holder stays E, which has no current decision left after R2.
- A1 and A13 accept a second, different addendum while the update is pending.
- Round 1's rule (E's latest decision per proposal) listed it. J2's equality claim is false across two addenda.

**Decision: accepted.** The fix is the hint: in case C, list every decision invalidated `by_revision` for a revision
recorded after E's revision, up to and including N's. Each such addendum belonged to this update, because E stays the
earlier codes until N.

**Revision.** 6.2 step 4 (and its explanation); 10; U11.

### R3T-5 (medium): an addendum during a re-run chain after the codes were final is not an update

**Claim.** During a chain re-run after the codes were final (R2B-3's processing state), an addendum leaves `earlier()`
and `earlier_for_new_context` with none:
- the re-run's assess #1 is on the current context;
- it is not of the new revision;
- T8's branch asked for the current revision.

The addendum, which cleared the final's approval, is then processed as a first processing, with no "Changes saved", no
earlier codes and no "what changed".

**Verified.**
- The vocabulary's branches and 4.5's code are as quoted.
- `addenda` moves `current_revision` and keeps `current_context`, and it invalidates the holder's (N1's) decisions.

4.5's bullet ("a save made during such a chain takes the assessment the page shows") is false for an addendum. 1.1 says
an addendum always makes an update.

**Decision: accepted.** T8's branch no longer asks that the assessment be of the current revision. An addendum recorded
during such a chain is an update (kind `documentation`) whose earlier codes are the assessment the page shows: the
vocabulary's claim "the earlier assessment is also the current assessment" holds. R3T-3's range then lists the last
final's cleared approval.

The hint's alternative (the decision holder, N1) was not taken, because N1 is not the current assessment there.

The same rule makes an addendum during a first processing whose unfinished assess #1 was shown an update of those codes,
as T8 makes a save. This narrows what is exportable: a draft of those codes is earlier, 8.1. That is consistent with 1.1's
"always".

**Revision.** Vocabulary (`earlier`, `update pending`); 4.5 (the code and two bullets); 6.2 step 4; 8.1; 10; U11, U22.

### R3T-6 (medium): a pre-install 401/402/403/429 held by `_failed_before` ends an update in an undescribed state

**Claim.** This is R3B-4's state from the truth side: a pre-install 429 on D1, met by a post-install update that sets D1.
No 7.1 row or `retry_update` outcome fits, and "Try updating again" would be refused with a false sentence.

**Verified.** As R3B-4.

**Decision: accepted.** It shares R3B-4's fix: the refused-before row, RETRY_UPDATE_REFUSED_BEFORE, and the stated limit.
The hint's "upload the document again" was not adopted as a suggested way out. A new upload is a new encounter,
`_failed_before` is per encounter, and the identical refused request would be sent once. That is the repeated request 7.3
stopped the refused text from inviting. The way out given is the restore, where A19 allows it.

**Revision.** As R3B-4.

### R3T-7 (low): after the release, PROVIDER_PAUSED still says the coding service "is paused"

**Claim.** PROVIDER_PAUSED reads the stage's record, as `interpreter_paused` does. After an operator's release it still
says the service "is paused on this installation".

**Verified.**
- `progress.interpreter_paused` reads only the stage (335-341), and `encounter_progress` keys the paused text on it
  (589-593).
- Round 2 made `provider_paused` "the analogue".

**Decision: accepted.** The fix is the hint's second option. `provider_paused` also reads the standing hold, a row the web
process can read, unlike the interpreter's mode, which only the worker knows. After the release the stage reads stopped by
the system (STOPPED_BY_SYSTEM, with Resume). During an update the held row gives way to 7.1's stopped-by-the-system row in
the same way: one reader serves both. The held row's after-release form is round 1's text; it is changed only so the one
reader stays one, and nothing else in it changed. INTERPRETATION_PAUSED's accepted tense (D11) is untouched.

**Revision.** 7.1 (the header; the held row's situation); 7.3 "What a held stage does"; 10 (`progress.py`,
`provider_holds.active`); U20.

---

## Defects in this judge's own fixes, found while re-reading them

### J5 (from A21): the case-B reason for RESTORE_REFUSED became false for a reconciled unknown

**What.** A19, and 2.5's paragraph on a save A19 keeps from being a restore, justify the case-B refusal by "the kept
context's rows would read B fresh again with every stage superseded". Under A21, a B whose own review is a reconciled
unknown on a context whose reading is owed no longer reads fresh, so that reason is false for that cause.

**Repair.** The sentence is scoped to say so. The refusal is kept for every cause: its text is true, and one rule answers
all of them. Relaxing it would have touched A19, 1.3, 1.4, 2.5 and U8 for a corner A19 already covers.

### J6 (from R3B-1): "no such status is committed without its hold" became false on the fallback path

**What.** A20's sentence and round 2's sentence in 7.3 both said no held status is ever committed without its hold. The
fallback commits the status, then writes the hold in a separate transaction.

**Repair.** Both sentences now say "on that path", and the fallback's own guarantee is stated: the run is UNKNOWN, so its
encounter is blocked whatever the hold's write does.

### J7 (from R3B-1): the fallback's FAILED stage with an UNKNOWN run had no `retry_update` refusal

**What.** The fallback leaves a FAILED predict whose run is UNKNOWN. 7.2 said "An UNKNOWN outcome is reconciled, never
retried" but listed no refusal for it, and RETRY_UPDATE_NOTHING's condition is false there. That is the gap R3T-6 names,
reopened by this fix.

**Repair.** `jobs.RETRY_UNKNOWN` (existing wording, already in `customer_api.KNOWN_ERRORS`) is listed among `retry_update`'s
refusals.

### J8 (from A21): kind `check` defined by the absence of save rows would mislabel install anomalies

**What.** The first definition was "no `context.changed` or `revision.addendum` row after the earlier codes and the newest
restore". It would also have labelled 9.5's "update pending that no save queued" anomalies as a reconciliation's update,
with a false cause line.

**Repair.** Kind `check` also requires A21's own condition. An earlier wording, "the one attempt it can release is the
reading … nothing else is sent", was also corrected: it was untrue for a v2 revision of an older inventory version, whose
context is a gemini context. There the reading is what `jobs.reconcile` releases.

### J9 (from R3B-5): the fix first covered a first processing only

**What.** During an update, 2.2 re-checks with "E's own run", which includes "a run carrying the same request as it". A
hold-setting run made during the update for E's request (E's own run not sent for a local reason, then the update's single
send refused) passes that test. It would make the same final with the refused run.

**Repair.** The rule applies in a first processing and during an update alike (2.2, 2.7).

### J10 (from A21): A21's update before its analyze escaped 9.4's `update_pending` hazard

**What.** 9.4 names encounters with a pending update at a switch-back by two tests: values that differ from the current
context's, or a current assessment off the current context. A21's update, before its analyze, passes neither test. Its
values are the context's, and its codes are on the current context. So the switch-back note would not list it, and the old
image would show the codes with the reconciled run and nothing pending.

**Repair.** The hazard reason gains A21's condition, and the note says what the old image is expected to show. U17 gains
the case and records what the old image actually shows.

Two authoring slips were corrected before the text was settled, and are not counted:
- an over-broad claim that every failed update meets exactly one refusal or a release (false for an unbuilt request);
- a stale reference to A10's old "sets no provider hold" wording.

---

## Re-read against the owner's words and the earlier rounds

**Against each of the owner's requirements:**
- **Background recheck after saving:** unchanged. A21 adds an update started by an operator's explicit act, not by a
  save, and names it so.
- **No calls on keystrokes or cosmetic changes:** untouched.
- **Truthful progress, "Changes saved—updating codes":**
  - R3T-1 and R3T-2 remove a false "Did not finish", "Stopped" and "Waiting to start".
  - R3T-7 removes a false "is paused".
  - R3B-6 says why an update with no listed change runs.
  - A21's update says "Updating codes", since nothing was saved. The owner's title stays exactly as given for every
    update a save starts.
- **Prevent duplicate submissions:**
  - no fix adds a chain or a send;
  - R3B-1 closes the re-post of refused credentials;
  - R3B-5 sends the refused request once, only after the release;
  - A21's reading is once per revision and version pair, its predict the one released attempt.
- **Bind results to the saved revision; older results never overwrite newer work:**
  - R3T-5 makes an addendum during a re-run an update, so A17 keeps the earlier codes until the addendum's final;
  - R3B-2 keeps an older result from becoming current over a newer answer.
- **Rerun only what changed; reuse only when inputs match:**
  - R3B-2 stops reusing B when an answer, one of its inputs, changed;
  - A21's reading is the one attempt the reconciliation released, on a reading never made at the current versions.
- **Preserve historical approvals and reports; no approval or export of stale codes as current:**
  - nothing widens what is approvable or exportable;
  - A21 and R3T-5 narrow it (the earlier codes are read-only while those updates run);
  - R3T-3 lists every approval the update cleared.
- **Updated codes and what changed:** R3T-3 and R3T-5 for addenda; A21 ends with "what changed" against the codes it
  replaces.
- **Retry with a clear explanation; quota and payment without repeated requests:**
  - R3B-4 and R3T-6 give the pre-install refusal its own text and a true refusal, with no Retry;
  - R3B-1 and R3B-5 close two repeated-request paths;
  - the one remaining case, the hold's own write failing in the fallback, is the killed-worker limit already stated.
- **Legacy and new encounters both:** A21 covers legacy and older-version encounters; R3B-2 applies only where an answer
  is recomputed (gemini contexts), by design.

**Against the first two rounds' fixes:**
- A17, A18 (R4, R5, T12), T8, T9, T11, T13, L4, L5, R6, T2, T5, T7, R2/L2, J1, and round 2's R2B-1 to R2B-7, RT1 to RT8 and
  J2 to J4 still hold where this round's changes meet them.
- J2's rows-only rule is kept and widened only in its case-C range. U11's "changing the participants configured changes
  nothing" still holds.
- R4's stopped-recompute restore still works: R3B-2's condition reads whether a recompute was queued.
- L4's "E's own run" is narrowed only by excluding hold-setting runs, which pause instead of making a final no worse than E.
- R2B-3's processing state is unchanged for a chain re-run with no save or addendum, and for every reconciliation on a v2
  revision at the current versions.
- RT3's newest-attempt rule survives for outcomes, restricted to attempts that started; its activity half is restored to
  today's fold.
- RT6 and A16 now hold for a save made during the pause.

**Confidentiality:** the 15 new or changed customer strings match nothing in `customer_api.FORBIDDEN`. The check forms name
no provider, model or reader.

## For the adoption

**Decisions to record (DECISIONS entries):**
- **A21 (new).** A reconciliation that releases the current codes' own unknown document review while a reading is owed
  (legacy, or a v2 revision of an older inventory version) starts an update of those codes with no save (kind `check`):
  the reading, then the chain, with "what changed" against them.
- **A19, amended:** a third condition. On a gemini context, every standing answer recorded after B had a recompute of B
  queued.
- **A20, amended:**
  - the fallback for an outcome whose record fails (UNKNOWN, with its status; the hold in a transaction of its own);
  - a pre-install refusal is held per encounter and never retried.
- **A10, amended:** a member's retry of the document review reads the status, never the hold row.
- **A16, amended:** no save made during a pause re-checks with the refused run.
- **A18, amended:** its parenthesis names R3B-2's answer.
- With these, FINAL-V2 4.12's row cites A20 and A16 as amended.

**Owner-facing items, through 9.5's report (class b):**
- An update that meets a refusal recorded before the install, for a request that is not the earlier codes' own, ends
  failed with "refused this same request before, and it is not sent again". It cannot finish for those details on that
  encounter: no operator act releases a pre-install refusal, as today. The restore, where A19 allows it, is the way back.
  The existing pre-install refusal count states this.
- New count: encounters whose current codes' own document review is an UNKNOWN run already reconciled while a reading is
  owed. From the install on they read an update that no save started. Expected 0, reported with ids.
- A21's reconciliation of a legacy encounter has the document read with the current reading, as v1's FINAL 6.9 made it:
  two Gemini passes and the Corti attempt, at 9.2's cost. Its final clears every legacy approval (D7), listed in "what
  changed". The operator's reconciliation therefore carries that cost and that effect. If the owner wants a reconciliation
  that changes nothing on a legacy encounter instead, that is a product choice (class a).
- A participant's reconciliation on fresh codes whose reading is owed releases nothing. Its reading ends superseded, and
  the codes stand without that participant's check, as after its failure (I10). This is recorded as a limit, not a
  defect: no state is false.

**Builder notes:**
- **5b.**
  - `_settle_unrecorded` writes `http_status` with its small fields. For a status A20 holds it records UNKNOWN whatever
    `sent` says, then calls `provider_holds.record` in a transaction of its own.
  - `_decide_after_save` and `reconcile`'s participant branch never re-check with a run a `ProviderHold` row names.
  - `review.fresh` gains A21's clause.
  - `earlier()` and `earlier_for_new_context` drop the current-revision test from T8's branch.
  - `review.restorable` gains A19's third condition, a rows query: standing `MemberAnswer`s of B's revision with
    `answered_at > B.created_at`, each with an AGAIN-mark assess on B's context created after it.
  - `retry_update` gains RETRY_UPDATE_REFUSED_BEFORE and lists `jobs.RETRY_UNKNOWN`.
  - `progress._fold`'s two parts: activity from every progress job; outcome from current-context stages and the newest
    started attempt of each kind. `progress.provider_paused` reads `provider_holds.active('corti')`.
- **3c** words:
  - the refused-before row's sentence and RETRY_UPDATE_REFUSED_BEFORE;
  - the three fixed lines for an empty `changes`;
  - the check forms (title "Updating codes"; "from before this update"; no "Your change is saved"; no restore clause).
  The meanings are given in the amendment, and the customer scan covers them.
- **5d** draws:
  - kind `check`'s title and its null "Saved by";
  - the fixed line in place of an empty saved-changes list.
- **6b** adds A21's count to 9.5 and states the refused-before limit in the report.
- **Tests:**
  - U8 (R3B-2, both shapes); U11 (two addenda; an addendum during a re-run chain); U17 (A21 at a switch-back, J10);
  - U16 (W1 with a 500 and a 402; a save beside a running pass 1; an expired twin);
  - U20 (the fallback with the record failing; a pre-install 402 met by an update; a save during a paused first
    processing; the page after the release);
  - U21 (check texts; the fixed lines); U22 (A21 on legacy and older-version fixtures; an addendum during the re-run).
- **Still unmeasured, carried from round 2:** the vendors' refusal statuses: Corti's 402 and 429, and both participants'.
  A20's fail-closed reading stands until they are measured.
