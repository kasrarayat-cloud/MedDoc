# CPT Studio core repair and customer interface: acceptance checklist

The acceptance contract for the owner's directive of 2026-11-03 (second message, "Implement the CPT Studio core repair
and customer-interface improvements below on https://cpt.quillmd.com"). The directive is recorded verbatim, with the
session's interpretation on receipt, in `docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`. Integration and
deployment owner: session a12d8fb3.

**Rules of this file.** Status is one of NOT RUN, IN PROGRESS, PASS, FAIL or BLOCKED. `[x]` marks only a PASS backed by
the evidence named in its row. A row says which kind of PASS it is: IMPLEMENTED (built and tested offline) or VERIFIED
LIVE (shown on cpt.quillmd.com with genuine responses). A passing offline test is never recorded as live verification.
Earlier failures and measurements stay in the log below and are never rewritten.

**Three results are reported apart and never merged:** functional completion (the installed workflow works), clinical
accuracy validation (not established by this work: no qualified coder adjudicates a predeclared set), and content-use
permissions (D3, D4 and D5 stay open owner decisions).

**Starting point, as found on 2026-11-03 at 22:34Z (read-only).**
- cpt.quillmd.com serves revision `41e03656df61` (#1459), image `sha256:31d8d09721d5…`; `main` is `7c9968a89`.
- Live database: 47 encounters, 71 provider runs (65 sent), 67 assessments, 28 decisions, 122 report artifacts, 230
  jobs (0 active), 0 unreconciled unknown runs, 3 users (`owner`, `demo-reviewer`, `review-agent`), 1 workspace.
- Mara (`effe4d0b-b449-4efd-b208-635ca1d09984`), as the owner described: current assessment `82679b83…` selects 43239
  (needs clarification), 45380 (ready) and 45385 (needs clarification); five open questions (conflict:biopsy on the
  upper endoscopy, conflict:snare on the colonoscopy, and the office E/M setting, patient status and E/M basis); no
  decision. Traced to the services inventory: the upper endoscopy's scope starts at the shared report title and runs to
  the end of the document, so the colonoscopy's "No snare resection was performed on COL-1", "No biopsy forceps were
  used on COL-2" and the COL-2 prophylactic clip are assigned to the upper endoscopy; the lesion-distinguishing sentence
  yields a negated snare act on the snare-treated lesion; routing reads the explicit "No separate office evaluation and
  management encounter ... is documented" as an uncertain E/M service with three missing facts.

## 1. Shared document-reading logic

| | Item | Status | Evidence | Remaining action |
|---|---|---|---|---|
| [x] | 1.1 Statement binding to procedure, lesion, anatomy, action, time and provider repaired as a general rule | PASS (IMPLEMENTED) | P1 rules 1-4 and 8 (`cux-bind.json`, declared before code), L1/L2 (`cux-lead.json`): `test_cux_bind` LesionLabelTests, CombinedTitleTests, AttributiveCompoundTests; `test_cux_lead` LabelledNotePartTests, PhysicianTitleTests | Live: the fresh case and Mara (6.9, 6.10) |
| [x] | 1.2 Negation kept within its scope (a distinguishing sentence negates nothing it only names) | PASS (IMPLEMENTED) | `test_cux_bind` CopularNegationTests (a distinguishing sentence negates only its own act); Mara's "No snare resection was performed on COL-1" stays on COL-1 | Live: Mara (6.9) |
| [x] | 1.3 Acts assigned to the procedure that performed them (the COL-2 clip, COL-1/COL-2 sentences) | PASS (IMPLEMENTED) | `test_cux_bind` MaraEndToEndTests: the COL-2 clip and the COL-1/COL-2 sentences bind to the colonoscopy; the upper endoscopy keeps only its own acts | Live: Mara (6.9) |
| [x] | 1.4 An explicitly absent separate E/M service asks no E/M question | PASS (IMPLEMENTED) | `test_cux_bind` EmAbsenceTests and EmQuestionsStayForAStatedVisitTests (a stated visit still asks); predicted on the live data's copy: Mara reassessed has no office E/M question | Live: Mara (6.9) |
| [x] | 1.5 Genuine uncertainty and conflicting documentation still held (round-4 standard: must-stay-held inputs stay held) | PASS (IMPLEMENTED) | battery and replay declared before code: battery violations 5 to 2 with the declared movements only, replay EQUAL, the H2 freeze holds (`cux-bind.json`, `cux-hold.json`, `cux-lead.json`); `test_cux_bind` GenuineConflictTests | Refutation round (lens L2) |
| [x] | 1.6 False READYs on failed, negated, historical or wrong-procedure evidence reproduced and repaired | PASS (IMPLEMENTED) | R8 register D1-D10, D12, D13, D15 reproduced on the base and held on the head: `test_cux_hold` RegisterRowsTests and the per-class tests; L3 at the own-passage release: `test_cux_lead` AttributiveCompoundReleaseTests | Refutation round (lens L1) |
| [x] | 1.7 A reinstated therapeutic code (45385) recomputes its conflict with the diagnostic base (45378) | PASS (IMPLEMENTED) | One base rule shared by the engine and the overlay (738df8dc4): `test_cux_review` ReinstatedBaseTests, D14Tests | Refutation round (lens L3) |
| [x] | 1.8 Checks recomputed after every selection, restoration, context change, reload and export | PASS (IMPLEMENTED) | Every reader reads the recomputed overlay (`review_view.py`, `review.effective_view`): `test_cux_review` StaleCheckTests, RejectAndRevokeTests, MemberAnswerTests; `test_cux_wire` MemberAnswerEffectTests, ApprovedExportMarkerTests | Live: decisions persist after reload (6.11) |
| [x] | 1.9 No approval through model agreement or hardcoded expected results | PASS (IMPLEMENTED) | Agreement never promotes (HARNESS.md I3; its tests green in the integrated suite); every expected result is a predeclared declaration row, never read by the code; only a member's or the agent's recorded decision approves |  |

## 2. Provider identities out of the customer experience

| | Item | Status | Evidence | Remaining action |
|---|---|---|---|---|
| [x] | 2.1 Customer screens use functional labels (Document review, Independent checks, Coding validation) in one compact progress panel | PASS (IMPLEMENTED) | The page (P6): one progress panel with the four steps and the three checks by function; `tests/frontend/app.test.cjs` (57), `test_customer_fixtures` (fixtures generated from the real serializer) | Live: desktop and mobile screenshots (6.6) |
| [x] | 2.2 Customer API responses carry no provider or model identity, usage, credits, request ids, hashes, rule ids or traces (enforced on the server) | PASS (IMPLEMENTED) | The customer API is an allowlist (`studio/customer_api.py`): `test_customer_surface` ScenarioTests drive 14 scenarios through every endpoint and refusal with a database-derived denylist and the section-7 key sets | Live: `ops/scan_customer.py` (6.4) |
| [x] | 2.3 The customer bundle carries none of them | PASS (IMPLEMENTED) | `test_customer_surface` CollectedStaticTests scan the collected static files, the templates and the served sign-in page (the expected-failure marker removed, b0c321346) | Live: the served bundle scanned (6.4) |
| [x] | 2.4 Customer downloads, notifications, accessibility labels and error messages carry none of them | PASS (IMPLEMENTED) | Customer reports (`cpt-studio-customer-report@1`), toasts, labels and error vocabulary (`customer_api.customer_error`) scanned in `test_customer_surface` ReportTests and ScenarioTests | Live: downloads scanned (6.4, 6.12) |
| [x] | 2.5 Platform-operator diagnostics keep full provenance, identities, usage, failures and audit history | PASS (IMPLEMENTED) | `/ops/` keeps the full encounter view, trace, reports, reconcile and originals: `test_operator` ConsoleLogicTests, `tests/operator/ops.test.cjs` (134) | Live: the walk's operator session (6.5) |
| [x] | 2.6 A workspace owner, reviewer or viewer is refused the diagnostic URLs and APIs | PASS (IMPLEMENTED) | `test_operator` MatrixTests: every `/ops/` URL answers 404 to viewer, reviewer, workspace owner, another workspace's owner and a revoked operator; no workspace role confers a grant (decision (h)) | Live: refused to review-agent (6.5) |
| [ ] | 2.7 Required disclosures kept accurate (none exists today; none removed) | BLOCKED | CPT Studio has no privacy or subprocessor page, and none was removed; after this change no customer screen names a subprocessor | Whether a disclosure is legally required is the owner's or legal question (decision (m)) |

## 3. Codes-first result

| | Item | Status | Evidence | Remaining action |
|---|---|---|---|---|
| [x] | 3.1 A short numbered list: code, units and modifier when applicable, status (Ready for review, Needs a detail, Approved, Excluded), one document-based sentence | PASS (IMPLEMENTED) | The numbered result list (`resultList`, DOM contract section 8): code, units, modifier, the four statuses, one sentence of CPT Studio's own reading; `tests/frontend/app.test.cjs` | Live: the fresh case (6.6, 6.10) |
| [x] | 3.2 Quotation and material qualification behind an optional "Why this code?" | PASS (IMPLEMENTED) | "Why this code?" (`whyThisCode`): CPT Studio's own passages first, then supporting provider passages only (`customer_api._quotes`); the walk and the download check accept exactly those (16a22f853) | Live: the walk's quotation checks (6.12) |
| [x] | 3.3 Review and download actions; suggested distinguished from approved | PASS (IMPLEMENTED) | Approve, reject, reinstate and revoke offered only as `allowed_actions`; the export dialog distinguishes the draft from the approved export; `test_cux_review`, app tests | Live (6.10) |
| [x] | 3.4 An approved export excludes unresolved and unapproved items and matches the persisted decisions | PASS (IMPLEMENTED) | Decision (f): the approved export only when every code is resolved, listing approved codes only, and stale (409) once its decision marker moves: `test_cux_wire` ApprovedExportMarkerTests, MemberAnswerEffectTests | Live: downloaded and compared (6.12) |
| [x] | 3.5 Concise limitations; no claim of complete validation; no unlicensed descriptor shown as CPT content | PASS (IMPLEMENTED) | `customer_api.limitations`: fixed, true limitations; no descriptor text shown; no claim of complete validation |  |

## 4. Clarification flow

| | Item | Status | Evidence | Remaining action |
|---|---|---|---|---|
| [x] | 4.1 Irrelevant questions suppressed; stated facts resolved by the reader | PASS (IMPLEMENTED) | E/M questions only for a stated visit (1.4); a date hold asks only the date (e3f65cae8); `test_cux_flow` DetailRowsTests | Live: the fresh case's manifest `expected_no_em_questions` |
| [x] | 4.2 One compact "A few details needed" panel with choices, date selectors and brief confirmations | PASS (IMPLEMENTED) | One "A few details needed" panel (`detailsPanel`): date control, choices, confirmations; `test_cux_flow` DetailRowsTests, app tests | Live (6.6) |
| [x] | 4.3 "Not documented" and "Cannot confirm" where appropriate | PASS (IMPLEMENTED) | "Not documented" and "Cannot confirm" exclude the code and never release it: `test_cux_wire` MemberAnswerEffectTests |  |
| [x] | 4.4 Each material question asked once; the saved answer kept | PASS (IMPLEMENTED) | A detail's id is stable across re-assessments (`answers.detail_id`: fact, family, code); `test_cux_flow` DetailSaveTests |  |
| [x] | 4.5 Independent supported services stay reviewable while another awaits a detail | PASS (IMPLEMENTED) | Codes that do not depend on a detail stay reviewable: `test_cux_review`, `test_cux_flow` |  |
| [x] | 4.6 Date conflict: document date and entered date side by side, "Use document date"; no silent choice, no unsupported prefill | PASS (IMPLEMENTED) | `test_cux_flow` DocumentDateTests and DateHoldDetailTests: the document's and the member's dates side by side, "Use document date" only for a single documented date, never prefilled |  |
| [x] | 4.7 Member context stored apart from the document, attributed and audited; no manufactured addendum, clinical fact or approval | PASS (IMPLEMENTED) | MemberAnswer stored apart from the revision, attributed and audited (`test_cux_flow` DetailSaveTests); an addendum is the physician's own text from a confirmation row only (08b5e59a3, `test_cux_addendum`); the agent makes no addendum |  |
| [x] | 4.8 Modifier review for separately treated forceps/snare colon lesions from dated sources; never both 59 and XS; no payer-validation claim | PASS (IMPLEMENTED) | `test_cux_review` ModifierReviewTests: offered only for separately treated lesions, none/59/XS, never both, never prefilled, dated CMS sources, no payer-validation claim | Live: the walk's modifier plan (6.10) |

## 5. Upload and processing progress

| | Item | Status | Evidence | Remaining action |
|---|---|---|---|---|
| [x] | 5.1 Immediate upload acknowledgement; stages tied to backend state; active and completed stages, elapsed time | PASS (IMPLEMENTED) | Upload acknowledgement from the POST 201; four steps from the backend rows (`progress.encounter_progress`): `test_cux_flow` ProgressFoldTests | Live (6.7) |
| [x] | 5.2 Uploading, queued, processing, awaiting a detail, completed, partially completed and failed told apart | PASS (IMPLEMENTED) | Phases queued, processing, action_needed, awaiting_detail, completed, partial, failed, stopped, being_confirmed and paused (decision (j), 372ec44b0): `test_cux_flow`, `test_cux_paused` | Live (6.7) |
| [x] | 5.3 No invented percentage or ETA; a truthful longer-than-expected message; no animation after failure | PASS (IMPLEMENTED) | Elapsed time only, no percentage or ETA; "taking longer than usual" from each stage's real bound (a31c40871); nothing animates after failure or while paused |  |
| [x] | 5.4 Plain-language actionable errors without provider names or payloads; "Action needed" at once for a blocking date conflict | PASS (IMPLEMENTED) | Plain errors from a fixed table (`progress.ERRORS`, `customer_api.customer_error`); "Action needed" right after analyze for a date conflict, listed and counted at once (`test_cux_queue_recheck` DateHoldQueueTests) |  |
| [x] | 5.5 Progress and job identity kept across reload and reconnect | PASS (IMPLEMENTED) | The page polls the same encounter; an upload's client key makes a retry reach the same document: `test_cux_flow` UploadKeyTests | Live (6.8) |
| [x] | 5.6 A working Stop and safe recovery; unknown outcomes reconciled before any retry; no duplicate paid request | PASS (IMPLEMENTED) | Stop and Resume (`test_customer_surface`); an unknown or orphaned sending run blocks every send (decision (k), `test_cux_sending`); the re-check sends one bounded request once (`test_cux_queue_recheck`) | Live (6.7, 6.8) |

## 6. Verification and install (the directive's acceptance checklist)

| | Item | Status | Evidence | Remaining action |
|---|---|---|---|---|
| [ ] | 6.1 Shared procedure/lesion/negation binding repaired | NOT RUN | | |
| [ ] | 6.2 Absent separate E/M no longer creates unnecessary questions | NOT RUN | | |
| [ ] | 6.3 Unsupported evidence and diagnostic/therapeutic conflicts remain correctly blocked | NOT RUN | | |
| [ ] | 6.4 Customer screens, API responses and downloads omit provider identities and technical traces | NOT RUN | | |
| [ ] | 6.5 Operator diagnostics remain intact and protected from customer accounts | NOT RUN | | |
| [ ] | 6.6 Compact code results and clarification controls work on desktop and mobile | NOT RUN | | |
| [ ] | 6.7 Upload acknowledgement, real progress, failure, Stop and recovery states work | NOT RUN | | |
| [ ] | 6.8 Reload/reconnect preserves the existing job without duplicate submissions | NOT RUN | | |
| [ ] | 6.9 Mara is reassessed using retained responses where possible, with no fabricated answers or approvals | NOT RUN | | |
| [ ] | 6.10 One fresh synthetic GI case passes the installed workflow with actual provider responses | NOT RUN | | |
| [ ] | 6.11 Review decisions persist after reload | NOT RUN | | |
| [ ] | 6.12 An actual approved report is downloaded and independently compared with saved selections, units, modifiers and source evidence | NOT RUN | | |
| [ ] | 6.13 Existing records and exports remain preserved | NOT RUN | | |
| [ ] | 6.14 The live site remains accessible during development and after installation | NOT RUN | | |

## Log

- 2026-11-03 22:32Z: preflight FIX-AND-GO (a transient load spike from the session's own start-up; parallelism kept
  moderate). Report `docs/preflight-reports/preflight-20261103T223207Z.md` (untracked, as every preflight report is).
- 2026-11-03 22:34Z: live baseline read (read-only transaction) and the Mara trace above.
- 2026-11-04 (integration, session a12d8fb3): rows 1 to 5 filled with their offline evidence at the integrated head
  (`feat/cpt-studio-core-ux-20261103`); each says IMPLEMENTED, and none says VERIFIED LIVE before the install and the
  walk. Section 6 stays NOT RUN until then. Seams the integration closed: an addendum from a details row (08b5e59a3),
  the bounded re-check kept (decision (n)), the queue listing what its badge counts (decision (o)), the walk's act
  evidence (16a22f853), the paused phase (decision (j)), and four I1 pins re-pinned with the installed-label proof
  (8b7913554). Measured on a copy of the live data (2026-11-04T04:34Z): migrate 0009-0012, RECOMPUTE unchanged for all
  48 encounters, no undo hazard, Mara reassessed with nothing sent (runs 76 to 76) to ready_for_review with 43239, 45380
  and 45385 ready and no open question.
