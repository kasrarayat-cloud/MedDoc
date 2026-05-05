---
id: A12-P3-001
title: Polish batch — typos, contractor formatting, dead cross-references, draft date drift
severity: P3
domain: docs/polish
---

# Issue

Cosmetic polish issues across the docs corpus. None block pilot, none are urgent. Listed for cleanup-batch when an engineer has 30 minutes between milestones.

# Evidence

**1. `docs/RUNBOOK_OFFSITE_BACKUP.md` references a section number incorrectly.**

§D.1 (line 372) describes "Tertiary" key copy. §D.4 (line 444) — "Q: Both the VPS AND the B2 bucket are gone…" — answers "Most recent backup = whatever's in the **paper** tertiary copy + Hetzner mirror". §G resolution checklist (line 549) refers to "C.* restoration drill" which is correct, but at line 549 the format `(C.*)` is mixed with prior `(A.5, D.1)` — minor inconsistency.

**2. `docs/HIPAA_COMPLIANCE.md` references a runbook with a wrong path.**

Line 24 evidence column: `[docs/RUNBOOK_ENCRYPTED_VOLUME.md](RUNBOOK_ENCRYPTED_VOLUME.md)` — fine. Line 191 closing reference: `[docs/RUNBOOK_OFFSITE_BACKUP.md §D](RUNBOOK_OFFSITE_BACKUP.md)` — but §D in RUNBOOK_OFFSITE_BACKUP is "Key custody", and the rotation procedure is in §E. Should be `§E`.

**3. `docs/LAUNCH_CHECKLIST.md` "last reviewed" date drift.**

Header (line 14): "Last reviewed: **2026-04-22**". The doc was clearly touched after 2026-04-22 because it references several Phase 5 / Phase 7 items that landed on 2026-05-01..2026-05-03. The "last reviewed" stamp should track the most-recent significant edit.

**4. PILOT_STATUS.md is dated 2026-04-27 — significantly stale.**

Line 1 stamp: "QuillMD pilot-ready snapshot — 2026-04-27". Subsequent shipped milestones (Phase 6.1 LUKS migration on 2026-05-02, decommission §21 on 2026-05-04, Phase 7 landing-v6 on 2026-05-03) are not reflected. The "Open findings" table claims `h8-h3-pilot-followup` open — it was superseded by Phase 6.1 (postgres encrypted via LUKS on 2026-05-02). Either re-date the snapshot or add a "superseded" note.

**5. `LAUNCH_READINESS.md` similarly stale.**

Header line 2: "Compiled 2026-04-26 by the Phase 9 final launch sequence". Document-history section ends at Phase 14 (2026-04-26). Phase 6.1, Phase 7, decommission, Phase 6.2 — all post-dated and uncovered. Either add later entries to "Document history" or add a "this snapshot is historical; current state lives in POST_MERGE_TODO" banner at the top.

**6. Backtick code-fence imbalance scan.**

Spot-check of `POST_MERGE_TODO.md` paragraph counts looks balanced; full-doc `awk` of triple-backtick parity not done in this review.

**7. `tests/automated/FIXTURES.md` and `tests/automated/README.md` exist** but are not cross-linked from any project-level doc. Onboardees won't know they exist.

**8. `docs/COMPONENT_INVENTORY.md`, `docs/CLINICIAN_MIGRATION_ORDER.md`, `docs/DESIGN_TOKENS.md`** — design-system docs that were used during Phase 5/6/7 remodels. Likely no longer load-bearing post-Phase-7. Either deprecate them with a top-of-file banner or keep them with a "stable as of <date>" stamp.

**9. `KASRA_HANDOFF.md` "first-week monitoring routine"** still references admin findings list with `h8-h3-pilot-followup`, `h8-h4-pilot-followup`, `h9-meddoc-e2e-residual`. Per `LAUNCH_READINESS.md` finding matrix, three are now resolved (only `h8-h3-pilot-followup` and `h13-meddoc-e2e-tenancy-residual` open at the LAUNCH_READINESS dating; per Phase 6.1 even h8-h3 superseded). Update the "Should still be the 3 expected" list to current state.

**10. Multiple docs use "MedDoc Pro" / "TranscribeMD" / "QuillMD" naming inconsistently.**

The product is now QuillMD. Phase 5/6/7 prose uses the new name; older docs use TranscribeMD; the meddoc-pro CRM is decommissioned but its name lingers in service IDs (`meddoc-pro-meddoc-pro-1`). T-M20.2 (POST_MERGE_TODO §13 lesson) explicitly says: "Internal identifiers (Docker services, package names, DB schemas, enum values, code comments) explicitly left alone..." — that's a deliberate choice. But user-facing docs should be consistent: every reference to TranscribeMD should be QuillMD or "QuillMD (formerly TranscribeMD)".

**11. `docs/A11Y_TESTING.md`** — file was NOT inspected in this review (token budget). Skim-read in a follow-up cleanup pass.

**12. README.md "Issues or questions: support@ashtechgroup.com (also the NextAuth admin address)."** — the parenthetical is internal trivia that's not useful to a public reader. Drop or move to a "for engineers" sub-section.

**13. The `LAUNCH_ANNOUNCEMENT.md`** file at root is a one-shot pilot launch announcement. Still useful as a historical artifact; consider moving to `docs/launches/` with a date stamp.

# Risk

Each item is cosmetic. Aggregate effect: doc set looks under-maintained, which propagates the perception that operational rigor is similarly under-maintained.

# Recommended fix

Single batch PR doing items 1-10, 12-13. Estimated 30-45 minutes of editing work. No cross-domain coordination needed.

For the deprecation banner pattern (item 8), use the same `[STABLE — last reviewed YYYY-MM-DD]` shape as the legal-page draft banner from A12-P2-004 — single source-of-truth manifest if possible.

For naming consistency (item 10), `grep -nE '\bTranscribeMD\b' docs/ apps/transcribe-md/WORKER.md README.md` produces a hit list. Replace with `QuillMD` except in historical phase-prose and explicit "formerly TranscribeMD" mentions.
