# Clinician Migration Order — Phase 2 Batches A–G

Generated: 2026-04-29
Direction: CLINICIAN (`docs/REMODEL_PHASE2_PLAN.md`)
Branch: `feature/clinician-remodel`

This file groups the 40 components in `docs/COMPONENT_INVENTORY.md` into 7 migration batches. Each batch is a unit of work for ONE Component Builder subagent. Batches A and F have no inter-dependency and run in parallel; B and C depend on A; D depends on A + B; E depends on A + B + C; G runs last (lowest priority — admin only).

For every batch: (1) component list, (2) routes that consume them, (3) backend seams from `docs/PROTECTED_CONTRACTS.md` that **must not be touched**, (4) complexity estimate, (5) dependencies.

---

## Batch A — Atomic primitives (parallelizable, NO dependencies)

**Goal**: every primitive a Clinician page mounts. Build first; everything else depends.

### Components
| File (`apps/transcribe-md/src/components/`) | LOC | Status | Migration target |
|---|---|---|---|
| `skeleton.tsx` | 94 | legacy → Clinician | Replace shimmer keyframe + colors with `--cream-2`/`--cream-3` warm palette |
| `glow-card.tsx` | 35 | legacy → Clinician | Swap to `.qm-cl-card-soft` + remove violet-glow |
| `specular-button.tsx` | 113 | legacy → Clinician | Reskin to `.qm-cl-btn-primary` + retain shine on `.qm-cl-btn-primary[data-shine]` |
| `specialty-dropdown.tsx` | 115 | legacy → Clinician | Reskin to Radix select + `.qm-cl-input` chrome |
| `toaster.tsx` | 41 | legacy → Clinician | Sonner config update — pass `theme="light"`, override toast styles to Clinician palette |
| `ui/empty-state.tsx` | 96 | neutral → Clinician | Adopt `.qm-cl-prose` body + line-art illustration slot |
| `empty-state.tsx` (top-level dup) | 106 | DROP — redirect imports to `ui/empty-state.tsx` | Delete after callers migrated; flag if any caller is missed |
| `error-fallback.tsx` | 122 | legacy → Clinician | Warm cream surface + `.qm-cl-card` + `.qm-cl-btn-soft` retry |
| `gradient-text.tsx` | 18 | neutral | Keep, but add Clinician variant `[data-variant="sage"]` for sage gradient (optional — may not survive Clinician's restraint) |
| `animated-grid.tsx` | 25 | neutral | Keep; mostly used in landing/marketing chrome — consider drop if not needed |
| `tilt-card.tsx` | 77 | neutral | Keep — no theme tokens |
| `page-wrapper.tsx` | 25 | neutral | Audit if still needed; likely deletable after `<AppFrame>` Clinician port (Batch B) |

### Routes consuming these
Every route. Atomics are global.

### Protected backend seams (do NOT modify)
- `lib/cn.ts` (className merger — used by every component; do not touch)
- Sonner's API signature (toaster.tsx wraps it; argument shape preserved)
- No server actions / API routes / hooks consumed by any Batch A component

### Complexity: **Medium**
~12 files, low logical risk, mostly className swaps + token updates. The one Vitest test (`components/rx/__tests__/rx-warning-card.test.tsx`) is NOT in this batch — it's in Batch D.

### Dependencies: **None.** Can start immediately.

---

## Batch B — Layout chrome (depends on Batch A)

**Goal**: every page shell mounts inside the right wrapper. After Batch B, every Clinician-migrated page can wrap in `<AppFrame>` and inherit the warm cream canvas + top-nav + sidebar without re-implementing.

### Components
| File | LOC | Migration |
|---|---|---|
| `ui/app-frame.tsx` | 70 | Currently wraps in `.qm-app`. Add Clinician variant: when prop `theme="clinician"` (or via route detection), wraps in `.qm-cl-app` instead. **Keep `.qm-app` mode working** for non-migrated routes during transition. |
| `ui/top-nav.tsx` | 273 | Reskin to `.qm-cl-topbar` (cream-w-blur backdrop), Source Serif 4 wordmark, `.qm-cl-input` search box, `.qm-cl-btn-soft` user-menu trigger |
| `ui/icon-rail.tsx` | 121 | Reskin to `.qm-cl-sidebar` + `.qm-cl-nav-item` family |
| `ui/auth-shell.tsx` | 208 | Reskin auth-page chrome to warm cream + line-art illustration moments (per Clinician landing) |
| `ui/page-header.tsx` | 65 | Apply Clinician type ramp (Source Serif 4 H1, DM Sans deck) |
| `ui/quill-logo.tsx` | 31 | Audit color values — should be ink-2 + sage in Clinician mode |
| `ui/word-mark.tsx` | 19 | Same — ink + sage swatch |
| `ui/avatar.tsx` | 65 | Adopt `.qm-cl-avatar` family (rounded-square serif initials, color variants) |
| `ui/local-time.tsx` | 69 | No theme tokens — verify still works |

### Routes consuming
Every page (mounts `<AppFrame>` or `<AuthShell>`).

### Protected seams
- `lib/auth.ts` (`getSession`, `requireSession`) — consumed by AppFrame's server-side parent. Do NOT modify the call signatures.
- Routes' redirect logic (login → callbackUrl) — handled by `proxy.ts` which is fully protected.

### Complexity: **Large**
~9 files, but `top-nav.tsx` and `icon-rail.tsx` are the biggest visual surface. Risky to break the existing dark-mode rendering. **Test both `.qm-app` (dark) and `.qm-cl-app` (Clinician) routes after this batch lands.**

### Dependencies: **Batch A** (uses `.qm-cl-card-soft`, `.qm-cl-btn-*`, `.qm-cl-input`)

---

## Batch C — Dashboard family (depends on Batch A + B)

**Goal**: the doctor's daily-driver. Highest visual impact for retention.

### Components
| File | LOC | Migration |
|---|---|---|
| `app/dashboard/page.tsx` | 100+ | Wrap in `.qm-cl-app`, replace dark `<AppFrame>` invocation with Clinician variant, swap dashboard-token classes |
| `dashboard/stat-card.tsx` | 68 | `.qm-cl-card` + `.qm-cl-big-num` + `.qm-cl-section-label` |
| `dashboard/patient-card.tsx` | 148 | Adopt `.qm-cl-card-soft` + `.qm-cl-avatar-{specialty}` + serif patient name |
| `dashboard/visit-list.tsx` | 209 | `.qm-cl-patient-row` family + soft pill status column |
| `patient-card.tsx` (top-level dup) | 89 | DROP — redirect imports to `dashboard/patient-card.tsx`. Flag if any non-dashboard caller exists |
| `visit-card.tsx` | 123 | Audit if still used; likely superseded by `dashboard/visit-list.tsx`. Drop if dead code. |
| `ui/empty-state.tsx` (already Batch A) | — | Used here for empty-list states |
| `lib/dashboard-pagination.ts` | — | **PROTECTED — do not modify.** Component reads `LoadMoreVisitsResult`, `DashboardCursor`, `DASHBOARD_PAGE_SIZE` byte-for-byte. |

### Routes consuming
- `/dashboard` (the main route)
- `/visits` (uses dashboard-style list)

### Protected seams
- `actions/visits.ts` — `loadMoreVisitsAction(cursor, ...)` signature must not change
- `lib/dashboard-pagination.ts` types
- `actions/patients.ts` if patient-card calls it (currently no — it consumes the type only)

### Complexity: **Large**
- 209-line visit-list.tsx is biggest single file
- Pagination: cursor-based + server-action-driven; preserve every fetch
- Has a Vitest unit test? No (only rx-warning-card has one)

### Dependencies: **Batch A** + **Batch B** (uses `<AppFrame>`)

---

## Batch D — Visit detail family (depends on Batch A + B + C)

**Goal**: the doctor's primary workspace. The biggest single chunk.

### Components
| File | LOC | Migration |
|---|---|---|
| `app/visits/[id]/page.tsx` | ~150 | Server component — wrap children in `.qm-cl-app`, swap layout structure to Clinician mockup |
| `app/visits/[id]/visit-ready-view.tsx` | (large) | Tabs row → `.qm-cl-tab-row`; SOAP section → `.qm-cl-soap-section` + `.qm-cl-prose`; status pill → `.qm-cl-pill-sage`/`-teal` |
| `app/visits/[id]/processing-state.tsx` | — | AI processing → `.qm-cl-ai-status` band with crossfade lines |
| `app/visits/[id]/visit-failed-view.tsx` | — | Coral pill + `.qm-cl-card` retry CTA |
| `app/visits/[id]/visit-lifecycle-actions.tsx` | — | `.qm-cl-btn-*` action buttons |
| `app/visits/[id]/edit-draft-dialog.tsx` | — | Radix Dialog + `.qm-cl-card` + `.qm-cl-input` |
| `app/visits/[id]/sign-and-send-modal.tsx` | — | Same — modal in Clinician chrome |
| `app/visits/[id]/soap-editor.tsx` | — | `.qm-cl-prose` body + `.qm-cl-editing` cursor + `.qm-cl-soap-letter` chips |
| `app/visits/[id]/codes-tab.tsx` | — | Pills + soft cards for ICD/CPT |
| `app/visits/[id]/rx-tab.tsx` | — | Hosts the `<RxWarningCard>` |
| `app/visits/[id]/extras-tab.tsx` | — | Misc extras |
| `app/visits/[id]/copy-section-button.tsx` | — | `.qm-cl-btn-soft` |
| `app/visits/[id]/back-link.tsx` | — | `.qm-cl-btn-ghost` |
| `app/visits/[id]/error.tsx` | — | Uses error-fallback (Batch A) |
| `app/visits/[id]/loading.tsx` | — | Skeleton (Batch A) |
| `app/visits/[id]/not-found.tsx` | — | Empty-state (Batch A) |
| `components/rx/rx-warning-card.tsx` | 518 | **Re-skin severity pills only.** Keep `.qm-warn-*` family structurally identical. New: replace gradient pills with `.qm-cl-pill-{coral,amber,sky}`. Re-test the existing Vitest. |
| `components/rx/override-confirm-modal.tsx` | 308 | Radix Dialog + Clinician chrome |

### Routes consuming
- `/visits/[id]` (the main visit-detail route — most-seen surface in the app)

### Protected seams (extensive)
- `lib/ehr-formatters.ts` — `sectionSoap`, `sectionCodes`, `sectionRx`, `sectionExtras` shapes (consumed by copy-section-button + visit-ready-view) **must not change**
- `actions/soap.ts` — `reassignSpeakerAction`, SOAP edit submissions
- `actions/visits.ts` — visit lifecycle (sign, retry, archive, etc.)
- `lib/rx-warning-audit.ts` ('use server') — consumed by rx-warning-card + override-confirm-modal
- `lib/visit-export.ts` → `VisitExportData` type
- `lib/visit-export-server.ts` (server-side; do not touch)
- API: `/api/visits/[id]/*` and `/api/visits/[id]/export/*` — all 14 routes are protected
- `packages/types/src/soap.ts` — `SoapNoteSchema` is consumed everywhere here

### Complexity: **Extra-Large**
- 16 files in `app/visits/[id]/`
- 518-line rx-warning-card with Vitest test (must stay green)
- Multiple server actions consumed
- The most-seen UI in the app

### Dependencies: **Batch A** + **Batch B** + **Batch C** (uses card/pill/avatar primitives, layout chrome, dashboard's pagination types)

---

## Batch E — Visit creation flow (depends on Batch A + B)

**Goal**: the magic moment. Recording widget halo, transcript slide-fade, AI status crossfade.

### Components
| File | LOC | Migration |
|---|---|---|
| `app/visits/new/page.tsx` | — | `.qm-cl-app` wrap + Clinician form chrome |
| `app/visits/[id]/record/page.tsx` | — | Wrap in Clinician |
| `app/visits/[id]/record/recording-client.tsx` | — | The active recording scene |
| `audio-uploader.tsx` | 274 | `.qm-cl-card` + `.qm-cl-btn-primary` + soft drop-zone styling |
| `voice-dictator.tsx` | 342 | `.qm-cl-halo` + `.qm-cl-mic-dot` + `.qm-cl-wave-bar` + `.qm-cl-transcript-line` family. **Most complex motion in the app.** |
| `text-composer.tsx` | 152 | Form `.qm-cl-input` + `.qm-cl-btn-soft` actions |
| `recording/live-orb.tsx` | 163 | **DROP or replace** — Three.js orb is too cinematic for Clinician's quiet halo idiom. Replace with the soft 8 px halo + breathing dot. |
| `violet-orb.tsx` (top-level) | 242 | DROP from Clinician routes (still used elsewhere — gate by `.qm-cl-app` selector) |
| `visit-orb.tsx` | 29 | Wrapper — drop or simplify |
| `ui/shader-bg.tsx` | 128 | DROP from Clinician routes |
| `specialty-dropdown.tsx` (Batch A already) | 115 | Used here for specialty pick |
| `command-palette.tsx` | 300 | `cmdk` + Clinician chrome — `.qm-cl-input` search, `.qm-cl-card` panel, soft pills for kbd hints |
| `user-menu.tsx` | 102 | Avatar trigger + Radix dropdown in Clinician chrome |
| `global-shortcuts.tsx` | 60 | No visual change — keyboard handler |

### Routes consuming
- `/visits/new`
- `/visits/[id]/record`
- (command palette is global — accessible from every page)

### Protected seams
- `actions/visits.ts` — `createVisitAction(formData)` signature
- `actions/command-palette.ts` — server-side search
- API routes: `/api/visits/[id]/upload`, `/api/visits/[id]/dictation/audio`, `/api/visits/[id]/dictation/upload`
- MinIO upload paths (`lib/minio.ts` server-side)
- Audio recording APIs (browser MediaRecorder — no protected zone, just don't break it)

### Complexity: **Extra-Large**
- 342-line voice-dictator with WebRTC + WebSocket + animation
- Most complex motion (recording halo, mic-breath, transcript slide-fade)
- Three.js drop decision per direction CL-5 (no Three.js orbs in Clinician)
- Command palette has its own state model (cmdk)

### Dependencies: **Batch A** + **Batch B**

---

## Batch F — Auth screens (parallelizable, NO dependencies on B/C)

**Goal**: the first impression. Should match the landing's warmth (per Clinician landing-and-recording mockup), not the dashboard's density.

### Components / routes
| Route | File | Migration |
|---|---|---|
| `/login` | `app/login/page.tsx` | `<AuthShell>` + Clinician hero idiom (sage line-art illustration, soft cream card, sage CTA) |
| `/signup` | `app/signup/page.tsx` | Same chrome — multi-step form in soft card |
| `/forgot-password` | `app/forgot-password/page.tsx` | Single-input form in soft card |
| `/reset-password` | `app/reset-password/page.tsx` | Two-input form |
| `/check-email` | `app/check-email/page.tsx` | Soft confirmation — italic-serif copy + warm illustration |

(There's no `app/(auth)/` route group today — auth pages are top-level. Subagent operates at the top level.)

### Protected seams
- `actions/auth.ts` — login/signup/forgot/reset actions; **DO NOT TOUCH** (full protection)
- API routes: `/api/auth/[...nextauth]/`, `/api/auth/forgot-password/`, `/api/auth/reset-password/`, `/api/auth/verify-email/`, `/api/auth/confirm-email/`, `/api/auth/resend-verification/`
- `lib/auth.config.ts`, `lib/nextauth.ts`, `lib/auth.ts`, `lib/auth-tokens.ts` — all NextAuth machinery, fully protected
- `proxy.ts` — edge middleware, fully protected

### Complexity: **Medium**
- 5 routes
- Each is a single page with a form
- The biggest risk is preserving the form's `<form action={someServerAction}>` invocation — visual swap only

### Dependencies: **Batch A** (uses `.qm-cl-card`, `.qm-cl-btn-primary`, `.qm-cl-input`). Implicitly depends on `<AuthShell>` from Batch B for the chrome — but the subagent can either:
- (a) Wait for Batch B's `<AuthShell>` reskin
- (b) Reskin `<AuthShell>` inline as part of Batch F (it's auth-only)

Decision: **Batch F includes reskinning `<AuthShell>`** because that component is used ONLY by auth pages. Move it from Batch B → Batch F. Batch B's scope reduces by 1 file (208 LOC).

---

## Batch G — Admin screens (lowest priority — gated to SUPER_ADMIN)

**Goal**: maintain visual consistency in the platform-admin surface.

### Components / routes
| Route | File |
|---|---|
| `/admin` | `app/admin/page.tsx` |
| `/admin/users` | `app/admin/users/page.tsx` + `_components/AdminNav.client.tsx`, `AdminOverview.client.tsx`, `_lib/admin-format.ts`, `_lib/dashboard-data.ts`, `_lib/users-data.ts` |
| `/admin/usage` | `app/admin/usage/page.tsx` |
| `/admin/threats` | `app/admin/threats/page.tsx` |
| `/admin/hipaa` | `app/admin/hipaa/page.tsx` |
| `/admin/layout.tsx` | The notFound() gate — **DO NOT CHANGE the gate logic, only the visual frame** |
| `/dev/rx-warnings` | Dev-only playground — defer or skip |

Plus `/settings` (user-level settings, not strictly admin):
- `app/settings/page.tsx` — settings forms in Clinician chrome

### Protected seams (admin-heavy)
- ALL `/api/admin/*` routes — 21 protected routes
- `lib/admin-api-gate.ts` (server-side authorization)
- `lib/admin-notifications.ts`
- `lib/admin-session-freshness.ts`
- `app/admin/layout.tsx` — `notFound()` gate is DELIBERATE (security note in PROTECTED_CONTRACTS.md §3); only the JSX inside it is touchable
- `app/admin/_lib/*.ts` — server-side data fetchers for admin pages

### Complexity: **Medium-Large**
- ~6 routes
- Tables-heavy (users list, usage timeline, threats list, HIPAA findings)
- Tables in Clinician get `.qm-cl-card` + `.qm-cl-patient-row`-style rows (re-purpose for users / threats / etc.)

### Dependencies: **Batch A** + **Batch B**

---

## Stage 3 launch (THIS turn)

The lead agent launches **2 parallel subagents** for **Batch A** and **Batch F** (revised — Batch F includes `<AuthShell>` reskin since it's auth-only). Both have no inter-batch dependency, can run in parallel.

After Stage 3 lands:
1. Both subagents push their commits to `feature/clinician-remodel`
2. Lead agent reports back with file change list, commit count, test failures
3. **STOP for user sign-off**
4. After sign-off, Stage 4 launches Batch B and Batch C in parallel

---

## Open questions for the user (low priority — can decide after Stage 3)

1. **`<AuthShell>` ownership**: I moved it from Batch B → Batch F (auth-only consumer). Confirm OK.
2. **Dropping `violet-orb.tsx` / `visit-orb.tsx` / `recording/live-orb.tsx` / `ui/shader-bg.tsx`**: Clinician explicitly rejects Three.js theatrical moments. Drop entirely OR gate to non-Clinician routes only? Recommendation: gate by `.qm-app` selector — keep them working for any non-migrated route, drop from Clinician routes.
3. **`patient-card.tsx` (top-level)** vs `dashboard/patient-card.tsx`: top-level appears unused after dashboard migration. Confirm it's safe to delete in Batch C.
4. **`visit-card.tsx`** vs `dashboard/visit-list.tsx`: visit-card.tsx may also be dead code post-migration. Same — confirm before deleting.
5. **PR strategy**: per-batch PR or single Phase 2 mega-PR? Recommendation: per-batch for review granularity. User overrideable.
