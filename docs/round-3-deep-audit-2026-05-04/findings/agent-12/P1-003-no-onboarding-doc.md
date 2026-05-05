---
id: A12-P1-003
title: No engineer onboarding doc; zero-to-productive path requires reading 7+ scattered files
severity: P1
domain: docs/onboarding
---

# Issue

QuillMD is a single-engineer codebase. Memory note flags that "when the next engineer joins, or when an incident strikes at 2 AM, docs must be enough." There is no onboarding document. A new engineer arriving today must reverse-engineer the entry points by reading at least seven different documents — README, AGENTS.md (effectively empty), CLAUDE.md (11 bytes — placeholder), DEPLOYMENT_RUNBOOK, ROTATION_RUNBOOK, BAA_CHECKLIST, KNOWN_ISSUES, POST_MERGE_TODO — none of which were written for an onboardee.

# Evidence

- `CLAUDE.md` is **11 bytes**: contains literally `@AGENTS.md` (a delegation marker). Memory says "should it have more?" Yes — it's a candidate location for the onboarding doc itself, or a ToC pointing to one.
- `AGENTS.md` is 28 lines and contains exclusively the "preflight-gate" + "nextjs-agent-rules" automation rules — nothing for a human engineer.
- `README.md` is the closest thing to onboarding (159 lines):
  - Architecture overview (good)
  - Local dev setup (5 commands — good but stale: claims 8 containers, actual is 9 — see A12-P2-002)
  - Tests section: `cd apps/transcribe-md && npx vitest run` etc. Does not mention the worker, the health endpoint, or how to reset the local DB.
  - No mention of Phase 6.1 LUKS setup, Phase 6.2 backup-script presence, the qa-bug-hunter skill v1.1, or how Server Actions vs API routes are distributed in the codebase.
- The "first-week monitoring routine" in `KASRA_HANDOFF.md` is owner-shape, not onboardee-shape.

The gaps a newly-arrived engineer hits in the first hour, by area:

1. **Where do I start dev?** README has the commands. Does it work as-is? The `npm install` + `docker compose up -d` + `db-migrate` flow works on a clean checkout but not on the current production VPS (LUKS-mounted /mnt/pgdata-encrypted, `secrets/`, `.env.phase-6.2.template`).

2. **How do I run the test suite I'll need to keep green?** README mentions vitest + playwright. Does not mention: `npm run test:all` per workspace, the GitHub Actions matrix, the a11y axe-core sweep on `app.quillmd.com`, the `qa-bug-hunter` v1.1 structural assertions, the `merge-prep` skill that runs on parallel port 8766.

3. **What's the production stack?** Can find it in pieces: README says "8 containers", PILOT_STATUS says "9/9", LAUNCH_READINESS lists each container with its UID. There's no canonical stack-overview-for-engineers doc.

4. **What slash commands / skills should I know?** Found inside `~/.claude/skills/qa-bug-hunter/SKILL.md` per POST_MERGE_TODO §10 — this is in the user's home, not the repo. New engineer doesn't know it exists.

5. **What's the deploy model?** README points at `DEPLOYMENT_RUNBOOK.md`. That runbook is targeted at first-time deploy + rolling update + rollback, not at "I want to ship a one-line doc fix and not break prod."

6. **What's the safe-changes ladder?** `KASRA_HANDOFF.md` Tier 1/2/3 rollback is the closest. Pre-flight check skill exists in `AGENTS.md` as a gate; without context, an onboardee won't run it.

7. **Where's secrets / how do I rotate?** ROTATION_RUNBOOK exists, well-written. Discoverability is OK if you read README §"Production deploy" closely.

8. **Where's the production state today?** Multiple sources, partially conflicting:
   - `PILOT_STATUS.md` is dated 2026-04-27 — pre-Phase-6.1, pre-Phase-7, pre-§21 decommission, pre-Phase-6.2.
   - `LAUNCH_READINESS.md` is dated 2026-04-26 — even older.
   - `LAUNCH_CHECKLIST.md` "last reviewed 2026-04-22".
   - `POST_MERGE_TODO.md` §22 is the authoritative current state.
   A new engineer finds the older docs first and learns wrong things.

9. **What's decommissioned vs active?** README §1 is good — calls out meddoc-pro as decommissioned. POST_MERGE_TODO §21 is the long-form. Nothing else makes the boundary explicit; an engineer might still try to run `apps/meddoc-pro` tests and find the no-op echo.

10. **What's the current pre-pilot blocker list?** LAUNCH_CHECKLIST has gates 3, 4, 6, 7, 8, 9 unchecked. POST_MERGE_TODO §22 has Phase 6.2 activation pending. Both lists are accurate but neither is "the one place new engineer reads to know what's still in flight."

# Risk

- **Pilot-launch timing**: a new engineer cannot help close the LAUNCH_CHECKLIST gates without first absorbing the entire history. That's a fixable cost.
- **2-AM-incident**: if Kasra is unreachable and a contractor must respond, the 7-file scavenger hunt costs ~2 hours of recovery time.
- **Knowledge concentration**: every undocumented decision is a key in Kasra's head. The longer the project runs, the more keys, the higher the bus-factor risk.
- **Compliance**: HIPAA §164.308(a)(5)(ii)(A) requires a security-awareness training program. The current "training" is "read the repo." Auditable training requires a written curriculum.

# Recommended fix

Create `docs/ONBOARDING.md` (or replace the 11-byte `CLAUDE.md` with this content + a link). Target: zero-to-productive in 2 hours. Sections:

1. **What QuillMD is** — 2 paragraphs, link README §1.
2. **Architecture in one diagram** — Mermaid in markdown OR a PNG checked into `docs/`. 9 containers + Anthropic + Deepgram + Resend + Backblaze. (See A12-P2-001 for the architecture-diagram finding.)
3. **Stack at a glance** — table: tech, version, why. Next.js 16, Postgres 16+pgvector, Redis 7, MinIO, Caddy, BullMQ, NextAuth v5, Prisma, age, b2, Sentry.
4. **Local dev — 30-minute path** — same shape as README §"Local dev setup" but updated commands (9 containers, MOCK_AI_CALLS, db seed, the test commands). Mark explicitly which commands work on the production VPS vs only on a fresh clone.
5. **Tests — what should be green** — vitest counts, playwright scenarios, a11y axe-core, qa-bug-hunter v1.1 assertions per tab, the structural-DOM assertions added in Phase 5.1.1.
6. **Where things live** — apps/ vs packages/, server actions vs API routes, the worker layers (1-7), the shared `@meddoc/ai` `redactPhi`. Decommissioned scope (`apps/meddoc-pro/*`) called out.
7. **First contributions to make** — the LAUNCH_CHECKLIST gates that an engineer can plausibly close: §6 (rotate OPENAI_API_KEY), §8 (Sentry alerts), §10 follow-ups. POST_MERGE_TODO §22 step 11.
8. **Slash commands / skills** — the `merge-prep-clinician`, `qa-clinician-remodel`, `qa-bug-hunter`, `preflight-health-check`, `hipaa-agent` skills. Where to find their `SKILL.md` files. When to run each.
9. **Deploy** — link to DEPLOYMENT_RUNBOOK; flag the "sequential build" rule from memory; flag the cache-prune-before-build rule.
10. **Rotation, BAAs, HIPAA** — link to BAA_CHECKLIST, ROTATION_RUNBOOK, HIPAA_COMPLIANCE; flag that public legal pages are still drafts (per A12-P0-001).
11. **Where to find current state** — POST_MERGE_TODO is the source-of-truth; PILOT_STATUS / LAUNCH_READINESS are historical snapshots.
12. **Who to ask** — `support@ashtechgroup.com`, the compliance email aliases.

Add `CLAUDE.md` to point at it (replace `@AGENTS.md` with `@AGENTS.md @docs/ONBOARDING.md`). Add a row to README §"Architecture at a glance" linking the new doc.

Once written, the doc itself becomes a regression target: every milestone PR should ask "did this change anything an onboardee needs to know?" and update accordingly.
