# Post-merge cleanup tasks

Items deferred from the Phase 2 Clinician remodel — to be addressed AFTER `feature/clinician-remodel` lands on `main`. None of these block the merge.

Created: 2026-04-29 during Phase 2 D+E gate review.

---

## 1. ✅ Verified: `/dev/rx-warnings` 404 in production is INTENTIONAL

**Status:** documented; no action needed.

`apps/transcribe-md/src/app/dev/rx-warnings/page.tsx:51` explicitly calls `notFound()` when `process.env.NODE_ENV === 'production'`. The route is a designer/QA preview surface for the RxWarningCard variants and is gated to development builds only. The page header itself notes "Dev-only route. 404s in production." (line 75).

QA Layer 3b's 404 on this route during Strategy A (production build) is therefore the **correct behavior**, not a regression. Surfaced here for forward-looking clarity so future contributors don't chase the 404 as a bug.

---

## 2. ✅ Fixed: typo `processing-state.tsx:426` literal `’` in JSX text

**Status:** fixed during merge prep, commit `87340e0`. Replaced the 8-character literal escape with the actual U+2019 character.

**Original notes (kept for archival):**

**Severity:** trivial; not Clinician-scope.

```tsx
// Line 426 — current:
Elapsed {elapsedMin} min · leave the page and we’ll finish in the background
```

JSX text content does NOT interpret backslash escapes like `’`, so users see the literal characters `we’ll` instead of the typographically-correct `we'll`.

**Fix options:**

- **Simplest:** replace `we’ll` with the actual Unicode character `we'll` (U+2019 right single quotation mark).
- **Or:** ASCII apostrophe `we'll`.
- **Or:** template-wrap inside JSX: `we{'’'}ll`.

Any of the above is a one-line change. Pre-existed before Phase 2; preserved verbatim through the Batch D dual-theme migration (commit `34e5dad remodel(clinician): processing-state dual-theme via theme prop`).

---

## 3. A11y pass via Playwright/axe-core

**Severity:** test-coverage gap; needs to run before final merge.

Layer 6 (a11y smoke) of the `qa-clinician-remodel` skill was SKIPPED in every batch (B+C, D, E) because the QA sandbox host has no headed browser binary. The a11y harness must run on a dev box or in CI before the PR ships.

**Suggested setup** (per the skill spec):

```javascript
// browser_evaluate in Playwright MCP
await import('https://cdn.jsdelivr.net/npm/axe-core@4.10.0/+esm')
  .then(m => m.default || m);
const results = await axe.run(document, { resultTypes: ['violations'] });
return results.violations.filter(
  v => v.impact === 'critical' || v.impact === 'serious'
);
```

**Routes to cover** (per QA skill):
- `/login`, `/signup`, `/forgot-password`, `/reset-password`, `/check-email` (Batch A + F)
- `/dashboard` (Batch C)
- `/visits`, `/visits/[id]?status=READY`, `?status=SIGNED`, `?status=PROCESSING` (Batch D)
- `/visits/new`, `/visits/[id]/record` (Batch E)
- `/admin/audit-logs` (Batch G — when complete)

**Pass criterion:** zero critical OR serious violations (color-contrast, missing-alt, missing-label, role-lacks-required-children).

---

## 4. (Reserved) Items surfaced during Batch G

To be appended after Batch G QA completes.

---

## 6. 📝 Pull mockup-fidelity dashboard content (Phase 3)

Current dashboard renders 4 metric cards + 1 patient pill. The Clinician mockup at `docs/design-directions-v3/clinician/dashboard.html` shows a richer surface: morning greeting ("Good morning, Dr. Chen."), 11-row patient list with colored avatars per specialty, "Three drafts, ready when you are." section with named surface CTAs.

Implementation gap is content/data-emit, not visual — palette + typography 100% match the mockup. Phase 3 task: extend dashboard data layer to surface the mockup's content density.

**Surfaced by:** merge-prep round 1 verdict `🟡 PASS-WITH-FLAGS` (report `merge-prep-20260430T001246Z.md`, Flag #2). Deferred per user decision at the merge-prep gate; merge-prep round 2 (`merge-prep-20260430T010915Z.md`) confirmed the deferral and proceeded to 🟢 PASS without it.

---

## 7. ✅ Phase 4 follow-up bugs — completed 2026-05-01

Three post-deploy bugs from user QA fixed and deployed via PR #89:

- **Bug 1 — visit-detail hero band too short.** `min-height` 280→360px on `.qm-cl-app .qm-cin-band-tall` so the cinematic photo crop opens up from ~30 % of vertical content to ~40 %. Recording band (`.qm-cin-band-short`, 200 px) unchanged. Commit `d153dc3`.
- **Bug 2 — `/patients` route never migrated to Phase 2 Clinician.** `apps/transcribe-md/src/app/patients/page.tsx` and `[id]/page.tsx` were rendering the legacy dark navy + violet `app-redesign-v1` theme via `<AppFrame>` / `<PageHeader>` defaults. Both files now pass `theme="clinician"` to opt into the existing Clinician branches of those shared components — no new components created. `<PatientCard>`, server actions, Prisma queries, auth gates byte-identical. Commits `fff6460` + `cf9bea0`.
- **Bug 3 — cream baseline too cool.** `--color-clinician-cream` `#FAF7F2 → #F2EBDC` in BOTH `apps/transcribe-md/src/app/globals.css` and `apps/marketing/src/app/globals.css`. Warmth +6 → +18; WCAG vs `--ink #2B2620`: 14.0:1 → 12.6:1 (still AAA Large + Normal). `--cream-card` and `--cream-2` tokens unchanged per user direction; revisit if section-band visibility looks off post-deploy. Commit `15d13f4`.

**Live verification:**
- `qm-cin-band-tall { min-height: 360px; padding: 32px 32px 28px; }` confirmed in `/_next/static/chunks/*.css` on `app.quillmd.com`.
- `color-clinician-cream: #f2ebdc` confirmed in served CSS on both `app.quillmd.com` and `quillmd.com`.
- `/patients` returns body class `qm-cl-app` (the Phase 2 Clinician scope marker; previously absent).

### Lesson learned for pre-launch

`docs/CLINICIAN_MIGRATION_ORDER.md` was incomplete — `/patients` slipped through Phase 2/3/4 without re-skin because it was never enumerated as an in-scope route. Before the pilot launch, do a full route inventory with this command and address any hits:

```bash
grep -rE 'AppFrame|gradient-violet|text-text-muted' \
  apps/transcribe-md/src/app/ | grep -v '_components' | grep -v 'node_modules'
```

Should return 0 hits across all routes (not counting routes that legitimately render the legacy `<AppFrame theme="default">`). Add this as a CI check in a follow-up PR — a tiny `grep` step in the existing GitHub Actions workflow next to the a11y job is sufficient.

---

## 8. ✅ Phase 5 — Linear V1 Faithful — completed 2026-05-01

Full visual replacement of Phases 2/3/4 with Linear V1 Faithful aesthetic. PR #90, 87 commits, ~$0 cost (pure CSS, no image gen).

### What changed
- Canvas: cream → dark (#08090a)
- Accent: sage retained (#7AA68C, replacing Linear's purple)
- Typography: Source Serif 4 fully removed; Inter + JetBrains Mono everywhere
- Chrome: cinematic photo heroes deleted; Linear-style top bar + thin sidebar + Cmd+K everywhere
- Tokens: `--color-clinician-*` / `qm-cl-*` / `qm-cin-*` / `av1-*` families fully removed; `--color-linear-*` / `qm-lin-*` canonical

### What survived (functional contracts)
- NextAuth, Server Actions, API routes, Prisma queries
- MediaRecorder + WebSocket + AudioContext lifecycle (recording pipeline byte-identical, verified by Subagent 4 diff)
- SUPER_ADMIN gate, RBAC, audit-log writes
- Rx warning class family (`.qm-warn-*`) — re-themed dark, names preserved (180 refs intact)
- Specialty templates, SOAP structure, visit lifecycle states

### Live verification (post-deploy)
- `#08090a` + 19 `--color-linear-*` tokens present in `/_next/static/chunks/*.css` on `quillmd.com`
- 10+ `.qm-lin-*` utilities served (`.qm-lin-app`, `.qm-lin-btn-primary`, `.qm-lin-cmdk`, `.qm-lin-pill`, `.qm-lin-fade-in`, etc.)
- 0 stale `qm-cl-app` / `qm-cin-` / `av1-` / `--color-clinician-` / `Source Serif` references in served CSS
- External smoke: `app.quillmd.com` 307 (auth redirect, expected), `pro.quillmd.com` 200, `quillmd.com` 200, `app.quillmd.com/login` 200, `quillmd.com/pricing` 200
- Deploy outage: ~11 seconds (UP-START 14:48:30Z → both healthy 14:48:41Z)

### Lessons added
- **Stage 2.5 (sequential shared-chrome migration before parallel surface fan-out) eliminated all merge conflicts** in Stage 4 (zero file overlap between any pair of 5 sibling branches). Fold this pattern into future large refactors: when N parallel subagents will all consume shared chrome, migrate the chrome sequentially first so the parallel agents work on isolated surface code only.
- **Pre-flight image-prune saved deploy time** (53 MB freed before build).
- **Worktree symlink quirk:** Turbopack rejects `node_modules` symlinks that cross filesystem boundaries (e.g. `/tmp/wt-…` → `/opt/meddoc-pro/node_modules`). Subagents must use `--webpack` flag in worktree builds, OR keep the worktree path inside the same filesystem as the project (e.g. `/opt/meddoc-pro/wt-…`). Production CI on `main` is unaffected (no symlinks).
- **Backward-compatible deprecated props pattern:** When migrating shared components (AppFrame, TopNav, etc.), keep the old `theme` prop in the type signature as a no-op while collapsing the rendered branches to one. Lets parallel surface subagents proceed without TS errors at every call site; deprecated props can be removed in a follow-up sweep without coordinating across branches.

---

## 9. ✅ Phase 5.1 — visit-detail tab interiors — completed 2026-05-01

Five tab content bodies re-implemented per v9 design exploration picks: SOAP V3 split-pane, Transcript V3 split-pane, Codes V2 power-table, Rx V3 split-pane, Extras V4 card-stream. PR #92, 15 commits, $0 cost (pure CSS, no AI image gen).

### What landed
- **SOAP NOTE** — V3 split-pane: 4 sections left (S/O/A/P with status pills + sage section letter chips + mono uppercase eyebrows), Sources rail right (transcript turn citations)
- **TRANSCRIPT** — V3 split-pane: diarised turns left (speaker chip + mono timestamp + body, low-confidence dotted-underline), audio waveform + speed picker + visit metadata rail right
- **CODES** — V2 power-table: ICD-10 + CPT sortable tables, 4 px sage confidence bars, evidence-quote popover, AI-suggestion accept/reject (rail), "(coming in T-M21)" tooltips on Add/Edit/Remove until mutations land
- **RX** — V3 split-pane: Rx list left with 4-col dose grid, severity-grouped warnings rail right (CRITICAL → SERIOUS → MODERATE → INFO with pulsing critical dot). `.qm-warn-critical/-serious/-moderate/-info` class names byte-identical (Subagent B grep-confirmed); worker emits 3-band severity (`critical|major|minor`), mapped at component boundary to 4-band rail (`major→serious`, `minor→info`)
- **EXTRAS** — V4 card-stream: 7 stacked cards with hairline borders, em-dash placeholders for the 6 unwired categories, AI extras (the existing `referrals + patientSummary`) wired today

### Live verification (post-deploy, 2026-05-01T18:01:33Z)
- 16 Phase 5.1 `qm-lin-*` utilities served across both prod CSS chunks (split, soap-section, source-card, tx-stream, tx-turn, codes-frame, codes-row, rx-split, rx-rail, card-stream, extras-card, extras-head, extras-vitals-tiles, etc.)
- Phase 5 baseline intact (`#08090a`, `--color-linear-sage`, `.qm-lin-app`, `.qm-lin-cmdk` all served)
- Avatar bug class regression: 0 renewed `4024354389` errors in last 2 min
- External smoke: `/login` 200, `/dashboard` 307 (auth), `/patients` 307 (auth)
- Deploy outage: 9 seconds (UP-START 18:01:24Z → HEALTHY 18:01:33Z)

### Follow-up PRs needed (UI in place, data plumbing pending)
- **T-M21:** SOAP citations field on Server Action (powers the Sources rail filter — currently shows all turns until per-section citation IDs are emitted by the SOAP draft worker)
- **T-M22:** `/api/visits/[id]/audio` streaming endpoint (powers the Transcript V3 audio scrubber — currently decorative; only the dictation-flow audio endpoint exists)
- **T-M23:** Extras data plumbing (vitals, allergies, current meds, problem list, demographics, audit log fetches threaded through `extras-tab` props — cards already render, just need wire data)
- **T-M24:** Code/Rx mutation Server Actions (Add / Edit / Remove buttons currently stubbed `disabled` with "(coming in T-M21)" tooltip — sort / expand / copy work today)

### Lessons added
- **Naive conflict-strip on additive globals.css broke a CSS rule mid-block.** When 3 parallel subagents all append utility classes to globals.css, git's 3-way merge conflicts span both branches' tail-additions. Stripping `<<<<<<<`/`=======`/`>>>>>>>` markers naively can leave a `.foo { ... }` opener separated from its closer by the conflict boundary. Fix used: `git show <branch>:globals.css` for each branch's clean version, then surgical concatenation of base + each branch's tail-additions. Brace balance check (`{ count == } count`) caught the issue. Future large additive merges should use this surgical pattern from the start, not after the conflict-strip fails.
- **Worktree path inside project dir works with Turbopack.** Phase 5 hit a cross-fs Turbopack quirk when worktrees lived at `/tmp/wt-*` symlinking back to `/opt/meddoc-pro/node_modules`. Phase 5.1 kept worktrees at `/opt/meddoc-pro/wt-p51-*` (same filesystem) and Turbopack worked unchanged. Faster build path. Worktree-symlinked node_modules across mountpoints still need `--webpack`.
