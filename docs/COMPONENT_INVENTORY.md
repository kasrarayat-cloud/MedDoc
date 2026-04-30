# Transcribe-MD Component Inventory

Generated: 2026-04-29
Source: `apps/transcribe-md/src/components/` (40 .tsx files, 5,409 LOC, plus 1 test file)
Migration target: App-redesign-v1 token set (see `docs/DESIGN_TOKENS.md`)

---

## Summary by status

| Status | Count | LOC |
|---|---|---|
| Already on App-redesign-v1 (`qm-*`) | **9** | ~1,700 |
| Token-neutral or atomic (no theme tokens) | **16** | ~1,250 |
| Legacy tokens (Linear/Raycast/Vercel/Resend) — **needs remodel** | **15** | ~2,460 |
| **Total** | **40** | **5,409** |

(+ 1 RTL test file under `rx/__tests__/`.)

---

## Categorization (component × layer × status × seam)

### Layout (the chrome — page shell + nav + frames)

| Component | Path | LOC | Client? | Status | Consumes | Notes |
|---|---|---|---|---|---|---|
| `<AppFrame>` | `ui/app-frame.tsx` | 70 | ✅ | ✅ migrated | Children only | The `.qm-app` wrapper; the Phase-1 chrome contract. Every redesigned page mounts inside it. |
| `<TopNav>` | `ui/top-nav.tsx` | 273 | ✅ | ✅ migrated | `<UserMenu>`, `<CommandPalette>` trigger | The chrome's top bar with global search trigger + user menu. |
| `<IconRail>` | `ui/icon-rail.tsx` | 121 | ✅ | ⚪ neutral | Routes (Link only) | Vertical icon nav. No theme tokens directly; visual identity comes from icons + `<AppFrame>`. |
| `<AuthShell>` | `ui/auth-shell.tsx` | 208 | ❌ | ✅ migrated | Children only | Auth-page chrome (login/signup/forgot/reset). |
| `<PageHeader>` | `ui/page-header.tsx` | 65 | ❌ | ⚪ neutral | Title prop | Title + breadcrumbs. Token-agnostic. |
| `<PageWrapper>` | `page-wrapper.tsx` | 25 | ✅ | ⚪ neutral | Children | Thin client wrapper — likely deletable post-migration. |

### Atomic UI (primitives — buttons, inputs, chips, basic visuals)

| Component | Path | LOC | Client? | Status | Notes |
|---|---|---|---|---|---|
| `<SpecChip>` | `ui/spec-chip.tsx` | 58 | ❌ | ✅ migrated | Specialty pill — exports `SpecialtyKind` type used by visit page. |
| `<Avatar>` | `ui/avatar.tsx` | 65 | ❌ | ⚪ neutral | Initials avatar — currently neutral, easy to migrate. |
| `<Ic>` (Icon) | `ui/icon.tsx` | 308 | ❌ | ⚪ neutral | Lucide wrapper (`<Ic name="..."/>`). Used everywhere. |
| `<LocalTime>` | `ui/local-time.tsx` | 69 | ✅ | ⚪ neutral | Hydration-safe timestamp. |
| `<QuillLogo>` | `ui/quill-logo.tsx` | 31 | ❌ | ⚪ neutral | SVG logo — pure visuals. |
| `<WordMark>` | `ui/word-mark.tsx` | 19 | ❌ | ⚪ neutral | Text wordmark — neutral. |
| `<EmptyState>` (ui) | `ui/empty-state.tsx` | 96 | ❌ | ⚪ neutral | Cleaner top-level dup. **Consolidate during remodel.** |
| `<EmptyState>` (top-level) | `empty-state.tsx` | 106 | ✅ | 🔧 legacy | Older client-side variant. **Duplicate — drop or merge.** |
| `<Skeleton>` | `skeleton.tsx` | 94 | ❌ | 🔧 legacy | Uses `surface-2`/`surface-3` shimmer. Replace with `.qm-shimmer`. |
| `<Toaster>` | `toaster.tsx` | 41 | ✅ | 🔧 legacy | Sonner wrapper — needs theme alignment to qm tokens (no `.qm-toast` exists yet). |
| `<SpecularButton>` | `specular-button.tsx` | 113 | ✅ | 🔧 legacy | The "shine" button — `.specular-button` CSS exists in globals; component still uses violet-500. |
| `<SpecialtyDropdown>` | `specialty-dropdown.tsx` | 115 | ✅ | 🔧 legacy | Custom dropdown — likely replaceable with Radix select + qm-input styling. |
| `<UserMenu>` | `user-menu.tsx` | 102 | ✅ | 🔧 legacy | Avatar + dropdown — needs port to qm tokens; consumed by `<TopNav>`. |
| `<GlowCard>` | `glow-card.tsx` | 35 | ✅ | 🔧 legacy | Wraps children in violet-glow card — replace with `.qm-glass.hover`. |
| `<TiltCard>` | `tilt-card.tsx` | 77 | ✅ | ⚪ neutral | 3D-perspective container — uses `.tilt-perspective` global helper, no theme tokens directly. |
| `<GradientText>` | `gradient-text.tsx` | 18 | ❌ | ⚪ neutral | Wraps text in `.text-gradient-violet`. |
| `<AnimatedGrid>` | `animated-grid.tsx` | 25 | ❌ | ⚪ neutral | The 48px `.grid-bg` helper as a component. |
| `<GlobalShortcuts>` | `global-shortcuts.tsx` | 60 | ✅ | ⚪ neutral | Keyboard listener — not visual. Reads `lib/shortcuts.ts`. |
| `<ErrorFallback>` | `error-fallback.tsx` | 122 | ✅ | 🔧 legacy | Render-error UI — must be reskinned. |

### Visual flourish (heavy 3D / motion — performance-sensitive)

| Component | Path | LOC | Client? | Status | Notes |
|---|---|---|---|---|---|
| `<VioletOrb>` | `violet-orb.tsx` | 242 | ✅ | 🔧 legacy | `@react-three/fiber` orb. Used on auth/landing. Heavy. **Phase 2 may simplify or 2D-ify.** |
| `<VisitOrb>` | `visit-orb.tsx` | 29 | ✅ | ⚪ neutral | Smaller orb stand-in — token-agnostic wrapper. |
| `<LiveOrb>` | `recording/live-orb.tsx` | 163 | ✅ | ⚪ neutral | Recording-state orb (volume-reactive). Three.js. |
| `<ShaderBg>` | `ui/shader-bg.tsx` | 128 | ✅ | ⚪ neutral | WebGL gradient mesh background. Mounts inside `<AppFrame>`. |

### Feature — Dashboard

| Component | Path | LOC | Client? | Status | Seam |
|---|---|---|---|---|---|
| `<StatCard>` | `dashboard/stat-card.tsx` | 68 | ❌ | ✅ migrated | Props only |
| `<PatientCard>` (dashboard) | `dashboard/patient-card.tsx` | 148 | ✅ | ✅ migrated | Exports `DashboardPatient` type — consumed by `app/dashboard/page.tsx` |
| `<VisitList>` | `dashboard/visit-list.tsx` | 209 | ✅ | ✅ migrated | Exports `DashboardVisit` type — consumed by `app/dashboard/page.tsx` |
| `<PatientCard>` (top-level) | `patient-card.tsx` | 89 | ✅ | 🔧 legacy | **Duplicate of dashboard/patient-card.tsx.** Resolve during remodel. |
| `<VisitCard>` | `visit-card.tsx` | 123 | ✅ | 🔧 legacy | Older visit summary card — likely superseded by visit-list. |

### Feature — Visit creation / recording

| Component | Path | LOC | Client? | Status | Seam |
|---|---|---|---|---|---|
| `<AudioUploader>` | `audio-uploader.tsx` | 274 | ✅ | 🔧 legacy | Calls `/api/visits/[id]/upload` — **API path is protected** |
| `<VoiceDictator>` | `voice-dictator.tsx` | 342 | ✅ | 🔧 legacy | Calls `/api/visits/[id]/dictation/{audio,upload}` — **API protected** |
| `<TextComposer>` | `text-composer.tsx` | 152 | ✅ | 🔧 legacy | Submits server action `createVisitAction` (text mode) — **action signature protected** |

### Feature — Rx safety

| Component | Path | LOC | Client? | Status | Notes |
|---|---|---|---|---|---|
| `<RxWarningCard>` | `rx/rx-warning-card.tsx` | 518 | ✅ | ✅ migrated | Largest single component. Uses the entire `qm-warn-*` family. **Has its own design spec — out of scope for visual changes in Phase 1 directions.** |
| `<OverrideConfirmModal>` | `rx/override-confirm-modal.tsx` | 308 | ✅ | ✅ migrated | Doctor-override flow. Calls `lib/rx-warning-audit.ts` (`'use server'`). |

(+ test: `rx/__tests__/rx-warning-card.test.tsx`)

### Feature — Global UX

| Component | Path | LOC | Client? | Status | Seam |
|---|---|---|---|---|---|
| `<CommandPalette>` | `command-palette.tsx` | 300 | ✅ | 🔧 legacy | `cmdk`-driven. Calls server action `lib/command-palette.ts` actions. **Action seam preserved.** |

---

## Components grouped by required Phase 2 effort

### High-priority remodel (high LOC + high user-visibility)

1. `audio-uploader.tsx` (274)
2. `voice-dictator.tsx` (342)
3. `command-palette.tsx` (300)
4. `text-composer.tsx` (152)
5. `error-fallback.tsx` (122)
6. `user-menu.tsx` (102)

These six are all on legacy tokens, all client components, and all visible on every visit-creation flow. Six dedicated component-builder PRs in Phase 2.

### Medium-priority (lower LOC, atomic — port quickly)

7. `skeleton.tsx` (94) → swap to `.qm-shimmer`
8. `glow-card.tsx` (35) → swap to `.qm-glass`
9. `specular-button.tsx` (113) → align to `.qm-btn` styles, keep specular `::before`
10. `specialty-dropdown.tsx` (115) → port to Radix select + `.qm-input`
11. `toaster.tsx` (41) → add a `.qm-toast` style block; sonner config update
12. `empty-state.tsx` × 2 (top-level + ui) → consolidate to single `.qm-app`-themed version

### Visual flourish (decide keep / drop / simplify per direction)

13. `violet-orb.tsx` (242) — Three.js orb. 3 directions can each propose its fate.
14. `visit-orb.tsx` (29) — wrapper.
15. `recording/live-orb.tsx` (163) — Three.js, volume-reactive.
16. `shader-bg.tsx` (128) — WebGL background.

### Already-migrated — preserve identity

17–25. Nine `qm-*` components (see status table). Phase 2 should re-validate their tokens but not reskin them unless a direction explicitly proposes new chrome.

---

## Backend seams — what each feature component consumes (read-only contracts)

| Component | Seam | Type |
|---|---|---|
| `<AudioUploader>` | `POST /api/visits/[id]/upload` | API |
| `<VoiceDictator>` | `POST /api/visits/[id]/dictation/audio` + `/upload` | API |
| `<TextComposer>` | `createVisitAction(formData)` | server action (`actions/visits.ts`) |
| `<CommandPalette>` | actions in `actions/command-palette.ts` | server action |
| `<UserMenu>` | `signOut()` from next-auth/react + `actions/profile.ts` | mixed |
| `<OverrideConfirmModal>` | `lib/rx-warning-audit.ts` (`'use server'`) | server action |
| `<RxWarningCard>` | `lib/rx-warning-audit.ts` events | server action |
| `<PatientCard>` (dashboard) | Type-only: `DashboardPatient` from sibling component (originates from server actions) | type |
| `<VisitList>` | Type-only: `DashboardVisit`, `loadMoreVisitsAction` from `actions/visits.ts` | mixed |
| `<StatCard>` | None (pure props) | — |
| `<TopNav>` | None directly | — |

---

## File-on-file duplication risk (resolve during remodel)

| Pair | Resolution |
|---|---|
| `patient-card.tsx` (top-level, 89 LOC) ↔ `dashboard/patient-card.tsx` (148 LOC) | The `dashboard/` version is migrated and exports `DashboardPatient`. The top-level should be **removed** during Phase 2 unless a non-dashboard caller is found. Grep before deleting: `grep -r "from.*components/patient-card" src/`. |
| `empty-state.tsx` (top-level, 106 LOC) ↔ `ui/empty-state.tsx` (96 LOC) | Migrate callers to `ui/empty-state.tsx`, delete the top-level. |

---

## Hooks / state files referenced by components (must not change)

These files are imported by components but live in `lib/` and are part of the protected zone:

- `lib/cn.ts` — class merger (purely cosmetic helper, but bundled with NextAuth integrations elsewhere — leave untouched)
- `lib/format-time.ts` — used by `<LocalTime>`, also by server code
- `lib/dob.ts` — used by patient cards + server code
- `lib/shortcuts.ts` — used by `<GlobalShortcuts>` + server actions
- `lib/ehr-formatters.ts` — `sectionSoap`, `sectionCodes`, `sectionRx`, `sectionExtras` used by `<CopySectionButton>` (under `app/visits/[id]/`) — **DO NOT change shape**

---

## Open questions for the remodel team (these are direction-decisions, not gaps)

1. **Three.js orbs — keep, simplify, or drop?** All three directions in Stage C should propose explicit treatment:
   - Keep 3D (current) — bundle cost ~hundreds of KB
   - Replace with CSS/SVG ambient gradient — lighter, less identity
   - Drop entirely — most minimal direction
2. **Specular button** — keep the shine effect or settle on a flatter Linear-style button?
3. **Shader background** — keep the WebGL mesh, switch to a static gradient/image, or drop?
4. **Command palette aesthetic** — current Raycast-imitation is dense. Stay dense? Lighten? Embed inline within the page instead of overlay?
5. **Fonts** — Source Serif 4 + Inter Tight + JetBrains Mono. The serif is currently used heavily in Rx warnings. Direction may propose consolidating to two faces or commit further to the three-face system.

The Stage C Design Director subagent answers these for each direction (A, B, C) with concrete proposals.
