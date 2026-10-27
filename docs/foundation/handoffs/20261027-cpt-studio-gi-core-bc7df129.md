# Handoff: CPT Studio GI core, session bc7df129 (meddoc-pro-01), stopped at the usage limit 2026-10-27 ~04:40Z

Owner chose "Take over now"; 909be030 was stopped at 02:50:59Z (ruling file interpretation 18). Branch
fix/cpt-studio-gi-service-core-20261027, local only, NOTHING PUSHED. Live install unchanged (2734a6f3).

## State of this commit (WIP 4, NOT a green tree)
- WIP 3 (4db8b7ab) = the peer's leftovers. Full suite on WIP 3: 291 failing records / 129 tests (runs/wip3-a).
- Triage workflow wf_a5737261-c1a (9 read-only clusters + skeptics) - reports in
  /tmp/claude-1000/-opt-meddoc-pro/bc7df129-c1e5-42ac-bc52-4068c37c67be/scratchpad/gi-core/triage/<cluster>-triage/
  (patches) and the journal under ~/.claude/projects/-opt-meddoc-pro/bc7df129-.../subagents/workflows/wf_a5737261-c1a.
- MERGED here (3-way, conflicts resolved as unions; 993 tests in the merged clusters' modules: only expected fails):
  routing_level (combined-all), dates fix-1 + test edits (fix-2 REVERTED: refuted by its skeptic), hedges (all),
  reports (all), coverage (all + test edits), time_plan (fix-all), Release2 test kept with both procedure-line cases,
  no-send on a member-vs-document date conflict (jobs/models/review + test; interpretation 19 draft), reflow (reader
  reads soft line wraps as spaces; shares _answered_line and the extraction-block rule).
- UNTESTED in this commit: studio/gi/context.py T1 (only the FIRST dated title line can be the note's own date; a
  qualified first title gives no date) and T2 (a member value settles a document-internal conflict only by choosing a
  documented value). Probes for T1 passed; no suite run yet.
- NOT MERGED: boxes_pdf, boxes_text, facts_wording (their triage stopped before reporting; patches exist in their
  scratch dirs - read and verify them, do not trust unreported patches). Skeptic verdicts for reports, hedges,
  routing_level, coverage, time_plan were not received (only dates').

## Left (in order)
1. Lead repairs T3-T9: see the TODO list (copied below). T4/T6 are send-discipline must-fixes; T5 (NOT_VERB scope:
   "was tattooed and not removed" negates the tattoo, hiding a missed act) was found by two agents.
2. Merge boxes_pdf/boxes_text/facts_wording after verifying their patches; full suite (tools/full_suite.sh), corpus,
   format harness (ocr/tools/formats_harness.py in the dev image cpt-studio:dev-build; at WIP 3 PDF 13/43 and scan
   38/43 documents read differently from text; with reflow 6 and 23), then tests/test_services_formats_corpus.py
   (draft in scratch gi-core/newtests) with format_known_differences.json, and the OCR test (ocr/ocr-test.patch).
3. Record interpretations 19-21 (draft: scratch gi-core/ruling-additions.md) + ARCHITECTURE + ACCURACY-RESIDUALS.
4. Refutation pass on the finished diff (9 lenses; template scratch gi-core/refute/peer-original.js), repairs re-attacked.
5. PR (body via file), CI (CI, cpt-studio, secrets-scan), merge-pr.sh; declaration
   docs/foundation/mutations/20261027-cpt-studio-gi-core-upgrade.md in its own PR (counts baseline: tools/live_counts.sh,
   03:23Z: encounters 11, proposals 134, decisions 15, audit 108, jobs 44/0 active, migrations 5, credits 0.504880);
   install phases preflight, image, app (--provider-mode live --authorization-ref the ruling file), verify.
6. Live walk with the held-out set (scratch of 909be030: gi-core/heldout + heldout-out, integrity verified), then
   ops/verify_downloads.py, usage, final report.
# Lead repairs after the triage merges (bc7df129)
T1 dates: fix-2 reverted (skeptic: it drops the note's own qualified title and keeps another document's date).
   Replace with: only the FIRST title-like line in the top lines can be the note's own dated title; a qualified first
   title gives no title date; any other dated title-like line makes the date a question, never a value.
   Closes HEAD's 'GI follow-up visit: 2026-10-20' + 'Pathology report: 2026-10-14' -> 2026-10-14 sent to the provider.
T2 dates: a member value against a DOCUMENT-INTERNAL conflict must equal one documented value; otherwise a member
   conflict (both sides kept). Elena-class: member 1998-01-01 vs two documented dates -> ready with 1998 sent.
T3 dates fix-1 scope: member-conflict wording also in services._em_service and reconcile.documentation_clarifications.
T4 sends: no second review while the service date is unknown; a dated act clause with no known service date reads
   uncertain (a phantom performed colonoscopy from 'Colonoscopy 2026-09-03: ...' triggered a paid second review).
T5 reader: NOT_VERB scope - a 'not' on another predicate never negates the act ('was tattooed and not removed',
   'if intake does not improve'); hidden missed acts (hedges + time_plan agents).
T6 sends: no second review after a primary response that was refused whole (reports triage residual, jobs.py
   _maybe_second_review checks only run.state).
T7 Declared6 (neutral 'Additional procedures:' label): UNCLEAR, over-hold kept; record as a known limit.
T8 formats: rerun the harness on the integrated tree; write format_known_differences.json; add the format tests.
T9 docs: interpretations 19-21 (+ any for T1-T6), ARCHITECTURE, ACCURACY-RESIDUALS.
