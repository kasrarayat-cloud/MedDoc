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
| [ ] | 1.1 Statement binding to procedure, lesion, anatomy, action, time and provider repaired as a general rule | NOT RUN | | |
| [ ] | 1.2 Negation kept within its scope (a distinguishing sentence negates nothing it only names) | NOT RUN | | |
| [ ] | 1.3 Acts assigned to the procedure that performed them (the COL-2 clip, COL-1/COL-2 sentences) | NOT RUN | | |
| [ ] | 1.4 An explicitly absent separate E/M service asks no E/M question | NOT RUN | | |
| [ ] | 1.5 Genuine uncertainty and conflicting documentation still held (round-4 standard: must-stay-held inputs stay held) | NOT RUN | | |
| [ ] | 1.6 False READYs on failed, negated, historical or wrong-procedure evidence reproduced and repaired | NOT RUN | | |
| [ ] | 1.7 A reinstated therapeutic code (45385) recomputes its conflict with the diagnostic base (45378) | NOT RUN | | |
| [ ] | 1.8 Checks recomputed after every selection, restoration, context change, reload and export | NOT RUN | | |
| [ ] | 1.9 No approval through model agreement or hardcoded expected results | NOT RUN | | |

## 2. Provider identities out of the customer experience

| | Item | Status | Evidence | Remaining action |
|---|---|---|---|---|
| [ ] | 2.1 Customer screens use functional labels (Document review, Independent checks, Coding validation) in one compact progress panel | NOT RUN | | |
| [ ] | 2.2 Customer API responses carry no provider or model identity, usage, credits, request ids, hashes, rule ids or traces (enforced on the server) | NOT RUN | | |
| [ ] | 2.3 The customer bundle carries none of them | NOT RUN | | |
| [ ] | 2.4 Customer downloads, notifications, accessibility labels and error messages carry none of them | NOT RUN | | |
| [ ] | 2.5 Platform-operator diagnostics keep full provenance, identities, usage, failures and audit history | NOT RUN | | |
| [ ] | 2.6 A workspace owner, reviewer or viewer is refused the diagnostic URLs and APIs | NOT RUN | | |
| [ ] | 2.7 Required disclosures kept accurate (none exists today; none removed) | NOT RUN | | |

## 3. Codes-first result

| | Item | Status | Evidence | Remaining action |
|---|---|---|---|---|
| [ ] | 3.1 A short numbered list: code, units and modifier when applicable, status (Ready for review, Needs a detail, Approved, Excluded), one document-based sentence | NOT RUN | | |
| [ ] | 3.2 Quotation and material qualification behind an optional "Why this code?" | NOT RUN | | |
| [ ] | 3.3 Review and download actions; suggested distinguished from approved | NOT RUN | | |
| [ ] | 3.4 An approved export excludes unresolved and unapproved items and matches the persisted decisions | NOT RUN | | |
| [ ] | 3.5 Concise limitations; no claim of complete validation; no unlicensed descriptor shown as CPT content | NOT RUN | | |

## 4. Clarification flow

| | Item | Status | Evidence | Remaining action |
|---|---|---|---|---|
| [ ] | 4.1 Irrelevant questions suppressed; stated facts resolved by the reader | NOT RUN | | |
| [ ] | 4.2 One compact "A few details needed" panel with choices, date selectors and brief confirmations | NOT RUN | | |
| [ ] | 4.3 "Not documented" and "Cannot confirm" where appropriate | NOT RUN | | |
| [ ] | 4.4 Each material question asked once; the saved answer kept | NOT RUN | | |
| [ ] | 4.5 Independent supported services stay reviewable while another awaits a detail | NOT RUN | | |
| [ ] | 4.6 Date conflict: document date and entered date side by side, "Use document date"; no silent choice, no unsupported prefill | NOT RUN | | |
| [ ] | 4.7 Member context stored apart from the document, attributed and audited; no manufactured addendum, clinical fact or approval | NOT RUN | | |
| [ ] | 4.8 Modifier review for separately treated forceps/snare colon lesions from dated sources; never both 59 and XS; no payer-validation claim | NOT RUN | | |

## 5. Upload and processing progress

| | Item | Status | Evidence | Remaining action |
|---|---|---|---|---|
| [ ] | 5.1 Immediate upload acknowledgement; stages tied to backend state; active and completed stages, elapsed time | NOT RUN | | |
| [ ] | 5.2 Uploading, queued, processing, awaiting a detail, completed, partially completed and failed told apart | NOT RUN | | |
| [ ] | 5.3 No invented percentage or ETA; a truthful longer-than-expected message; no animation after failure | NOT RUN | | |
| [ ] | 5.4 Plain-language actionable errors without provider names or payloads; "Action needed" at once for a blocking date conflict | NOT RUN | | |
| [ ] | 5.5 Progress and job identity kept across reload and reconnect | NOT RUN | | |
| [ ] | 5.6 A working Stop and safe recovery; unknown outcomes reconciled before any retry; no duplicate paid request | NOT RUN | | |

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
