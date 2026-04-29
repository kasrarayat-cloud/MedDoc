# Transcribe-MD Remodel — Phase 2 Plan

Generated: 2026-04-29
Branch: `feature/clinician-remodel` (cut from `main` at `b9f699a` — Phase 19)
Direction: **CLINICIAN** (humane medical, light-mode-first, sage + teal on warm cream)
Reference mockups (the canonical visual contract for Phase 2):
- `docs/design-directions-v3/clinician/landing-and-recording.html` (987 lines)
- `docs/design-directions-v3/clinician/dashboard.html` (939 lines)
- `docs/design-directions-v3/clinician/visit-detail.html` (942 lines)

Scope: `apps/transcribe-md` frontend only (covers `app.quillmd.com` + `admin.quillmd.com`).
Out of scope: `apps/marketing`, `apps/meddoc-pro`, all backend/logic per `docs/PROTECTED_CONTRACTS.md`.

---

## Decisions carried from Phase 1 (`docs/REMODEL_PHASE1_PLAN.md`)

These are reaffirmed for Phase 2. **None of them change because of the Clinician choice.**

- **D1 — Continue the existing tokens**, EXTEND with Clinician tokens. The App-redesign-v1 token set + the legacy "Linear/Raycast/Vercel/Resend" set both stay in `globals.css` until every consumer is migrated. Clinician tokens are **additive**, namespaced `--clinician-*` (Tailwind utilities) + `.qm-cl-*` (utility classes).
- **D2 — Server-action-only state**. No Zustand / Redux / React Query / SWR / new Context providers added in Phase 2. Per-component `useState`/`useReducer`/`useTransition` is fine. Visual swap only.
- **D3 — Route-by-route migration on a feature branch**. This branch (`feature/clinician-remodel`) is that branch. Each component or batch lands as one commit (or one small PR if we want PR-style review). No `/v2/*` parallel routes. No feature-flag library.

## Direction-specific decisions for Clinician

### CL-1 — Light-mode-first
Clinician is **light-mode**. The existing dark App-redesign-v1 surfaces continue to work for non-migrated routes during the transition (they wrap in `.qm-app` and resolve to the dark `--color-bg` tokens). Migrated routes wrap in `.qm-cl-app` and resolve to cream `--clinician-cream` tokens. **No dark mode switcher in Phase 2.** A future phase can wire one up by toggling the wrapper class.

### CL-2 — Type face: DM Sans for body, Source Serif 4 for content
The mockup loads DM Sans for the sans face. We will:
- Load DM Sans via `@import` from Google Fonts inside `globals.css` (no `layout.tsx` change in Phase 2)
- Override `--sans` inside `.qm-cl-app` to DM Sans (Inter Tight remains the global default for non-Clinician surfaces)
- Source Serif 4 + JetBrains Mono are already loaded via `next/font` in `apps/transcribe-md/src/app/layout.tsx` — no change

Performance note: the `@import` approach is one HTTP request + render-blocking until DM Sans loads. Acceptable for Phase 2; can be migrated to `next/font` in layout.tsx during Batch B (layout chrome) if perf measurement says it matters.

### CL-3 — Patient names in serif (Source Serif 4 19 px+)
The mockup commits to serif patient names — flagged as "the most controversial decision" by the Design Director. We carry that forward. Override available in 1 line of CSS if a stakeholder rejects it.

### CL-4 — Body copy in serif at 16px line-height 1.7
SOAP body and visit-detail prose use Source Serif 4 16 px / 1.7 lh. The mockup commits to this. We carry it forward. Override available later.

### CL-5 — No springs, no bounces — gentle ease-out only
Motion is `cubic-bezier(0.22, 1, 0.36, 1)` (`--ease-clinician`) at 240–360 ms. No `framer-motion` `spring` configs. No bounces. The recording halo + AI status crossfade are the magic moments.

### CL-6 — `<RxWarningCard>` re-skin policy
The Rx warning component (`apps/transcribe-md/src/components/rx/rx-warning-card.tsx`, 518 LOC) has its own `qm-warn-*` design spec at `docs/design/rx_warning_handoff/`. Phase 2 will adapt the SEVERITY PILLS to the Clinician palette (soft-bg + deep-fg, no gradients) but keep the structural CSS family. Reskin happens in Batch D (visit detail).

---

## Foundation work (Stage 1 — lead agent, not a subagent)

### Files modified by Stage 1

| File | What changed |
|---|---|
| `apps/transcribe-md/src/app/globals.css` | Added Clinician `@theme` token block (`--color-clinician-*`), `.qm-cl-app` scoped bare-name aliases, full `.qm-cl-*` utility class family, animations |
| `docs/DESIGN_TOKENS.md` | Added §H — Clinician tokens (per CL-1 to CL-5) + class catalog |
| `docs/REMODEL_PHASE2_PLAN.md` | This file |
| `docs/CLINICIAN_MIGRATION_ORDER.md` | Batch breakdown (A–G) for Component Builder subagents |

**No source code (`.tsx` / `.ts`) modified by Stage 1.** The CSS is purely additive. Existing components continue to work because their (dark) tokens are still defined.

---

## Migration order — Batches A–G (full plan in `docs/CLINICIAN_MIGRATION_ORDER.md`)

| Batch | Surface | Why this order |
|---|---|---|
| **A — Atomic primitives** | button, input, card, dialog, skeleton, empty-state, toaster, dropdown | No route — consumed everywhere. Build first; everyone depends on these. |
| **B — Layout chrome** | `<AppFrame>`, `<TopNav>`, `<IconRail>`, `<AuthShell>`, `<PageHeader>` | Touches every page. Build second so route-level work has the right shell to mount inside. |
| **C — Dashboard family** | `app/dashboard/page.tsx` + `<StatCard>`, `<DashboardPatient>`, `<VisitList>`, `<PatientCard>` (top-level dup) | High-traffic; biggest visual impact for daily user. |
| **D — Visit detail family** | `app/visits/[id]/page.tsx` + 16 sub-files (visit-ready-view, soap-editor, codes-tab, rx-tab, transcript view, Rx warning re-skin) | The biggest single chunk; doctor's primary workspace. |
| **E — Visit creation flow** | `<AudioUploader>`, `<VoiceDictator>`, `<TextComposer>`, `app/visits/new/page.tsx`, `app/visits/[id]/record/page.tsx` | Most complex motion (recording widget halo, transcript slide-fade, AI crossfade). Build after foundation is solid. |
| **F — Auth screens** | `app/(auth)/login/`, `signup/`, `forgot-password/`, `reset-password/`, `check-email/` | Self-contained; can be parallelized at any time. |
| **G — Admin screens** | `app/admin/*` + `app/system-admin/*` (in apps/meddoc-pro out of scope but admin in transcribe-md is in scope) | Lowest priority — gated to `Product.SUPER_ADMIN` only. |

**Phase 2 — Stage 3 launch in this turn**: Batches **A** (atomics) and **F** (auth) — they have no dependency on each other and no dependency on B (layout chrome). Lead agent will spawn 2 subagents in parallel.

After A + F land cleanly + user signs off, **Phase 2 — Stage 4** will run Batches B + C in parallel. Then D + E in parallel. Then G last.

---

## Automatic QA after every batch (no human review burden)

After ANY Component Builder subagent completes a batch, the lead agent MUST invoke the `qa-clinician-remodel` skill (installed at `~/.claude/skills/qa-clinician-remodel/`) BEFORE asking the user to sign off. The skill produces a unified report at `docs/qa-reports/batch-<X>-<timestamp>.md` covering:

1. TypeScript (`tsc --noEmit`)
2. Unit tests (`vitest run`)
3. E2E smoke (Playwright MCP against a temporary `next start` on port 8766; falls back to source-code class-name verification if build fails on the RAM-constrained VPS)
4. Visual regression vs `docs/design-directions-v3/clinician/*.html` mockups (identity-match score 0–10 + per-criterion table)
5. HIPAA + protected-zone diff scan (verifies no `PROTECTED_CONTRACTS.md` files were touched + no new PHI exposure surfaces)
6. A11y smoke (axe-core via Playwright MCP — only if Layer 3 succeeded)

**Verdict-driven user contact:**
- 🟢 PASS — lead agent posts the report path + a one-line summary, asks "ship next batch?", proceeds on yes.
- 🟡 PASS-WITH-FLAGS — lead agent surfaces the warnings; user decides per-warning. Distinguish:
  - **User-judgment** ("sage too saturated vs mockup") → user calls it
  - **Fix-and-retry** ("TS error in line 42") → lead spawns a fixup subagent silently, never reaches user
- 🔴 FAIL — lead agent blocks, lists failures, asks user to approve fix-and-retry path.

The user's review burden drops to zero on green batches. The user only sees red/yellow.

## Workflow rules for every Component Builder subagent

These are the rules every subagent must follow. Repeated here so no one has to dig through this doc.

1. **Visual swap only.** Keep TypeScript types, props, hooks, event handlers, server-action signatures, and data flow IDENTICAL. Replace inline Tailwind classes with `.qm-cl-*` classes or new Clinician-token Tailwind utilities (`bg-clinician-cream`, `text-clinician-sage`, etc.).
2. **Protected zone is sacred.** If a migration requires editing anything in `docs/PROTECTED_CONTRACTS.md`, STOP and report. Do not work around it.
3. **Per-component commits.** Each component is its own commit, message: `remodel(clinician): <component-name> to clinician tokens`. Easier to revert one bad migration than 20.
4. **Run TS + tests after each component.**
   - `cd apps/transcribe-md && npx tsc --noEmit` (must pass)
   - `cd apps/transcribe-md && npx vitest run path/to/component.test.tsx` (must pass for that file's tests, if any)
5. **Preserve every `data-testid`.** E2E tests at `tests/e2e/scenarios/*.spec.ts` and `tests/automated/e2e/*.spec.ts` rely on these.
6. **No new deps.** No `npm install`. Clinician should work entirely with existing deps + the new Clinician CSS classes.
7. **No state library / hook / server action additions.** D2 from Phase 1.
8. **Push the batch when done.** `git push origin feature/clinician-remodel`. Report files changed, commits, test failures.
9. **Flag the awkward.** If a component's protected-zone constraints make migration ugly, flag it for human review — don't paper over.

---

## Test posture for Phase 2

| Layer | What to run during migration |
|---|---|
| TypeScript | `npx tsc --noEmit` after each component (must pass) |
| Vitest unit tests | `npx vitest run <path>` for that component's test file (if any). Per `apps/transcribe-md/src/components/rx/__tests__/rx-warning-card.test.tsx` is the only component-level RTL test today. |
| Vitest worker tests | Out of scope for visual remodel. Should pass unchanged. |
| Playwright e2e | NOT run per-component — too expensive. QA custodian (not assigned in Stage 3) runs them as a batch at the end of each Phase 2 stage. Expect selector breakage; fix in lockstep PRs. |

---

## Branch / push protocol

- Branch: `feature/clinician-remodel`
- Push: `git push origin feature/clinician-remodel` — uses `gh` auth on this VPS (token already configured in `~/.config/gh/hosts.yml`). NEVER embed tokens in the URL.
- PR: lead agent creates a draft PR after Stage 3 completes via `gh pr create --draft`. User reviews before merge to `main`.
- Squash policy: TBD by user. Granular commits make per-component reverts easy; squash collapses to a single Phase 2 entry.

---

## What's preserved unchanged from Phase 1

- All Phase 1 docs in `docs/` (audit, plan, tokens, inventory, contracts) — committed in this branch's first commit.
- All design exploration (`docs/design-directions{,-v2,-v3,-v4}/`) — committed as historical record.
- Apothecary at `docs/design-directions-v2/` — kept as the second-place baseline (the user picked Clinician but Apothecary remains a valid hybrid source).

---

## Stop point

After Stage 3 completes (Batches A + F merged on this branch + pushed), STOP. Wait for user sign-off before launching Batches B + C (layout + dashboard). Do not start D / E / G.
