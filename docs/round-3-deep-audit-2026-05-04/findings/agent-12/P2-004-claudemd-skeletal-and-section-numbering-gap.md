---
id: A12-P2-004
title: CLAUDE.md is 11-byte placeholder; POST_MERGE_TODO has §5 missing + §11.5 misplaced; legal pages flag draft state but don't expire
severity: P2
domain: docs/structure
---

# Issue

Three smaller structural-quality problems that don't individually block the pilot but collectively reduce documentation usefulness.

# Evidence

**1. `CLAUDE.md` is an 11-byte placeholder.**

`cat /opt/meddoc-pro/CLAUDE.md` →
```
@AGENTS.md
```
Total: 11 bytes (10 chars + newline). Memory note flags it: "should it have more?". Per Claude Code convention, `CLAUDE.md` is the project-context entry point for AI agents. The current `@AGENTS.md` redirect works as a delegation marker — but `AGENTS.md` itself is 28 lines of automation-only guidance (preflight gate + nextjs-agent rules), not project context.

A useful `CLAUDE.md` for QuillMD should additionally contain:
- The decommission line (meddoc-pro DECOMMISSIONED 2026-05-04, scope = QuillMD = transcribe-md + marketing).
- The active-branch convention (`chore/round-3-deep-audit-2026-05-04`, `feature/clinician-remodel`, etc.).
- The "9 containers, 1 VPS, single-engineer" constraint set.
- The "balloon blacklist + RAM regression" memory note as a safety constraint (per memory).
- Pointer to ONBOARDING.md (when it exists, per A12-P1-003).
- Pointer to THREAT_MODEL.md + ADR index (when they exist, per A12-P1-004).

**2. `POST_MERGE_TODO.md` has structural gaps.**

`grep -n '^## ' docs/POST_MERGE_TODO.md` shows:
- §1 ✅
- §2 ✅
- §3 (a11y pass)
- §4 (Reserved)
- §5 — MISSING
- §6 dashboard mockup-fidelity
- ...
- §23 ✅
- **§11.5** placed at the end (line 1413), AFTER §23

The numbering is non-monotonic: §5 is missing entirely, §11.5 appears after §23. The doc's own §22 step 11 says "Update §22 status here from ⏳ pending → ✅ active" — section anchors matter for status-flip references.

§24 ("where Round 3 audit summary lands per audit prompt") does not exist yet — not a finding per se since the round-3 audit is still in progress, but the prompt explicitly mentions §24 as a prepared landing-pad and the doc is unprepared.

**3. Legal pages are flagged "[DRAFT — PENDING LEGAL REVIEW]" with no expiry / no owner / no review cadence.**

`apps/marketing/src/app/privacy/page.tsx:63-74`, `apps/marketing/src/app/terms/page.tsx:59-71`, `apps/marketing/src/app/hipaa/page.tsx:49-58` all have:
```tsx
<strong>[DRAFT — PENDING LEGAL REVIEW]</strong>
<p>This document is a placeholder structure. The content below is an
   operational summary of how we handle data; it has not yet been
   reviewed by counsel...</p>
```

`LAST_UPDATED = '2026-04-20'` — these were drafted ~2 weeks ago. The disclaimer banner is good (and matches LAUNCH_CHECKLIST §7 "[ ] Legal docs reviewed + published") — but it has no:
- Expected resolution date
- Named owner (Kasra? counsel TBD?)
- Action required (which counsel? which contract terms?)
- Mechanism to flip the banner once counsel-reviewed

Combined with A12-P0-001 (the BAA over-statement), the draft state of these pages is also a vector for misrepresentation: a Covered Entity who reads the privacy page may take "[DRAFT — PENDING LEGAL REVIEW]" as a procedural disclaimer rather than as a flag that the body content is unverified.

# Risk

- **`CLAUDE.md`**: agents (Claude Code instances) entering the repo without context from a parent agent get an empty entry point. They fall back to scanning README/AGENTS, missing decommission state, missing the "single-engineer / 5.6 GB RAM / 296 GB disk" envelope, missing the active branch.
- **POST_MERGE_TODO numbering**: §22 step 11 "Update §22 status here" is fine; the next operator searching for "§5" or "§24" finds nothing. Tedious but auditable.
- **Legal-page draft state**: indefinite "[DRAFT]" is a smell. Either ship reviewed content or commit to a date.

# Recommended fix

**`CLAUDE.md`** — extend to ~50-100 lines covering:
- Active scope (QuillMD = transcribe-md + marketing, meddoc-pro decommissioned)
- Operating envelope (9 containers, single VPS, RAM constraint, disk constraint per memory)
- Active branch convention + how round-3 audit ladders into POST_MERGE_TODO
- Pointer to AGENTS.md (preflight gate)
- Pointer to ONBOARDING.md (when it exists)
- Pointer to THREAT_MODEL.md + ADR index (when they exist)
- Pointer to POST_MERGE_TODO §22 (open work)
- Pointer to LAUNCH_CHECKLIST gates (open pre-pilot blockers)

**`POST_MERGE_TODO.md`** —
- Either fill §5 with a placeholder ("§5 — Reserved for Round 1 audit follow-ups (no items surfaced)") or renumber §6+ down by one. Renumbering is risky because of cross-references; placeholder is safer.
- Move §11.5 inline between §11 and §12 where it logically belongs.
- Pre-create §24 ("Round 3 deep-audit summary lands here") with a one-line placeholder so this doc is ready when the audit synthesis lands.

**Legal-page draft banner** —
- Add "Owner: Kasra (until counsel engaged), then <counsel firm>", "Expected resolution: <date>", "Last reviewed: 2026-04-20".
- LAUNCH_CHECKLIST §10 "Blockers" already lists "Legal counsel retained — 2-4 week lead time." Sync the date there with the page banner.
- Auto-render the banner from a single source: a `MetadataBanner` component reading from a JSON manifest in `apps/marketing/src/app/_legal/draft-status.json`. Then a single edit promotes a doc from draft → reviewed across all surfaces.
- Once counsel-reviewed, replace the banner with `<p>Last counsel review: <date>. Next review: <date+12mo>.</p>`.

For all three — none individually requires more than an hour. Together they raise the floor of doc quality to "an outsider can navigate without confusion."
