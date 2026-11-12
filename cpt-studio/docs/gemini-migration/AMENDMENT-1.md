# FINAL-V2 amendment 1: the codes are updated automatically after a save

**Status.** The design of FINAL-V2 amendment 1, written 2026-11-12 by the designer of workflow `cpt-gemini-v2-amend1`. It
was refuted by three lenses (races and duplicates; truth, staleness, approval and export; legacy, cost and compatibility)
and revised by the judge of the refutation on 2026-11-12: 30 findings, each verified against the code at `c0d6d52a7`,
30 accepted (`AMEND-REFUTATIONS.md` gives each finding, what was verified and the decision). Every change the refutation
made is tagged `[R:<lens>-<id>]`; the text before it is `AMENDMENT-1-pre-refutation.md`. A bounded second refutation of
the revision (two lenses: binding, races, duplicates and holds; truth, exports, the screen and confidentiality) reported
16 findings; its judge accepted 14, accepted one in part and rejected one (`r2/AMEND-REFUTATIONS-R2.md`). Every change it
made is tagged `[R2:<lens>-<id>]`, and the text before it is `r2/AMENDMENT-1-r1.md`. A bounded third refutation of
that second revision (two lenses: binding, restores and holds; truth, the screen, exports and confidentiality) reported
13 findings; its judge accepted 12 and accepted one in part (`r3/AMEND-REFUTATIONS-R3.md`). Every change it made is
tagged `[R3:<lens>-<id>]`, and the text before it is `r3/AMENDMENT-1-r2.md`. Nothing was built, sent, installed or run
in docker. It was written blind to `acceptance-a1/` and to every sealed set.

**Governs.** The owner's amendment of 2026-11-12, verbatim
(`gemini-migration/owner-autorecheck-20261112-verbatim.md`; the rulings file, "Owner amendment, 2026-11-12"):

> Amend my previous acceptance: make Gemini rechecking automatic after a successful save of changes affecting clinical content or coding context. Remove the mandatory “Check again” step from the normal workflow.
>
> Requirements:
> - Queue the recheck in the background after saving. Do not call providers on every keystroke or for cosmetic changes.
> - Show “Changes saved—updating codes” with truthful progress.
> - Prevent duplicate submissions. Bind results to the exact saved revision; results from an older revision must never overwrite newer work.
> - Rerun only stages whose inputs changed. Reuse results only when their inputs and relevant versions still match.
> - Preserve historical approvals and reports. While updated coding is pending, prevent approval or export of stale codes as current.
> - When complete, show the updated codes and what changed. Keep final reviewer approval explicit.
> - Keep a manual Retry button for failures, with a clear explanation. Handle quota and payment failures without repeated requests.
>
> Apply this to edited legacy encounters as well as new encounters. Verify rapid successive edits, failures, reload persistence and actual exports. Record this as superseding the earlier mandatory manual-recheck decision, then continue implementation and installation.

Below the owner's words: DECISIONS D184 and the session interpretation (a)-(h) recorded with it; then FINAL-V2
(`docs/gemini-migration/FINAL-V2.md`, sha256 `9d650797c41091d3ab9ce2f783c1838e5aa394bb926c5d5b2733c2186d733b21`) as this
amendment changes it. Where this amendment and the owner's words disagree, the owner's words win and the disagreement is
a defect of this amendment.

**Base.** Branch `feat/cpt-studio-gemini-interpreter-20261109` at `c0d6d52a7`. Paths are relative to `cpt-studio/`. Code is
cited as `FILE:FUNCTION` and describes the CURRENT code (the v1 migration's plus the installed release's). The v2 pipeline
of FINAL-V2 7.4 (extract, interpret = pass 1, appraise = pass 2, analyze, predict, astra, fable, assess #1, astra_peer,
fable_peer, assess #2) is designed and not built; this amendment specifies what step 5b and the others build on top of it.

**Read for this design:** `studio/jobs.py` (the stages, keys, doors, member actions, `mark_stale`), `studio/review.py`
(decisions, persistence, readiness, the derived state), `studio/api.py` (whole), `studio/progress.py` (whole),
`studio/customer_api.py` (most), `studio/reports.py` (the customer report and the operator snapshot's revision and context),
`studio/models.py` (whole), `studio/answers.py` (save, revoke, the date block), `studio/static/studio/app.js` (the progress
panel, the details panel, decisions, exports, polling), `studio/interpretation/holds.py` and `adapter.classify`,
`studio/interpretation/facts.derive`, `studio/client_contract.py`, the installer's stage scripts. **Not read, so no claim is
made about them:** `studio/serializers.py`, `studio/operator.py`, `styles.css`, the internals of `answers._rows` and of
`review.effective_view`. The builders read them before changing anything that touches them.

---

## Vocabulary

These definitions are used in every section. Each is a pure function of stored rows, evaluated under the encounter's row
lock wherever it gates a write.

| term | definition |
|---|---|
| **coding-context fields** | `types.CONTEXT_FACTS` = `service_date`, `setting`, `billing_context`, `patient_status` |
| **values(x)** | the member values of an encounter or a context, normalized: only the four fields, only non-empty stripped strings, `service_date` as a canonical ISO date. `values(encounter)` reads `Encounter.user_values`; `values(context)` reads `EncounterContext.user_values` |
| **fresh(encounter)** | the current assessment A exists, `A.revision == current_revision`, `A.context == current_context`, `values(A.context) == values(encounter)`, and `review.is_final(A)`; and, while a reading is owed, A's own document review is not an unknown outcome an operator's reconciliation has released (`A.provider_run` UNKNOWN with `reconciled_at` set): that reconciliation's one attempt is then the reading (7.4), so those codes are being updated (A21) [R3:binding-R3B-3]. The codes on the page are then the current codes |
| **earlier(encounter)** | while the encounter is not fresh: A when A is final; else, when A is not on the current context, the current context's recorded `earlier_assessment` (4.5) [R2:binding-R2B-3]; else A when A is not of the current revision, or its context is not the current one, or its values are not the saved ones: a save or an addendum after an unfinished assessment whose codes the member was shown — a first processing's [R:truth-T8], or the assess #1 of a chain re-run after the codes were final, which an addendum recorded during that chain finds current [R3:truth-R3T-5]; else none. "The earlier codes" are this assessment's. While an update is pending, the earlier assessment is also the current assessment: an assessment of the update that is not final never becomes current (A17) [R:races-R3][R:legacy-L6]. A non-final A of the current revision, on the current context, with the saved values gives none [R2:binding-R2B-3][R3:truth-R3T-5]: it is the assess #1 of a chain re-run after the codes were final (an operator's reconciliation of an unknown outcome, a Resume), which persist makes current outside an update as today; that is processing, never an update |
| **update pending** | not fresh and `earlier(encounter)` exists. A first processing that no save has made stale (no codes shown before a change) is not an update [R:truth-T8], nor is a chain re-run on the current context after the codes were final (4.5) [R2:binding-R2B-3], until a save or an addendum is recorded during it [R3:truth-R3T-5]. An operator's reconciliation that releases the current codes' own unknown document review while a reading is owed makes one, with no save (A21) [R3:binding-R3B-3] |
| **reading owed** | the current context is missing, is of another revision, is not a gemini context, names an inventory not read at the current versions, or `values(current context) != values(encounter)`. Only then do the stages that read or derive the document (interpret, appraise, analyze) serve the encounter |
| **target jobs** | the jobs that serve the encounter's saved state (3.4): when fresh, the jobs of the current revision created after the current assessment whose context is the current context; when not fresh, the jobs of the current revision whose context is the current context, plus, while a reading is owed, those that carry no context (extract, interpret, appraise, analyze). A job whose `result` says `superseded` is never a target job. Target jobs decide the derived state, readiness, Resume and Retry; they never decide progress, which folds the progress jobs [R:truth-T2] |
| **progress jobs** | what the progress panel folds (5.2) [R:truth-T2]: the current revision's jobs, oldest first, minus every superseded job (a finished job whose `result` says `superseded`; an active job for which `jobs._superseded` answers a reason), cut into runs by today's rule (`progress._runs`: a job queued while every earlier job of the revision had finished starts a run; a job queued while one was still active joins its run, so the chains of rapid saves form one run). The current run is the last one; when fresh it is the run that made the current assessment |
| **member-act stage** | a stage a member's or an operator's act on the current final assessment queued [R:races-R4][R:races-R5]: an answer's recompute or a re-assessment after a confirmation (an assess whose key carries `jobs.AGAIN_MARK`, `:c:`), the bounded second review (`review2`) and the assess its follow-up queues (a key carrying `jobs.REVIEW2_MARK`), and an operator's `reassess_retained` |
| **superseded** | a stage that no longer serves the saved state (3.4). It ends without sending, writes no context and no assessment, records `{'skipped': <why>, 'superseded': true}` and state SUCCEEDED, and queues nothing |

## Decisions this amendment takes

To be recorded as DECISIONS entries with the amendment's adoption. Each section gives its reason.

- **A1** A save is accepted while an update is pending; the newer save supersedes the older one (3.1). The refusal while
  busy stays for clinical answers, their withdrawal, Resume, reconcile, Retry and the second review; and a context save is
  refused while a member-act stage on the current context is queued or running (A18) [R:races-R4][R:races-R5].
- **A2** Binding is by inputs: a result becomes current only if, at its commit and under the row lock, its revision, its
  context and the saved values are the encounter's (4). Superseded work is recorded as superseded, never as a failure.
- **A3** A save with no changed value writes nothing. A save that restores the earlier codes' own values makes those codes
  current again, with nothing queued, at any point before the update's final assessment: the earlier codes stay the
  current assessment until then (A17), so a recorded assess #1 of the update no longer turns a restore into a new update
  (2.5) [R:races-R3][R:legacy-L6]. A restore applies only within one revision, only to final earlier codes, and only to
  earlier codes that can be current again as they stand (A19) [R2:binding-R2B-4][R2:binding-R2B-5].
- **A4** On a revision with no inventory at the current versions, a save stores the values and queues the first stage the
  reading owes, coalesced with one already queued (never with one that is running, which may not reach the analyze: the
  save queues the owed stage beside it, and the doors reuse what it stores) [R:races-R6]. Coalescing is a compare-and-set
  that renews the queued stage's queue deadline, and never takes the stale sweep's settled path, which sends nothing
  whatever it finds [R2:binding-R2B-7]. Analyze derives the context with the newest values under the row lock (2.3, 4.2).
- **A5** One new nullable column, `EncounterContext.earlier_assessment`, set at insert (4.5). It names the earlier codes
  while the update runs and the base of "what changed" afterwards.
- **A6** During an update, the earlier codes E are replaced only by a final assessment (A17) whose reading settled and whose
  document review succeeded, was reused, or was held on purpose (a member date conflict) — or whose document review is
  E's own: the update's Corti request is byte-identical to the one E's run carried, or neither could be built from the
  same revision text, so the review's input did not change and its outcome is E's, with nothing re-sent
  [R:legacy-L4]. Any other outcome — a failure, a request not sent for any reason, a request that cannot be built — ends
  the update failed, or paused under a provider hold (A16), and leaves the earlier codes in place as earlier codes (7)
  [R:legacy-L5].
- **A7** While an update is pending, every decision and every new export of the earlier codes is refused server-side (5.3).
- **A8** "What changed" is computed from stored rows only, against the assessment the update replaced (6.2).
- **A9** Earlier exports stay downloadable. An export is current only while its marker matches AND no update is pending
  [R:races-R1][R:truth-T1][R:legacy-L1]; a customer download of an export that is not current is served with an EARLIER
  EXPORT banner, instead of today's 409 for an approved one; every new export states the revision, the details and the
  time its codes were made (customer report format @2) (8).
- **A10** Retry: the recorded retry of D11 for the reading (pass 1 and pass 2); a recorded, once-per-failed-run retry of the
  document review for a failure whose status 7.3's table does not hold (a 5xx, another 4xx, a transport failure, or a
  request not sent for a local reason) [R3:binding-R3B-4]; a re-run of a failed stage that sends nothing (7.2).
  Authentication, permission, payment and quota refusals — the statuses 7.3's table holds, read by status whether or not
  a `ProviderHold` row names the run — are never retried by a member: from the install on they set the provider hold
  (A16), as A20 classifies them [R:races-R2][R:legacy-L2][R2:truth-RT1]; one recorded before the install stays held
  against its identical request, and an update that meets it ends failed with its own text and nothing to retry (7.1,
  7.3) [R3:binding-R3B-4][R3:truth-R3T-6]. No retry of a document too long to be read (C5).
- **A11** HTTP 402 joins the interpreter's quota hold (fail-closed; Google is not documented to send it) (7.3).
- **A12** A context save on a revision that has no inventory at the current versions and is over the size bound, or cannot be
  framed, is refused before anything is written: its update could never finish (1.4). The same refusal applies to an
  addendum whose combined text would be over the bound or cannot be framed, before the revision is recorded and before any
  decision is invalidated (2.4) [R:truth-T7].
- **A13** An addendum whose text equals the current revision's own addendum text is refused as a duplicate (3.9).
- **A14** The earlier codes of a legacy encounter are always read under their own sentinel label (5.1).
- **A15** The member-actions invariant of `jobs.py` ("at most one stage chain is ever queued per encounter") is replaced by:
  at most one chain serves the saved state; every other chain sends nothing after it is superseded, and nothing it computes
  becomes current (3.10).
- **A16** [R:races-R2][R:legacy-L2] Corti, Astra and Fable each get an installation-wide provider hold, shaped like the
  interpreter's (append-only, ended by an operator's recorded release): an authentication, permission, payment or quota
  refusal by that provider sets it (A20's classification, recorded with the outcome that carries it, whatever the stage)
  [R2:truth-RT1][R2:binding-R2B-1], and while it stands no request of that provider is sent by any encounter (7.3); a
  stored answer is still reused. A Corti request that sets it pauses its document as one the hold keeps unsent does, in a
  first processing as during an update [R2:truth-RT6], and no save made while it is paused re-checks with that refused
  run: the save queues the predict, which the hold pauses again or, after the release, sends once (2.2)
  [R3:binding-R3B-5][R3:truth-R3T-4]. This amends FINAL-V2 4.12 ("Corti, Astra and Fable unchanged"): the owner's
  "Handle quota and payment failures without repeated requests" and D184's "quota, authentication and payment failures
  hold without repeated requests" rule it, and the automatic recheck is what multiplies the sends a refusal would
  otherwise repeat.
- **A17** [R:races-R3][R:legacy-L6][R:truth-T6] While an update is pending, an assessment that is not final (an assess #1
  that owes peer stages) is recorded without becoming the current assessment and changes no other assessment's rows (it
  withdraws and closes no earlier clarification); the final assessment that passes 4.1 becomes current and does everything
  `persist_assessment` does today. So the earlier codes stay the current assessment, with their open questions, until the
  update's final assessment; a restore applies until then (2.5); and nothing on the page is read from the update's
  unfinished work. During a first processing nothing changes: its assess #1 becomes current as today.
- **A18** [R:races-R4][R:races-R5][R:truth-T12] A context save is refused (the existing busy sentence) while a member-act
  stage on the current context is queued or running, and an answer's withdrawal is refused while an update is pending, as
  a new answer is (1.4). A member's act on the current codes is therefore never superseded by a context save, and a
  restore never brings back codes that read an answer whose change was never applied (A19 covers the answer a details
  save itself replaces [R2:binding-R2B-5], and the one it records beside a change of the details, which no recompute
  reads [R3:binding-R3B-2]).
- **A19** [R2:binding-R2B-4][R2:binding-R2B-5] A restore applies only to earlier codes that can be current again as they
  stand: B reads no member answer that no longer stands (`review._reads_a_withdrawn_answer(B)` is false; a value saved in
  a details row answered "Not documented" revokes that answer, `answers._save_details`), and B's document review is not an
  unknown outcome an operator's reconciliation has released (`B.provider_run` UNKNOWN with `reconciled_at` set: its one
  released attempt is still owed, and `jobs.reconcile` will not release it twice); and, where B is on a gemini context
  (whose answers are recomputed, `jobs.recompute_after_answers`; on a legacy one an answer stands on the overlay by
  design), every member answer of B's revision recorded after B was made that still stands had a re-assessment of B
  queued after it (an assess on B's context carrying `jobs.AGAIN_MARK`) — a details save that records an answer beside a
  change of the details queues none, leaving the answer to the change's own chain (`answers._save_details`), so B would
  come back with that answer applied by the overlay alone, read by no assessment [R3:binding-R3B-2]. Otherwise a save of
  B's values is an ordinary change where it makes a new context (case A, 2.2): its chain makes the codes for those values
  with the answers that stand now and spends the released attempt, reusing every stored provider answer; where it would
  keep the context (case B) it is refused with RESTORE_REFUSED, nothing written (2.5), because the kept context's rows
  would read B fresh again with every stage superseded (for a reconciled unknown, A21 keeps them from reading fresh; the
  one refusal is kept for every cause, J5) [R3:binding-R3B-3]. The texts offer a restore only where one applies
  (`update.restorable`, 5.1).
- **A20** [R2:truth-RT1][R2:binding-R2B-2][R2:binding-R2B-1][R2:truth-RT2] One classification of the refusals that set a
  provider hold, stated once (7.3's table) and read by every other passage: Corti's coding service answering 401, 402,
  403 or 429; Corti's token endpoint answering any 4xx (its request carries only the installation's credentials and is
  the same for every encounter, so no 4xx of it is request-specific); a participant's exchange answering any 4xx but 413
  (fail-closed: a vendor's payment refusal may arrive under another status, D39's lesson; Anthropic has answered an
  exhausted credit balance with HTTP 400). `jobs._send` records the hold in the transaction that records that status, so
  on that path no such status is committed without its hold; when that record fails, the fallback records the run
  unknown with the status among its few fields, and the hold right after it in a transaction of its own, so the run's
  encounter is blocked whatever that second write does (7.3) [R3:binding-R3B-1]. A hold-setting run is a run a
  `ProviderHold` row names, never one read by its status alone; a refusal recorded before the install, which no row
  names, is still never retried by a member (A10, by status) and holds only its identical request, in its encounter
  (7.3) [R3:binding-R3B-4].
- **A21** [R3:binding-R3B-3] An operator's reconciliation that releases the current codes' own unknown document review
  while a reading is owed (a legacy encounter, or a v2 revision whose inventory is of an older version) starts an update
  of those codes: there the one attempt it releases is the reading (7.4, `jobs.reconcile`; on a context that is not a
  gemini context nothing else can be sent, `jobs._earlier_reading`), so those codes are no longer fresh (vocabulary), the
  reading is a target job that 3.4 never supersedes as restored, and its chain ends in a final that replaces them, with
  "what changed" against them. No save started it: `update.kind` is `check`, and the update's texts name no change of the
  member's (5.1, 7.1). Before the reconciliation the codes stay fresh and read "being confirmed", truly.

---

## 1. Triggers

### 1.1 What queues an update

| save | where it enters today | queues an update when |
|---|---|---|
| a new revision: an addendum | `api.py:addenda` (a new `SourceRevision`, `review.invalidate_for_new_revision`, `jobs.start_pipeline`) | always (clinical content changed) |
| a new revision: an upload | `api.py:encounters` POST, `intake.create_encounter` | never as an update: an upload makes a new encounter, and its first processing has no earlier codes. Its own pipeline is unchanged |
| a context save through the API | `api.py:context` -> `jobs.change_context` (accepts `service_date`, `setting`, `billing_context`) | the saved values differ (1.3) |
| a context save through the details panel | `api.py:details` -> `answers.save_details` -> `_save_details` -> `jobs.change_context` (accepts the date row and the choice rows: `setting`, `patient_status`, `billing_context`) | the saved values differ (1.3) |
| a reviewer's confirmation of a date | `review.confirm_finding` -> `jobs.change_context` | dormant in this release (`review.confirmations_offered` is False); if offered, as a context save |

The coding-context fields are the four of `types.CONTEXT_FACTS`; `interpretation.facts.derive` refuses any other name. What
reads them (`review.py:_what_differs` states it): the service date for every dated check and for Corti's request (D2); the
setting, patient status and billing context for the E/M codes; the billing context for a PC/TC code.

### 1.2 What does not

| change | why nothing is queued |
|---|---|
| a save whose values equal the saved ones (1.3) | nothing changed: nothing is written either, not even an audit row |
| typing in a field | never reaches the server: `app.js:onInput` and `app.js:onChange` call `enterDetailDate` and `chooseDetail`, which only change `state.answers`; the one request is `app.js:saveDetails`, on the Save button |
| the title | set at upload by `api.py:encounters`; `cptstudio/urls.py` has no route that edits it. A future title edit is not a coding-context field and must not call `change_context` |
| a decision | `api.py:decisions` -> `review.record_decision`: its own flow, no stage |
| a member answer ("Not documented", "Cannot confirm") and its withdrawal | `answers._save_details` and `answers.revoke_answer` -> `jobs.recompute_after_answers`: their own flow, an AGAIN assess, nothing sent (unchanged) |
| display state (an open "Why this code?", the selected passage, the open History) | client only: `state.open`, `state.selectedEvidence` in `app.js` |
| polling the page | `progress.py` writes, queues and sends nothing (its docstring; R6 4.5), and neither does `customer_api.encounter_json` |
| Stop, Resume, Retry, reconcile, the second review, an export | explicit acts with their own rules (3.6, 7, 8) |

### 1.3 How "changed" is computed, server-side

In `jobs.change_context`, inside the transaction that holds the encounter's row lock (`jobs._locked`), before anything is
written:

1. `before = values(encounter)`.
2. `after = values(merge(encounter.user_values, submitted))`, where `merge` is `jobs._merge_values`' rule (an empty value
   clears the field) applied to a copy. `api.py:context` already canonicalizes the date (`_parse_date`) and the choices
   (`_PIPE_choice`); `answers._save_details` already validates each row's value.
3. `changed = sorted(field for field in CONTEXT_FACTS if before.get(field) != after.get(field))`.
4. `changed` empty: nothing is written (no `Encounter` save, no context, no job, no audit row) and the call returns
   `ContextSave(unchanged=True)`. `api.py:context` answers 200 `{"context_id": <the current context>, "unchanged": true,
   "updating": <update pending>}`; a change answers 201 `{"context_id": ..., "updating": true}`, and a restore (2.5)
   answers 201 `{"context_id": ..., "updating": false, "restored": true}` [R:truth-T13]. `answers._save_details` answers
   `reassessing` from the same `ContextSave` (`updating`, or a recompute it queued), never from `bool(changed)`, and adds
   `restored`; `app.js:saveDetails` toasts "Saved. The codes from before your change are current again." for a restore,
   and "The results are being updated." only when `reassessing` is true [R:truth-T13].
5. Otherwise, in this order: A18's member-act refusal (1.4) [R:races-R4]; the restore rule (2.5), with A19's refusal of a
   case-B save of earlier codes that cannot stand as they are (RESTORE_REFUSED, 2.5) [R2:binding-R2B-4][R2:binding-R2B-5];
   else A12's refusals (1.4); else the update (2). A restore needs no reading, so it is allowed even on a revision A12
   would refuse.

`answers._save_details` keeps its own `changed` computation (only the changed values are passed); `change_context` now
does the same comparison itself, so both routes behave alike, and a double submission of one save is a no-op the second
time (3.9). The comparison is against the **saved** values, never against the page: two tabs, a stale page and a repeated
POST all compare against the same row.

### 1.4 Refusals kept, lifted and added

- **Kept:** `jobs._change_context`'s refusal while the revision has no extracted text ("Context can be set once the document
  text has been extracted."); a save on an encounter with no context, no earlier codes and no reading stage queued or
  running (`jobs.CONTEXT_NONE_MESSAGE`); a save after the reading failed when the encounter has no earlier codes
  (`jobs.CONTEXT_UNREAD_MESSAGE`, first processing only).
- **Kept for member acts (A18)** [R:races-R4][R:races-R5]: `jobs._change_context` refuses, with its existing sentence
  ("Wait for processing to finish (or stop it) before changing context."), while a member-act stage (vocabulary) of the
  encounter on its current context is QUEUED or RUNNING. Such a stage applies a member's act to the current final
  assessment (an answer, its withdrawal, a confirmation, the bounded second review, an operator's release refresh) and is
  short: a local assess, or the one second-review send. Superseding it would lose the act for the codes it was asked on:
  a restore would bring back an assessment that still reads a withdrawn answer (STALE_ANSWER_BLOCKER standing with
  nothing queued, and no Resume, since a superseded stage is not a target job), or an answer applied by the overlay alone
  (the "false 'reviewed' with an approved export" the `CONTEXT_VERSION` comment records), and a superseded second review
  uses its key (SECOND_REVIEW_ASKED) or its paid answer is never assessed. A Stop lifts the refusal, as it does for every
  busy refusal: the stopped stage stays a target job of the restored state and Resume runs it.
- **Lifted:** the busy refusal of `jobs._change_context` ("Wait for processing to finish (or stop it) before changing
  context.") and `api.py:addenda`'s ("Wait for processing to finish (or stop it) before adding documentation."), by A1;
  the context save's stays only for A18's member-act stages (above) [R:races-R4].
  `jobs.CONTEXT_UNREAD_MESSAGE` and `jobs.CONTEXT_NONE_MESSAGE` are lifted where an update is pending or a reading stage is
  queued or running: the values are stored and the failure or the running reading stands (7).
- **Narrowed:** `answers._save_details` refuses with `answers.BUSY` only a save that records a member answer (a
  `MemberAnswer` row) while any stage of the encounter is queued or running or an update is pending. A save that carries
  only context values, or only the confirmation of a date, is accepted (subject to A18's member-act refusal).
  `answers.revoke_answer` keeps its busy refusal and is also refused while an update is pending, with
  UPDATE_ANSWER_WITHDRAW "You can change your answers once the codes are updated." (a `customer_api.KNOWN_ERRORS`
  entry) [R:truth-T12]: a withdrawal during an idle update writes its revocation but its recompute returns None (the final
  is not on the current context), and a restore would then make E current again still reading the withdrawn answer, with
  nothing queued. "Earlier answers, not applied" keep their Withdraw link hidden while an update is pending.
- **Added (A12):** on a revision with no inventory at the current versions, `jobs._size_bound(revision)` non-empty refuses
  the save with SAVE_TOO_LONG, and a text that fails the pure framing check refuses it with SAVE_UNPREPARED (FINAL-V2 1.2's
  `[S\d+]` refusal in `contract/segment.py`, run in the web process without the interpreter adapter: the key is mounted in
  the worker only, D14, so the web cannot build the request itself). Nothing is written. Reason: such an update could
  never finish (C5 forbids a member's paid retry of a document too long to be read), so accepting the save would only make
  the earlier codes stale with no way forward. Measured: no live document is over the character bound (the live maximum
  is 19,398 characters, D25); 6b counts live current revisions over either bound before the switch (9.5).

  - SAVE_TOO_LONG: "This document is too long to be read in one piece, so its details cannot be changed here. The codes
    shown stay as they are."
  - SAVE_UNPREPARED: "This document could not be prepared for reading, so its details cannot be changed here. The codes
    shown stay as they are. Upload it again to change them."

Both are added to `customer_api.KNOWN_ERRORS` as customer sentences.

- **Added (A12, addenda)** [R:truth-T7]: `api.py:addenda`, under the row lock and before the revision is recorded or
  `review.invalidate_for_new_revision` runs, refuses an addendum whose combined text — `combined`, which `addenda` already
  computes as the extraction will (`canonicalize(parent.text + jobs.addendum_block_text(...))`) — is over
  `INTERPRET_MAX_CHARS`, or whose parent's pages are over `INTERPRET_MAX_PAGES` (an addendum revision carries its parent's
  pages: `stage_extract`), with ADDENDUM_TOO_LONG "With this documentation the document would be too long to be read in
  one piece, so it was not added."; and one whose combined text fails the pure framing check with ADDENDUM_UNPREPARED
  "This documentation could not be prepared for reading, so it was not added.". **The sentence names where the cause is**
  [R2:truth-RT7]: the parent's own text is checked first, alone, and when it alone is over `INTERPRET_MAX_CHARS`, its
  pages over `INTERPRET_MAX_PAGES`, or its text fails the framing check, no addendum can pass and the refusal says so:
  ADDENDUM_DOCUMENT_TOO_LONG "This document is too long to be read in one piece, so documentation cannot be added to it
  here. Upload it again, shorter or split, with the documentation included." or ADDENDUM_DOCUMENT_UNPREPARED "This document
  cannot be prepared for reading as it stands, so documentation cannot be added to it here. Upload it again with the
  documentation included, without bracketed markers such as [S2]." (3c words all four, naming no provider). No addendum
  refusal says "the codes shown stay as they are": an addendum is accepted during a first processing and after a failed
  first reading, when no codes are shown. (All four `customer_api.KNOWN_ERRORS`, 409; the earlier wording blamed "this
  documentation" for a cause in the existing document, such as a legacy text holding `[S2]`, 9.5's framing class, so every
  rewording of the addendum was refused with no way forward named.) Nothing is written. Reason, A12's own: today such an
  addendum is accepted, clears every approval at once, and its update can never finish (the reading refuses the size,
  C5 forbids a member's paid retry, and no restore exists across revisions). The live maximum is 19,398 characters (D25),
  so a 700-character addendum to that document is refused; this is reported to the owner with 9.5's count (class b).
- **Added (A19)** [R2:binding-R2B-4][R2:binding-R2B-5]: a case-B save of the earlier codes' own values, when those codes
  cannot be current again as they stand (2.5), is refused with RESTORE_REFUSED "The codes from before your change cannot
  be used again as they were, so their details cannot be restored until the update has finished." (409, a
  `customer_api.KNOWN_ERRORS` entry). Nothing is written. A save of any other values is accepted as before.

---

## 2. What runs

### 2.1 The rule: each stage's inputs, and the door that reuses its result

| stage | its inputs | reused by | runs again when |
|---|---|---|---|
| extract | the revision's file or text | `stage_extract`: an extraction recorded once (`SourceRevision.record_extraction`) | never for the same revision |
| interpret (pass 1) | the revision text, its page framing, the pinned pass-1 objects (`INTERPRETATION_VERSION`); never a member value (D1) | FINAL-V2 7.4: an extraction already read at the current versions; a stored SUCCEEDED answer to the identical request in the same workspace (door 2, `jobs._retained_interpretation`) | the revision is new, or `INTERPRETATION_VERSION` changed and no stored answer matches the new request |
| appraise (pass 2) | the revision text, pass 1's stored bytes, `INVENTORY_VERSION`, `APPRAISAL_VERSION`; never a member value (FINAL-V2 7.4) | FINAL-V2 7.4 doors 1 and 2 (an inventory read for this extraction run and versions; a stored answer to the identical request by sha) | pass 1's answer, the checks or the claim set changed |
| analyze | the inventory and the saved values | none needed: pure and local | the values or the inventory changed |
| predict (Corti) | the revision text and the effective service date (`provider.build_request(revision.text, service_date)`) | `jobs.stage_predict`'s retained-result door (any SUCCEEDED run of the identical request in the workspace); `jobs._decide_after_save` re-checks with the run in use when it answers the new context's request (`jobs._run_answers`) | the text or the effective date changed |
| astra, fable (first readings) | the revision only: text, pages, kind, the PDF original (`jobs.stage_participant`'s docstring: "a context change reuses its answer") | `jobs._retained_answer` | the revision changed, or a participant has no outcome for it (`jobs._participants_owed`) |
| assess #1 | the context, the inventory, Corti's run, the participants' runs, the standing member answers | `review._same_assessment` returns the identical assessment | any input changed (it is local: no send) |
| astra_peer, fable_peer | assess #1's reading without member values (`jobs._cpt_studio_reading`, `jobs._peer_text`), Corti's conclusions, the other model's frozen reading | `jobs._retained_answer` by request sha | assess #1's reading or Corti's conclusions changed |
| assess #2 | what assess #1 read, plus the peer runs | as assess #1 | as assess #1 |

"Nothing is reused across a changed input or version" holds because every reuse above is keyed by a request sha256 that
covers the input and the pinned versions (the adapters' requests, FINAL-V2 7.4's appraise key), by an inventory read at
the current versions, or by `_same_assessment`'s full input comparison. This amendment adds no reuse path.

### 2.2 Case A: a v2 revision with an inventory read at the current versions

`jobs._saved_inventory(revision, previous)` returns the inventory. Under the row lock, in `jobs._save_on_inventory`
(unchanged in substance, FINAL-V2 7.4's D8):

1. the values are stored (`_merge_values`);
2. the context is derived over the frozen inventory (`interpretation.facts.derive`, in v2 `engine/derive.py` with
   `effective()`), under a new_path sentinel scope, and recorded with `earlier_assessment` set (4.5);
3. its routing stand-in is recorded for a new effective date;
4. it is made current; the audit row `context.changed` is written;
5. `jobs._decide_after_save` queues, changed only as follows: while an update is pending (that is, after any save on an
   encounter with earlier codes) it re-checks with the run in use (an assess, or the participants' chain when one is
   owed) only when that run answers the new context's request and either **succeeded** or **is E's own run** — the run
   the earlier codes E were assessed with (`E.provider_run`), or a run carrying the same request as it
   [R:legacy-L4]. Any other run in use (failed, not sent, unknown, and not E's) queues the predict instead
   (`_queue_predict`, which still records the member date conflict's hold itself), and the predict's doors decide; it
   never re-sends an identical request that failed (`jobs._failed_before`). The run in use is never a hold:
   `jobs._run_in_use` leaves holds out. Today `_decide_after_save` re-checks with any run in use that answers the request,
   including a failed one, which during an update would replace the earlier codes with an assessment that has no document
   review when E had one (A6). When E's own review failed or was not sent, the same re-check replaces E by an assessment
   no worse than it, and queueing the predict instead would end the update failed on the unchanged request (or, through
   `retry_update`, pay to re-send a request whose input did not change): the review's input is unchanged, so it does not
   rerun (the owner: "Rerun only stages whose inputs changed") [R:legacy-L4]. During a first processing the rule is
   unchanged, except that no re-check takes a run a `ProviderHold` row names (a hold-setting run: a coding-service 401,
   402, 403 or 429, or a token-endpoint 4xx recorded not sent with its request, which `_run_in_use` keeps as the run in
   use), there as during an update, where such a run carrying E's request would otherwise pass as E's own: a save made
   while such a run paused the document queues the predict, whose hold door pauses it again while the hold stands and
   which, after the release, sends the identical request once (`_failed_before` leaves that run out, 7.3).
   Re-checking with it made a final with the refused run: "could not complete its review ... You can upload the document
   again", with no Resume, while every other paused document resumed after the release; and the participants' first
   readings were sent for it [R3:binding-R3B-5][R3:truth-R3T-4]. `jobs.reconcile`'s participant branch, which re-checks
   with the run in use the same way, queues the predict too when a `ProviderHold` row names that run.

What runs: no interpret, no appraise, no analyze. Predict only when Corti's request changed (a new effective date) or the
run in use did not succeed and is not E's own run [R:legacy-L4]; it reuses a stored answer to the identical request. The
participants reuse their answers. Assess #1 runs locally. The peer reviews reuse their answers when assess #1's reading is unchanged (`jobs._peer_text`
removes every member value from it, so a change of setting, patient status or billing context that changes no outcome makes
the identical peer request). Assess #2 runs locally.

Gemini calls: none. Corti: at most one, only for an effective date whose request has no stored answer in the workspace and
is not blocked by `_failed_before`, the unknown-outcome block or Corti's provider hold (A16) [R:races-R2]. Astra and Fable
first readings: none, unless one has no outcome for the revision. Peer reviews: none unless assess #1's reading changed;
then at most one each, and none from a participant whose provider hold stands.

### 2.3 Case B: a legacy revision, or a v2 revision without an inventory at the current versions

`jobs._saved_inventory` returns None: the installed release's revisions (read by the legacy reader, no `EventInventory`),
a v2 revision whose inventory is of an earlier version, and a v2 revision whose reading did not finish (stopped between the
passes, failed, paused). `jobs._save_before_reading` is replaced by `jobs._save_awaiting_reading`:

1. A12's refusals first (1.4).
2. The values are stored (`_merge_values`); `clear_stop`; the audit row `context.changed` (with `reading: <job>` when one
   is queued). No context is made: the current one is kept, as today.
3. The first stage the reading owes is queued, unless one is already queued:
   - **coalesced:** a job of kind extract, interpret or appraise of this revision is QUEUED (never one that is RUNNING:
     see below) [R:races-R6], other than the stale sweep's settled path (`interpret:...:settled:<run>`), which sends
     nothing whatever it finds and ends cancelled when its run does not settle, so a save it took in would never be read
     [R2:binding-R2B-7]. **Coalescing is a compare-and-set** under the row lock [R2:binding-R2B-7]: the save sets that
     stage's `deadline_at` to now plus `jobs.QUEUE_DEADLINE` (`UPDATE ... WHERE state = QUEUED`) and coalesces only when
     that changed the row; when it did not (`claim_next` claimed or expired the stage meanwhile), the save queues the owed
     stage as the branches below say. The renewed deadline gives the save its own window: `enqueue` sets `deadline_at`
     once, so a save coalesced into a stage queued 29 minutes before, behind a backlog, expired with it a minute later,
     and the update read stopped by the system with that save never rechecked in the background. Nothing more is queued:
     the analyze that follows derives with the values saved at its own commit (4.2), so this save's values are read.
     (Extract is listed for safety only: `_change_context` refuses a save before the text is extracted. Queueing an
     interpret under the base key before extraction would be fatal: it would
     skip, and `_after_extract`'s `enqueue` of the same key would then return that finished job and queue nothing.) The
     QUEUED stage's start check reads the encounter under its row lock (3.4), so it runs after this save commits and sees
     it: a stage the save coalesced with cannot have decided "superseded" from the state before the save.
   - **a reading stage is RUNNING** [R:races-R6]: the save does not coalesce with it, because a running stage may never
     reach the analyze: a Stop recorded on it survives `clear_stop` (`Job.stop_requested_at`, which `_stop_requested`
     still reads, so it ends CANCELLED at its send); its start check or successor gate may already have decided
     "superseded" from a restored state just before this save; or its worker may be dead, and the stale sweep cancels it
     up to `STALE_RUNNING_SECONDS` (600 s) later. The first stage the reading owes is queued under its base key plus
     `:after-save:<uuid>` as the "otherwise" branch below says. Nothing is sent twice: the worker runs one job at a time,
     the queued stage starts after the running one ends, and its doors then reuse what the running one stored (door 1, an
     extraction read at the current versions; door 2, a stored answer to the identical request), the failed-before door
     holds what it failed, and the unknown-outcome block holds what it left unknown; its successor `enqueue`s meet the
     running stage's successors under the same keys and return them. A send happens only when the running one sent
     nothing (stopped before its send, or dead before it), which is what this save asked for.
   - **the reading failed:** the newest attempt of the stage the reading owes (pass 1, or pass 2 once 5b extends
     `jobs.retry_target` to appraisal runs) is a sent attempt that failed or was cut off — `retry_target`'s second value —
     and `jobs.released_for_retry` does not release it, so the failed-before door would hold the identical request.
     Nothing is queued; the encounter shows the failure with its Retry, or the too-long text (7). The values are stored,
     so the Retry's reading derives with them.
   - **otherwise:** interpret when no pass-1 extraction is read at the current interpretation version, else appraise
     (FINAL-V2 7.4's Resume rule). Its key is the stage's base key (`jobs._interpret_key(revision)`; FINAL-V2 7.4's appraise
     key) when no job holds it, else the base key plus `:after-save:<uuid>` (today's `AFTER_SAVE` mark). A stage that would
     pause (hold or disabled interpreter) is queued as today and pauses without sending (`stage_interpret`'s doors); a
     later save while it stands paused queues it again, and it pauses again, recording a not-sent run and sending nothing
     (today's `test_a_save_while_the_first_reading_is_paused_queues_it_again`).

What runs: interpret (pass 1) and appraise (pass 2) with their doors; analyze (4.2); then the whole chain of case A from
predict on, with Corti's request carrying the v2-derived date (D2). Each pass runs **once per revision and version pair**:
door 1 or door 2 answers every later stage, so a second save on the same revision is case A.

Gemini calls: at most one pass-1 and one pass-2 send per revision and version pair (none when a stored answer to the
identical request exists in the workspace, as after an earlier, abandoned update). Corti: at most one, when the v2-derived
effective date gives a request with no stored answer (on a legacy encounter the legacy reader's date and the v2 reading's
can differ, so expect one). Astra and Fable first readings: none (their request is the revision alone, already answered).
Peer reviews: on a legacy encounter expect one each, because the reading they are shown is new (D9: the events engine's
heading, `jobs._peer_reading_heading`); on a v2 revision only if assess #1's reading changed.

### 2.4 Case C: a new revision (an addendum)

`api.py:addenda` (A1: no busy refusal; A13: duplicate refusal; A12: the size and framing refusal, before anything is
written [R:truth-T7]) records the revision, invalidates the current decisions (`review.invalidate_for_new_revision`,
reason "Source revised to revision N"), and starts the pipeline (`jobs.start_pipeline`), all in one transaction, as today.
No restore exists for a new revision (2.5 restores within one revision), so no case-C text offers one (7.1).

What runs: every stage, because the text changed: extract, interpret, appraise, analyze (with the saved values), predict,
the first readings, assess #1, the peer reviews, assess #2. Reuse happens only where a request is byte-identical to one
already answered in the workspace (the same text uploaded elsewhere).

Gemini: one pass-1 and one pass-2 send. Corti: one. Astra and Fable: one first reading and one peer review each. Every
stage of the earlier revision still queued ends superseded at its start (3.4); one already sending completes, and its
answer is stored for reuse.

### 2.5 Restore: a save that brings back the earlier codes' own values

Under the row lock, after 1.3 found a change, and only while the encounter is not fresh (a change from a fresh state
cannot equal the current codes' values): let B = `earlier(encounter)`. When B exists, B is final, `B.revision ==
current_revision`, B is the current assessment, `after == values(B.context)`, and B can be current again as it stands
(A19) [R2:binding-R2B-4][R2:binding-R2B-5] — it reads no member answer that no longer stands
(`review._reads_a_withdrawn_answer(B)` is false), its document review is not an unknown outcome a reconciliation has
released (`B.provider_run` UNKNOWN with `reconciled_at` set), and, on a gemini context, every standing answer recorded
after B was made had a re-assessment of B queued after it (A19's third condition) [R3:binding-R3B-2]:

- the values are stored, `current_context = B.context` (when it is not already), the audit row `context.changed` records
  `restored: <B>`; nothing is queued; the reply says `restored` (1.3) [R:truth-T13];
- the encounter is fresh at once: B's codes are the current codes again, with their decisions and their open questions
  (none was carried, invalidated, withdrawn or closed: carries and invalidations happen only when a final assessment is
  recorded, and under A17 an assessment of the update that is not final changes no other assessment's rows);
- every stage of the abandoned update ends superseded when it starts or reaches its reservation (3.4); one already sending
  completes, and its answer is stored.

**B is the current assessment at every point before the update's final assessment** [R:races-R3][R:legacy-L6]. Under
A17 an assess #1 of the update that owes peer stages is recorded but never made current, so a restore made while the
peer reviews run, after a Stop of them, or after any failure, still finds B current, and the restore above applies: the
update's peer stages end superseded (their context is no longer current) and send nothing. (The pre-refutation text made
such a restore an ordinary change once an assess #1 was current. On a legacy encounter that "restore" was a new v2 update:
peer requests on the new reading were sent, since a Stop had cancelled the abandoned chain's and the legacy ones carry the
legacy heading (D9), and its final invalidated every legacy approval (D7), so the legacy codes never came back; and simply
setting `current_assessment` back to B would not have been enough, because assess #1's persist had already withdrawn B's
open clarifications that it did not raise again (`review._withdraw_superseded`), leaving B readable as ready with its
questions gone.) Once the update's final assessment is current the encounter is fresh, so a change back is a new update,
and its chain reuses every provider answer by request sha.

A restore applies only to a final B (the codes a member could decide): when `earlier(encounter)` is a first processing's
unfinished assessment that a save made stale (vocabulary [R:truth-T8]), a save back to its values is an ordinary change.
A18 keeps every member-act stage from being superseded by the change the restore undoes, so B never comes back still
reading an answer whose change was not applied [R:races-R4][R:truth-T12]; A19 covers the answer the details save itself
replaced [R2:binding-R2B-5] and the one it recorded beside the change [R3:binding-R3B-2].

**A save A19 keeps from being a restore** [R2:binding-R2B-4][R2:binding-R2B-5] is an ordinary change where the save makes
a new context (case A, 2.2): a context with B's values, whose chain makes the codes for them. Where the save keeps the
context (case B, 2.3: a legacy revision, or a v2 revision whose inventory is of an older version, before the update's
analyze), B's values on the kept context would make the encounter fresh with B as it stands — `fresh` reads rows only —
and every stage of the update would end superseded (SUPERSEDED_RESTORED), stranding it exactly as a restore would (for
the reconciled unknown, A21 keeps the kept context from reading fresh, and the same refusal is kept so that one rule
answers every cause: J5 [R3:binding-R3B-3]); so that save is refused, nothing written, with RESTORE_REFUSED "The codes
from before your change cannot be used again as they were, so their details cannot be restored until the update has
finished." (`customer_api.KNOWN_ERRORS`, 409; 3c words it). Once the update's analyze has made a gemini context, a
save is case A and the ordinary change applies. Each case A19 names is a state a restore would strand:

- **B reads an answer that no longer stands.** A details save giving a value in a row answered "Not documented" revokes
  that answer (`answers._save_details`: a `SUPERSEDED` revocation) in the same save that starts the update, and nothing
  refuses it (it records no `MemberAnswer`; during a case-B update B's rows stay drawn). A restore would make B current
  still reading it: STALE_ANSWER_BLOCKER standing with nothing queued, no Resume and no Retry (the encounter is fresh), the
  row no longer showing the answer, and the code it excluded excluded by an answer the member replaced. In case A the
  update's chain reads the answers that stand, so that code is offered again; its provider requests are B's own and are
  reused.
- **B's document review is an unknown outcome a reconciliation released.** The reconciliation queued one attempt for the
  saved state (`predict:<context>:after-reconcile:<run>`, or the interpret stage while a reading is owed, 7.4); a restore
  would supersede it and make B current with that run, which `review._state_and_run` reads as provider_unknown whether or
  not it was reconciled: "being confirmed" with nothing pending, and `jobs.reconcile` refusing the run a second time. In
  case A the update's predict sends B's request instead, as the released attempt (`_run_in_use` leaves a reconciled
  unknown out, and the unknown-outcome block no longer holds it). A restore is not the only thing that superseded that
  attempt: where a reading is owed, 3.4 superseded the reconciliation's interpret whenever the codes were fresh, with no
  save at all; A21 makes such codes not fresh once their own unknown is released, so the reading runs as an update of
  them [R3:binding-R3B-3].
- **B would come back with an answer no assessment read** [R3:binding-R3B-2]. One details save can record a "Not
  documented" answer in one row and change a detail in another: `answers._save_details` writes the `MemberAnswer` and
  queues no recompute, because the change's own chain reads the answers. A restore abandons that chain, so on a gemini
  context B would be current again with the answer applied by the review overlay alone — no blocker, readiness able to
  read reviewed, the approved export made of B's stored rows plus the overlay: the "false 'reviewed' with an approved
  export" the `CONTEXT_VERSION` comment records, which 1.4 says a restore must never bring back. In case A the update's
  chain reads the answer; its provider requests are B's own and are reused. An answer whose own recompute of B was queued
  is not this case: that recompute is B's member-act stage, which A18 keeps from being superseded and which, stopped, stays
  a target job of the restored state for Resume (1.4). On a legacy B an answer stands on the overlay by design
  (`recompute_after_answers` returns None), so the condition does not apply.

`update.restorable` (5.1) is false in all three, so no text offers a restore A19 refuses (7.1).

This is the member's way out of every failure that cannot be retried (7), within one revision: restoring the earlier
details makes the earlier codes current again with nothing sent (where A19 allows it; otherwise the same save updates the
codes for those details in case A, and is refused in case B until the update has finished). On a legacy encounter it
works before and after the
reading completed, and after the update's assess #1, because B (the legacy assessment) stays current until the update's
final assessment. After an addendum (case C) there is no restore: the earlier codes are of another revision and their
decisions were invalidated when the documentation was added, so no case-C text offers one (7.1) [R:truth-T7].

### 2.6 Provider calls per case

| case | Gemini pass 1 | Gemini pass 2 | Corti | Astra, Fable first readings | peer reviews |
|---|---|---|---|---|---|
| no-op save, restore | 0 | 0 | 0 | 0 | 0 |
| A: context change, v2 with inventory | 0 | 0 | 0, or 1 for a new effective date with no stored answer | 0 (1 for a participant owed its turn) | 0, or 1 each when assess #1's reading changed |
| B: context change, no inventory at current versions | at most 1 per revision and version pair; 0 when a stored answer matches | at most 1 per extraction run and claim set; 0 when reused | as A, with the v2-derived date | 0 | as A; on a legacy encounter expect 1 each |
| C: addendum | 1 | 1 | 1 | 1 each | 1 each |

A change of setting, patient status or billing context is read by no provider request: Corti's carries the text and the
date, the first readings the revision, the peer requests no member value. On a v2 revision such a change therefore calls
no provider unless it changes an outcome the peers are shown.

Every count above is 0 for a provider whose hold stands (A16): its doors record a not-sent run and send nothing
[R:races-R2][R:legacy-L2].

### 2.7 What changes in the current code for this section

- `jobs.change_context`: returns `ContextSave(context, changed, updating, restored, unchanged)`; its callers
  (`api.py:context`, `answers._save_details`, `review.confirm_finding`) read `.context` where they read the context today.
- `jobs._change_context`: no busy refusal, except A18's member-act refusal [R:races-R4]; 1.3's comparison; 2.5's restore;
  then `_save_on_inventory` (case A) or `_save_awaiting_reading` (case B).
- `jobs._save_on_inventory`: passes `earlier=` to `record_derived_context` (4.5).
- `jobs._save_before_reading`: replaced by `jobs._save_awaiting_reading` (2.3), which coalesces only with a QUEUED reading
  stage [R:races-R6].
- `jobs._decide_after_save`: while an update is pending, the re-check with the run in use only for a SUCCEEDED run or E's
  own run (2.2) [R:legacy-L4]; in a first processing as during an update, never with a run a `ProviderHold` row names
  [R3:binding-R3B-5][R3:truth-R3T-4].
- `jobs.record_derived_context`: an `earlier` argument, stored in `EncounterContext.earlier_assessment`, outside the
  context's sha256 (like `document_date`).
- `api.py:addenda`: no busy refusal; A13; A12's size and framing refusal [R:truth-T7].

---

## 3. Rapid successive edits and duplicates

### 3.1 The decision: accept the newer save and supersede the pending update (A1)

Two designs were weighed:

- **Refuse while an update is pending** (today's `jobs.busy` rule in `_change_context`, `answers._save_details`,
  `api.py:addenda`). A second save within seconds of the first is refused with "Wait for processing to finish", and the
  member saves again a minute later. Nothing ever needs superseding.
- **Accept the newer save and supersede.** The newer save is stored at once; queued stages of the older update end without
  sending; a stage already running finishes, its provider answer is stored for reuse, and nothing it computes becomes
  current.

The second is chosen, against the owner's words:

- "Queue the recheck in the background after saving": the member keeps working while it runs; a refusal makes the update a
  foreground wait.
- "results from an older revision must never overwrite newer work": this presupposes newer work saved while older results
  are in flight. Under the refusal rule there is no such state to guard; the owner asks for the guard, so the state is meant
  to exist.
- "Verify rapid successive edits": under the refusal rule, the second rapid edit fails, and the verification would record
  the owner's own scenario as refused.
- "Rerun only stages whose inputs changed": a context-free stage already in flight (the legacy reading) serves the newer
  save too and is not restarted (coalescing, 3.3); under the refusal rule the member would have to wait for it anyway.
- "Prevent duplicate submissions": met by the no-op comparison (1.3), the keys (3.2), the doors and the single-flight lock
  (3.10), not by refusing.

The refusal while busy stays where a newer submission cannot supersede anything: member answers (they bind to the question
of a specific assessment), their withdrawal, Resume, reconcile, Retry, the second review and the confirmation acts. And
the reverse holds too (A18) [R:races-R4][R:races-R5]: while one of those member acts' stages is queued or running on the
current context, a context save is refused rather than allowed to supersede it, because a superseded member act is lost
for the codes it was asked on (1.4). Rapid successive edits are saves following saves and are never refused by it.

### 3.2 Keys

Unchanged from today and FINAL-V2 7.4, which already bind each stage to what it serves:

- `interpret:<revision>:<INTERPRETATION_VERSION>` (+ `:after-save:<uuid>` when a save finds the base key taken,
  `:retry:<run>`, `:retry-release:<run>`, `:after-reconcile:<run>`, `:settled:<run>`, `:resume:<uuid>`);
- `appraise:<revision>:<extraction run>:<16 hex of the request sha>` (+ the same suffixes);
- `analyze:<revision>:<inventory>` (+ `:resume:<uuid>`, which `jobs._analyze_inventory_id` already strips);
- `predict:<context>` (+ `:after-reconcile:<run>`, `:resume:<uuid>`, A10's `:retry-release:<run>`, and `:retry:<run>`
  for a retry of a run not sent for a local reason [R:legacy-L5]);
- `<participant>:<chain>`, `<peer kind>:<12 hex of assess #1's id>`, `assess:<context>:<run>[...]` (`jobs._assess_key`,
  `jobs._final_key`).

Every stage after analyze names the context, and every v2 save makes a new context row, so two saves never share a stage
key. Contexts are not deduplicated by content: reusing an earlier context row would make a new save meet that context's
finished jobs under the same keys, and `jobs.enqueue` would return them and queue nothing.

### 3.3 Coalescing

- **Context-free stages** (interpret, appraise) serve the revision, not a save. A save that finds one QUEUED for the
  current revision queues nothing more (2.3); one that finds one only RUNNING queues the owed stage under
  `:after-save:<uuid>`, whose doors reuse what the running one stores [R:races-R6]. Analyze reads the values at its commit
  (4.2), so every save made before that commit is in the context it derives.
- **Context stages** are never coalesced across saves: the newer save's context gets its own chain, and the older chain's
  queued stages supersede themselves. Their provider work is still reused: when the newer chain's predict runs, the older
  predict has finished (the worker takes the oldest queued job, `jobs.claim_next`, and one provider request runs at a time,
  `jobs._send`'s advisory lock), and the retained-result door reuses its answer when the request is identical.
- **Identical requests in flight.** Two stages can never send one request at once: the second `pg_try_advisory_lock`
  fails and the stage is put back (`Requeue`); when it runs, the first one's stored answer answers it (reuse door), its
  failure blocks it (`_failed_before`), or its unknown outcome blocks it (the unknown-outcome block).

### 3.4 Supersession: the predicate and where it is asked

`jobs._superseded(job)` returns '' when the job still serves the saved state, else one of the fixed reasons below. It reads
the encounter afresh, under the encounter's row lock (`jobs._locked`) at the start check and at the successor gate as well
as at the commit [R:races-R6]: a save holds that lock while it decides whether to coalesce (2.3), so a stage's
supersession decision and a save's coalescing decision are serialized, and a stage the save coalesced with reads the
save. The lock is held only for the read (a short transaction), never across a send.

1. `job.revision != current_revision` -> SUPERSEDED_REVISION ("a newer revision of the document exists; nothing was sent").
   Extract is never superseded: a child addendum needs its parent's text.
2. A stage that carries a context: `job.context != current_context` -> SUPERSEDED_CONTEXT ("the details changed after this
   step was queued; nothing was sent"); `values(job.context) != values(encounter)` -> the same reason.
3. A context-free stage (interpret, appraise, analyze): `review.fresh(encounter)` -> SUPERSEDED_RESTORED ("the details were
   restored to those of the current codes; nothing was sent"). Analyze also when no reading is owed (`review.reading_owed`
   false: a save already derived the context from this inventory with these values) -> SUPERSEDED_DERIVED ("the details
   were saved on this reading already"). An operator's reconciliation's reading of codes whose own unknown document
   review it released is never superseded as restored: A21 makes those codes not fresh while that reading is owed
   [R3:binding-R3B-3].

Where it is asked:

| point | stages | effect |
|---|---|---|
| at the start, before any door that can send or write | interpret (after `_settle_from_exchange`, which never sends), appraise, analyze, predict, astra, fable, the peers, assess (all modes), review2 | `{'skipped': reason, 'superseded': true}`; no run row, no context, no assessment |
| immediately before the reservation, inside `jobs._send`, after `_check_loop_time` and the advisory lock and before `ProviderRun.objects.create(... RESERVED)` (the Stop check stays where it is, after the reservation) | every sending stage | raises `StageSuperseded`; the lock is released in `_send`'s `finally`; no run row |
| before queueing a successor | `_settle_interpretation`'s `_queue_analyze`, the appraise stage's analyze, `stage_predict`'s `next_assess`, `_participant_done`, `_peer_done`, `mark_stale`'s successors | nothing is queued; the stage's own run and inventory stay stored |
| at the commit, under the row lock | analyze (4.2), `review.persist_assessment` (4.1) | `Superseded`; nothing written |

`jobs.run_job` maps `StageSuperseded` to state SUCCEEDED with `{'skipped': ..., 'superseded': true}`, never CANCELLED (which
reads "stopped") and never FAILED. Existing start checks that already return `skipped` for a changed revision or context
(`stage_predict`, `stage_participant`, `stage_peer`, `stage_review2`, `stage_interpret`'s revision check, the FINAL and AGAIN
basis checks of `_assess_events`) add `'superseded': true` to their result. `stage_assess` on a gemini context gains the
context check at its start (today it runs the bounded child and only `persist_assessment` refuses).

### 3.5 The late finisher

A stage for an older revision or context that finishes after a newer save:

- **a sending stage** (interpret, appraise, predict, a first reading, a peer review): its run is recorded with its outcome,
  usage and bytes, exactly as today, and a refusal A20 holds sets the provider hold with it (7.3) [R2:binding-R2B-1]. Its
  answer is the stored answer to its request and is reused wherever the identical request comes again. It queues no
  successor (3.4).
- **analyze:** its commit fails the compare-and-set (4.2); no context is written.
- **assess:** `persist_assessment`'s compare-and-set fails (4.1); no `Assessment`, `Proposal` or `Clarification` row is
  written, no open clarification is withdrawn or closed, no decision is carried or invalidated, the current assessment is
  untouched. (Today the same check raises `ValueError`, which `_assess_events` turns into a FAILED stage that reads
  `processing_failed`.)
- **its outcome as an encounter state:** none. It is not a target job, so neither its success, its failure nor its stop
  decides the encounter's state (5.2). One exception, kept on purpose: an outcome it left UNKNOWN blocks every send of the
  encounter until reconciled (`review._unreconciled_unknown`), because that request may have been billed.

### 3.6 Stop and Resume

- **Stop** (`jobs.stop_encounter`) is unchanged: it cancels every queued job of the encounter and asks every running one to
  stop before its next send, superseded ones included. The update then reads stopped (7.1).
- **A save after Stop** lifts the Stop (`clear_stop`, as today) and queues per section 2. `clear_stop` clears only
  `Encounter.stopped_at`; a running stage keeps its own `Job.stop_requested_at` and still ends CANCELLED at its send, so
  the save never coalesces with it: the queued jobs were cancelled by the Stop, and a running one is not coalesced with
  (2.3), so the save queues the owed stage afresh and the update goes on in the background [R:races-R6].
- **Resume** (`jobs.resume`) is allowed when the derived state is `stopped` (`review.can_resume`), which includes the
  idle-owed state (5.2). It queues the first stage the saved state owes, computed from rows, not from the cancelled job's
  kind alone:
  1. a reading is owed: interpret when no pass-1 extraction is read at the current interpretation version, else appraise
     when no inventory is read at the current versions (FINAL-V2 7.4), else analyze (`analyze:<revision>:<inventory>:resume:
     <uuid>`) — the last is new: a legacy update stopped between the reading and the derivation;
  2. otherwise today's rule over the latest target job (an assess whose context changed re-runs from predict; any other
     kind re-runs under its own key plus `:resume:<uuid>`); with no target job at all, a predict for the current context
     (`predict:<context>:resume:<uuid>`), whose doors reuse every stored answer.

  Resume refuses while any job of the encounter is queued or running (`jobs.busy`, unchanged: conservative, because a
  superseded stage may still be sending). A Resume while a provider hold stands queues the stage, which records a held
  not-sent run and pauses again, sending nothing (7.3) [R:races-R2].

### 3.7 A worker's death

`jobs.mark_stale` is unchanged in what it settles: a run left sending becomes UNKNOWN (or SUCCEEDED from its recorded
exchange, P-6), a reservation becomes not sent, an interpret's settled path is queued. **A predict's finished run is
settled exactly as the stage would settle it** [R2:binding-R2B-6] — by 7.2's exhaustive list while an update is pending,
and as today otherwise, except for the provider hold:

- a run that set Corti's provider hold, or one the hold kept unsent (`scope.held = 'provider_hold'`), ends the job
  CANCELLED with the paused text, resumable, queueing nothing, in a first processing as during an update (7.3; the hold
  itself was recorded with the run's outcome, A20);
- during an update, a FAILED run, a not-resent run of a request that is not E's, a NOT_SENT run carrying its request for a
  local reason, or a request that could not be built when E's could, ends the job FAILED with no successor;
- a success, a reuse, the member date conflict's hold and E's own outcome queue the successor under the key the stage
  would have used.

Its `held` branch, which today queues the assess with any held predict run, is narrowed to the member date conflict's
hold (`HELD_MEMBER_DATE_CONFLICT`). (Left unchanged, the stale path queued the assess after any finished predict run, so
a worker killed between the run's outcome and the stage's decision, by an OOM kill or a host reset, let an update's
failed, unsent or held document review replace the earlier codes and clear their approvals, which A6 forbids, and
completed a held first processing with the provider not run instead of pausing it.) Added: it queues a successor only
when `_superseded(job)` is ''; else it records the job superseded. A dead worker's job for the saved state that
recorded nothing ends CANCELLED as today
(resumable), and the update reads stopped by the system (7.1).

### 3.8 The hold

The installation-wide interpreter hold (D11, D39; `interpretation.holds`) is unchanged and applies to both passes
(FINAL-V2 7.4). During an update:

- interpret and appraise check the hold at their start; while it stands they record a not-sent run with `scope.held` and
  end CANCELLED with `PAUSED_MESSAGE` (`stage_interpret`); no request is built for sending;
- the encounter reads `stopped` with the paused phase (`progress.interpreter_paused`), and the earlier codes stay earlier
  (not approvable, not exportable);
- a save while paused stores the values and queues the reading again, which pauses again: a not-sent run, nothing sent;
- after an operator's release (`interpreter_hold --release`), the member's Resume queues the reading, which sends once.

A Gemini answer that sets a hold is not sent again while the hold stands: the hold keeps every Gemini request unsent,
installation-wide. `jobs._interpretation_failed_before` deliberately leaves hold effects out ("never a hold, which an
operator's release ends"), so after the operator's recorded release the next member act — Resume, Retry, or a save that
queues the reading — sends the identical request once (W4); a send refused again sets a new hold
[R:legacy-L9]. `_record_unsettled_holds` records a hold whose stage died before settling it (D53, D53b).

### 3.9 Duplicate submissions

| duplicate | what prevents it |
|---|---|
| a double click on Save, a repeated POST after a network error, the same save from two tabs | the row lock serializes them; the second finds no changed value (1.3) and writes nothing. The page's `guarded('details', ...)` also drops a second click client-side |
| two different saves from two tabs | both are stored, the newer supersedes the older (last save wins, per field: `_merge_values` merges); one chain serves the result |
| a duplicate addendum (double click, two tabs) | A13: under the row lock, `api.py:addenda` refuses an addendum whose stripped text equals the current revision's own `addendum_text` (when the current revision is an addendum): 409, ADDENDUM_DUPLICATE "This documentation was already added as revision {n}." (a `customer_api.KNOWN_TEMPLATES` entry). `guarded('addendum', ...)` stays |
| a repeated upload | unchanged: `intake.find_upload` and the client key |
| two stages for one key | `jobs.enqueue`'s `get_or_create` on `Job.idempotency_key` (unique) |
| a provider request sent twice | the reuse doors, `_failed_before` and its interpreter twin, the unknown-outcome block and the single-flight advisory lock (3.3); after an authentication, permission, payment or quota refusal, the provider holds (7.3), which keep every request of that provider unsent until an operator's release [R:races-R2][R:legacy-L2] |
| a double click on Retry, Resume or Stop | the existing busy refusals; Retry's own "asked again for the same attempt" branch (`jobs.retry_reading`) |

### 3.10 Guarantees, and the invariant they replace

The comment above `jobs.busy` ("Every action that can queue a stage ... refuses while any stage is queued or running. So at
most one stage chain is ever queued per encounter, each provider attempt answers exactly one member action") and
`progress._runs`' premise ("each refused while a stage is queued or running (R6 4.5)") no longer hold for saves. They are
replaced by:

1. At most one chain serves the saved state (the target jobs).
2. A superseded stage sends nothing after the moment it is superseded: its start check and its pre-reservation check
   (3.4) come before any reservation. A request that was already reserved or sending when the newer save landed completes.
   That is the only provider work an older save can still cost, and its answer is stored and reused.
3. Nothing a superseded stage computes becomes current: the compare-and-set at analyze and at `persist_assessment` (4).
4. No request is sent twice: 3.9's table.
5. Every save is stored, and every stored save is read: the newest values are in the context analyze or the save itself
   derives under the lock (4.2), so no save is lost to a race between two stages. A save coalesces only with a QUEUED
   reading stage whose start check, taken under the row lock, reads it, and whose queue deadline the save renewed by a
   compare-and-set, never with the stale sweep's settled path [R2:binding-R2B-7]; never with a running one that a Stop, an
   earlier supersession decision or a dead worker may keep from reaching the analyze (2.3) [R:races-R6]. (A reading
   stage queued
   beside a running one serves the same revision; their successors share keys, so they still form one chain.)
6. An update never stays pending without a visible state: active target jobs read "updating"; a failed one reads failed
   with its explanation; a cancelled one, or none at all, reads stopped with Resume (5.2).
7. A member's act on the current codes is never superseded by a context save (A18), and an assessment of an update that
   is not final never becomes current (A17) [R:races-R4][R:races-R3]; a restore never makes current codes that cannot
   stand as they are (A19) [R2:binding-R2B-4][R2:binding-R2B-5].

---

## 4. Binding

### 4.1 The compare-and-set that makes an assessment current

`review.persist_assessment` already takes the encounter's row lock (`review._lock`) and refuses, in `review._check_inputs`,
a revision that is no longer current and a context that is no longer current. This amendment keeps the place and changes
the outcome:

```
with transaction.atomic():
    locked = _lock(encounter)                         # SELECT ... FOR UPDATE on the encounter row
    if locked.current_revision_id != revision.pk:     raise Superseded(SUPERSEDED_REVISION)
    if locked.current_context_id != context.pk:      raise Superseded(SUPERSEDED_CONTEXT)
    if values(context) != values(locked):            raise Superseded(SUPERSEDED_CONTEXT)   # new
    ... the other checks of _check_inputs and _check_event_inputs, unchanged
    ... _same_assessment, the insert, the assessment's own clarifications (_create_clarifications, _close_answered)
    if update_pending(locked) and not is_final(assessment):                                  # new: A17
        return assessment          # recorded, never current; no _withdraw_superseded, no carry   [R:races-R3]
    ... _withdraw_superseded, the carry, current_assessment = assessment (unchanged)
```

- **A17** [R:races-R3][R:legacy-L6][R:truth-T6]: while an update is pending (read under the same lock), an assessment that
  is not final is recorded — its `Assessment`, `Proposal` and `Clarification` rows, and `_close_answered` over its own
  questions — and is not made current: `current_assessment` stays the earlier codes, `_withdraw_superseded` does not run
  (it would withdraw the earlier codes' open questions that the unfinished assessment does not raise again), and nothing
  is carried or invalidated (unchanged: only a final carries). `encounter.state` is refreshed from the target jobs. The
  final assessment of the update then does everything today's persist does: `_withdraw_superseded` over every open
  clarification of the encounter but its own (the earlier codes' and the abandoned assess #1's), the carry from
  `decision_holder`, and `current_assessment`. Nothing in the chain needs the unfinished assessment to be current: the peer
  stages and assess #2 read the revision's newest assessment by creation (`jobs._first_assessment`,
  `jobs._newest_assessment`, the FINAL basis check of `_assess_events`), never `current_assessment`. During a first
  processing (`update_pending` false) persist is unchanged, and its assess #1 becomes current as today.
- **The newest assessment leaves out an abandoned one** (A17's own consequence, found by the judge while applying it).
  `jobs._newest_assessment(revision)` returns the revision's newest assessment by creation **that is the encounter's
  current assessment or is on its current context**: it leaves out an update's unfinished assessment that a restore or a
  later save abandoned (recorded, never current, its context no longer current — contexts are never deduplicated and a
  restore makes B's own context current, so an abandoned one's context never comes back). Without this, after a restore
  that followed an update's assess #1, that assess #1 would stay the revision's newest assessment and every act on the
  restored codes would refuse or skip: `recompute_after_answers` (newest is not the final: an answer or a withdrawal never
  recomputed), `reassess_retained` (RETAINED_NOT_NEWEST), and the AGAIN and second-review-follow-up basis checks of
  `_assess_events` and `stage_assess` (ASSESS_MOVED). While an update runs, its own assess #1 is on the current context
  and stays the newest, so its peer stages and assess #2 find it as before; during a first processing nothing changes
  (its assessments are current or on the current context). `progress`'s own newest-assessment lookup (the checks summary's
  "what was recorded before") uses the same helper. U8's restore cases check it.

- `review.Superseded` subclasses `ValueError`, so a caller that only knows `ValueError` still records nothing.
  `jobs._assess_events` and `jobs.stage_assess` catch it first and return `{'skipped': ..., 'superseded': true}`.
- The values check is new. It catches the one state in which the context is still current but a save is not in it: a save
  on a revision whose current gemini context is of an older inventory version (case B stores the values without making a
  new context).
- The check happens at commit time, after the bounded child, so a save that lands while the child computes is seen.
- Decisions are carried only by a final assessment that passed this check (`review._carry_decisions` after `is_final`,
  unchanged), so an older result never carries, invalidates, closes or withdraws anything.

### 4.2 Analyze's compare-and-set

`jobs.stage_analyze` today derives with `encounter.user_values` read before the lock and makes its context current whenever
the revision is current. A save landing between its read and its commit was lost. Changed: the derivation and the commit
happen under the row lock:

```
with transaction.atomic():
    locked = jobs._locked(encounter)
    if locked.current_revision_id != revision.pk:     -> superseded (SUPERSEDED_REVISION)
    if review.fresh(locked):                          -> superseded (SUPERSEDED_RESTORED)
    if not review.reading_owed(locked):               -> superseded (SUPERSEDED_DERIVED)
    derived = derived_facts(locked, inventory, stored)          # pure, local; reads locked.user_values
    context = record_derived_context(locked, revision, inventory, derived, earlier=earlier_for_new_context(locked))
    locked.current_context = context; locked.save(update_fields=['current_context', 'updated_at'])
_queue_predict(... context ...) unless superseded
```

`reading_owed` is false when a save already derived a context from this inventory with these values (a save that landed
after the inventory existed takes case A itself). The derivation is the one `_save_on_inventory` already runs under the
same lock in a web request; it reads the stored row (`_stored_inventory`) and no text for meaning.

### 4.3 How every reader reads "current"

| reader | today | changed |
|---|---|---|
| `review.refresh_state` / `review._state_and_run` | the current revision's latest job, then the live assessment | target jobs only (5.2); "fresh" decides whether the assessment's own state stands; the idle-owed state reads stopped |
| `review.readiness` | `_active_jobs` (any job of the encounter) and the live assessment's blockers | active **target** jobs; while an update is pending, the blocker UPDATE_BLOCKER and `draft: false` |
| `review._allowed`, `review.allowed_actions` | the current assessment of the current revision, final | also fresh: otherwise [] (A7) |
| `review.record_decision` | `live_assessment(locked)` and `_allowed` | under the lock: update pending -> `ValidationError(UPDATE_DECISION)`; not final -> `NOT_FINAL_DECISION` (unchanged); not fresh -> `UPDATE_DECISION` |
| `customer_api.encounter_json` (the review view) | codes of `live_assessment` | `codes` only when fresh (or during a first processing, as today); while an update is pending, `codes: []` and `earlier_codes` (5.1); `what_changed` when fresh and the current context records an earlier assessment (6.2). While an update is pending, every other assessment-derived key (`other_codes`, `not_separately_coded`, `unresolved`, `limitations`, `details_needed`, `earlier_answers`) is read from `earlier(encounter)` — under A17 the current assessment itself — and the page draws them inside the earlier codes' section (5.1), never as the document's current findings; none is ever read from an assessment of the update that is not final [R:truth-T6] |
| reload | GET derives everything from rows | unchanged in kind: every new key is derived from rows (5.5) |
| `customer_api.readiness`, `api.py:create_report`, `reports.customer_snapshot` | the live assessment | refuse while an update is pending (8.1), including a first processing's unfinished assessment that a save made stale (a draft of it) [R:truth-T8] |
| `api.py:download_report`, `reports.customer_artifact_current`, `customer_api._reports` | 409 for an approved export that is not current; current = the marker digest matches | current = the marker digest matches **and no update is pending**; a non-current export is served with the banner (8.3) [R:races-R1][R:truth-T1][R:legacy-L1] |
| `progress.encounter_progress`, `progress.checks_summary` | every job of the current revision; `jobs.busy` | progress jobs for the steps and the times; target jobs for busy and the phase (5.2) [R:truth-T2] |
| `progress.date_held`, `customer_api.customer_state`, `customer_api.list_row` | the current context's member date conflict, read first | a conflict held only while the saved values are the current context's (`values(encounter) == values(current context)`); while they differ (a case-B update pending) the update's own state decides the phase, the state and the list row (5.1) [R:truth-T3] |
| `answers.service_date_block`, `answers._rows`, `answers._date_row` (the date block and the details rows) | the current context's facts and `context.user_values` | while `values(encounter) != values(current context)` (case B pending): the entered values and the row values from `Encounter.user_values`; the document's own date and quote still from the context; no member conflict asserted until a context derives one (5.1) [R:truth-T3] |
| `customer_api.customer_state`, `customer_api.list_row` | the stored state | `updating` while an update is pending and a target job is active |
| `jobs._second_review_bounds` | `assessment.context == context` | refuses while an update is pending (the context differs, busy, or `values(context) != values(encounter)`: a case-B save keeps the context), with UPDATE_DECISION's wording, so the re-check is never offered on the earlier codes [R:truth-T15] |
| `jobs.recompute_after_answers`, `jobs.reassess_after_confirmation`, `jobs.reassess_retained` | require the final assessment on the current context | unchanged |
| the operator console (`/ops/`) | every row | unchanged; superseded jobs show their `result` |

### 4.4 Older assessments are history

An assessment that is not the encounter's current one is a historical record. It is never deleted or rewritten (immutable
rows). It is shown to a member only as:

- the **earlier codes** while an update is pending (`earlier(encounter)`, which under A17 is still the current
  assessment), read-only (5.1);
- the **base of "what changed"** after the update (6.2);
- through its decisions in **Earlier decisions** and its exports in **Earlier downloads** (5.4).

A superseded stage records no assessment at all (4.1), so there is no "older finished assessment" made after a newer save:
the work it did is cheap to redo locally, and every provider answer it used is stored and reused.

### 4.5 `EncounterContext.earlier_assessment` (A5)

`EncounterContext` is immutable; the new nullable foreign key is set at insert, by `jobs.record_derived_context(...,
earlier=...)`, from analyze (4.2) and from a context save (2.2), and is outside the context's sha256:

```
earlier_for_new_context(locked):
    A = locked.current_assessment
    if A is not None and review.is_final(A):  return A          # the codes the member saw: a stale or a fresh final
    C = locked.current_context
    if C is not None and C.earlier_assessment_id and (A is None or A.context_id != C.pk):
        return C.earlier_assessment                              # only off the current context [R2:binding-R2B-3]
    if A is not None:  return A        # the codes the page shows, of this revision or the one an addendum follows
                                       # [R:truth-T8][R3:truth-R3T-5]
    return None                                                  # a first processing with nothing shown yet
```

- For rapid saves S1, S2 on a final E: S1's context records E; under A17, E is still the current assessment when S2 lands
  (S1's assess #1, if recorded, is not current), so S2's context records E too. Every context of one update names the same
  E. (The second branch, written for an assess #1 of the update being current, no longer meets that state under A17.)
- **A chain re-run after the codes were final** [R2:binding-R2B-3]: an operator's reconciliation of a participant's
  unknown outcome restarts the chain on the current context (`jobs.reconcile` -> `_after_predict(..., origin=
  'reconcile:<run>')`), as does a Corti reconciliation's predict or a Resume; its assess #1 persists while the encounter is
  fresh, so A17 does not apply and it becomes current as today. The second branch of this function and of `earlier()`
  applies only when the current assessment is not on the current context, so that state is processing, never an update.
  (Applied to it, the branch returned the context's recorded `earlier_assessment` — the codes from before the previous,
  completed update: the panel read "Changes saved—updating codes" with nothing saved, the earlier codes, `update.changes`
  and `started_at` were the completed update's, UPDATE_DECISION refused, and a Stop offered "restore the earlier details",
  whose save then undid the completed update.) A save made during such a chain takes the assessment the page shows, as
  T8's branch does, and "what changed" then reads the decisions from the assessment that held them (6.2 step 4). So does
  an addendum recorded during it [R3:truth-R3T-5]: the T8 branch no longer asks that the assessment be of the current
  revision, so the addendum's update has that assess #1 as its earlier codes (kind `documentation`), and "what changed"
  lists the approvals the addendum cleared on the last final. (Asking it left the addendum with no earlier codes: no
  "Changes saved—updating codes", and "what changed" null, though the addendum had cleared those approvals.) The same
  rule makes an addendum during a first processing whose unfinished assess #1 was shown an update of those codes, as T8
  makes a save there (8.1).
- For a save during a first processing whose unfinished assess #1 A1 is current (its codes were shown, a draft could be
  made of them) [R:truth-T8]: the new context records A1, so the update is pending from that save: the panel reads
  "Changes saved—updating codes", A1's codes are the earlier codes (read-only; they were never decidable, being not
  final), exports are refused until fresh (8.1), and "what changed" compares the final with A1 (6.2). A1 stays current
  until the final (A17). A save back to A1's values is an ordinary change, not a restore (2.5: B must be final).
- For an addendum: R2's analyze records R1's final, or the unfinished assessment of R1 the page showed when the addendum
  was recorded (a first processing's, or a re-run chain's assess #1) [R3:truth-R3T-5].
- For a legacy update: analyze's context records the legacy final.
- For an upload: none.
- A context the installed release (`c2e53f8e`) writes after a switch-back has it NULL: the old image knows no such column.

Migration 0015 (FINAL-V2 6.3, owned by 1d) adds it: `ForeignKey(Assessment, on_delete=PROTECT, null=True, blank=True,
related_name='+')`, no default, no NOT NULL. The installer's migration gate reads it as additive (nullable), as it read 0014's
`EncounterContext.event_inventory`.

---

## 5. While pending

### 5.1 The screen

The customer page (`app.js`, drawn from `customer_api.encounter_json`) shows, while an update is pending:

1. **The progress panel**, phase `updating`, title exactly **"Changes saved—updating codes"** (for the one update no save
   starts, kind `check`, A21: "Updating codes", the state label, since nothing was saved [R3:binding-R3B-3]), with the
   truthful steps of 5.2, the elapsed time since the update began, "Stop processing", and under the title what was saved,
   from the `update` block:
   - `Date of service: 10 November 2026` (or `Date of service removed`);
   - `Place of service: Hospital outpatient department` (`answers.CHOICE_LABELS`);
   - `Patient: New patient`, `Claim: Facility claim`;
   - `Documentation added (revision 2)`;
   - `Saved by <member>, <time>` (the newest `context.changed` or `revision.addendum` audit row).

   `changes` is computed as `values(encounter)` against `values(earlier.context)`, plus the revision when it differs: the
   member sees what this update will apply, however many saves it took. When it is empty (the saved details are the
   earlier codes' own, within one revision), the list shows one fixed line in its place, chosen from rows, so the panel
   always says why the codes are being updated [R3:binding-R3B-6]: the earlier codes not final (a save back to a first
   processing's unfinished codes, T8) — "The codes from before your change were not finished; they are being finished
   for these details."; a save A19 keeps from being a restore — "These are the details of the codes from before your
   change; the codes are made again because your answers, or an earlier check, changed since those codes were made.";
   kind `check` (A21) — "An earlier check was settled, so the document is being read again with the current reading.",
   with no "Saved by" line (3c words all three).
2. **The earlier codes**, headed "Codes from before your change", with "Made <time>, with date of service <date>. They
   cannot be approved or exported: they are from before your latest change." — true in every update state, running or
   not [R:truth-T4]. Each row has the shape of `codes` (`customer_api.code_rows` over the earlier assessment, its current
   decisions and its review overlay) with `allowed_actions: []`. Rows are greyed; no decision button is drawn. The earlier
   assessment's other sections — "Other codes considered (not suggested)", "Not separately coded", "Still open",
   "Limitations" — are drawn inside this section, under the same heading and greyed, never as the document's current
   findings; the re-check offer is not drawn (T15) [R:truth-T6].
   - **A14:** the earlier codes are read inside `sentinel.relabel(<the earlier assessment's own label>)`, the way
     `readers.labelled` relabels list rows (R-6). Under A17 the current assessment stays the earlier one until the update's
     final, so the encounter's label (`readers.label_of`, the current assessment's engine) is normally the earlier codes'
     own; the relabel stays as a guard, so that whatever the encounter's label (a state an older image wrote, or a future
     change), a legacy earlier assessment's overlay is never read in a new_path scope, where it would count legacy
     executions against the new path [R:races-R3].
3. **The details panel.** Date and choice rows (context rows) stay editable: a rapid successive edit is a context save.
   While a case-B update is pending (the saved values differ from the current context's), the date block and the rows
   show the saved values (`Encounter.user_values`: "Saved: …"), never the kept context's, and assert no member date
   conflict until a context derives one; the date block's document date and quote still come from the context
   [R:truth-T3]. Rows that take "Not documented" or "Cannot confirm" show "You can answer this once the codes are
   updated." and no control (1.4's narrowed refusal). "Earlier answers, not applied" keep their Withdraw link hidden while
   busy or while an update is pending (1.4) [R:truth-T12].
4. **Downloads.** "Review and download" stays; in the dialog both export kinds are disabled, with UPDATE_EXPORT_NOTE by
   the update's state [R:truth-T4]: while it is `updating`, "Your change is saved and the codes are being updated. Exports
   are available again once the update finishes."; in every other state (`failed`, `stopped`, `paused`,
   `being_confirmed`), "Your change is saved, but the codes have not been updated yet; the panel above says why. The codes
   from before your change cannot be exported as current." "Earlier downloads" are listed and downloadable (8.3); during an
   update every export made before it is listed as earlier, a case-B update included (8.3) [R:races-R1][R:truth-T1].
5. **History.** "Earlier decisions" (5.4) and the activity log (`customer_api.activity`, unchanged: `context.changed` is
   "Encounter details changed").

What the page never does while pending: draw a decision button, enable an export of the earlier codes, call them "Ready for
review" as the current state, animate a step no target job runs, say the codes "are being updated" when nothing runs
[R:truth-T4], say that no codes were suggested [R:truth-T5], or draw anything from an assessment of the update that is not
final [R:truth-T6].

**The results section while pending** [R:truth-T5]: `codes` is `[]`, so `app.js:resultList` would draw `emptyResults`,
whose lookup has no `updating` and whose failed, stopped and paused sentences say that no codes were suggested.
`emptyResults` and `tallyText` read `update` first: with `update.pending` and state `updating`, "The updated codes appear
here when the update finishes. The codes from before your change are shown below."; in the other update states, "The
codes have not been updated after your change yet; the panel above says why. The codes from before your change are shown
below." The review bar's tally reads the earlier codes, prefixed "Before your change: " (never "No codes yet" while they
exist). When `earlier_codes` is empty (the earlier assessment listed no code: none was suggested, or only alternatives
and exclusions no reviewer can reinstate), "The codes from before your change are shown below." reads "No code was
suggested before your change.", and the tally reads "Before your change: no code suggested" [R2:truth-RT8].

The new keys of `GET /api/encounters/<id>` (every one listed, as CORE-UX-DESIGN.md 7 requires; 6b extends
`customer-contract.json` with them):

```
"update":           null | {"pending": true,
                            "state": "updating" | "failed" | "stopped" | "paused" | "being_confirmed",
                            "kind": "details" | "documentation" | "check",  # documentation: a new revision (case C); check: A21 [R3:binding-R3B-3]
                            "restorable": bool,                    # 2.5's restore applies to the earlier codes [R2:binding-R2B-4][R2:binding-R2B-5]
                            "changes": [string], "saved_by": string, "saved_at": iso, "started_at": iso,
                            "earlier": {"made_at": iso, "revision": int, "details": [string]}}
"earlier_codes":    [<a code row, as "codes", with "allowed_actions": []>]          # [] unless an update is pending
"what_changed":     null | {"compared_with": {"made_at": iso, "revision": int},
                            "details": [string],
                            "codes": [{"code": string, "change": "added" | "removed" | "status" | "units" | "detail",
                                       "text": string}],
                            "unchanged": int,
                            "decisions": [{"code": string, "action": string,
                                           "outcome": "kept" | "kept_then_cleared" | "kept_then_changed" | "cleared",   # [R:truth-T9][R2:truth-RT4]
                                           "text": string}],
                            "answers": null | string}                      # 6.2 step 5 [R:truth-T11]
"decision_history": [{"code": string, "action": string, "by": string, "by_kind": "human" | "agent", "at": iso,
                      "revision": int, "why": string}]
"reports":          [... the existing keys ..., "revision": int]
```

`progress.phase` gains `updating`; the customer state vocabulary gains `updating` ("Updating codes"). Every string is
CPT Studio's fixed wording, built by allowlist (`customer_api`'s rule), with no stored free text. `update.kind` is
`documentation` when the earlier codes are of another revision (case C); `check` when the update is A21's (the earlier
codes' own document review is an unknown outcome a reconciliation released while a reading is owed) and no
`context.changed` or `revision.addendum` row was recorded after the later of the earlier assessment's creation and the
newest restore — the operator's reconciliation started it, and `saved_by` and `saved_at` are null [R3:binding-R3B-3]; and
`details` otherwise; 7.1 chooses its texts by it, so no case-C text offers a restore [R:truth-T7] and no check text names
a change of the member's. `update.restorable` is true only when a save of the earlier codes'
own values would be 2.5's restore (within one revision, B final and current, A19's conditions); it is false for case C
and wherever A19 refuses one, and 7.1 then drops every restore clause [R2:binding-R2B-4][R2:binding-R2B-5].
`update.started_at` is the `created_at` of the oldest
`context.changed` or `revision.addendum` audit row recorded after the later of the earlier assessment's creation and the
newest restore (a `context.changed` row naming `restored`): the update began at the first save, however many saves
followed [R:truth-T2]; for kind `check`, the `provider.reconciled` row that started it [R3:binding-R3B-3].

### 5.2 Truthful progress

`progress.py` (5b) folds the **progress jobs** (vocabulary) for the steps and the times, and reads the **target jobs**
for `busy` and the phase, so a superseded stage never colours a step and a stage that ran for the update keeps its step
once the reading is no longer owed [R:truth-T2]. (The pre-refutation text folded target jobs for the steps too. Target
jobs drop the context-free stages once a reading is no longer owed and, when fresh, keep only jobs made after the current
assessment, so the steps flipped to "Not needed" right after an addendum's or a legacy update's reading ran, the elapsed
time reset at the predict, a legacy update before its analyze counted from the upload days earlier (the original legacy
chain carries the still-current legacy context), every upload read "Reading your document: Not started" beside a running
check, and a completed document lost its finished time and read every step "not started".)

- `progress.encounter_progress`: `busy` = a target job is QUEUED or RUNNING (instead of `jobs.busy`). With an update
  pending and busy, the phase is the new `updating`; its message follows today's rules for a queued or a running step
  (`progress.queued_message`, `TAKING_TURN`, `NEXT_STEP_QUEUED`, the slow messages of `progress._slow`), except for the
  waiting case below. A step's state comes from `progress._fold` over the progress jobs of that step in the current run,
  read in two parts [R2:truth-RT3][R3:truth-R3T-1][R3:truth-R3T-2]. **Activity** is read from every progress job of the
  step, as today's fold reads it: one RUNNING reads in progress (`active`), one QUEUED beside a finished one reads in
  progress, and only QUEUED ones read `waiting`; so the running stage an `:after-save:` stage was queued beside (2.3)
  keeps its step in progress, with its active detail. **The outcome** of a step none of whose progress jobs is active is
  read only from the attempts that served the saved state: a stage that carries a context colours the step only while
  its context is the current context, so a late finisher of an older save's context (3.5) never does, whatever its
  outcome and whether or not the newer chain ran a stage of its kind (a re-check with the run in use, 2.2, runs no
  predict); of those, and of the context-free stages (interpret, appraise, analyze), only the newest attempt of each kind
  that started colours it, and one that never started (expired or cancelled while QUEUED: no `started_at`) colours it
  only when no attempt of its kind in the run started. Every attempt keeps its row and its times. (Folding every attempt,
  `progress.FOLD_ORDER` ranks stopped and failed above done, so a Stop on a running appraise followed by a save read
  "Identifying procedures: Stopped", and a late finisher's FAILED predict read "Checking suggested codes: Did not finish",
  beside the next step in progress and after completion, for work the update did; neither overlap exists today, where a
  save is refused while busy and a Resume starts a run of its own. The second revision's rule, the newest attempt of each
  kind for activity and outcome alike, read a running pass 1 "Waiting to start" beside its queued `:after-save:` twin,
  still coloured "Checking suggested codes" with a late finisher's FAILED or held predict when the newer chain re-checked
  with the run in use, and read "Identifying procedures: Stopped" when an `:after-save:` twin expired in a backlog after
  the running reading had read the document.) While an update is pending, a step before the
  current run's first step reads `skipped` ("Not needed" in
  `app.js:STEP_STATES`) instead of the earlier run's state; otherwise today's `progress._steps` rule stands (the latest
  earlier run's state). A step after the active one reads `not_started` until a job runs it. So a context save on a v2
  revision shows "Reading your document: Not needed", "Identifying procedures: Not needed", then "Checking suggested
  codes" and "Preparing your results" by what runs; a legacy update shows "Reading your document: Not needed" and
  "Identifying procedures" running, with the active detail "Reading the documented procedures" (interpret) or "Checking
  the reading against the document" (appraise: FINAL-V2 4.12's `progress.DETAILS['appraise']`, in interpret's step,
  IDENTIFYING), and keeps "Identifying procedures: Done" once its analyze ran; an addendum's run starts at its extract,
  so every step it ran keeps its state.
- `started_at`: while an update is pending, `update.started_at` (5.1: the first save's time, however many saves followed);
  otherwise the current run's first job's `created_at` (today's rule, over progress jobs). `finished_at`: today's rule over
  the current run's progress jobs, so a completed document, after an update or not, keeps "finished in …" [R:truth-T2].
- When the next target job waits behind a superseded stage that is still RUNNING (the worker runs one job at a time), the
  phase stays `updating` and the message is WAITING_FOR_EARLIER: "Your change is saved. A step started before it is
  finishing first; its result is used only where it still applies." Never "Waiting to start".
- `progress._runs` keeps cutting runs, now over progress jobs [R:truth-T2]; its docstring's R6 4.5 premise is replaced by
  3.10: a run is the jobs queued while an earlier job of the revision was still active, plus the job that started it, so
  the overlapping chains of rapid saves form one run.
- `progress.date_held` holds the phase at `action_needed` only while the saved values are the current context's; while a
  case-B update is pending they differ, the kept context's member conflict is no longer the member's choice, and the
  update's own state decides the phase, so its failure text and its Retry are shown [R:truth-T3].
- `progress.final_assessment` returns the live assessment only when `review.fresh` holds (today it compares the context
  only, and for a legacy update the context is unchanged while the values differ), so `progress.checks_summary` and
  `progress._partial` never present the earlier codes' checks as the current result; with an update pending each function
  reads its target jobs' state.
- Steps, details and messages name functions, never vendors (FINAL-V2 4.12): "Document review", "Independent checks",
  "Coding validation", "Reading the documented procedures", "Checking the reading against the document". The customer
  output scan (3c) runs over the new messages.

`review._state_and_run` (the stored state the list and the panel derive from) becomes:

```
revision missing, or an active target job                         -> processing
extraction failed / pending                                       -> as today
latest target job CANCELLED                                       -> stopped
latest target job FAILED or UNKNOWN                               -> _failed_stage_state (unchanged, with appraise added in 5b)
fresh                                                             -> the current assessment's state, as today (provider run, _review_state, refused run)
not fresh and nothing above (idle-owed)                           -> provider_unknown when an outcome is unknown, else stopped
```

The idle-owed line is new; today the same rows read `processing` with nothing running, which never ends. Stopped offers
Resume (3.6), with STOPPED_BY_SYSTEM "Processing paused before it finished." or, during an update, 7.1's text.

### 5.3 Approval and export refused server-side

| act | where refused | text (internal = customer, fixed, no vendor) |
|---|---|---|
| approve, reject, reinstate, confirm, revoke on the earlier codes | `review._allowed` returns []; `review._record_decision` under the lock | UPDATE_DECISION: "These codes are from before your latest change and cannot be decided on. Decide on the codes once they are updated." [R:truth-T4] |
| a draft or an approved export | `api.py:create_report` (before `reports.generate_customer`), and again in `reports.customer_snapshot` under the lock | UPDATE_EXPORT: "These codes are from before your latest change and cannot be exported as current. Exports are available again once the codes are updated; earlier downloads stay available, marked as earlier." [R:truth-T4] |
| readiness | `review.readiness` adds UPDATE_BLOCKER "The codes are from before the latest change; the update has not finished" | customer, by the update's state [R:truth-T4]: while `updating`, "The codes are being updated after your change."; otherwise "The codes have not been updated after your change yet." (both `customer_api.BLOCKER_EXACT`; `customer_api.readiness` chooses by `update.state`) |
| the second review | `jobs._second_review_bounds`: refused while an update is pending, a case-B save included (its context is unchanged, its values are not) [R:truth-T15] | UPDATE_DECISION |
| an answer's withdrawal | `answers._revoke_answer`, under the lock (1.4) [R:truth-T12] | UPDATE_ANSWER_WITHDRAW: "You can change your answers once the codes are updated." |

Every refusal text above joins `customer_api.KNOWN_ERRORS`. The refusals are evaluated under the encounter's row lock, so
a save that lands between the page's load and the click is seen. A page loaded before the save (another tab) is refused
the same way.

### 5.4 Records

- **Earlier decisions** (`decision_history`, new, `customer_api`): every `Decision` of the encounter that has a
  `DecisionInvalidation`, newest first (bounded to 200): its code, its action label, who, when (`review.decision_root`'s
  time), the revision number it was made on, and why it no longer applies, in fixed words chosen from the rows, first
  match wins:
  - `by_revision` set: "Cleared when documentation was added (revision {n})."
  - the decision's assessment is a legacy one (`interpretation.is_new_assessment` false) and `by_context` is a gemini
    context (`interpretation.is_new_context`): "Made on the earlier reading of the document; the current codes come from
    a new reading, so it does not carry. Decide the current codes."
  - `by_context` is the decision's own assessment's context (a final made with the same details cleared it: an answer's
    recompute, the follow-up of a re-check of what is still open, an operator's re-assessment — `_carry_decisions`
    records the new final's own context, which for such a final is unchanged) [R:truth-T10]: "Cleared when the codes were
    checked again with the same details: the code it was made on changed."
  - otherwise (`by_context` is another context: the details changed): "Cleared when the details changed: the code it was
    made on changed."
  The `DecisionInvalidation.reason` text itself is never shown (it is internal prose, `review._context_reason`). The
  same-details sentence also labels truthfully the clearings already in live history from the installed release's answer
  recomputes and re-checks [R:truth-T10].
- **Earlier downloads:** every customer artifact, newest first (`customer_api._reports`), each with its revision number
  (new key `revision`) and `current` (8.3: the marker matches and no update is pending [R:races-R1][R:truth-T1]). A
  non-current one is listed "Earlier — made on revision {n}; it may not show the current codes" — a marker also differs
  when only the details changed and every code and decision carried [R:truth-T14] — and its link downloads it with the
  banner (8.3). Today `app.js:reportItem` drops the link of a non-current artifact.
- Nothing is deleted or rewritten: `Decision`, `DecisionInvalidation`, `ReportArtifact` and `Assessment` rows are immutable.

### 5.5 What reload shows

Everything on the page is derived from rows on each GET: `fresh`, `earlier`, the `update` block (values, audit rows), the
target jobs and the phase, the earlier codes, `what_changed`, the decision history and the downloads. A reload in the
middle of an update shows the same phase, the same steps and the same earlier codes; a reload after it shows the same
updated codes and the same "what changed". The only browser state is the unsent choices in `state.answers` (lost on reload,
by design: nothing was saved) and the display state (open disclosures, kept in memory only). A reload sends no request to
any provider (`progress.py` and `customer_api` write, queue and send nothing).

---

## 6. On completion

### 6.1 Updated codes

The update completes when a final assessment N of the saved state passes 4.1: the encounter is fresh. The page then shows
N's codes as `codes`, with their actions (`review.allowed_actions`), the progress panel's completed, partial or
awaiting-detail phase (unchanged), and "What changed" above the codes.

### 6.2 What changed

`customer_api.what_changed(encounter)` returns null unless the encounter is fresh and the current context records an earlier
assessment E (4.5). The current assessment is N. It reads stored rows only — `Assessment`, `Proposal`, `Clarification`,
`EncounterContext`, `Decision`, `DecisionInvalidation`, `SourceRevision`, and for step 5 `MemberAnswer` and
`MemberAnswerRevocation` [R:truth-T11] — never the review overlay, a reader, the clock or the configuration, so it is the
same on every read and in every process:

1. **Compared with:** E's `created_at` and revision number ("Compared with the codes as suggested on {time}, before any
   answer or decision" [R:truth-T11]). The comparison is of the suggestions as each assessment made them (stored rows),
   not of the screen the member saw, which the review overlay drew with their answers and decisions applied: it says so,
   and step 5 names the answers, so a code the member saw excluded by their own answer and now asked about again is
   explained rather than counted unchanged without a word.
2. **Details:** for each coding-context field whose value differs between `E.context.facts` and `N.context.facts`, the
   field's label with both values in the member's words (dates as "10 November 2026", choices by `answers.CHOICE_LABELS`,
   "not documented" for none, "two dates to choose from" for a conflict). Plus "Documentation added (revision {n})" when
   the revisions differ, and "The document was read again with the current reading." when the engine families differ (a
   legacy E).
3. **Codes.** For each assessment X, its listed rows are the proposals `customer_api.code_rows` numbers, decided on stored
   fields only: bucket SELECTED, or bucket EXCLUDED and reinstatable, or excluded by a member's answer
   (`questions.answered_away`). A row's status is read from the row: SELECTED and READY "Ready for review"; SELECTED and
   NEEDS_CLARIFICATION "Needs a detail"; EXCLUDED "Excluded by a documentation check"; answered away "Excluded: a needed
   detail is not documented". A row's detail is the `fact` of the first clarification of X naming the proposal (by
   creation order), else of the first service-scoped clarification of X whose `family` is the proposal's, shown by
   `answers.PROMPTS` (`answers.DEFAULT_PROMPT` for a fact it does not list). Clarification rows change state when a later
   assessment withdraws them (`review._withdraw_superseded`), so the state is not read: the fact is the row's own and does
   not change. Rows of E and N are paired by code, and within one code by stored position.
   - a row of N with no pair: **added** — "{code} is now suggested ({status})";
   - a row of E with no pair: **removed** — "{code} is no longer suggested", with, when N has a stored proposal of that
     code that it does not list, the reason the other-codes list gives it — the expression `customer_api.code_rows` uses,
     applied to that stored row: bucket ALTERNATIVE reads "Listed as an alternative only; not suggested for approval.",
     any other "Not suggested: …" (`customer_api._exclusion_reason`, from the row's stored checks) [R:truth-T14]; no reason
     when N has no proposal of that code;
   - paired, statuses differ: **outcome changed** — "{code}: {before} → {after}";
   - paired, units differ: "{code}: {before} → {after} units";
   - paired, both "Needs a detail", facts differ: **the item changed** — "{code}: the detail needed changed: "{before}" →
     "{after}"" (D182's one item per held code);
   - otherwise unchanged, counted ("{n} codes unchanged").
4. **Decisions** [R:truth-T9]. The decisions listed are those the update acted on [R2:binding-R2B-3], read from rows:
   every `Decision` on an assessment created before N's context was recorded that a final on N's context carried (a
   `Decision` of an assessment of N's context names it as `carried_from`) or invalidated (`DecisionInvalidation.by_context`
   is N's context), and in case C every one invalidated for a revision recorded after E's revision, up to and including
   N's (`DecisionInvalidation.by_revision`) [R3:truth-R3T-3]: each addendum of the update invalidated the holder's current
   decisions as it was recorded, so with two addenda before the update's final the first one cleared them and the second
   found none (reading N's revision alone, "what changed" then listed no decision, though the update had cleared the
   reviewer's approvals). These are exactly the decisions `_carry_decisions` or `invalidate_for_new_revision` acted on
   during the update, at each addendum and when its final was recorded: the current decisions of the assessment that held
   them then (`review.decision_holder`), which is E whenever E is final — so each is E's decision as it stood when the
   update replaced E — and the last final when E was an unfinished assessment a save or an addendum made stale (T8's
   states, and a save or an addendum during a chain re-run after the codes were final, 4.5). A decision the reviewer
   revoked before the change was not current, nothing carried or cleared it, and it is not listed; a decision a later
   final on N's context acted on was made on an assessment of that context and is not listed either. (The rule never asks
   which assessment is final, which reads the participants configured now; 11.1's U11 changes them and nothing may
   change.) Each listed decision D reads, the action one of the fixed nouns Approval, Rejection, Reinstatement,
   Confirmed exclusion:
   - **kept** when the chain of carries from D (`Decision.carried_from`, followed forward) reaches a decision that is
     current on N (`review.current_decisions(N)`): "{action} of {code} kept: the code is unchanged.";
   - **kept, then cleared** when D was carried onto the update's final but the chain was cleared afterwards by a final
     made with the same details (an answer's recompute, a re-check's follow-up): "{action} of {code} was kept by the
     update, then cleared when the codes were checked again with the same details." (5.4's same-details sentence);
   - **kept, then changed by a reviewer** [R2:truth-RT4] when D was carried onto the update's final and the chain's last
     decision, on N or on a later final made with the same details, is no longer current there because a reviewer
     recorded a later decision on its code on that assessment (a revoke, or a new decision), with no
     `DecisionInvalidation` on it: "{action} of {code} was kept by the update, then changed by a reviewer.";
   - **cleared** when D has a `DecisionInvalidation`: 5.4's words for it.

   The four are exhaustive [R2:truth-RT4]: the chain ends current on N, ends at a decision a same-details final cleared,
   ends at one a reviewer's later decision replaced, or D itself was cleared. (With three, an approval the update kept and
   the reviewer then revoked, or revoked and approved again, on N matched none, and the natural fall-through read
   "Cleared when the details changed: the code it was made on changed." beside the code shown Ready for review or
   Approved.)
5. **Answers** [R:truth-T11]. When the revision's standing member answers include one answered before N's context was
   recorded (`MemberAnswer.answered_at` before `N.context.created_at`) [R2:truth-RT5] that N's stored rows do not read (no
   clarification of N names it as its answer, and no proposal of N records it as answering it away) while the revision
   is the one E was made on, one fixed line: "Some answers you gave before this change are not applied to the updated
   codes; they are listed under Earlier answers, not applied." (the section `answers.earlier_answers` draws, 5.1). An
   answer N applies needs no line: N's stored rows show its effect. No answer is recorded while an update is pending
   (1.4), so the answers counted were given before the change; an answer given after the update to a question N asks —
   recorded while its recompute is queued, running, stopped or failed — is never counted [R2:truth-RT5]: it was not given
   before the change, it is the saved answer of a question asked now (not an earlier answer), and the recompute's
   assessment reads it. (Counting every standing answer N's rows do not read put both false clauses on the page beside
   that answer's own effect, for as long as the recompute had not run.)

Order: details, then codes by code, then decisions by code, then the answers line. The same function serves the page and
the differential check of 11.3.

After an answer's recompute (an AGAIN assessment on the same context), N is that assessment and E is unchanged: "what
changed" then reads "since the codes as suggested on {time}", the decisions part follows the carried chain to the new
current assessment (step 4: a carried decision the recompute cleared reads "kept by the update, then cleared"), and the
answers line follows the new N [R:truth-T9].

### 6.3 Approval stays explicit

- A recheck never records a decision. The only decisions an update writes are `review._carry_decisions`' copies, which
  carry a reviewer's own decision onto a proposal with the same fingerprint, code, list, status and profile version
  (`review._carry_target`; ARCHITECTURE 5.7), unchanged. "What changed" names every kept approval, so the reviewer sees it.
- The approved export after an update is a new, explicit act (`api.py:create_report`), gated by readiness over N.
- Nothing auto-approves (FINAL-V2 4.12).

### 6.4 What carries and what does not

- **Across engines (D7):** nothing carries. ENGINE_VERSION @2 changes every fingerprint (FINAL-V2 6.5), so a legacy E's
  decisions are all invalidated by N's persist (reason containing "the interpretation changed",
  `review._what_changed`), and every one is listed in Earlier decisions.
- **Within the events engine:** a decision carries only when the proposal's fingerprint is unchanged. FINAL-V2 6.5's
  fingerprint carries the engine, code, family, the check results, the context values, units, status and the read facts'
  ids, results, values and spans; whichever context values it carries for a code, a change of one clears that code's
  decision, and a change it does not carry keeps it.
- **Member answers:** bound to their question's fingerprint, unchanged (FINAL-V2 6.5): an answer to a question N still asks
  is applied; one N asks differently or no longer is kept and shown as an earlier answer, never applied silently.
- **A new revision:** every decision is cleared at the addendum (`review.invalidate_for_new_revision`), as today.

### 6.5 Legacy approvals as records

A legacy encounter's first update clears every legacy decision (6.4). Each stays as its `Decision` row with its
`DecisionInvalidation`, is listed in Earlier decisions with "Made on the earlier reading of the document ...", and appears in
"what changed" as cleared. The legacy exports stay in Earlier downloads and download with the banner (8.3).

---

## 7. Failures

### 7.1 What each failure shows during an update

During a first processing the existing texts stand (`progress.ERRORS`, `progress.INTERPRETATION_ERRORS`), and one is
added [R2:truth-RT6]: a document paused under Corti's provider hold reads PROVIDER_PAUSED (`progress.provider_paused`;
3c words it, naming no provider), with the meaning "The coding service is paused on this installation, so this
document's codes are not checked yet. Nothing more is sent to it until it is available again; resume once it is." — true
both for a document the hold kept unsent and for the one whose own request set the hold (7.3). INTERPRETATION_PAUSED,
which says the reading is paused, is never shown for it. PROVIDER_PAUSED is shown only while Corti's hold stands
[R3:truth-R3T-7]: `progress.provider_paused` reads the stage's own record (a predict the hold ended paused) and the
standing hold, a row the web process can read (`provider_holds.active`), unlike the interpreter's mode, which only the
worker knows and which `progress.interpreter_paused` therefore reads from the stage alone. Once an operator has released
the hold, the same stage reads stopped by the system (STOPPED_BY_SYSTEM, "Processing paused before it finished.", with
Resume, which sends once), never "is paused"; during an update the held row below gives way to the stopped-by-the-system
row the same way. During an update
(earlier codes exist), `progress.encounter_progress` uses UPDATE_ERRORS (5b; worded by 3c), keyed by the same derived state
and run, and the panel's title is the update's (`app.js`):

| situation (rows that decide it) | phase | text | action |
|---|---|---|---|
| reading, pass 1 definite failure: 5xx, a per-minute paid-tier 429, another refusal, an unreadable envelope, a refused reading (`interpretation_effect` failed) | failed | "Your change is saved, but the codes could not be updated: reading the documented procedures could not be completed. The codes shown are from before your change and cannot be approved or exported until the update finishes." | `retry_reading`: "Try reading again" |
| reading, pass 2 definite failure or an unhealthy appraisal (FINAL-V2 7.5) | failed | the same, with "checking the reading against the document could not be completed" | `retry_reading` (re-sends pass 2 only) |
| too long: the size bound, an answer cut off at its output limit (MAX_TOKENS), or a claim set over pass 2's bound | failed | "Your change is saved, but the codes could not be updated: this document is too long to be read in one piece. The codes shown are from before your change and cannot be approved or exported. Restore the earlier details to use them again, or shorten the document and upload it again." | none (C5) |
| document review: a definite failure the retry may release (7.2): a 5xx, another 4xx, a transport failure | failed | "Your change is saved, but the codes could not be updated: the coding service could not complete its review. The codes shown are from before your change and cannot be approved or exported until the update finishes." | `retry_update`: "Try updating again" |
| document review not sent for a local reason: Corti's run NOT_SENT carrying its request (its credentials file unreadable, no HTTP session, the service unreachable, the deadline before sending, or a token endpoint that answered a 5xx or a redirect, could not be read, or gave no usable token: `providers.corti.send`'s not-sent paths other than a token-endpoint 4xx, which sets the hold, 7.3) [R:legacy-L5][R2:truth-RT1] | failed | "Your change is saved, but the codes could not be updated: the coding service could not be used just now, and the document was not sent to it. The codes shown are from before your change and cannot be approved or exported until the update finishes." (true for every member of the class: an unreadable credentials file is no unreachable service, and a token endpoint that answered was reached [R2:truth-RT1]) | `retry_update`: "Try updating again" (the coding request never left, so no release is needed) |
| the coding service held: a provider hold on Corti stands, whether this request set it (7.3's classification, A20: HTTP 401, 402, 403 or 429 from the coding service, or any 4xx from its token endpoint) or it kept this request unsent [R:races-R2][R:legacy-L2][R2:truth-RT1]; once an operator has released it, the same stage reads the stopped-by-the-system row below [R3:truth-R3T-7] | paused | "Your change is saved. Updating the codes is paused on this installation: the coding service refused its requests, and nothing more is sent to it until it is available again. The codes shown are from before your change and cannot be approved or exported until the update finishes. You can restore the earlier details to use them again." | `resume` when `can_resume` (after an operator's release) |
| document review: this request was refused before the install — the not-resent run's failed run, which `jobs._failed_before` finds, carries HTTP 401, 402, 403 or 429 and no `ProviderHold` row names it (7.3) [R3:binding-R3B-4][R3:truth-R3T-6] | failed | "Your change is saved, but the codes could not be updated: the coding service refused this same request before, and it is not sent again. The codes shown are from before your change and cannot be approved or exported. Restore the earlier details to use them again." | none: `retry_update` refuses it with RETRY_UPDATE_REFUSED_BEFORE (7.2) |
| the document review's request could not be built (`ProviderUnavailable` at `build_request`: a not-sent run with no request), when E's own request could be built (A6: when E's could not either, the update goes on with E's outcome) [R:legacy-L4] | failed | "Your change is saved, but the codes could not be updated: the document could not be prepared for the coding service, and nothing was sent. The codes shown are from before your change. Restore the earlier details to use them again." | none |
| processing failed in a stage that sends nothing (analyze, assess: an overrun, a refused store row, a sentinel refusal) | failed | "Your change is saved, but the codes could not be updated: processing could not be completed, and nothing was sent. The codes shown are from before your change and cannot be approved or exported until the update finishes." | `retry_update` |
| interpreter hold (authentication, permission, quota, payment, model) or the interpreter disabled | paused | "Your change is saved. Updating the codes is paused on this installation, and nothing was sent. The codes shown are from before your change and cannot be approved or exported until the update finishes. You can restore the earlier details to use them again." | `resume` when `can_resume` |
| the coding service disabled while Corti's request changed (7.2) | paused | "Your change is saved. The coding service is not available on this installation right now, so the codes are not updated yet, and nothing was sent. The codes shown are from before your change. Resume once it is available, or restore the earlier details." | `resume` |
| an outcome still unknown (`review._unreconciled_unknown`) | being_confirmed | "Your change is saved. We are confirming whether an earlier check completed; the codes are updated once that is settled, and nothing is sent again until then." | none (an operator reconciles at `/ops/`) |
| stopped by a member | stopped | "Updating the codes was stopped. The codes shown are from before your change and cannot be approved or exported until the update finishes. Resume to finish it, or restore the earlier details." | `resume` |
| stopped by the system (a dead worker, a queue expiry, idle-owed) | stopped | "Updating the codes paused before it finished. The codes shown are from before your change. Resume to finish it." | `resume` |
| the worker not responding (`jobs.worker_responding` False) | paused | `progress.MESSAGES['paused']`, unchanged | none |

"The coding service" is the existing customer name of the document review (`progress.ERRORS`); none of these sentences
names a provider or model. A first-reading or peer-review failure of Astra or Fable never fails an update: it blocks only
itself (HARNESS I10), and the update completes "partial" (`progress._partial`), with any code only that check had given
shown as removed in "what changed". A participant whose provider hold stands (7.3) is treated the same way: its stage
records a held not-sent run and the chain goes on without it [R:races-R2][R:legacy-L2].

**Case C texts** [R:truth-T7]. When the update is for a new revision (`update.kind` `documentation`: an addendum), no text
offers a restore, which does not exist across revisions (2.5): every sentence above loses its "restore the earlier
details" clause ("Resume to finish it, or restore the earlier details." becomes "Resume to finish it."; "You can restore
the earlier details to use them again." and "Restore the earlier details to use them again." are dropped), "from before
your change" reads "from before the documentation was added", and the too-long and the could-not-be-prepared texts end
"Upload the document again, shorter or split, to have it read." instead. A12 refuses an addendum over the size bound
before it is recorded (1.4), so the too-long case C text is met only by an answer cut off at its output limit or a claim
set over pass 2's bound.

**No restore where A19 refuses one** [R2:binding-R2B-4][R2:binding-R2B-5]. Within one revision, when `update.restorable`
is false (5.1), every restore clause is dropped exactly as for case C ("Resume to finish it, or restore the earlier
details." becomes "Resume to finish it."; "You can restore the earlier details to use them again." and "Restore the
earlier details to use them again." are dropped, and the too-long text then ends "Shorten the document and upload it
again."), and nothing else changes: a save of those details is then an update (2.5), and no text promises it brings the
earlier codes back. Where that drops the refused-before row's only way forward, the row offers none: such an update
cannot finish for those details on that encounter (7.3's stated limit) [R3:binding-R3B-4].

**Check texts** [R3:binding-R3B-3]. When no save started the update (`update.kind` `check`, A21: an operator's
reconciliation released the earlier codes' own unknown document review while a reading was owed), no text names a change
of the member's: the title reads "Updating codes"; every update text of 5.1, 5.3 and this section drops "Your change is
saved" ("Your change is saved, but the codes could not be updated: …" reads "The codes could not be updated: …"; "Your
change is saved. Updating the codes is paused …" reads "Updating the codes is paused …"); "from before your change" and
"from before your latest change" read "from before this update", and "after your change" is dropped ("The codes are
being updated."); and no restore clause is offered (`update.restorable` is false: the saved details are the earlier
codes' own, so there is nothing to restore). 3c words them; the customer scan covers them.

### 7.2 Retry

**The reading (D11; v1's FINAL 11.3, as the code cites it; FINAL-V2 7.5).** `jobs.retry_reading` is unchanged in kind: one
recorded attempt, keyed
`interpret:...:retry-release:<run>` (or `:retry:<run>` when it releases nothing), audited `interpretation.retry`. 5b extends
`jobs.retry_target` to the appraisal runs (pass 2: a retry re-sends pass 2 only). Added: refused with RETRY_NOTHING when the
encounter is fresh (nothing is owed). Its existing refusals stand: busy, read, unknown outcome, paused, too long, unbuilt.

**The document review (A10).** New `jobs.retry_update(encounter, user)` and `POST /api/encounters/<id>/retry-update`
(owners and reviewers), under the row lock, refused while busy or fresh. When the latest target job is a FAILED predict whose
run — or, for a not-resent run, the failed run `jobs._failed_before` finds for the same request — was sent and failed with
an HTTP status other than 401, 402, 403 or 429 (a 5xx, another 4xx, or no status: a definite transport failure), and no
release of it exists:

- a predict is queued for the current context under `predict:<context>:retry-release:<run>`, audited `update.retry` with
  the run id;
- `jobs._failed_before` skips, for purpose `primary` only, a failed run for which a job whose key contains
  `:retry-release:<run>` exists. One release is one attempt: if the attempt fails, its own new failed run is not released,
  and the door holds the request again until the member asks again.

When the latest target job is a FAILED predict whose run is NOT_SENT carrying its request for a local reason (7.1's
not-sent row) [R:legacy-L5], a predict is queued under `predict:<context>:retry:<run>`, audited `update.retry`: nothing
reached the vendor, so no release is needed and the failed-before door (sent runs only) does not hold it.

Never retried by a member: every refusal 7.3's classification holds (A20) — 401, 403 (the installation's credentials),
402 and 429 (payment and quota) from the coding service, and any 4xx from its token endpoint [R2:truth-RT1], read by
the status whether or not a `ProviderHold` row names the run [R3:binding-R3B-4]. Recorded from the install on, they set
Corti's provider hold (7.3), which an operator releases; then Resume sends once [R:races-R2][R:legacy-L2]. One recorded
before the install, which no row names, stays held against its identical request by `_failed_before` and is never sent
again for that encounter: an update that meets it ends failed with 7.1's refused-before row, and `retry_update` refuses
it [R3:binding-R3B-4][R3:truth-R3T-6]. A token
endpoint's 5xx, redirect, unreadable answer or missing token is the local not-sent class, retried under
`predict:<context>:retry:<run>` [R2:truth-RT1]. An UNKNOWN outcome is reconciled, never retried. `retry_update`'s
refusals, each a customer
sentence in `customer_api.KNOWN_ERRORS`: `jobs.RETRY_BUSY` (unchanged); `jobs.RETRY_UNKNOWN` "An earlier request has an
unknown outcome; it is reconciled before anything is tried again." (unchanged wording: an outcome is unknown and not
reconciled, `review._unreconciled_unknown`, as after 7.3's fallback for an outcome whose record failed)
[R3:binding-R3B-1]; RETRY_UPDATE_NOTHING "There is no failed update
to try again." (fresh, or the latest target job did not fail); RETRY_UPDATE_HELD "Updating the codes is paused on this
installation; resume once the coding service is available again." (a provider hold on Corti stands) [R:races-R2];
RETRY_UPDATE_READING "This update failed while reading the document; use Try reading again." (a failed interpret or
appraise, which `retry_reading` serves); RETRY_UPDATE_REFUSED_BEFORE "The coding service refused this same request
before, so it is not sent again." (the latest target job is a FAILED predict whose not-resent run's failed run carries
401, 402, 403 or 429 and no `ProviderHold` row names it: 7.1's refused-before row) [R3:binding-R3B-4][R3:truth-R3T-6].
A released attempt that fails again with another status leaves a new failed run,
which the member's next Retry may release once more: every send is one recorded member act, never an automatic one (D11).

**A stage that sends nothing** (analyze, assess, FAILED): `retry_update` queues the same stage, context and run under its own
key plus `:resume:<uuid>` (the form `jobs.resume` uses and `jobs._analyze_inventory_id` already strips), audited
`update.retry`. Nothing is sent by that stage; whatever it queues meets every door.

**During an update, a document review that is not E's and did not succeed ends the update (A6).** `jobs.stage_predict`,
while an update is pending — an exhaustive list: every outcome the stage can reach is named [R:legacy-L5]:

- **the provider hold first** (7.3) [R:races-R2][R:legacy-L2]: when Corti's hold stands, the stage records a not-sent
  run with `scope.held = 'provider_hold'` after the reuse door and before the send, and ends CANCELLED with the paused text
  (resumable); a run that **sets** the hold (7.3's classification, A20 [R2:truth-RT1]: HTTP 401, 402, 403 or 429 from
  the coding service, or any 4xx from its token endpoint) ends the stage the same way, never FAILED, whatever the rules
  below would say of it;
- a run that SUCCEEDED or was reused, and the member date conflict's hold, go on as today (`next_assess`);
- **E's own outcome** [R:legacy-L4]: a run whose request is byte-identical to the request of E's own run
  (`E.provider_run.request_sha256`, same provider and adapter) — a not-resent run the failed-before door recorded for it,
  or a NOT_SENT or FAILED run of it — or a request that cannot be built when E's own run is also one that could not build
  one, for the same revision text: goes on (`next_assess`). The review's input is unchanged since E, so the update's
  final is no worse than E (A6). Nothing is re-sent for a request E's run sent and that failed (the failed-before door);
  one E's run never sent (a local not-sent reason) is sent once, as its first attempt. On a legacy E this needs the
  v2-derived date to equal the date E's run carried; otherwise the request is new and the rules below apply to it;
- an UNKNOWN run: the stage queues nothing; the encounter reads provider_unknown through the unknown-outcome block;
- the coding service disabled (`get_provider()` is None) with a request the run in use does not answer: StageCancelled with
  the paused text (resumable);
- **every other outcome** — a FAILED run (a 5xx, another 4xx, a transport failure), a not-resent run of a request that is
  not E's, a NOT_SENT run carrying its request for a local reason (an unreadable credentials file, no HTTP session, the
  service unreachable, the deadline before sending, a token endpoint's 5xx, redirect, unreadable answer or missing token:
  7.1's not-sent row [R2:truth-RT1]), or a not-sent run that carries no request (`ProviderUnavailable`)
  when E's could be built: the stage ends FAILED (`StageFailure`), queueing nothing; `review._failed_stage_state` reads
  the run (provider_failed, run), unchanged. (The pre-refutation list named FAILED, not-resent and unbuilt runs only, so a
  NOT_SENT run carrying its request — Corti's token refusal among them — went on as today: the update's final was made
  with no document review and replaced the earlier codes, clearing their approvals, the outcome this rule exists to
  prevent.)

So a transient failure of the document review never replaces the earlier codes with an assessment that has none when E
had one, and never clears the approvals on them. During a first processing, `stage_predict` is unchanged, except that
Corti's provider hold is read at its send door as everywhere, and a run that sets the hold ends the stage CANCELLED,
paused and resumable, as a held one does — never a final made with the refused run (7.3) [R2:truth-RT6], nor through a
save made while it is paused, which queues the predict instead of re-checking with that run (2.2)
[R3:binding-R3B-5][R3:truth-R3T-4]. The stale path
settles a predict's finished run by these same rules (3.7) [R2:binding-R2B-6].

### 7.3 Quota, authentication and payment: the hold, with no repeated requests

The interpreter's hold is FINAL-V2 7.4's and D11/D39's, read by `interpretation.adapter.classify` alone:

| response | effect |
|---|---|
| ErrorInfo or `error.status` `API_KEY_INVALID`, `API_KEY_EXPIRED`, `UNAUTHENTICATED`, or HTTP 401 | hold (auth) |
| `BILLING_DISABLED` | hold (quota): a payment failure |
| `API_KEY_SERVICE_BLOCKED`, `SERVICE_DISABLED`, `PERMISSION_DENIED`, `FAILED_PRECONDITION`, or HTTP 403 | hold (permission) |
| 429 or `RESOURCE_EXHAUSTED` with no QuotaFailure (the monthly spending cap, measured 2026-11-10, D39) | hold (quota): a payment failure |
| 429 whose violations name a daily, zero, free-tier or unnamed window | hold (quota) |
| HTTP 402 (A11: added to `adapter.HOLD_STATUSES` as quota; fail-closed, since Google is not documented to send it) | hold (quota): a payment failure |
| an answer naming another model (P-5) | hold (model) |
| 429 whose every violation is a per-minute paid-tier quota with a limit above 0 | FAILED: the retry door |

While a hold stands, no Gemini request of either pass is built for sending, installation-wide: every update's reading
pauses (3.8), no retry is offered (`RETRY_PAUSED`), and an operator's recorded release ends it. The answer that set the hold
is not sent again while it stands; after the release the next member act sends it once (3.8) [R:legacy-L9]. Saves while
paused send nothing.

**The provider hold: Corti, Astra and Fable (A16)** [R:races-R2][R:legacy-L2]. The pre-refutation text kept these three
without a hold as a "stated limit": an identical failed request was never re-sent, but any other request was. That
contradicted the owner ("Handle quota and payment failures without repeated requests") and D184 ("quota, authentication
and payment failures hold without repeated requests"), and the automatic recheck is exactly what produces the other
requests: after a Corti 402, the member following the refused text's own advice to change the date made a new request
that was sent and refused again; every other encounter's update sent too; and a token refusal is recorded NOT_SENT, which
the failed-before door (sent runs only) never holds, so every save re-posted the credentials. The rule now:

| a run of | sets that provider's hold when |
|---|---|
| Corti (`corti`, and its replay) | the coding service answered HTTP 401 or 403 (credentials, permission), 402 (payment) or 429 (quota; Corti's 429s are not classified finer, so fail-closed), or its token endpoint answered any 4xx [R2:truth-RT1] (reason `quota` for 402 and 429, `permission` for 403, `auth` for every other: the token request carries only the installation's credentials and is the same for every encounter, so no 4xx of it is request-specific): the adapter records that status on its not-sent run (`http_status`, `sent` False), so the hold reads a field, never the error text. The token endpoint's 5xx or redirect, an answer that cannot be read or carries no usable token, and a transport failure set no hold: they are the local not-sent class (7.1), retried without a release |
| Astra, Fable (their own adapters) | a sent exchange of the run answered any 4xx but 413 [R2:binding-R2B-2] (reason `auth` for 401, `permission` for 403, `quota` for 402 and 429, `refused` for any other). Fail-closed: a vendor's payment refusal may arrive under another status (Anthropic has answered an exhausted credit balance with HTTP 400 `invalid_request_error`; D39 records Gemini's spend cap read as a rate limit), and the repository has measured neither participant vendor's refusals. A 413, the request's own size, fails only that request (I10). The participants' loop records each exchange's status |

**One classification** (A20) [R2:truth-RT1]. The table above is the only statement of which refusals set a hold; 7.1's
held and not-sent rows, 7.2's list and its retry paragraph, A10 and U12/U20 refer to it. (The revision stated it four
times and two disagreed: the table held a token refusal only on 401 or 403 while 7.1 and 7.2 held "a token refusal", so a
token 429 or 402 was either neither held nor explained — the stage ended FAILED reading "could not be reached", and every
save, every other encounter and a member's Retry re-posted the credentials — or, read the other way, a token 5xx paused
every encounter until an operator acted.)

**Where the hold is recorded** (A20) [R2:binding-R2B-1]. `jobs._send` records it from the outcome it records, in the
same transaction: with Corti's run outcome (`_finish_run`), and with a participant exchange's record
(`_record_exchange`, and `_finish_loop` for the exchanges it records), whatever the stage's state — a first processing,
an update, a stage superseded while it sent (3.5), or one whose worker dies right after. On that path no status the
table holds is ever committed without its hold. (The revision named no writer outside 7.2's list for an update, and
`_send` commits the outcome before the stage decides: a worker killed between the two, by an OOM kill or a host reset —
the class D53 closed for the interpreter — left a refusal with no hold, the stale sweep then queued the chain on (3.7),
and the next encounter's request was sent and refused again.) An outcome whose full record fails is settled by
`_settle_unrecorded` with small fields only, and they include its HTTP status [R3:binding-R3B-1]. A run whose exchange
carries a status the table holds — a coding-service refusal, or a token-endpoint 4xx on a not-sent exchange — is
recorded unknown whatever `sent` says, so the unknown-outcome block holds its encounter, no member's Retry is offered
("An UNKNOWN outcome is reconciled, never retried", 7.2), and the one attempt `jobs.reconcile` releases meets the hold
door; its hold is recorded from those fields right after, in a transaction of its own, so every other encounter is held.
Any other not-sent exchange is recorded not sent, as today (the local not-sent class, 7.1). (`_settle_unrecorded`
recorded every not-sent exchange not sent, with no status: a token refusal whose record failed had no hold, read as
7.1's local not-sent row, and the member's "Try updating again" and every other encounter's predict posted the refused
credentials again; a coding refusal's unknown run blocked only its own encounter while every other one sent once more.)
Only when the hold's own write fails as well can another encounter send one more request of that provider before an
operator acts: the limit a worker killed between the answer and its record already has (3.7).

- **Shape.** `ProviderHold` and `ProviderHoldRelease`, beside `InterpreterHold` and shaped like it: append-only, a hold
  stands until a release names it; the hold names its provider, reason (`auth`, `permission`, `quota`, and for a
  participant `refused` [R2:binding-R2B-2]), HTTP status and run; installation-wide, so it names no workspace. One run
  sets at most one hold, and a reuse of a run sets none. An
  operator (an operator grant, as `interpreter_hold`) releases every standing hold of one provider with `manage.py
  provider_hold --release <provider> --note "…"`.
- **Every send door reads it**, after the reuse door (a stored answer is still reused: a reuse sends nothing) and before
  the send (`_live_gate`, `_send`; for Corti the request is built first, as today, for the reuse door's lookup):
  `stage_predict`, `stage_participant`, `stage_peer`, `stage_review2`, and the second review's offer
  (`_second_review_bounds` refuses while Corti's hold stands). While it stands the door records a not-sent run with
  `scope.held = 'provider_hold'` and sends nothing, for every encounter: an upload, an addendum, a save, a Resume or a
  Retry alike. A held run carries `scope.held`, so `jobs._run_in_use` and `jobs._unsent_attempt` leave it out, as they
  leave out the member date conflict's hold: it is never the outcome of a request.
- **What a held stage does.** Corti held: the predict ends CANCELLED with the paused text (resumable): during an update the
  update reads paused (7.1's held row); during a first processing the document reads paused, as for the interpreter hold
  (`progress` gains `provider_paused`, the analogue of `interpreter_paused`, which also reads the standing hold: once an
  operator has released it the stage reads stopped by the system, with Resume [R3:truth-R3T-7]), with its own text,
  PROVIDER_PAUSED (7.1's header) [R2:truth-RT6]. The predict whose own request sets the hold ends the same way, in a
  first processing as during an update [R2:truth-RT6], as the interpreter's own hold-setting answer does
  (`jobs._settle_interpretation`): never a final made with the refused run, which read "could not complete its review ...
  You can upload the document again." with no Resume, while every later upload paused with one, and after the release
  could not be resumed — nor through a save made while the document is paused, which queues the predict rather than
  re-checking with the refused run (2.2) [R3:binding-R3B-5][R3:truth-R3T-4]. A participant held:
  its stage records the held run and the chain goes on without it (HARNESS I10), so the update completes partial (7.1).
  While a participant's hold stands every chain goes on without it, as after its failure; a request-specific 4xx that
  A20 holds fail-closed costs that participant's checks on every encounter until an operator's release, the stated
  price of never repeating a refused request [R2:binding-R2B-2].
- **After the release.** A run that set a provider hold — a run a `ProviderHold` row names, never one classified by its
  status alone [R2:truth-RT2] — is never held against its own request by `jobs._failed_before` or the participants'
  attempted-before door (as `_interpretation_failed_before` leaves hold effects out): while the hold stands the hold keeps
  the request unsent; after the operator's release the next member act (Resume, or a save that queues the stage) sends it
  once. Refused again, it sets a new hold. So after an authentication, permission, payment or quota refusal recorded from
  the install on, no provider request of that provider is sent by anyone until an operator acts, and then one is.
- **Refusals recorded before the install** [R2:truth-RT2]. A Corti or participant run the installed release recorded
  FAILED with 401, 402, 403 or 429 has no `ProviderHold` row, so `_failed_before` keeps holding its identical request in
  its encounter exactly as today (read by status, the door would have released every such refusal with no operator's act:
  a legacy encounter's first edit re-sent E's refused request). An update that meets one — a not-resent run whose failed
  run is such a refusal, of a request that is not E's own (E's own goes on with E's outcome, 7.2) — ends failed with
  7.1's refused-before row: nothing is sent, no Retry is offered (`retry_update` refuses with RETRY_UPDATE_REFUSED_BEFORE:
  a member's retry reads the status, never the hold row, A10), and the earlier details restore the earlier codes where
  A19 allows; the text does not suggest other details or a new upload, which would make a new request to a service that
  refused this one [R3:binding-R3B-4][R3:truth-R3T-6]. (The second revision
  held such a request and named no state for the update: no 7.1 row described it, "Try updating again" was offered and
  refused with "There is no failed update to try again.", and 7.2 promised a hold and a Resume that no release could
  give.) **Stated limits:** no operator act releases such a refusal (no `ProviderHold` row names it), so that update
  cannot finish for those details on that encounter, as today; and the installed adapter recorded a token refusal as not
  sent with no status (only its own sentence carries it), which no door holds and A20 cannot classify from
  fields; such a request is sent once after the install, as any request is after a release, and a refusal again sets the
  hold, so at most one is sent per provider before an operator acts. 9.5 counts both classes for the owner.
- `retry_update` is refused while Corti's hold stands (RETRY_UPDATE_HELD, 7.2); A10 never releases those statuses.
- The refused text no longer tells the member to change the date of service or add documentation: those make new
  requests, which the hold now keeps unsent, and recommending them invited the repeated requests the owner forbade.

### 7.4 Unknown outcomes

Unchanged: an outcome that may have reached the vendor is UNKNOWN; every send of the encounter waits on its reconciliation
(`review._unreconciled_unknown`); an operator reconciles it at `/ops/` (`jobs.reconcile`), which queues one attempt — the
interpret stage `:after-reconcile:<run>` while a reading is owed (P-6 settles the run from its recorded exchange first,
sending nothing), else a predict for the current context `:after-reconcile:<run>`. Added: the attempt is for the saved
state (the current context and values), so a reconciliation during an update continues the update.

**A reconciliation of fresh codes' own unknown while a reading is owed** (A21) [R3:binding-R3B-3]. On a legacy encounter
(a context that is not a gemini context) or a v2 revision whose inventory is of an older version, the codes can be fresh
by rows while their own document review is UNKNOWN (a read cut off before the install, or after it). The attempt the
reconciliation releases is then the reading (`jobs.reconcile` queues the interpret whenever a reading is owed; on a
context that is not a gemini context nothing else can be sent, `jobs._earlier_reading`), and 3.4 superseded it at its
start as restored (the codes were fresh), so nothing was sent and the codes stayed, reading
provider_unknown ("being confirmed") with the outcome reconciled, nothing pending, `jobs.reconcile` refusing the run a
second time, no Resume and no Retry; the same when a save and a restore came before the reconciliation. Under A21 the
release itself makes those codes not fresh (vocabulary), so the reading is a target job of an update of them: it is not
superseded, the encounter reads "Updating codes" (kind `check`, 5.1, 7.1) with those codes as the earlier codes,
read-only, its analyze records them as the new context's earlier assessment, its predict sends the released attempt, and
its final replaces them with "what changed" against them. A participant's reconciliation there releases no such state
(the codes' own document review stands): its reading ends superseded as before, and the codes stand without that
participant's check, as after its failure (I10). On a v2 revision at the current versions nothing changes: the
reconciliation's predict runs on the current context as a chain re-run (4.5).

### 7.5 TOO_LONG

A document over the size bound never reaches an update (A12), and neither does an addendum that would take a document over
it: it is refused before it is recorded (1.4) [R:truth-T7]. An answer cut off at its output limit, or a pass-2 claim set
over its bound, ends the update failed with the too-long text (7.1). No member retry (C5); an operator's recorded override
stays at `/ops/` (`operator.retry_reading`). Within one revision (cases A and B), restoring the earlier details makes the
earlier codes current again with nothing sent (2.5), where A19 allows it [R2:binding-R2B-4][R2:binding-R2B-5]; after an
addendum (case C) there is none, and the text says to upload
the document again (7.1) [R:truth-T7]. A live document reaching the claim bound is reported to the owner (FINAL-V2 7.5,
class b).

---

## 8. Exports

### 8.1 Creating an export

- **While an update is pending:** `api.py:create_report` answers 409 UPDATE_EXPORT before `reports.generate_customer`, for
  both kinds; `reports.customer_snapshot` refuses again under the encounter lock (a save between the request's read and the
  lock), raising `CustomerExportNotReady([UPDATE_BLOCKER])`. `customer_api.readiness` returns `draft: false, approved: false`
  with the customer blocker. No artifact is written.
- **After the update:** unchanged rules (`customer_api.readiness`, `reports.customer_snapshot`), over the fresh assessment.
- **During a first processing:** unchanged while no save made its shown codes stale. A save during a first processing
  after its assess #1 was shown (current, not final) makes an update pending (vocabulary, 4.5) [R:truth-T8], and so does
  an addendum then (kind `documentation`) [R3:truth-R3T-5]: the draft of those earlier codes is refused like any other
  export of earlier codes, and a draft made before the save or the addendum is listed as earlier (8.3). (The
  pre-refutation text left that state as "a first processing": the old codes stayed the page's codes under "Processing
  your document", draft-exportable, and a draft made then was listed current until the new assessment landed.)

### 8.2 What every new export states (format @2)

`reports.CUSTOMER_FORMAT` becomes `cpt-studio-customer-report@2`. The snapshot reads the **assessment's own** revision and
context, never the encounter's current context (today `date_of_service` comes from `answers.service_date_block(encounter)`,
which a later save changes):

- TXT, after "Encounter: ...": `Document: revision {n}`; `Details used: date of service {date or "not documented"};
  place of service {..}; patient {..}; claim {..}`; `Codes made: {assessment created_at}`. "Date of service" is read from
  the assessment's context.
- CSV: three columns appended after `review_label`: `revision_number`, `details_used`, `codes_made_at`, on every row.
- The marker stays `reports.customer_marker` (the assessment, the context, the current decisions, the standing answers).
  It never gains the member values [R:truth-T1]: every stored artifact's `snapshot_sha256` was computed without them, so
  adding them would make every export made before the install non-current at once. Currency gains the update instead
  (8.3).

### 8.3 Downloading

`api.py:download_report`, for a customer artifact of the caller's workspace (membership checked as today):

- **current** (`reports.customer_artifact_current`): served as stored, unchanged. **Current now means: its marker digest
  equals the encounter's AND no update is pending** (`review.update_pending`), in `reports.customer_artifact_current`,
  `customer_api._reports` and so `api.py:download_report` alike [R:races-R1][R:truth-T1][R:legacy-L1]. A case-B save
  (a legacy revision, or a v2 revision whose inventory is of an older version) stores the values and keeps the context,
  the assessment, the decisions and the answers, so the marker alone stayed byte-identical: the pre-refutation design
  listed and served the pre-save approved export as current, with no banner, for the whole update and indefinitely after
  a failure, a hold or a Stop — the stale codes exported as current while the panel said they could not be. With the
  update in the test, every export made before the save is earlier for exactly as long as the update is pending, and a
  restore (fresh again, the marker unchanged) makes it current again by itself;
- **not current** (any kind, any format, @1 included): served as an **earlier export**, built by
  `reports.earlier_download(report)`:
  - TXT: two lines before the stored bytes — `EARLIER EXPORT — MAY NOT SHOW THE CURRENT CODES` and `Made {generated_at}
    on revision {n}. This document has changed since (its details, its documentation, its codes or its decisions); create
    a new export for the current codes.` — then a blank line [R:truth-T14] (a marker also differs when only the details
    changed and every code and decision carried, so the banner never claims the codes or decisions changed);
  - CSV: one row inserted after the header row, whose `report_format` cell carries the same two sentences and whose other
    cells are empty (the stored file's header is its first line: `reports.render_customer_csv`);
  - the download filename is the stored one with `-earlier` before the extension;
  - the revision number is the artifact's assessment's (`report.assessment.revision.number`), so a @1 artifact, whose body
    names no revision, is still marked.

  The stored artifact is never changed: `ReportArtifact` is immutable, its `sha256` still describes its stored bytes, and an
  operator's `/ops/` download serves those bytes exactly. Today a non-current approved artifact answers 409
  (`customer_api.STALE_EXPORT`); A9 reverses that for customers because the owner asks for historical reports to be
  preserved, and the banner keeps it from being presented as current.
- A download that races a save (the check reads `customer_artifact_current` without the lock) may serve as current an
  export made a moment before the save. The file states its revision, details and time (8.2), so it still says what it
  describes. This is the only window: once the save commits, the update is pending and the export is earlier
  [R:races-R1][R:truth-T1].

### 8.4 Operator reports

Unchanged. The operator snapshot already states the revision (`reports._revision`) and the context with its values
(`reports._context`); operators may make one while an update runs, as a diagnostic.

---

## 9. Legacy encounters

### 9.1 The first reading after an edit

A legacy encounter is one the installed release `c2e53f8e` assessed: a legacy context (`gi-context@4` or `@5`), a legacy
assessment, no `EventInventory`. Nothing about it changes at the install (D16). Its first coding-context save:

1. is checked against A12 (size bound, framing) and stored (case B, 2.3); the legacy assessment becomes the earlier codes;
2. queues interpret (pass 1), then appraise (pass 2), with their doors: the first time, both send;
3. analyze derives the first gemini context with the newest saved values, recording the legacy assessment as its earlier
   assessment (4.5);
4. predict: Corti's request carries the v2-derived date (D2), so it is sent when that date's request has no stored answer;
5. the first readings are reused (their request is the revision); the peer reviews are asked again (the reading they are
   shown is new, D9);
6. assess #2 becomes current only through 4.1; the legacy decisions are cleared (D7) and listed (6.5). Assess #1, which
   owes the peer stages, is recorded but never current (A17): the legacy assessment stays the current one, with its
   decisions and its open questions untouched, until assess #2 [R:legacy-L6].

Every later save on that encounter is case A: no Gemini call. Rapid saves before analyze coalesce into one reading (3.3).
A restore at any point before assess #2 — before the reading, after it, while the peer reviews run, or after a Stop of
them — makes the legacy codes current again (2.5) with nothing more sent and every legacy decision intact
[R:races-R3][R:legacy-L6], where A19 allows it (the legacy assessment reads no answer the member has since replaced, and
its document review is no unknown outcome a reconciliation released) [R2:binding-R2B-4][R2:binding-R2B-5]. An
operator's reconciliation of the legacy codes' own unknown document review starts their first update with no save (A21,
kind `check`): the same reading, analyze and chain as the first save's, with no change of the member's named
[R3:binding-R3B-3].

### 9.2 Its cost

| item | per encounter, first edit |
|---|---|
| Gemini, both passes (FINAL-V2 7.1, F1 1.0) | median about $0.083, mean about $0.118, p90 about $0.174 at November prices; median about $0.166, mean about $0.236 from 2026-12-01; the largest document about $0.468 (November) |
| Corti | zero or one request, at its per-request cost as today (the operator report's usage per run) |
| Astra, Fable | no first reading; one peer review each when configured, at their per-request cost as today (`review.estimated_cost`) |
| latency | both passes median about 53 s, p90 about 138 s (FINAL-V2 7.2), plus the chain |

Each run records its usage and `usage_basis` (FINAL-V2 7.4); the operator report sums them per encounter, so the actual cost
of every update is visible, and the session's usage ledger (D183) records the walk's.

### 9.3 Legacy approvals and reports as records

6.5 and 5.4: the legacy decisions are cleared by the first update's final and kept as rows, listed in Earlier decisions,
and named in "what changed". The legacy exports (customer format @1) stay in Earlier downloads and download with the EARLIER
banner (8.3). The legacy assessment stays, immutable, as the base of "what changed".

### 9.4 The rollback image (FINAL-V2 6.4)

The old image knows neither `EventInventory`, `appraise`, nor `EncounterContext.earlier_assessment`; it ignores the new
column and leaves it NULL in any context it writes. It reads a v2 assessment fail-closed (FINAL-V2 6.4). For a legacy
encounter with a v2 update, at a switch-back:

| state at the switch | what the old image shows |
|---|---|
| **pending, before analyze** (values saved, the legacy context and legacy assessment current, a reading stage open) | the undo closes the open interpret or appraise stage (`ops/install.py` CLOSE_STAGES, which FINAL-V2 6.4 extends to `appraise`), as FINAL-V2 6.4 and v1's FINAL 12 already accept for an open interpret stage; how the old image words that closed stage is its own. Its codes are the legacy ones, on the current context, so it shows them **approvable and exportable**: it has no update concept, and its date block reads the legacy context's values. **The undo also reverts the unapplied save** [R:legacy-L7]: in the same step that closes the stages, under each encounter's row lock, it sets `Encounter.user_values` to the current (legacy) context's member values, writes one `context.rollback_reverted` audit row per encounter naming the fields, and its answer (the operator's transcript, synthetic data only) names each encounter with each reverted field's saved and restored values; the switch-back note lists them so the operator tells the member to save the change again on the old image. Reason: the old image's details panel shows the context's values while its `answers.save_details` compares a save with `Encounter.user_values`, so re-entering the pending value there was "unchanged" and silently not saved, and a save of another field applied the hidden value unannounced; the pre-refutation text relied on "the old image's next context save", which fails for the save a member is most likely to make. After the revert the old image's own save path applies a re-entered value (a legacy context through its legacy reader) |
| **pending, after analyze** (a gemini context current, the legacy assessment on the earlier context) | by this tree's `review.readiness` and `review._allowed`, which the old image's predate: the approved export is blocked ("The encounter context changed; re-assessment has not finished"), while per-code approval and the draft export do not check the context. U17 measures what the old image actually shows |
| **completed** (a v2 assessment current, legacy decisions cleared) | the v2 codes, read fail-closed (FINAL-V2 6.4: held stays held, READY stays approvable); the cleared legacy decisions as invalidated rows |

The first two are a stated rollback limit, as D59's `reinstatable` limit is: v2's undo answer names such encounters with a
new hazard reason `update_pending` (an encounter whose `values(encounter)` differs from `values(current context)`, or whose
current assessment is not on its current context, or whose current assessment's own document review is an UNKNOWN run
already reconciled while a reading is owed: A21's update, which no save started [R3:binding-R3B-3]), and the switch-back
note lists them; for the last, the old image is expected to read the reconciled run as an outcome still being confirmed,
with nothing pending (as this tree read it before A21), and the note tells the operator so. For the first row the undo
reverts the unapplied values and names them (above), so the old image is consistent and the member saves the change
again there [R:legacy-L7]; for the second the old image shows the legacy codes as U17 measures, and the note tells the
operator which encounters' members to warn that the codes shown predate their change. The hazard is reported, never a
refusal of the switch-back (a rollback is the incident path). A v2 encounter with a pending update reads like the second
row. (An update's assess #1 is never current, A17, so the old image never reads a v2 assess #1 as an encounter's codes.)

### 9.5 Install-time checks (6b)

Read-only, on the target, before the switch, printed into the install transcript:

- the count of live encounters whose current revision has no inventory and is over `INTERPRET_MAX_CHARS` or
  `INTERPRET_MAX_PAGES` (expected 0 for characters: D25), and the count of those whose text fails the pure framing check
  (FINAL-V2 1.2 rule 8's `[S\d+]` refusal, A12's SAVE_UNPREPARED) [R:legacy-L8]. A non-zero count is reported to the
  owner before the install (class b: their details could not be changed after the install, A12). The same report states
  that an addendum which would take a document over the character bound, or whose text cannot be framed, is refused
  before it is recorded (A12, 1.4), with the live maximum length measured on the target (19,398 characters at D25), so the
  owner sees how little room the longest documents have [R:truth-T7];
- the count of encounters that have a current context of their current revision and whose `values(encounter)` differs
  from `values(current context)` [R:legacy-L3]. It is printed on every install and **never stops one**: after v2 has run,
  a case-B update leaves exactly this state by design (pending, paused under a hold, failed and not retried, or stopped)
  for as long as it lasts, and refusing on it would refuse a fix release, the re-install after a switch-back and a
  same-revision `app` re-run (the provider-mode switch of D83, an incident's recovery): FINAL-V2 6.2's MO-1 defect, and
  the shape `ops/install.py` already records as wrong (round-7c8 skeptic, sk:2). Encounters with no current context (an
  upload whose extraction or analysis failed on `c2e53f8e`, which stored its date in `Encounter.user_values` and recorded
  no context) are outside the count: they have no earlier codes and read no update. On the first install over
  `c2e53f8e` (no v2 row exists: no gemini context, no `EventInventory` row of a v2 version) the count is expected 0, and a
  non-zero one is reported to the owner before the switch, with the encounter ids, as the first count is: those
  encounters would read an update pending that no save queued (idle-owed: stopped, with Resume).
- the count of provider refusals recorded before the install, which no `ProviderHold` row names [R2:truth-RT2]: Corti and
  participant runs FAILED and sent with 401, 402, 403 or 429 (a participant's with any exchange A20 holds), and Corti runs
  recorded not sent with the installed adapter's token-refusal sentence ("Corti authentication was refused (HTTP …"),
  each with its newest date. Printed, never a refusal, and reported to the owner with the class-b counts: the first stay
  held against their identical request as today, the second are sent once after the install (7.3's stated limit). The
  report says what an edit meets there [R3:binding-R3B-4][R3:truth-R3T-6]: an update whose request is one of the first
  ends failed with 7.1's refused-before text and cannot finish for those details on that encounter;
- the count of encounters whose current assessment's own document review is an UNKNOWN run already reconciled while a
  reading is owed (A21) [R3:binding-R3B-3]: from the install on they read an update that no save started (kind
  `check`). Expected 0, printed, never a refusal; a non-zero one is reported to the owner with the encounter ids, as the
  second count is.

---

## 10. Files and ownership

One owner per file (FINAL-V2 8.0). A step that needs a change in another step's file asks the integration owner, who applies
it serially.

| file | owner | what changes |
|---|---|---|
| `studio/models.py`, `studio/migrations/0015_inventory_appraisal.py` | **1d** STORE | `EncounterContext.earlier_assessment` (4.5) in migration 0015 beside `EventInventory.appraisal_run`; `ProviderHold` and `ProviderHoldRelease` (A16: CreateModel, shaped like `InterpreterHold` and its release, `reason` a plain column with no choices) [R:races-R2]; the migration test's additive verdict covers them |
| `studio/interpretation/adapter.py` | **3b** ADAPT | `HOLD_STATUSES[402] = QUOTA` (A11); its adapter test vector |
| `studio/provider_holds.py` (new) | **5b** PIPE | A16 [R:races-R2][R:legacy-L2]: what a Corti or participant run means for its provider (from recorded `http_status` and `sent` only, never error text), by A20's one classification (the token endpoint's any 4xx [R2:truth-RT1], a participant exchange's any 4xx but 413 [R2:binding-R2B-2]), `record` (called by `jobs._send` in the outcome's transaction [R2:binding-R2B-1], and by its fallback from the small fields `_settle_unrecorded` writes, in a transaction of its own [R3:binding-R3B-1]), `active(provider)` (read by `progress.provider_paused` too [R3:truth-R3T-7]), `release`, and the test of a hold-setting run (a `ProviderHold` row names it [R2:truth-RT2]); the held reason `provider_hold` |
| `studio/providers/corti.py` | **5b** PIPE (FINAL-V2 8.1 names no owner for it; the integration owner assigns it here) | its token endpoint's refusal status recorded on the not-sent exchange (`http_status`, `sent` False), so the hold reads a field [R:legacy-L2]; nothing else changes |
| `studio/management/commands/provider_hold.py` (new) | **6b** OPS | `--status`, `--release <provider> --note`, an operator grant as `interpreter_hold` [R:races-R2] |
| `studio/jobs.py` | **5b** PIPE | `change_context` (`ContextSave`), `_change_context` (A18's member-act refusal [R:races-R4]), `_save_on_inventory`, `_save_awaiting_reading` (replaces `_save_before_reading`; coalesces only with a QUEUED reading stage [R:races-R6]), `_decide_after_save` (E's own run [R:legacy-L4]), `record_derived_context(earlier=)`, `earlier_for_new_context` (T8's branch [R:truth-T8]), `_superseded` (under the row lock at the start and the successor gate [R:races-R6]) and `StageSuperseded`, the start checks of every stage, `_send`'s pre-reservation check, the successor gates, `stage_analyze` (4.2), `stage_assess` and `_assess_events` (start check, `Superseded`), `stage_predict` (7.2's exhaustive list, the provider hold [R:legacy-L4][R:legacy-L5]), the provider hold at `stage_participant`, `stage_peer` and `stage_review2` (A16), `_failed_before` (release, primary only; a hold-setting run left out [R:races-R2], a run a `ProviderHold` row names [R2:truth-RT2]), `_newest_assessment` (an abandoned unfinished assessment left out, 4.1 [R:races-R3]), `_second_review_bounds` (update pending, Corti's hold [R:truth-T15]), `run_job` (`StageSuperseded`), `mark_stale` (successor gate; a predict's finished run settled by 7.2's list and the provider hold, its `held` branch narrowed to the member date conflict [R2:binding-R2B-6]), `resume` (3.6), `retry_reading` (fresh refusal; appraise in `retry_target`), `retry_update` (new; RETRY_UPDATE_HELD, the not-sent retry [R:legacy-L5]); and `_send` (the provider hold recorded with the outcome [R2:binding-R2B-1]), `_save_awaiting_reading` (coalescing as a compare-and-set renewing `deadline_at`, never with `:settled:` [R2:binding-R2B-7]), `_change_context` (A19's restore conditions, and RESTORE_REFUSED for such a save in case B [R2:binding-R2B-4][R2:binding-R2B-5]), `stage_predict` (a first processing's hold-setting run pauses [R2:truth-RT6]), `earlier_for_new_context` (the second branch only off the current context [R2:binding-R2B-3]); and `_settle_unrecorded` (the HTTP status among its small fields; a status A20 holds recorded unknown whatever `sent` says, its hold recorded right after [R3:binding-R3B-1]), `_decide_after_save` and `reconcile`'s participant branch (never re-check with a run a `ProviderHold` row names, in a first processing too [R3:binding-R3B-5][R3:truth-R3T-4]), `retry_update` (RETRY_UPDATE_REFUSED_BEFORE; the release reads the status [R3:binding-R3B-4][R3:truth-R3T-6]), `_change_context` (A19's third condition [R3:binding-R3B-2]), `earlier_for_new_context` (T8's branch for any revision [R3:truth-R3T-5]) |
| `studio/review.py` | **5b** PIPE | `values`, `fresh` (A21's reconciled unknown while a reading is owed [R3:binding-R3B-3]), `earlier` (T8 [R:truth-T8]; the second branch only off the current context [R2:binding-R2B-3]; T8's branch for any revision [R3:truth-R3T-5]), `restorable` (A19 [R2:binding-R2B-4][R2:binding-R2B-5]; its third condition [R3:binding-R3B-2]), `update_pending`, `reading_owed`, `target_jobs`; `latest_job`, `_active_jobs`, `_state_and_run` (idle-owed), `can_resume`; `readiness` (UPDATE_BLOCKER); `_allowed`, `allowed_actions` (its `.only(...)` gains the context and values), `_record_decision` (UPDATE_DECISION); `Superseded`, `_check_inputs` (values check), `persist_assessment` (A17: an update's non-final assessment recorded, never current, withdrawing nothing [R:races-R3]); `confirm_finding` (reads `ContextSave.context`); `_failed_stage_state` for `appraise` (FINAL-V2 5b already) |
| `studio/progress.py` | **5b** PIPE | progress jobs for the steps and the times, target jobs for busy and the phase [R:truth-T2]; a step's activity from every progress job, its outcome from the attempts that served the saved state (a context stage only on the current context; the newest started attempt of each kind) [R2:truth-RT3][R3:truth-R3T-1][R3:truth-R3T-2]; phase `updating`; skipped steps; WAITING_FOR_EARLIER; `date_held` while the saved values are the context's [R:truth-T3]; `provider_paused` (A16) with PROVIDER_PAUSED in a first processing [R2:truth-RT6], only while Corti's hold stands [R3:truth-R3T-7]; UPDATE_ERRORS keys (worded by 3c); `STEP_OF`/`DETAILS` for `appraise` (FINAL-V2 5b already) |
| `studio/customer_api.py` | **3c** WORD (applied by the integration owner on 5d's request) | `encounter_json` keys `update` (with `kind`, `started_at`, `restorable` [R2:binding-R2B-4][R2:binding-R2B-5]; kind `check` and its null `saved_by` [R3:binding-R3B-3]; the fixed line for empty `changes` [R3:binding-R3B-6]), `earlier_codes`, `what_changed`, `decision_history`, and the other assessment-derived keys from `earlier` while pending [R:truth-T6]; `readiness` (the blocker by update state [R:truth-T4]); `customer_state` and `list_row` (T3) and `STATE_LABELS['updating'] = 'Updating codes'`; `_reports` (`revision`; current only with no update pending [R:races-R1]); `KNOWN_ERRORS` and `KNOWN_TEMPLATES` (UPDATE_DECISION, UPDATE_EXPORT, SAVE_TOO_LONG, SAVE_UNPREPARED, ADDENDUM_DUPLICATE, ADDENDUM_TOO_LONG, ADDENDUM_UNPREPARED, ADDENDUM_DOCUMENT_TOO_LONG and ADDENDUM_DOCUMENT_UNPREPARED [R2:truth-RT7], RESTORE_REFUSED [R2:binding-R2B-5], UPDATE_ANSWER_WITHDRAW, the retry_update refusals with RETRY_UPDATE_HELD and RETRY_UPDATE_REFUSED_BEFORE [R3:binding-R3B-4]); `BLOCKER_EXACT` (both UPDATE_BLOCKER texts, and their check forms [R3:binding-R3B-3]); the update texts of 7.1 with their case-C forms [R:truth-T7], their forms without a restore clause (`update.restorable` false [R2:binding-R2B-4]) and their check forms [R3:binding-R3B-3]; the refused-before row's sentence [R3:binding-R3B-4][R3:truth-R3T-6]; PROVIDER_PAUSED [R2:truth-RT6]; the not-sent row's sentence [R2:truth-RT1]; `what_changed` (6.2, steps 1-5 [R:truth-T9][R:truth-T11][R:truth-T14]; step 4's holder and fourth outcome [R2:binding-R2B-3][R2:truth-RT4], and its case-C range of revisions [R3:truth-R3T-3]; step 5's answered-before rule [R2:truth-RT5]); `decision_history` (5.4's same-details sentence [R:truth-T10]); the relabel of the earlier codes (A14) |
| `studio/interpretation/wording.py` | **3c** WORD | none |
| `studio/api.py` | **5d** UPDATE-UX (new) | `context` (200 unchanged, `updating`, `restored` [R:truth-T13]), `details` (`updating`, `restored`), `addenda` (A1, A13, A12's size and framing refusal [R:truth-T7], its sentence chosen by where the cause is [R2:truth-RT7]), `create_report` (8.1), `download_report` (8.3), `retry_update` (new view) |
| `cptstudio/urls.py` | **5d** | the `retry-update` route |
| `studio/answers.py` | **5d** | `_save_details`: the narrowed busy refusal (1.4), `updating`/`reassessing`/`restored` in its answer [R:truth-T13], `ContextSave.context`; `_revoke_answer`: refused while an update is pending [R:truth-T12]; `service_date_block`, `_rows`, `_date_row`: the saved values while a case-B update is pending [R:truth-T3] |
| `studio/reports.py` | **5d** | format @2 (8.2), the snapshot from the assessment's own context, the update refusal in `customer_snapshot`, `customer_artifact_current` (no update pending [R:races-R1][R:truth-T1][R:legacy-L1]), `earlier_download` (the banner's wording [R:truth-T14]) |
| `studio/client_contract.py` | **5d** | `VERSION` to a new build value (the payload gains keys) |
| `studio/static/studio/app.js` | **5d** | `PHASES`/`PHASE_TITLES`/`ANIMATED_PHASES`/`PANEL_PHASES`/`POLL_PHASES`/`LEAVE_NOTES` gain `updating` ("Changes saved—updating codes"; "Updating codes" for kind `check` [R3:binding-R3B-3]); the update titles of 7.1 by `update.kind` [R:truth-T7]; the fixed line in place of an empty saved-changes list [R3:binding-R3B-6]; the saved-changes list; the earlier codes section with the earlier assessment's other sections inside it [R:truth-T6]; `emptyResults`, `tallyText`, `reviewBar` for the update states [R:truth-T5], and for empty earlier codes [R2:truth-RT8]; the restore clauses by `update.restorable` [R2:binding-R2B-4]; the fourth what-changed outcome [R2:truth-RT4]; "What changed"; "Earlier decisions"; `detailRow`/`detailsPanel` (context rows editable while updating, answer rows not, Withdraw hidden while pending [R:truth-T12]); `exportOptions` (UPDATE_EXPORT_NOTE by state [R:truth-T4]) and `reportItem` (earlier downloads linked, labelled); `saveDetails`'s toast (`restored` [R:truth-T13]); `ERROR_ACTIONS.retry_update` ("Try updating again") and its handler; `CLIENT_VERSION` |
| `studio/static/studio/styles.css` | **5d** | the earlier-codes and what-changed styles (read it first) |
| `API.md`, `CORE-UX-DESIGN.md` section 7 | **5d** | the new keys, the routes, the texts |
| `ops/install.py`, `ops/verification/customer-contract.json`, `ops/verify_login.py`, `ops/scan_customer.py`, `ops/verify_browser.cjs` | **6b** OPS | the `update_pending` hazard and the undo's revert of a pending-before-analyze save (9.4 [R:legacy-L7]), the install counts of 9.5 (printed, never a refusal [R:legacy-L3]; the framing count [R:legacy-L8]; the pre-install refusal count [R2:truth-RT2]; A21's count [R3:binding-R3B-3]), the provider holds in the install transcript, the contract's new keys and vocabulary (`updating`, the update block), the client version, the differential check of 11.3, the rollback test rows of 11.2 |
| `tests/test_guard_matrix_new_path.py`, `tests/v2/test_properties.py` | **6a** GUARD | the new worlds of 11.1 (U15) |
| `tests/v2/test_update_pipeline.py`, `tests/v2/test_update_review.py` | **5b** | U1-U12, U16, U18-U20, U22 [R2:binding-R2B-3] |
| `tests/v2/test_update_customer.py` | **3c** | the texts, the scan, what-changed wording |
| `tests/v2/test_update_api.py`, `tests/v2/test_update_reports.py`, `tests/frontend/app.test.cjs` | **5d** | U13, U14, U21, the page |

**The new step 5d UPDATE-UX.** Depends on 5b and 3c. Done when: U2, U13, U14, U21 and the page tests pass; the customer
contract and the scan pass with the new keys; no customer string names a provider or model; the existing suites are green with
their tests updated where this amendment changes a pinned behaviour (named below). 5d merges after 5b and before 6a.

**Pinned behaviours this amendment changes** (their tests are updated by the step that owns the file):
`test_change_context_events.py::test_a_save_after_the_reading_ended_failed_is_refused_and_nothing_is_stored` (refused only
during a first processing now); any assertion in `test_cux_flow.py` of `answers.BUSY` for a save that carries only context
values (accepted now; its assertions for a save carrying an answer stand); the
409 of a non-current approved download (`STALE_EXPORT`, now served with the banner); `stage_analyze`'s commit outside the
lock; `persist_assessment`'s `ValueError` on a changed context (now `Superseded`, a skip); an update's assess #1 becoming
the current assessment (A17: recorded, never current, while an update is pending [R:races-R3]); a Corti or participant
request refused with 401, 402, 403 or 429 being held only against its identical request (`_failed_before`): now the
provider hold holds every request of that provider until a release, and the release lets the identical one go once
(A16 [R:races-R2]); `answers._save_details`'s `reassessing: bool(changed)` (now from the `ContextSave` [R:truth-T13]);
a participant 4xx other than 413 failing only its own request (now a hold, A20 [R2:binding-R2B-2]); `jobs.mark_stale`
queueing the assess after any finished predict run (now 7.2's rules and the provider hold [R2:binding-R2B-6]); a first
processing's final made with a Corti run that set the hold (now paused [R2:truth-RT6]); a save that coalesced with a
queued reading stage leaving its deadline as it was (now renewed [R2:binding-R2B-7]); `jobs._settle_unrecorded` recording
every not-sent exchange not sent with no status (now unknown, with its status and its hold, for a status A20 holds
[R3:binding-R3B-1]); `_decide_after_save` re-checking during a first processing with any run in use that answers the
request (now never with a run a `ProviderHold` row names [R3:binding-R3B-5][R3:truth-R3T-4]).

**FINAL-V2 text superseded or amended** (the adoption's DECISIONS entry records each):

| FINAL-V2 | status |
|---|---|
| 0, "What the refutation changed": "a legacy context save is an explicit re-check" | superseded by 2.3 and 9 |
| 1.1, INVENTORY_VERSION row: "a changed claim set needs a new pass-2 send, an explicit act for an existing record (6.2)" | amended: a coding-context save on such a revision queues it (D184); pass 1's stored answer is reused |
| 6.2, "Legacy encounters and context saves [R:MO-4]" (store the values, queue nothing, "Check again with the current reading", refuse a new approval or export until the re-check) | superseded by 2.3, 5.3, 6.5 and 9 |
| 6.2, "Older v2 inventory versions ... an explicit act and never a save's (D8)" | amended: a coding-context save on such a revision queues the reading at the current versions (case B) |
| 6.4 | extended by 9.4 (the `update_pending` hazard; the rollback test rows of 11.2) |
| 7.4, Stop and resume: "On a revision only the legacy reader read, a context save stores the values and sends nothing; the explicit re-check of 6.2 is the only way that revision is read again [R:MO-4]. (The pre-refutation sentence ...)" | superseded by 2.3: such a save queues the first stage the reading owes, at most one pass-1 and one pass-2 send per revision and version pair |
| 7.4, "Resume queues the first missing stage" | extended by 3.6 (analyze; the no-job case) |
| 7.5, the member-facing column | extended by 7.1 during an update |
| 8.1 step 5b, files: "`_change_context` on a revision with no v2 inventory stores the values and queues nothing, with the explicit re-check action of 6.2 [R:MO-4]" | superseded by section 10's 5b row |
| 8.1 step 5b, done when: "D8 (a save sends nothing, on a legacy revision too; a new approval of a legacy assessment whose context changed is refused until the re-check) [R:MO-4]" | superseded by: D8 on a revision with an inventory (a save sends nothing to Gemini); 11.1's U3-U12 green |
| 8.1 step 8: "the owner told ... the legacy context-save loss (class b, 6.2)" | closed by D184 |
| 9.3, pipeline: "D8" | amended by 11.1 |
| 9.9 | extended by 11.2 |
| 10, R24 | superseded: the risk is the first edit's cost and latency on a legacy encounter (9.2), stated, measured by the usage per run |
| D8 (v1): "A new Gemini request is made only for a new revision (upload, addendum), or by an explicit retry" | amended by D184: also the first coding-context save of a revision with no inventory at the current versions, once per revision and version pair |
| 4.12, "Corti, Astra and Fable unchanged" (their send discipline) | amended by A16: each has an installation-wide provider hold on an authentication, permission, payment or quota refusal, read by every send door, released by an operator (7.3) [R:races-R2][R:legacy-L2]; which refusals, and where the hold is recorded, by A20 [R2:truth-RT1][R2:binding-R2B-1][R2:binding-R2B-2] |
| (not FINAL-V2 text: HARNESS.md 12.1 as `review.persist_assessment` applies it) an assess #1 that owes peer stages becomes the current assessment | amended by A17 while an update is pending: recorded, never current, withdrawing nothing; unchanged during a first processing; the adoption's DECISIONS entry records it beside HARNESS.md [R:races-R3][R:legacy-L6] |

---

## 11. Tests and the walk

### 11.1 Unit tests (9.3 additions; text-only and synthetic, replay, no network)

Each runs on synthetic fixtures with the replay adapters, and drives the worker by calling `jobs.claim_next` and
`jobs.run_job` explicitly, so the interleavings are deterministic.

| id | test | passes when |
|---|---|---|
| U1 | **triggers**: a save of identical values through `api.context` and through `api.details`; a save clearing an absent value; then one save per coding-context field; then a change and its restore [R:truth-T13] | the identical and empty saves answer 200 `unchanged` and add no `EncounterContext`, `Job`, `AuditEvent` or `ProviderRun` (row counts equal before and after); each real change adds exactly one `context.changed` row; the restore answers `updating: false, restored: true` (`/details`: `reassessing: false`) |
| U2 | **typing**: a browser-level test (the fake-DOM harness of `ops/verification`, or `ops/verify_browser.cjs` on the test instance) types a date and chooses a setting without pressing Save | no request is made (the fetch stub's count, or the network log, stays 0) until Save, then exactly one POST `/details` |
| U3 | **case A**: on a v2 revision with an inventory, a setting change, then a date change | the setting change creates no interpret, appraise, analyze or predict job and no `ProviderRun` with `sent=True`; the date change sends at most one Corti request (none when the date's request has a stored answer); Gemini runs created: 0 |
| U4 | **case B, legacy**: a legacy fixture (legacy context and assessment, no inventory); save S1; save S2 while the interpret job is queued; run the worker to completion | exactly one interpret job and one appraise job for the revision; one pass-1 and one pass-2 send; the derived context's values equal S1 merged with S2; the legacy assessment is the context's `earlier_assessment`; a third save afterwards creates no Gemini job |
| U5 | **rapid successive edits**, two and three saves before the worker runs, on a v2 and a legacy fixture; and the same with the worker between saves at every possible point (each stage boundary); and, on the legacy fixture [R:races-R6]: (a) a save while appraise RUNNING after a Stop recorded on it; (b) a restore, then a change landing between a reading stage's supersession decision and its recorded result (the stage's start check driven to decide, the save committed, then `run_job` finishing); (c) a save while a reading stage is RUNNING on a worker killed before it ends, then `mark_stale` and a new worker; and [R2:binding-R2B-7] (d) a save coalescing with an interpret queued 29 minutes before it behind a backlog, the worker claiming it 2 minutes later; (e) a save while the stale sweep's settled path is QUEUED and its run cannot settle | the final current assessment's context has the last save's values; every stage of an earlier save ends `superseded` and records no run after its supersession; no request sha256 is sent twice; `review.fresh` is true at the end, in (a)-(c) with no Resume: a reading stage queued `:after-save:` beside the running one carries the update on, and a QUEUED stage the save coalesced with reads the save at its start; in (d) the interpret runs, its deadline renewed by the save, and reads the save; in (e) the save queued its own `:after-save:` stage, and the update goes on with no Resume |
| U6 | **late finisher**: an assess for C1 runs its bounded child; a save makes C2 current before its persist | the job ends SUCCEEDED with `superseded`; no `Assessment`, `Proposal` or `Clarification` row is added and no clarification changes state; the current assessment is unchanged; C2's assessment later becomes current |
| U7 | **analyze CAS**: a save lands after the inventory is read and before analyze runs; and a save lands while analyze waits for the lock | analyze ends superseded in the first case; in the second the saved values are in the context analyze records; exactly one context of the inventory carries the final values |
| U8 | **restore**: legacy save then restore while the interpret is queued; v2 save then restore before assess #1; v2 save, assess #1 recorded, then restore; legacy save, the reading and assess #1 recorded with Astra and Fable configured, Stop while the peer stages are queued, then restore [R:races-R3][R:legacy-L6]; a first processing's assess #1 shown, a save, then a save back [R:truth-T8]; and A19 [R2:binding-R2B-4][R2:binding-R2B-5]: on a fresh v2 encounter whose final read a "Not documented" answer, a details save giving a value in that row, then a save back to the earlier values (while the update runs, and after it fails); a first processing whose Corti read ended unknown, a date change, the operator's reconciliation, then a save back before the released predict runs (and the same with the reconciliation first); and the first of these on a legacy fixture, saved back before the update's analyze (case B); and [R3:binding-R3B-2] on a fresh, idle v2 encounter, one details save answering one row "Not documented" and changing another detail, then a save back to the earlier details (while the update runs, and after it fails), and the same with that answer saved alone first, its recompute stopped, then the change and the save back | first four: fresh at once with B (the earlier assessment) current and never replaced, the update's stages end superseded with no `ProviderRun` sent after the restore, B's decisions have no `DecisionInvalidation` and no carry, B's open clarifications are still OPEN (A17), the earlier codes are approvable again; the update's assess #1 was never `current_assessment`; the legacy restore sends no peer review; after the v2 restore that followed a recorded assess #1, an answer saved on B is recomputed (its AGAIN assess of B runs, never ASSESS_MOVED) and `reassess_retained` accepts B (`_newest_assessment` leaves the abandoned assess #1 out); the fifth: no restore (B not final), an ordinary update; the A19 cases: no restore, `update.restorable` false and no text offering one, each save back an ordinary update — the first ends with no STALE_ANSWER_BLOCKER standing and the excluded code offered again, sending no Corti request (E's is reused); the second sends the released request once and never reads "being confirmed" with nothing queued; the legacy case-B save back answers 409 RESTORE_REFUSED and writes nothing, and the update goes on; the R3B-2 save back is no restore (`update.restorable` false before it) but an ordinary update whose final's stored rows read the answer, sending no Corti request, and never leaves the answer applied by the overlay alone on a current final; with the recompute queued and stopped before the change, the save back restores and Resume runs that recompute |
| U9 | **Stop, Resume, worker death, hold**: Stop mid-update; Resume; a dead worker mid-predict (`mark_stale`); a hold set by a bare 429; release; Resume; and [R2:binding-R2B-6] a worker killed after a predict's outcome was recorded and before the stage decided, for a Corti 500, a Corti 402 and a run Corti's hold kept unsent, during an update and in a first processing | Stop reads stopped with the update text; Resume queues the first owed stage (analyze for a legacy update stopped after the reading); `mark_stale` queues no successor for a superseded job; while held, every save records only not-sent runs; after release and Resume exactly one send; after the kills, `mark_stale` ends the update's job FAILED for the 500 and CANCELLED, paused, for the 402 and the held run, queueing nothing, the earlier codes and their decisions untouched; the first processing's 402 and held runs end paused, never in a final |
| U10 | **binding and refusals**: during an update, approve, reject, revoke and both exports through the API; `allowed_actions` of the earlier codes; the second review's offer and ask during an idle case-B update on a v2 revision whose inventory is of an older version [R:truth-T15] | each decision answers 409 UPDATE_DECISION and writes no `Decision`; each export answers 409 UPDATE_EXPORT and writes no `ReportArtifact`; `allowed_actions` is [] for every earlier row; `recheck.available` is false and the ask is refused, with no `provider.second_review_requested` row and no `review2` job; after completion approve answers 201 |
| U11 | **what changed**: fixtures with added, removed, status-changed, units-changed, item-changed codes, a kept and a cleared approval, a legacy E and an addendum; and [R:truth-T9][R:truth-T10][R:truth-T11][R:truth-T14]: an approval revoked before the change; an approval carried by the update and cleared afterwards by a same-context final (a re-check's follow-up, an answer's recompute); an approval cleared by a same-context final with no update (its Earlier decisions sentence); a code suggested by E and an alternative in N; a legacy E whose code the member answered away without a recompute, then asked again by N; and an approval the update kept, then revoked by the reviewer on N, and one revoked and approved again [R2:truth-RT4]; an answer given after the update to a question N asks, read while its recompute is queued and after a Stop of it [R2:truth-RT5]; a save during a participant reconciliation's re-run chain after a completed update, whose approvals sit on the previous final [R2:binding-R2B-3]; two different addenda recorded before the first one's update finished, E's approval cleared at the first [R3:truth-R3T-3]; an addendum recorded during that re-run chain [R3:truth-R3T-5] | the computed lists equal the expected ones exactly; two computations are byte-identical; changing the participants configured or the clock changes nothing; the revoked approval is not listed; the carried-then-cleared one reads "kept by the update, then cleared"; the same-context clearing reads the same-details sentence in Earlier decisions; the alternative's removal reason is "Listed as an alternative only; not suggested for approval."; the answers line is present when an answer is not applied to N; the revoked and the replaced kept approvals read "kept by the update, then changed by a reviewer"; the answer given after the update draws no answers line; the re-run chain's save lists the previous final's decisions as kept or cleared; the two-addenda update lists E's approval as "Cleared when documentation was added (revision 2)."; the addendum during the re-run chain compares with that chain's assess #1 and lists the previous final's approval as cleared |
| U12 | **failures**: pass-1 500; pass-2 unhealthy; Corti 500; Corti 429 and 402; Corti's token endpoint refusing (401); Corti not sent for a local reason (no credentials file, the service unreachable); MAX_TOKENS; analyze overrun; and [R:legacy-L4] a v2 E and a legacy E whose own Corti run failed (a 500) or could not be built, each followed by a setting change that leaves Corti's request unchanged | the texts and actions of 7.1; `retry_reading` releases one pass-1 (or pass-2 only) attempt; `retry_update` releases one Corti attempt for the 500, re-queues the not-sent one, and is refused (RETRY_UPDATE_HELD) for the 429, 402 and token refusal, which pause the update under Corti's hold (U20); no assessment replaces the earlier codes after any of them — the token refusal and the not-sent runs included [R:legacy-L5]; the earlier codes' decisions are untouched; a restore makes them current; in the L4 fixtures the update completes with E's own outcome, sending no Corti request and, on the legacy E, after both Gemini passes only |
| U13 | **exports**: a current download; an earlier draft and an earlier approved download (@1 and @2, TXT and CSV); a @2 export's content; [R:races-R1][R:truth-T1][R:legacy-L1] an approved @1 export of a legacy encounter downloaded during a case-B update (before analyze, after a pass-1 failure, under a hold, after a Stop), then after a restore | a current artifact downloads byte-identical to its stored bytes; an earlier one starts with the banner (TXT) or has the banner row second (CSV), names its revision, has the `-earlier` filename, and the stored `content` and `sha256` are unchanged; a @2 export states revision, details and codes made, read from the assessment's context; during the case-B update the pre-save export is listed `current: false` and downloads with the banner in every one of those states, and after the restore it is current again and downloads as stored |
| U14 | **duplicates**: two identical details POSTs; two tabs saving different fields; a repeated addendum; a double Retry; [R:truth-T7] an addendum that would take the document over `INTERPRET_MAX_CHARS`, and one whose text fails the framing check; and [R2:truth-RT7] an addendum to a document whose own text holds `[S2]`, one to a document already over `INTERPRET_MAX_PAGES`, and an over-bound addendum during a first processing | the second identical POST is a no-op; both fields are in the final values; the second addendum answers 409 ADDENDUM_DUPLICATE and adds no revision; the second Retry is refused; the over-bound and unframeable addenda answer 409 ADDENDUM_TOO_LONG and ADDENDUM_UNPREPARED and add no revision, no `DecisionInvalidation` and no job; the document-caused ones answer ADDENDUM_DOCUMENT_UNPREPARED and ADDENDUM_DOCUMENT_TOO_LONG; no addendum refusal says the codes shown stay |
| U15 | **sentinel**: the page of a legacy encounter whose update has recorded its assess #1 (never current, A17), and the same page with the encounter's label forced to new_path (the relabel guard) | the new_path scope counts 0 legacy executions while the earlier codes are drawn; the guard matrix's new worlds (an update pending on a legacy encounter; a completed update's what-changed read) are green |
| U16 | **truthful progress** [R:truth-T2]: a setting-only v2 update; a legacy update, read before and after its analyze; an addendum, read before and after its analyze; an upload, read after its analyze; rapid saves in case A; a completed document; a target job waiting behind a superseded running job; and [R2:truth-RT3] a Stop on a running appraise followed by a save (U5 a), and a late finisher's FAILED predict of an older save's context in the same run as the newer chain; and [R3:truth-R3T-1][R3:truth-R3T-2] W1's three saves (date, setting, the date back) with the first save's Corti request answering 500, and again answering 402, the third save re-checking with E's run (no predict of its own), with and without participants configured; a legacy save while pass 1 is RUNNING, read while it runs, after it finishes and before its `:after-save:` twin runs; and an `:after-save:` twin that expires in a backlog after the running reading read the document | steps a job of the current run does not run read `skipped` while an update is pending; a step that ran for the update keeps its state after the reading is no longer owed ("Identifying procedures" done after a legacy update's analyze; the addendum's reading steps done); an upload never reads "Not started" before a running later step; `started_at` is the first save's time throughout an update, rapid saves included, and the first job's for an upload; a completed document has `finished_at` and its steps' states; the legacy update's active detail names the pass that runs; the waiting case reads `updating` with WAITING_FOR_EARLIER; no message names a provider or model (the customer scan); in the two overlap cases "Identifying procedures" and "Checking suggested codes" read in progress or done, never stopped or did not finish, while the update runs and after it completes; in W1's runs "Checking suggested codes" never reads "Did not finish" or "Stopped" for the first save's predict (in progress or done while the third save's chain runs it; "Not needed" when nothing of the current context ran in it), and the 402 sets Corti's hold; the save beside a running pass 1 reads "Identifying procedures: In progress" with its active detail, never "Waiting to start"; the expired twin leaves the step done |
| U17 | **rollback rows**: the D15 runtime rollback test (FINAL-V2 6.4) on a database holding a legacy encounter with an update pending before analyze, one pending after analyze, and one completed; and on the old image, after the switch-back, the first encounter's pending value saved again [R:legacy-L7]; and a legacy encounter whose own unknown document review was reconciled with no save, switched back before its update's analyze [R3:binding-R3B-3] | the old image starts, lists and renders all three as 9.4 states; the undo names the two pending ones `update_pending`; the undo reverted the first one's `Encounter.user_values` to its context's values, wrote its `context.rollback_reverted` row and named the fields and values in its answer; the value saved again on the old image takes effect there (a new legacy context with it); the undo names the A21 encounter `update_pending` too, and the old image's reading of it is recorded |
| U18 | **member acts and saves (A18)** [R:races-R4][R:races-R5][R:truth-T12]: a context save while an answer's recompute is queued, and while it runs; a context save while a second review is queued, and while it is sending; an answer's withdrawal during an idle update (a failed document review); then each act's own outcome | each such save answers 409 with the busy sentence and writes nothing; after the stage ends the save is accepted; the withdrawal answers 409 UPDATE_ANSWER_WITHDRAW and writes no revocation; no restore ever leaves STALE_ANSWER_BLOCKER standing with nothing queued, and the second review's key is never used by a superseded stage |
| U19 | **case-B details** [R:truth-T3]: a legacy encounter held on a member date conflict; "Use document date" (case B); the reading then failing (pass-1 500), then pausing under a hold; and a case-B date change with no conflict | while pending, the phase follows the update (`updating`, then `failed` with 7.1's text and "Try reading again", then `paused`), never `action_needed`; the customer state and the list row agree; the date row shows the saved value, the document date and quote stay; a reload shows the same |
| U20 | **the provider hold (A16)** [R:races-R2][R:legacy-L2]: Corti 402 during an update; then a save with another date, another encounter's update, an upload, an addendum, a Resume and a Retry; then the operator's release and one Resume; Corti's token endpoint refusing; Astra 429 on a peer review, then another encounter's peer review; and a worker killed right after Corti's 402 was recorded, then another encounter's predict; a 402 during a first processing; a 402 answering a predict a newer save superseded while it sent [R2:binding-R2B-1]; Fable answering 400 on one exchange and 413 on another [R2:binding-R2B-2]; Corti's token endpoint answering 429, 400 and 500 [R2:truth-RT1]; a legacy encounter whose E's Corti run, recorded by the installed release, FAILED with 429, and one whose E's run is that release's token refusal, each edited after the install with Corti's request unchanged [R2:truth-RT2]; and [R3:binding-R3B-1] Corti's token endpoint answering 401, and the coding service answering 402, each with the outcome's record failing (`_finish_run` made to raise), then a Retry from a second tab and another encounter's predict; [R3:binding-R3B-4][R3:truth-R3T-6] a pre-install FAILED 402 (and 429) on a date that is not E's, met by an update that sets that date again, on a legacy and a v2 fixture, then a Retry and a save back; [R3:binding-R3B-5][R3:truth-R3T-4] a first processing paused by its own Corti 402 (and by a token 401), then a setting save while paused, before and after the operator's release, with Astra and Fable configured; [R3:truth-R3T-7] the paused first processing read after the release and before any Resume | one `ProviderHold` per refusal; while it stands every listed act records a not-sent run with `scope.held = 'provider_hold'` and no Corti request is sent by any encounter; after the release exactly one send, of the identical request (the failed-before door does not hold a hold-setting run); the token refusal sets the hold from the run's recorded status; the Astra hold sends no further Astra request and the updates complete partial; each refusal above has its hold before anything else runs, so the next request of that provider records a held run; Fable's 400 sets a hold and its 413 does not; the token 429 and 400 set the hold, and the token 500 ends the update failed with the not-sent text and "Try updating again"; the first processing's 402 pauses its document with PROVIDER_PAUSED and, after the release, Resume sends once; the pre-install FAILED 429 is held by `_failed_before` (nothing sent), and the pre-install token refusal is sent once, its refusal setting the hold; with the record failing, each run is recorded UNKNOWN with its status and its `ProviderHold` exists, the encounter reads being confirmed with no Retry (a Retry POST is refused), and the other encounter's predict records a held run, sending nothing; the update meeting the pre-install refusal sends nothing, ends failed with the refused-before text, its Retry answers RETRY_UPDATE_REFUSED_BEFORE, and the save back restores the earlier codes; the save during the paused first processing queues the predict (no participant first reading is sent, no final is made with the refused run), which pauses again while the hold stands and after the release sends once; after the release and before any Resume the paused first processing reads stopped by the system with Resume, never PROVIDER_PAUSED |
| U21 | **the page while pending** [R:truth-T4][R:truth-T5][R:truth-T6]: an update in each state (`updating`, `failed`, `stopped`, `paused`, `being_confirmed`), in cases A and C; and the peer phase of a case-A update with Astra and Fable configured; and an update whose earlier codes listed none [R2:truth-RT8]; and an A21 update (kind `check`) in each state, and a details update whose saved details are the earlier codes' own (A19's ordinary change; a save back to a first processing's unfinished codes) [R3:binding-R3B-3][R3:binding-R3B-6] | the results section never says no codes were suggested and the tally never "No codes yet" while earlier codes exist; "being updated" appears only in `updating`; the earlier assessment's other sections are drawn inside the earlier codes' section and none is read from the update's assess #1; no case-C text offers a restore; with no earlier code, the results section and the tally say none was suggested before the change, never that the earlier codes are shown below; no text of the A21 update names a change of the member's (title "Updating codes"), and the panel of each update whose saved-changes list would be empty shows its fixed line in its place |
| U22 | **a chain re-run after completion** [R2:binding-R2B-3]: Astra and Fable configured, a date change whose Fable peer review ends unknown, the update completing; the operator's reconciliation of that run; the page read while the re-run chain's peer stages run, and after its final; and [R3:truth-R3T-5] an addendum recorded while that chain's peer stages run; and [R3:binding-R3B-3] a legacy fixture whose E's own Corti run is UNKNOWN, reconciled with no save, and the same after a save and a restore made before the reconciliation, and a v2 fixture of an older inventory version reconciled the same way | while the chain runs the encounter reads processing as today, never `update.pending`: no "Changes saved—updating codes", no earlier codes, no UPDATE_DECISION; after the chain's final, "what changed" compares with the update's earlier codes as before; the addendum reads an update (kind `documentation`) whose earlier codes are the chain's assess #1, and on completion "what changed" lists the previous final's approval as cleared; each A21 reconciliation's reading runs, never superseded, the page reads "Updating codes" (kind `check`) with no "Changes saved", no "Saved by" and no restore offer, the earlier codes read-only, the released predict sends once, and the final replaces them with "what changed" against them; before the reconciliation the encounter reads being confirmed |

### 11.2 Installed-walk checks (9.9 additions)

Run on the installed site with synthetic documents, after 9.9 steps 1-5. The three failure checks (W3, W4, W8) need a
provider fault and run on the test instance (`testinst`, the installed image against a restored dump) with recorded fault
responses through the replay adapters: inducing a quota hold or a 500 on the installed site would cost money or hold
every upload. Each check
records its operator evidence (runs, requests, usage) from `/ops/` and the operator report.

| id | check | passes when |
|---|---|---|
| W1 | **rapid edits, new encounter**: upload; when ready, three saves within 5 seconds (date, setting, the date back) | the page shows "Changes saved—updating codes" from the first save until completion; the final codes' details equal the last save's; Gemini runs for the encounter after the upload: 0; no request sha256 sent twice; the earlier codes were never decidable (an approve posted during the update from a second tab loaded before the first save is refused with UPDATE_DECISION) |
| W2 | **rapid edits, legacy encounter**: a walk encounter uploaded, approved and exported on `c2e53f8e` before the switch, in the walk's own workspace (no other encounter is edited); after the install, two saves within 5 seconds | exactly one pass-1 and one pass-2 send for the revision; the final context carries both saves; **during** the update (before its analyze) the legacy export is listed as earlier and downloads with the banner, never as stored [R:races-R1][R:truth-T1][R:legacy-L1]; the legacy approvals appear in Earlier decisions and as cleared in "What changed"; after completion the legacy export still downloads with the banner |
| W3 | **failure with Retry** (test instance): a recorded pass-1 500 during an update | the failed text and "Try reading again" are shown; the earlier codes stay read-only; one Retry sends one request and the update completes |
| W4 | **quota hold** (test instance): a recorded bare 429 during an update | the paused text; no Gemini request is sent after the hold by any encounter (the runs after the hold are all not-sent); after the operator's release and one Resume, one send and the update completes |
| W5 | **reload persistence**: reload during W1's and W2's updates, and after them | before and after each reload the phase, the steps, the earlier codes and (after completion) "What changed" are identical; the reload created no job and no run |
| W6 | **actual exports**: during an update try the draft and the approved export; during it, download an export made before the save (W2's, a case-B update) [R:races-R1][R:truth-T1][R:legacy-L1]; after completion approve and export both; download an earlier export | both are refused with UPDATE_EXPORT and nothing is written; the pre-save export downloads with the banner and the `-earlier` filename while the update is pending; after completion the approved export's content equals the saved approvals and states revision, details and codes made; the earlier export downloads with the banner; no downloaded file names a provider or model (`gemini_unknown` included) |
| W7 | **what changed correctness**: for W1's and W2's encounters | the page's "What changed" equals the differential check's (11.3) exactly |
| W8 | **the provider hold** (test instance) [R:races-R2][R:legacy-L2]: a recorded Corti 402 during an update; then a save with another date on that encounter and an update on a second encounter; the operator's release and one Resume | the paused text, never "change the date of service"; no Corti request is sent by either encounter while the hold stands (their runs after the hold are all not-sent, `scope.held = 'provider_hold'`); after the release and one Resume, one send and the update completes |

### 11.3 The differential check of "what changed"

6b adds to `ops/verification` an independent implementation of 6.2, written from this text without reading
`customer_api.what_changed`, that reads the rows through the operator API. U11 and W7 compare the two outputs field by
field; a difference fails the check and is the finding.
