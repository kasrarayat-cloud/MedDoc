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
| [x] | 1.1 Statement binding to procedure, lesion, anatomy, action, time and provider repaired as a general rule | PASS (IMPLEMENTED) | verified and repaired 2026-11-04 after #1465 merged: the lead's own probe of main 20a64b86 found four false READYs worse than installed (45380 for an upper-exam biopsy bound by a colon polyp's label, its exam told by a bare endoscope, by 'Upper endoscopy was then performed' or by the gastroscope before 'after withdrawal of the colonoscope'; 45382 for a prophylactic hemostatic clip at a labelled polyp in a combined note), so the row was FAIL until repaired; repaired by R1a-r5 hold-only (cux-r5-binding.json: rounds 5, 5b, 5c; the word-list repairs of rounds 4 and 4b and an unbinding form refuted and not taken): over 2,924 + 371 refuter cases no cell moves toward READY against main and no violation main lacks, 113 + 53 of main's violations fixed; battery 1 declared movement (A3 control held), 0 new violations against main or installed; residuals recorded in ACCURACY-RESIDUALS.md rounds 5 to 5c (the declared hold class; B3 base code alone and an act whose own sentence names the colonoscope's withdrawal, both pre-existing on main and worse than installed); previously: repaired: round 2 (L1a-L1f, R1a/R1b) and round 3 (A1, A2, A3, A4, A6, A7, L1-h) repairs; confirmed offline at 9ffbe9b53: full suite 5,778 Django + 524 ops + node, all pass; battery vs installed 41e03656df61 violations 72 to 2 (the two pinned), 0 new; round 3 confirmation 22 of 25 fixed, 3 recorded | Live: Mara and the fresh case (6.9, 6.10) |
| [x] | 1.2 Negation kept within its scope (a distinguishing sentence negates nothing it only names) | PASS (IMPLEMENTED) | `test_cux_bind` CopularNegationTests (a distinguishing sentence negates only its own act); Mara's "No snare resection was performed on COL-1" stays on COL-1 | Live: Mara (6.9) |
| [x] | 1.3 Acts assigned to the procedure that performed them (the COL-2 clip, COL-1/COL-2 sentences) | PASS (IMPLEMENTED) | verified and repaired 2026-11-04 after #1465 merged: the lead's own probe of main 20a64b86 found four false READYs worse than installed (45380 for an upper-exam biopsy bound by a colon polyp's label, its exam told by a bare endoscope, by 'Upper endoscopy was then performed' or by the gastroscope before 'after withdrawal of the colonoscope'; 45382 for a prophylactic hemostatic clip at a labelled polyp in a combined note), so the row was FAIL until repaired; repaired by R1a-r5 hold-only (cux-r5-binding.json: rounds 5, 5b, 5c; the word-list repairs of rounds 4 and 4b and an unbinding form refuted and not taken): over 2,924 + 371 refuter cases no cell moves toward READY against main and no violation main lacks, 113 + 53 of main's violations fixed; battery 1 declared movement (A3 control held), 0 new violations against main or installed; residuals recorded in ACCURACY-RESIDUALS.md rounds 5 to 5c (the declared hold class; B3 base code alone and an act whose own sentence names the colonoscope's withdrawal, both pre-existing on main and worse than installed); previously: repaired: round 2 R1a (an act never moved to another service's lesion), round 3 A3 (no section heading) and A4; confirmed offline at 9ffbe9b53: full suite 5,778 Django + 524 ops + node, all pass; battery vs installed 41e03656df61 violations 72 to 2 (the two pinned), 0 new; round 3 confirmation 22 of 25 fixed, 3 recorded | Live (6.9) |
| [x] | 1.4 An explicitly absent separate E/M service asks no E/M question | PASS (IMPLEMENTED) | repaired: round 2 rule-8 narrowing (F07, F08), round 3 A5 (post-modified evaluations); a same-day evaluation stated in wording outside R8b-r3's closed list is recorded (ACCURACY-RESIDUALS.md); confirmed offline at 9ffbe9b53: full suite 5,778 Django + 524 ops + node, all pass; battery vs installed 41e03656df61 violations 72 to 2 (the two pinned), 0 new; round 3 confirmation 22 of 25 fixed, 3 recorded | Live: the fresh case's no-E/M check |
| [x] | 1.5 Genuine uncertainty and conflicting documentation still held (round-4 standard: must-stay-held inputs stay held) | PASS (IMPLEMENTED) | repaired: round 2 R4a (dated combined denials), R2a (doubtful compounds), R1c, round 3 A2 (the same-lesion conflict kept); confirmed offline at 9ffbe9b53: full suite 5,778 Django + 524 ops + node, all pass; battery vs installed 41e03656df61 violations 72 to 2 (the two pinned), 0 new; round 3 confirmation 22 of 25 fixed, 3 recorded |  |
| [x] | 1.6 False READYs on failed, negated, historical or wrong-procedure evidence reproduced and repaired | PASS (IMPLEMENTED) | verified and repaired 2026-11-04 after #1465 merged: the lead's own probe of main 20a64b86 found four false READYs worse than installed (45380 for an upper-exam biopsy bound by a colon polyp's label, its exam told by a bare endoscope, by 'Upper endoscopy was then performed' or by the gastroscope before 'after withdrawal of the colonoscope'; 45382 for a prophylactic hemostatic clip at a labelled polyp in a combined note), so the row was FAIL until repaired; repaired by R1a-r5 hold-only (cux-r5-binding.json: rounds 5, 5b, 5c; the word-list repairs of rounds 4 and 4b and an unbinding form refuted and not taken): over 2,924 + 371 refuter cases no cell moves toward READY against main and no violation main lacks, 113 + 53 of main's violations fixed; battery 1 declared movement (A3 control held), 0 new violations against main or installed; residuals recorded in ACCURACY-RESIDUALS.md rounds 5 to 5c (the declared hold class; B3 base code alone and an act whose own sentence names the colonoscope's withdrawal, both pre-existing on main and worse than installed); previously: repaired: the regressions repaired (rounds 2 and 3); seven wordings the installed revision also reads READY recorded in ACCURACY-RESIDUALS.md, the three declared-form variants (R05, R06, R12) fixed in code; A8 recorded (the frozen layout); confirmed offline at 9ffbe9b53: full suite 5,778 Django + 524 ops + node, all pass; battery vs installed 41e03656df61 violations 72 to 2 (the two pinned), 0 new; round 3 confirmation 22 of 25 fixed, 3 recorded | Accuracy beyond the battery is the owner's adjudicated evaluation |
| [x] | 1.7 A reinstated therapeutic code (45385) recomputes its conflict with the diagnostic base (45378) | PASS (IMPLEMENTED) | One base rule shared by the engine and the overlay (738df8dc4): `test_cux_review` ReinstatedBaseTests, D14Tests | Refutation round (lens L3) |
| [x] | 1.8 Checks recomputed after every selection, restoration, context change, reload and export | PASS (IMPLEMENTED) | Every reader reads the recomputed overlay (`review_view.py`, `review.effective_view`): `test_cux_review` StaleCheckTests, RejectAndRevokeTests, MemberAnswerTests; `test_cux_wire` MemberAnswerEffectTests, ApprovedExportMarkerTests | Live: decisions persist after reload (6.11) |
| [x] | 1.9 No approval through model agreement or hardcoded expected results | PASS (IMPLEMENTED) | Agreement never promotes (HARNESS.md I3; its tests green in the integrated suite); every expected result is a predeclared declaration row, never read by the code; only a member's or the agent's recorded decision approves |  |

## 2. Provider identities out of the customer experience

| | Item | Status | Evidence | Remaining action |
|---|---|---|---|---|
| [x] | 2.1 Customer screens use functional labels (Document review, Independent checks, Coding validation) in one compact progress panel | PASS (IMPLEMENTED) | The page (P6): one progress panel with the four steps and the three checks by function; `tests/frontend/app.test.cjs` (57), `test_customer_fixtures` (fixtures generated from the real serializer) | Live: desktop and mobile screenshots (6.6) |
| [x] | 2.2 Customer API responses carry no provider or model identity, usage, credits, request ids, hashes, rule ids or traces (enforced on the server) | PASS (IMPLEMENTED) | repaired: round 2 L4-4 (no source key on a customer surface); confirmed offline at 9ffbe9b53: full suite 5,778 Django + 524 ops + node, all pass; battery vs installed 41e03656df61 violations 72 to 2 (the two pinned), 0 new; round 3 confirmation 22 of 25 fixed, 3 recorded | Live scan (6.4) |
| [x] | 2.3 The customer bundle carries none of them | PASS (IMPLEMENTED) | repaired: round 2 L4-1 (no developer comment in the bundle); confirmed offline at 9ffbe9b53: full suite 5,778 Django + 524 ops + node, all pass; battery vs installed 41e03656df61 violations 72 to 2 (the two pinned), 0 new; round 3 confirmation 22 of 25 fixed, 3 recorded | Live scan (6.4) |
| [x] | 2.4 Customer downloads, notifications, accessibility labels and error messages carry none of them | PASS (IMPLEMENTED) | Customer reports (`cpt-studio-customer-report@1`), toasts, labels and error vocabulary (`customer_api.customer_error`) scanned in `test_customer_surface` ReportTests and ScenarioTests | Live: downloads scanned (6.4, 6.12) |
| [x] | 2.5 Platform-operator diagnostics keep full provenance, identities, usage, failures and audit history | PASS (IMPLEMENTED) | `/ops/` keeps the full encounter view, trace, reports, reconcile and originals: `test_operator` ConsoleLogicTests, `tests/operator/ops.test.cjs` (134) | Live: the walk's operator session (6.5) |
| [x] | 2.6 A workspace owner, reviewer or viewer is refused the diagnostic URLs and APIs | PASS (IMPLEMENTED) | repaired: round 2 L4-2, L4-3 (every /ops/ URL answers a non-operator as an unknown URL does); confirmed offline at 9ffbe9b53: full suite 5,778 Django + 524 ops + node, all pass; battery vs installed 41e03656df61 violations 72 to 2 (the two pinned), 0 new; round 3 confirmation 22 of 25 fixed, 3 recorded | Live (6.5) |
| [ ] | 2.7 Required disclosures kept accurate (none exists today; none removed) | BLOCKED | CPT Studio has no privacy or subprocessor page, and none was removed; after this change no customer screen names a subprocessor | Whether a disclosure is legally required is the owner's or legal question (decision (m)) |

## 3. Codes-first result

| | Item | Status | Evidence | Remaining action |
|---|---|---|---|---|
| [x] | 3.1 A short numbered list: code, units and modifier when applicable, status (Ready for review, Needs a detail, Approved, Excluded), one document-based sentence | PASS (IMPLEMENTED) | repaired: round 2 L3-8 and round 3 B-05 (a reinstated code or held visit never reads "Ready for review" without approve); confirmed offline at 9ffbe9b53: full suite 5,778 Django + 524 ops + node, all pass; battery vs installed 41e03656df61 violations 72 to 2 (the two pinned), 0 new; round 3 confirmation 22 of 25 fixed, 3 recorded | Live (6.6) |
| [x] | 3.2 Quotation and material qualification behind an optional "Why this code?" | PASS (IMPLEMENTED) | repaired: round 2 L3-7, L3-10: one quotation rule for the page and the approved export (review.evidence_spans), the tools accept exactly it; confirmed offline at 9ffbe9b53: full suite 5,778 Django + 524 ops + node, all pass; battery vs installed 41e03656df61 violations 72 to 2 (the two pinned), 0 new; round 3 confirmation 22 of 25 fixed, 3 recorded | Live (6.12) |
| [x] | 3.3 Review and download actions; suggested distinguished from approved | PASS (IMPLEMENTED) | Approve, reject, reinstate and revoke offered only as `allowed_actions`; the export dialog distinguishes the draft from the approved export; `test_cux_review`, app tests | Live (6.10) |
| [x] | 3.4 An approved export excludes unresolved and unapproved items and matches the persisted decisions | PASS (IMPLEMENTED) | repaired: round 2 L3-1, L3-3, L3-6 and round 3 B-02, B-04: the download check passes genuine exports (wrapped quotations included) and fails misstatements; the agent label on every agent approval in TXT and CSV; confirmed offline at 9ffbe9b53: full suite 5,778 Django + 524 ops + node, all pass; battery vs installed 41e03656df61 violations 72 to 2 (the two pinned), 0 new; round 3 confirmation 22 of 25 fixed, 3 recorded | Live: the downloaded export compared (6.12) |
| [x] | 3.5 Concise limitations; no claim of complete validation; no unlicensed descriptor shown as CPT content | PASS (IMPLEMENTED) | `customer_api.limitations`: fixed, true limitations; no descriptor text shown; no claim of complete validation |  |

## 4. Clarification flow

| | Item | Status | Evidence | Remaining action |
|---|---|---|---|---|
| [x] | 4.1 Irrelevant questions suppressed; stated facts resolved by the reader | PASS (IMPLEMENTED) | repaired: round 2 rule-8 narrowing and round 3 A5: relevant E/M questions kept; confirmed offline at 9ffbe9b53: full suite 5,778 Django + 524 ops + node, all pass; battery vs installed 41e03656df61 violations 72 to 2 (the two pinned), 0 new; round 3 confirmation 22 of 25 fixed, 3 recorded | Live (6.10) |
| [x] | 4.2 One compact "A few details needed" panel with choices, date selectors and brief confirmations | PASS (IMPLEMENTED) | One "A few details needed" panel (`detailsPanel`): date control, choices, confirmations; `test_cux_flow` DetailRowsTests, app tests | Live (6.6) |
| [x] | 4.3 "Not documented" and "Cannot confirm" where appropriate | PASS (IMPLEMENTED) | repaired: round 2 L7-01: a member answer never makes another code approvable (the overlay counts an answered-away code where it holds another); confirmed offline at 9ffbe9b53: full suite 5,778 Django + 524 ops + node, all pass; battery vs installed 41e03656df61 violations 72 to 2 (the two pinned), 0 new; round 3 confirmation 22 of 25 fixed, 3 recorded |  |
| [x] | 4.4 Each material question asked once; the saved answer kept | PASS (IMPLEMENTED) | repaired: round 2 L7-06 (a saved patient status closes its question), L7-08 (one question per service fact); confirmed offline at 9ffbe9b53: full suite 5,778 Django + 524 ops + node, all pass; battery vs installed 41e03656df61 violations 72 to 2 (the two pinned), 0 new; round 3 confirmation 22 of 25 fixed, 3 recorded |  |
| [x] | 4.5 Independent supported services stay reviewable while another awaits a detail | PASS (IMPLEMENTED) | Codes that do not depend on a detail stay reviewable: `test_cux_review`, `test_cux_flow` |  |
| [x] | 4.6 Date conflict: document date and entered date side by side, "Use document date"; no silent choice, no unsupported prefill | PASS (IMPLEMENTED) | repaired: round 2 L7-02, L7-03, L7-07 and round 3 B-01: an upload date choosing between documented dates is confirmed with both in view, the approved export waits for it, every date can be settled; confirmed offline at 9ffbe9b53: full suite 5,778 Django + 524 ops + node, all pass; battery vs installed 41e03656df61 violations 72 to 2 (the two pinned), 0 new; round 3 confirmation 22 of 25 fixed, 3 recorded |  |
| [x] | 4.7 Member context stored apart from the document, attributed and audited; no manufactured addendum, clinical fact or approval | PASS (IMPLEMENTED) | repaired: round 2 L7-05: a member's saved date can be corrected or cleared, attributed and audited; confirmed offline at 9ffbe9b53: full suite 5,778 Django + 524 ops + node, all pass; battery vs installed 41e03656df61 violations 72 to 2 (the two pinned), 0 new; round 3 confirmation 22 of 25 fixed, 3 recorded |  |
| [x] | 4.8 Modifier review for separately treated forceps/snare colon lesions from dated sources; never both 59 and XS; no payer-validation claim | PASS (IMPLEMENTED) | `test_cux_review` ModifierReviewTests: offered only for separately treated lesions, none/59/XS, never both, never prefilled, dated CMS sources, no payer-validation claim | Live: the walk's modifier plan (6.10) |

## 5. Upload and processing progress

| | Item | Status | Evidence | Remaining action |
|---|---|---|---|---|
| [x] | 5.1 Immediate upload acknowledgement; stages tied to backend state; active and completed stages, elapsed time | PASS (IMPLEMENTED) | Upload acknowledgement from the POST 201; four steps from the backend rows (`progress.encounter_progress`): `test_cux_flow` ProgressFoldTests | Live (6.7) |
| [x] | 5.2 Uploading, queued, processing, awaiting a detail, completed, partially completed and failed told apart | PASS (IMPLEMENTED) | repaired: round 2 L5-1, L5-3 and round 3 C-R3-1: an unknown outcome reads being confirmed, a reservation is settled, the stored state follows every save; confirmed offline at 9ffbe9b53: full suite 5,778 Django + 524 ops + node, all pass; battery vs installed 41e03656df61 violations 72 to 2 (the two pinned), 0 new; round 3 confirmation 22 of 25 fixed, 3 recorded | Live (6.7) |
| [x] | 5.3 No invented percentage or ETA; a truthful longer-than-expected message; no animation after failure | PASS (IMPLEMENTED) | repaired: round 2 L5-2, L5-4, L5-5, L5-6 and round 3 C-R3-4, C-R3-5: no stage reads done unless it was, paused only for a silent worker; confirmed offline at 9ffbe9b53: full suite 5,778 Django + 524 ops + node, all pass; battery vs installed 41e03656df61 violations 72 to 2 (the two pinned), 0 new; round 3 confirmation 22 of 25 fixed, 3 recorded | Live (6.7) |
| [x] | 5.4 Plain-language actionable errors without provider names or payloads; "Action needed" at once for a blocking date conflict | PASS (IMPLEMENTED) | Plain errors from a fixed table (`progress.ERRORS`, `customer_api.customer_error`); "Action needed" right after analyze for a date conflict, listed and counted at once (`test_cux_queue_recheck` DateHoldQueueTests) |  |
| [x] | 5.5 Progress and job identity kept across reload and reconnect | PASS (IMPLEMENTED) | The page polls the same encounter; an upload's client key makes a retry reach the same document: `test_cux_flow` UploadKeyTests | Live (6.8) |
| [x] | 5.6 A working Stop and safe recovery; unknown outcomes reconciled before any retry; no duplicate paid request | PASS (IMPLEMENTED) | repaired: round 2 L5-1: an unknown outcome never offers "upload again"; the re-check sends one bounded request; confirmed offline at 9ffbe9b53: full suite 5,778 Django + 524 ops + node, all pass; battery vs installed 41e03656df61 violations 72 to 2 (the two pinned), 0 new; round 3 confirmation 22 of 25 fixed, 3 recorded | Live (6.8) |

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
- 2026-11-04 (refutation round 2, seven lenses, every finding independently reproduced): 21 blocking and 22 major
  findings. The rows they refute went back from PASS (IMPLEMENTED) to FAIL above, with their finding ids; the install
  waits until they are repaired and re-verified. Installer defects (L6-1, L6-3: an interrupted nginx reload or a failed
  S4 undo could leave the site without a healthy upstream or run new-revision stages on the old worker; L6-2: the
  operators phase cannot run) are repaired before any install phase runs (6.14).
- 2026-11-04 (rounds 2 and 3 repaired and confirmed): the 19 rows round 2 refuted are repaired (seven owners in round 2,
  five in round 3, plus the integration's own follow-ups) and confirmed offline at 9ffbe9b53. They are PASS
  (IMPLEMENTED) again with that evidence; none says VERIFIED LIVE. Round 3, bounded to the round-2 repairs, held the head
  to never reading worse than installed. Its focused confirmation reran all 25 of its findings' own reproductions:
  22 fixed, 3 recorded (A3's 43239 is rule 4's declared cost, a false hold in one combined shape; A8 needs the frozen
  layout; C-R3-3 is worse only on a factory-built shape no real send makes).
- 2026-11-04 (verification after #1465 merged, session a12d8fb3): the first fresh walk document, unsealed once #1465's code froze, held all three of its codes on main and on installed; the gaps it exposed (numbered 'PROCEDURE N:' headings; the 'Label (site):' form) are recorded, not repaired. The refutation of a repair for them led the lead to probe main directly: four false READYs worse than installed (rows 1.1, 1.3 and 1.6: FAIL). Rounds 4 and 4b repaired them with word lists and were refuted 12 of 12; an unbinding form of R1a-r5 was refuted (it released diagnostic base codes); the hold-only form and its fixes (rounds 5, 5b, 5c, each refuted and its findings repaired or recorded) hold every shape without moving any cell toward READY against main. Rows 1.1, 1.3 and 1.6 are PASS (IMPLEMENTED) again with that evidence; none says VERIFIED LIVE. The second fresh document (f2), sealed before any of this work and never read by an agent, is the walk's held-out case.
