# Transcribe-MD Remodel — Phase 1 Plan

Generated: 2026-04-29
Scope: `apps/transcribe-md` frontend only (covers `app.quillmd.com` and `admin.quillmd.com` — same Next.js app).
Out of scope: `apps/marketing`, `apps/meddoc-pro`, all backend logic (API routes, server actions, hooks, DB, workers, AI pipeline, auth).

Reference: `/opt/meddoc-pro/docs/REMODEL_AUDIT.md`.

---

## Decisions made by the lead agent (no user roundtrip)

The audit identified three open questions (§9, items 2/4/2 — design-system reconciliation, migration strategy, state). The lead agent made each call below. The user can override any of them at the Stage D handoff.

### D1 — In-progress redesign reconciliation: **CONTINUE (extend the App-redesign-v1 / HANDOFF tokens)**

**Decision**: keep the existing `--color-bg`, `--color-fg`, `--color-accent`, `--color-mint`, `--color-amber`, `--color-coral` token block in `apps/transcribe-md/src/app/globals.css` (lines 61–100 + the `:root` aliases and `.qm-app` scoped tokens at lines 105–160) as the **foundation** of the new design system. The `.qm-*` utility class layer (lines 496–878) and the `.qm-warn-*` Rx-warning component CSS (lines 880–1324) stay where they are — they're load-bearing for already-migrated screens.

**Reasoning**:
1. Nine components already ship the new tokens to production (`ui/{app-frame,auth-shell,top-nav,spec-chip}`, `dashboard/{patient-card,stat-card,visit-list}`, `rx/{override-confirm-modal,rx-warning-card}`). Scrapping silently reverts merged work and breaks the dashboard.
2. The token names (`--color-fg`, `--color-bg`, `--color-line`, `--color-accent`) are semantic and Tailwind-friendly. They map cleanly to a future expansion (more shades, more semantic roles).
3. The `/tmp/design_handoff_quillmd_app/` source directory referenced in the comment block is gone, but the tokens themselves are recoverable verbatim from the CSS. The tokens **are** the source of truth now.
4. The older "Linear/Raycast/Vercel/Resend" tokens (`--color-bg-base`, `--color-violet-500`, `--color-text-primary`) at lines 20–60 are still referenced by 15 unmigrated components. They stay until those components migrate. **No mass deletion in Phase 1.**

**What this means for Phase 2 (component builds)**:
- New components use the App-redesign-v1 token names (`bg-bg-1`, `text-fg-2`, `border-line`, `text-accent`, `text-mint`).
- Components must wrap in `.qm-app` (or be nested inside something that already does) so the scoped radii/shadows/glow resolve.
- Atomic primitives that lack a current `.qm-*` equivalent (e.g. tabs, accordions beyond Radix-default, tables, stepper) get newly-authored `.qm-*` classes added to `globals.css` as the design directions land.

**What is explicitly NOT changing in Phase 1**:
- The legacy `--color-bg-base` / `--color-violet-500` / `--color-text-primary` token names. They must continue to resolve while unmigrated components depend on them.
- The `.qm-warn-*` Rx-warning card CSS (it has its own design spec and a Vitest test).
- The `tailwindcss-animate` plugin reference + the duplicate animation-keyframe fallbacks (intentional belt-and-suspenders per the comment in `globals.css`).

---

### D2 — State management posture: **STAY SERVER-ACTION-ONLY**

**Decision**: do not introduce Zustand, Jotai, Redux, React Query, SWR, or new React Context providers in Phase 1. The current pattern — server components fetch from Prisma, pass data to `'use client'` leaves, leaves call server actions via `useTransition` — is preserved.

**Reasoning**:
1. The audit confirmed there is **no client state library at all** in `apps/transcribe-md/src` today. Adding one is a logic change, not a remodel.
2. The "MUST NOT CHANGE" zone explicitly includes hooks and state machinery. Introducing a global store changes the contract every component consumes.
3. Server actions plus `useTransition` are sufficient for everything currently shipped (form submits, optimistic UI, redirects, revalidation). The remodel does not add any feature that demands client-side caching or cross-tab sync.

**Narrow allowed exceptions** (must be documented when added):
- **Per-component local state** via `useState`/`useReducer`/`useTransition` — already pervasive, fine to keep using.
- **One-screen client cache** if a remodel direction needs a quick optimistic toggle (e.g. tab switching in `visit-ready-view`) — `useState` only, no library.
- **The command palette** already uses `cmdk` (which has its own state model). Not a violation; it ships in production.

If a Phase 2 direction *requires* a global store (e.g. for a multi-pane editor), the agent that proposes it must escalate to the user before importing the library.

---

### D3 — Migration strategy: **ROUTE-BY-ROUTE on a feature branch**

**Decision**: ship the remodel route-by-route directly on a branch (likely `feat/remodel-phase2`). No parallel `/v2/*` routes, no feature-flag toggle. Each route's reskin lands in its own commit (or small PR) so the diff is reviewable.

**Reasoning**:
1. The redesign is **already mid-route-by-route** in production: dashboard + visit shell are on the new tokens, settings/login/signup are not. Continuing the same pattern is lower risk than introducing a parallel surface.
2. Parallel `/v2/*` routes double the work in `proxy.ts` (auth gating must be replicated), break NextAuth callback URLs, and require both versions to stay green. Not worth it for a single-team remodel.
3. A feature flag would need a flag library (none currently in repo) and a rollout mechanism (none either). It's a refactor before the remodel can start.
4. Branch-based work matches the repo's existing rhythm (`Phase 19`, `T-M16.4`, etc. — all sequential).

**Per-PR shape that the team will follow in Phase 2+**:
- One route or one component family per PR.
- Tests in lockstep: every Playwright spec touched by a new selector must be updated in the same PR. The QA custodian (Agent A6 in the audit) owns this.
- No "redesign" PR can land that breaks an existing e2e (`tests/e2e/scenarios/{1-4}.spec.ts` or `tests/automated/e2e/*.spec.ts`).
- Commits follow the existing convention (`Phase XX: <description>`).

**Branch posture**:
- Phase 1 (this stage) commits **no code** — only docs under `/opt/meddoc-pro/docs/`. Working tree on `main` stays clean.
- Phase 2 cuts the branch from `main` after the user picks a design direction.

---

## Stage B foundation work (this phase)

| Doc | Path | Status |
|---|---|---|
| Audit | `docs/REMODEL_AUDIT.md` | ✅ exists (written prior turn) |
| Phase 1 plan + decisions | `docs/REMODEL_PHASE1_PLAN.md` | ✅ this file |
| Extracted design tokens | `docs/DESIGN_TOKENS.md` | ✅ written |
| Component inventory + migration map | `docs/COMPONENT_INVENTORY.md` | ✅ written |
| Protected backend contracts | `docs/PROTECTED_CONTRACTS.md` | ⏳ Logic Protector subagent |
| 3 visual directions (HTML mockups) | `docs/design-directions/{A,B,C}.html` + `README.md` | ⏳ Design Director subagent |

## Stage D handoff (after both subagents finish)

The lead agent stops here. The user picks one of A/B/C (or asks for a revised direction) before Phase 2 begins. Phase 2 will spin up Component Builder subagents working route-by-route on the chosen direction.

## Out-of-scope reminders (same as audit §3)

The remodel must NOT modify:
- `apps/transcribe-md/src/app/api/**` (62 routes)
- `apps/transcribe-md/src/actions/**` (7 server-action files)
- `apps/transcribe-md/src/proxy.ts`, `src/lib/auth*`, `src/lib/nextauth.ts`
- `apps/transcribe-md/src/worker/**`, `src/worker.ts`, `src/worker-sentry.ts`
- `apps/transcribe-md/src/lib/{audit,deepgram-vocabulary,docx-generator,pdf-generator,minio,queue,redis,rate-limit,visit-export-server,*-pagination,patients-query,problem-list,specialties,clinical-rules,deliveries,fingerprint,email,email-enabled,format-time,log,shortcuts,cleanup-heartbeat,admin-*,api-error}.ts` — lib code is logic, not styling. Only `lib/cn.ts`, `lib/dob.ts`, `lib/format-time.ts` are display helpers (and even those should stay byte-for-byte if possible).
- `packages/{ai,auth,db,types}/**`
- `packages/db/prisma/**` (schema + 41 migrations)

The full inventory is in `docs/PROTECTED_CONTRACTS.md` (written by the Logic Protector subagent in Stage C).
