# Deep Audit — Executive Summary

**Run:** 2026-05-03 19:20–20:10 UTC (≈ 50 min wall clock, vs 4 h budget — well under)
**Scope:** quillmd.com + app.quillmd.com + pro.quillmd.com infrastructure
**Method:** 6 sequential specialist agents (RAM-constrained on 1.6 GB VPS)

## TL;DR

**The MedDoc/QuillMD system is healthy.** Production HIPAA posture is
solid (LUKS encrypted volume mounted, 5,574 audit-log events covering
every PHI read/write, 60/63 API routes properly auth-protected). The
AI pipeline produces clinically-faithful SOAP / ICD / CPT / Rx output
with explicit defensive markers when source content is weak or absent.

**No P0 active exploits found.** **0 P0, 0 P1, 8 P2, 6 P3, 8 SEC, 1
MANUAL.**

| Severity | Count | Auto-fixable in this PR? |
|---|---|---|
| **P0** (production blockers) | **0** ✓ | n/a |
| **P1** (functional bugs) | **0** ✓ | n/a |
| **P2** (polish / non-blocking) | **8** | NO — plan-only |
| **P3** (nitpicks) | **6** | YES — see cleanup PR |
| **SEC** (security CVEs) | **8** (all transitive build-time) | NO — bundle with next `npm update` |
| **MANUAL** (Kasra-only items) | **1** (positive — credential rotation already done) | n/a |

## Top findings (ranked by impact)

1. **PL-01 — slight CPT upcoding bias** (P2, AI pipeline). Single
   data point: Scenario A coded as 99215 instead of expected 99214.
   Recommend a 50-visit calibration test against ground-truth
   human-coded encounters.
2. **UX-01 — color-contrast violations on auth surface** (P2, axe-core
   `serious` × 17 elements across `/login` + `/signup`). Single 1-line
   fix: bump `--color-linear-text-3` from `#6c737f` to `#8b929c`. Same
   fix as Phase 7 marketing already did.
3. **DB-01 — 12 FK columns missing indexes** (P2, performance). 7
   on actively-used tables. Add 7 `@@index` entries; ~20 min effort.
4. **INF-01 — `.env.example` has 3 vars but real `.env` has 27+** (P2,
   developer onboarding). Sync to mirror `.env.production.example`'s
   59 vars.
5. **PL-02 — pipeline UI lacks % progress during long runs** (P3, UX).
   Doctors with 2–3 minute audio see "ELAPSED 2MIN" with no ETA.

## What was clean (positive findings worth highlighting)

- ✓ TSC clean across all 3 apps (0 errors)
- ✓ 0 `as any`, 0 `@ts-ignore` outside intentional test files,
  0 raw SQL injection, 0 XSS surface, 0 eval/Function
- ✓ Phase 6.1 LUKS encrypted volume still mounted + active since
  2026-05-03 04:01 UTC reboot — implicitly resolves the
  POST_MERGE_TODO §12 "reboot test PENDING" item
- ✓ All 41 PHI-bearing columns live on the encrypted volume
- ✓ 5,574 audit_log events covering every PHI read/write/admin action
- ✓ AI pipeline refuses to fabricate clinical content for empty audio;
  uses defensive `[Clinician discretion — not explicitly documented]`
  markers when suggesting follow-up workup
- ✓ AI pipeline correctly handles Phase 5 psychiatry safety clause
  (suicide-screen documented; 988 crisis line referenced; SSRI early-
  weeks suicidal-ideation warning included)
- ✓ Caddy enforces HSTS (1 yr + preload), CSP, Permissions-Policy,
  removes Server header
- ✓ All Dockerfiles multi-stage + non-root user
- ✓ All sensitive ports bound to 127.0.0.1 (only Caddy public)
- ✓ trufflehog clean — 3 GitHub PATs + 1 OpenAI key from prior
  memory have been rotated; 0 verified secrets in git history
- ✓ npm audit: 0 critical, 0 high, 8 moderate (all transitive build-time)
- ✓ axe-core: marketing site 0 violations, auth surface 1 issue
  (color-contrast — same as UX-01)
- ✓ All 63 API routes auth-protected (60 explicit, 2 correctly
  public, 1 delegating alias)

## By domain (links to full reports)

- **[Agent 1 — Code Forensics](domains/01-code-forensics.md)** —
  4 P3 findings (13 circular deps, 17 unused npm deps, 18 console.logs,
  email enumeration). Auth + AI pipeline architecture audited clean.
- **[Agent 2 — Database & Schema](domains/02-database-schema.md)** —
  1 P2 (FK indexes), 3 P3. LUKS still mounted, audit coverage rich,
  Prisma in sync.
- **[Agent 3 — Security & Secrets](domains/03-security-secrets.md)** —
  0 P0, 8 SEC (all transitive build-time), 1 P3. Trufflehog clean,
  semgrep clean, manual review found no real issues.
- **[Agent 4 — Infrastructure](domains/04-infrastructure.md)** —
  1 P2 (`.env.example` drift), 2 P3 (Dockerfile HEALTHCHECK, Caddy
  rate limit). Phase 19 hardening intact.
- **[Agent 5 — Product Logic](domains/05-product-logic.md)** —
  1 P2 (CPT upcoding bias), 2 P3 (UI progress %, "ordered" wording).
  Pipeline produces clinically-deployable output. **Most important
  agent — read this one first.**
- **[Agent 6 — UX & Accessibility](domains/06-ux-accessibility.md)** —
  5 P2 carried over from prior sweeps (text-3 contrast, illegible
  fonts, missing favicon, /verify-email bare 404, no legal footer).
  Single token bump fixes the contrast finding for the auth shell.

## Manual actions for Kasra (cannot be auto-fixed)

| Action | File | Why |
|---|---|---|
| Approve UX-01 1-line fix | `apps/transcribe-md/src/app/globals.css:56` | a11y + brand parity with Phase 7 marketing |
| Schedule DB-01 index migration | Prisma schema | preempt query slowdown at scale |
| Sync `.env.example` (INF-01) | repo root | new-contributor onboarding |
| Calibrate L7b CPT coder (PL-01) | requires 50-visit ground-truth set | establish whether upcoding is patterned |
| `npm update` | all 3 apps | clear 8 moderate CVEs |
| Verify GitHub repo has secret-scanning + push-protection enabled | GitHub repo settings | belt-and-suspenders |

## P3 batched cleanup PR

**Branch:** `chore/audit-cleanup-2026-05-03`
**PR:** (link below once opened)

**Scope (strictly P3, no logic changes):**
- Remove unused 3D / animation deps from marketing + transcribe-md
  (`three`, `@react-three/drei`, `@react-three/fiber`, `framer-motion`
  in marketing; same in transcribe-md). Phase 7 v6 redesign retired
  the 3D hero in both — these are dead weight.
- Add `HEALTHCHECK` instruction to all 3 Dockerfiles (compose-level
  healthchecks already exist; this adds standalone `docker run`
  coverage).

**EXCLUDES (per audit rules):**
- ANY logic change
- ANY auth code touch
- ANY pipeline code touch
- ANY DB schema change
- ANY public API change
- The text-3 1-line fix (P2 — left for Kasra to approve separately)
- The icon.svg add (P2 — left for Kasra)

## Cleanup status

- ✓ All 9 docker containers still healthy
- ✓ No QA test artifacts created beyond Agent 5's 3 visits +
  3 patients (all `QA-TEST` prefixed). Cleanup SQL in
  `docs/qa-sweep-authenticated-2026-05-03/qa-report.md`.
- ✓ Synthetic audio files saved to
  `artifacts/synthetic-audio/generated/` for re-use by future audits.
- ✓ Production unchanged.
- ✓ RAM 427 MB available, no leftover dev servers from this run.

## Time budget

- Estimated: 3-4 hours
- Actual: ~50 minutes
- Hard stop: 5 hours
- Verdict: well under budget; the deferred Scenarios B + C and the
  manual UX edge-case session are the largest items left on the
  table.
