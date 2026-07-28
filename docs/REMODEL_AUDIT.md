# QuillMD Remodel Audit

Generated: 2026-04-29
Repo: `/opt/meddoc-pro` @ `main` (HEAD `0f27cb9` — Phase 19, working tree clean)

## TL;DR

QuillMD is a 3-app npm-workspace monorepo (`marketing`, `meddoc-pro`, `transcribe-md`) plus 4 shared packages (`@meddoc/ai|auth|db|types`). The user's mental subdomain model is slightly off: **`pro.quillmd.com` is not a marketing site — it's a legacy CRM/EHR app** (`apps/meddoc-pro`, with Zustand + blue-medical theme). The true marketing site is at the apex `quillmd.com` (`apps/marketing`). The Transcribe-MD app at `app.quillmd.com` and the admin surface at `admin.quillmd.com` **are the same Next.js app** (`apps/transcribe-md`, both routed to port 3011) — `/admin/*` routes live inside it, gated by a `Product.SUPER_ADMIN` check in `app/admin/layout.tsx`. A redesign-in-progress is already partially merged into `apps/transcribe-md/src/app/globals.css` (the "App-redesign-v1" / HANDOFF token block, ~lines 80–250 of a 1,324-line file), referencing a `/tmp/design_handoff_quillmd_app/` source that no longer exists on disk — this is the single biggest hazard for a fresh remodel. Stack: Next.js **^16.2.4** (the repo's `AGENTS.md` warns this is *not* the Next.js you know — read the bundled `node_modules/next/dist/docs/` before writing code), React 19.2.4, Tailwind **v4 with CSS-first config** (no `tailwind.config.ts`), NextAuth v5 beta gated via `proxy.ts` (Next 16's renamed `middleware.ts`), Prisma 7 with 28 models / 41 migrations, BullMQ worker for the 7-layer AI pipeline. Frontend has **no client-side state library at all** in `transcribe-md` — every screen is a server component fetching Prisma → passing data to `'use client'` leaves that call server actions back. Protected zone is large: 62 API routes + 7 server-action files + the worker + `@meddoc/ai` + the entire Prisma schema. The remodel is feasible because the seam is well-defined (server actions return typed shapes; client components consume them via `useTransition`), but the UI is more entangled than first appears: **`apps/transcribe-md/src/components/` (41 files) and `apps/transcribe-md/src/app/visits/[id]/` (16 files)** make up most of the surface and import directly from `@/lib/*` and `@/actions/*`. A 5–7 specialist agent team is recommended (see §8). Major open questions for the user are in §9, with the scope question — "is `pro.quillmd.com` (the legacy meddoc-pro CRM) in scope?" — being the most consequential.

---

## 1. Repo overview

### Tooling

| Item | Value |
|---|---|
| Monorepo type | npm workspaces (`workspaces: ["apps/*", "packages/*"]`) — NOT pnpm, NOT turbo, NOT nx |
| Package manager | npm (`package-lock.json` ~600 KB) |
| TS base config | `tsconfig.base.json` at root |
| Lint | per-app `eslint.config.mjs` (flat config) |
| Test runner | Vitest 4 (unit) + Playwright 1.59 (e2e) |
| CI | `.github/` (not enumerated in this audit) |
| Reverse proxy | Caddy (`Caddyfile`, 11 KB) |
| Containerization | `docker-compose.yml` (10 services + 5 volumes) |
| Observability | Sentry (`@sentry/nextjs` + `@sentry/node`); per-app instrumentation.ts |

### Apps × subdomains × ports

| Subdomain | App folder | Container port | Purpose | Notes |
|---|---|---|---|---|
| `quillmd.com` / `www.quillmd.com` | `apps/marketing` | 3010 | Public marketing site | Static-ish Next.js, dark/violet design (matches transcribe-md), 10 pages, Three.js used for hero |
| `pro.quillmd.com` | `apps/meddoc-pro` | 3000 | **Legacy CRM/EHR** (the original product before transcribe-md spun off) | Light/blue medical theme, **the only app that uses Zustand**, has its own `dashboard` + `system-admin` surfaces |
| `app.quillmd.com` | `apps/transcribe-md` | 3011 | **TranscribeMD** — the AI scribe app (this is the user's primary remodel target) | Dark/violet theme; has a redesign-in-progress already merged into `globals.css` |
| `admin.quillmd.com` | `apps/transcribe-md` | 3011 | **Platform admin** — same Next app, routes under `/admin/*` | Caddy routes the admin host to identical app; gating is in-app via `Product.SUPER_ADMIN` |

### Docker services (`docker-compose.yml`)

`postgres`, `redis`, `minio`, `caddy`, `marketing` (Next), `meddoc-pro` (Next), `transcribe-md` (Next), `transcribe-md-worker` (BullMQ consumer, separate Dockerfile `Dockerfile.worker`), `db-migrate` (one-shot Prisma deploy), `postgres-backup` (sidecar from T-M16.4).

### Packages (`packages/`)

| Package | Purpose | Notable exports |
|---|---|---|
| `@meddoc/ai` | Anthropic + Deepgram + embeddings | `ModelClient`, `redactPhi`, `logAiCall`, `deepgramBatchCostCents`, `claudeSonnet46CostCents` |
| `@meddoc/auth` | Shared NextAuth config (edge-safe) + UserSession helpers | `authConfig`, `Session`, `UserRole`, `AuthError` |
| `@meddoc/db` | Prisma client (re-export) + schema + migrations | `prisma` (default export), schema in `packages/db/prisma/schema.prisma` |
| `@meddoc/types` | SOAP Zod schemas | `SoapNoteSchema`, `AssessmentItemSchema`, `ConfidenceLevel`, render helpers |

### Repo-level project guidance

- `CLAUDE.md` is one line: `@AGENTS.md`.
- `AGENTS.md` (single block): warns Next.js in this repo is post-breaking-change ("NOT the Next.js you know") — anyone writing code must read `node_modules/next/dist/docs/` first. Heed deprecations.

---

## 2. Frontend surface (THE THING BEING REMODELED)

### 2.1 `apps/transcribe-md` — TranscribeMD (`app.quillmd.com` + `admin.quillmd.com`) — DEFINITE remodel target

**Routes (20 page.tsx files):**

| Route | File | Surface |
|---|---|---|
| `/` | `app/page.tsx` | Authed-shell landing (redirects to `/dashboard` when signed in) |
| `/login` | `app/login/page.tsx` | Login |
| `/signup` | `app/signup/page.tsx` | Signup |
| `/check-email` | `app/check-email/page.tsx` | Post-signup verification waiting screen |
| `/forgot-password` | `app/forgot-password/page.tsx` | Forgot-password form |
| `/reset-password` | `app/reset-password/page.tsx` | Reset-password form |
| `/dashboard` | `app/dashboard/page.tsx` | Patients tab (default) + ?tab=all visits — uses new `<AppFrame>` shell (already on App-redesign-v1) |
| `/visits` | `app/visits/page.tsx` | All-visits list |
| `/visits/new` | `app/visits/new/page.tsx` | Create-visit form (specialty + patient picker + input mode) |
| `/visits/[id]` | `app/visits/[id]/page.tsx` | The single biggest screen — visit lifecycle (uploader → processing → ready → signed) |
| `/visits/[id]/record` | `app/visits/[id]/record/page.tsx` | Live recording capture |
| `/patients` | `app/patients/page.tsx` | Patient list |
| `/patients/[id]` | `app/patients/[id]/page.tsx` | Patient detail + history |
| `/settings` | `app/settings/page.tsx` | User settings (email/password/account/data export) |
| `/dev/rx-warnings` | `app/dev/rx-warnings/page.tsx` | Dev-only Rx warning playground |
| `/admin` | `app/admin/page.tsx` | Platform admin home (gated `Product.SUPER_ADMIN`) |
| `/admin/users` | `app/admin/users/page.tsx` | User management |
| `/admin/usage` | `app/admin/usage/page.tsx` | API usage analytics |
| `/admin/threats` | `app/admin/threats/page.tsx` | Security threat detector dashboard |
| `/admin/hipaa` | `app/admin/hipaa/page.tsx` | HIPAA findings dashboard (Phase 7B) |

`app/visits/[id]/` is unusually fat: **16 files** (page + 6 client `*-tab.tsx` / dialog / editor / lifecycle-actions / processing-state / ready/failed views, plus `error.tsx`/`loading.tsx`/`not-found.tsx`). This single screen is half the in-app surface area visually.

**Component inventory (`apps/transcribe-md/src/components/` — 41 .tsx files):**

| Category | Files |
|---|---|
| Shell/chrome (mostly under `components/ui/`) | `app-frame.tsx`, `auth-shell.tsx`, `top-nav.tsx`, `icon-rail.tsx`, `page-header.tsx`, `quill-logo.tsx`, `word-mark.tsx` |
| Atomic UI (also under `components/ui/`) | `avatar.tsx`, `icon.tsx`, `local-time.tsx`, `empty-state.tsx`, `spec-chip.tsx`, `shader-bg.tsx` |
| Visual flourish | `animated-grid.tsx`, `gradient-text.tsx`, `glow-card.tsx`, `tilt-card.tsx`, `specular-button.tsx`, `violet-orb.tsx`, `visit-orb.tsx` |
| Feature — visit creation/recording | `audio-uploader.tsx`, `voice-dictator.tsx`, `text-composer.tsx`, `recording/live-orb.tsx` |
| Feature — dashboard | `dashboard/patient-card.tsx`, `dashboard/stat-card.tsx`, `dashboard/visit-list.tsx` (also a top-level `patient-card.tsx` + `visit-card.tsx` — duplication risk) |
| Feature — Rx safety | `rx/rx-warning-card.tsx`, `rx/override-confirm-modal.tsx` (+ Vitest test) |
| Feature — global UX | `command-palette.tsx`, `global-shortcuts.tsx`, `user-menu.tsx`, `toaster.tsx`, `specialty-dropdown.tsx` |
| Misc | `page-wrapper.tsx`, `error-fallback.tsx`, `skeleton.tsx`, `empty-state.tsx` (top-level; second copy of the `ui/` one) |

> Two pairs of near-duplicates worth flagging: top-level `patient-card.tsx` vs `dashboard/patient-card.tsx`; top-level `empty-state.tsx` vs `ui/empty-state.tsx`. The remodel should consolidate.

**UI library / design system:**

- **No shadcn** (`components.json` absent).
- **Custom component layer** under `src/components/ui/` (13 files; not generated, hand-written).
- Underlying primitives via Radix: `@radix-ui/react-dialog`, `react-dropdown-menu`, `react-select`, `react-toast` are direct deps.
- `cmdk` 1.x for the command palette. `sonner` 1.7 for toasts (instantiated via `components/toaster.tsx`).
- `lucide-react` for icons (wrapped through `components/ui/icon.tsx` — a thin `<Ic name="..."/>` indirection).
- 3D: `@react-three/fiber` 9 + `@react-three/drei` 10 + `three` 0.169 — used by the orb components and shader background.

**Theme / design tokens:**

- Tailwind v4 with **CSS-first config** (no `tailwind.config.ts` anywhere in the app — `globals.css` is the source of truth via `@theme` directive).
- `apps/transcribe-md/src/app/globals.css` = **1,324 lines**.
- Two coexisting token systems in the same file:
  1. The original "TranscribeMD design tokens — Linear/Raycast/Vercel/Resend idiom" (deep dark + violet brand + cyan/green/amber/red status), tokens like `--color-bg-base`, `--color-violet-500`, `--color-text-primary`.
  2. The **App-redesign-v1 tokens** ported from `/tmp/design_handoff_quillmd_app/app/tokens.css` (HANDOFF §1, ~line 80 onward) — `--color-bg`, `--color-bg-1..4`, `--color-line`, `--color-accent`, `--color-mint`, plus bare-name `:root` aliases. Comment explicitly says these tokens were "ported 1:1" — the `/tmp/design_handoff_quillmd_app/` directory **no longer exists on this machine**, so the design source-of-truth is no longer reachable from disk.
- Fonts: Geist Sans + Geist Mono (already-installed `geist` package) **plus** the App-redesign-v1 trio (Source Serif 4 → `--serif`, Inter Tight → `--sans`, JetBrains Mono → `--mono`) loaded in `app/layout.tsx`. Both font systems are live simultaneously.
- `tailwindcss-animate` 1.0.7 plugin loaded via `@plugin` directive (a v3-era plugin). Comment in `globals.css` notes the utilities are also duplicated inline as a fallback.

**Animation deps:**
- `framer-motion` ^11.11.11 (note: `apps/meddoc-pro` uses ^12.38.0 — **version drift across apps**).
- No GSAP / Lottie / Motion-One.

**Other notable deps:** `bcryptjs`, `bullmq`, `ioredis`, `minio`, `next-auth@5.0.0-beta.30`, `pdfkit`, `docx`, `archiver`, `resend`, `zod@4.3.6`.

**Frontend LOC (rough):**
- `apps/transcribe-md/src/components/` ≈ 41 .tsx files; sampled sizes range 50–700 lines each → **~8–12K LOC** estimated.
- `apps/transcribe-md/src/app/` page + co-located UI files (excluding `api/`) ≈ 30–40 files → **~6–10K LOC**.
- `globals.css` 1,324 lines.
- Combined frontend code in transcribe-md alone: **~15–25K LOC** rough order. (`wc -l` over the actual files would give an exact figure.)

**Subjective design observations (facts only):**

- Two design systems co-exist in a single `globals.css` — the older "Linear/Raycast/Vercel/Resend" tokens and the newer App-redesign-v1 HANDOFF tokens. Some components reference the old tokens (`bg-bg-base`, `text-violet-400`); the dashboard and `<AppFrame>` reference the new ones.
- Heavy use of effect components: `violet-orb.tsx`, `visit-orb.tsx`, `live-orb.tsx`, `shader-bg.tsx`, `animated-grid.tsx`, `tilt-card.tsx`, `glow-card.tsx`, `specular-button.tsx`, `gradient-text.tsx`. Three.js + framer-motion drive these. Performance budget will be tight on entry-level hardware.
- Component duplication (two `patient-card.tsx`, two `empty-state.tsx`).
- No design-system docs in the repo besides `docs/design/rx_warning_handoff/` (a one-feature handoff: `DESIGN_SPEC.md`, `tokens.css`, `spec-page.html`, `screenshots/`, `variants/`).
- No Storybook / Ladle / Playroom present.

### 2.2 `apps/marketing` — `quillmd.com` (TBD: USER DECIDES if in scope)

- 10 routes (`/`, `/about`, `/contact`, `/demo`, `/hipaa`, `/pricing`, `/privacy`, `/security`, `/signup`, `/terms`).
- 28 .tsx components in `src/components/` (top-level: `animated-grid`, `badge`, `footer`, `glow-card`, `gradient-border`, `gradient-text`, `nav-bar`, `specular-button`, `tilt-card`, plus a `home/` subfolder).
- Same dark/violet design idiom as transcribe-md. `globals.css` is 271 lines — a smaller, derivative copy of the transcribe-md token set (header comment says so verbatim: "TranscribeMD design tokens — Linear/Raycast/Vercel/Resend idiom").
- Animation: `framer-motion` ^11.11.11 + `three` 0.169. No `@react-three/fiber` here (raw three.js usage only).
- `src/hooks/` directory exists (transcribe-md has no `hooks/` dir).
- No backend code, no API routes, no auth.

### 2.3 `apps/meddoc-pro` — `pro.quillmd.com` (TBD: this is **NOT** a marketing site — see TL;DR. USER DECIDES if in scope)

- 15 routes including a full `/dashboard/*` family (`audit`, `doc-editor`, `history`, `patients/*`, `schedule`, `settings`) plus a `/system-admin/*` family (`audit`, `metrics`).
- 12 API routes (separate from transcribe-md's 62).
- 16 .tsx components in `src/components/` (`dashboard/`, `landing/`, `system-admin/`, `ui/`, `LogoutButton.tsx`).
- Different design language: light/blue medical palette (`--color-primary-500: #3b82f6` blue + teal accent). 248-line `globals.css`. **No App-redesign-v1 tokens** — this app is on a separate visual track.
- **The only app that uses Zustand** (^5.0.12). All transcribe-md client state is component-local + server-action.
- `framer-motion` is on **^12.38.0** (one major version ahead of transcribe-md/marketing on ^11.11.11).
- Has its own Playwright + Vitest test suites (5 e2e, 9 unit — see §5).

If the user keeps this app in scope, treat it as an **independent remodel** — different palette, different animation lib version, different state library. Reusing components across apps will require a `@meddoc/ui` package that does not currently exist.

---

## 3. Protected zone (THE THING THAT MUST NOT CHANGE)

Everything below is treated as a read-only contract by the remodel.

### 3.1 API routes — 62 in transcribe-md, 12 in meddoc-pro

| Group | Path prefix (transcribe-md) | Why protected |
|---|---|---|
| Auth | `/api/auth/[...nextauth]/route.ts`, `/api/auth/forgot-password`, `/api/auth/reset-password`, `/api/auth/verify-email`, `/api/auth/confirm-email`, `/api/auth/resend-verification` | NextAuth contract + token state machine. Changing the URLs breaks server-side redirect targets and email links already in production. |
| Visits lifecycle | `/api/visits/[id]/{route,status,progress,upload,sign,retry,delete,archive,unarchive,restore,text}` | These drive the BullMQ pipeline status display. The frontend polls `/api/visits/[id]/progress`. |
| Visit dictation | `/api/visits/[id]/dictation/{audio,upload}` | MinIO upload paths used by `voice-dictator.tsx`. |
| Visit export | `/api/visits/[id]/export/{clipboard,docx,email,pdf}` | Patient/clinic delivery surface. PDF/DOCX generators are heavy and stable. |
| Patients | `/api/patients/{route,[id]/route,[id]/export,fuzzy-match}` | Includes the fuzzy-match endpoint the patient-picker relies on (deduplicating "Smith, John" vs "John Smith"). |
| Settings | `/api/settings/{change-email,change-password,delete-account,export-data}` | Account state mutations + GDPR-style data export. |
| Admin | `/api/admin/users/[id]/{...}`, `/api/admin/audit-logs/*`, `/api/admin/hipaa/*`, `/api/admin/threats/*`, `/api/admin/usage/*`, `/api/admin/system/*`, `/api/admin/stream/activity` | Platform-admin surface; many `[id]` parameterized actions. The `/api/admin/stream/activity` route is an SSE stream — careful not to layout-shift it. |
| Misc | `/api/health`, `/api/client-errors` | Health probe + browser error capture. |

### 3.2 Server actions — 7 files

All under `apps/transcribe-md/src/actions/`:

- `visits.ts` — `createVisitAction`, `loadMoreVisitsAction` (cursor pagination)
- `patients.ts` — patient CRUD
- `soap.ts` — `reassignSpeakerAction` (consumed by `visit-ready-view.tsx`); SOAP edit submissions
- `profile.ts` — user profile mutations
- `session.ts` — session lifecycle
- `command-palette.ts` — server-side search backing the command palette
- `auth.ts` — login/signup/forgot-password actions

Plus 4 lib files marked `'use server'` (paginations + Rx warning audit) — semantically identical to actions, just colocated.

### 3.3 Hooks — almost none

No custom React `use*` hooks in `apps/transcribe-md/src` (a grep for `^export (const|function) use[A-Z]` returned only `lib/shortcuts.ts`, which exports keyboard-shortcut utilities). Stated plainly: **the remodel does not have to worry about a hooks layer in transcribe-md** — there isn't one. State is component-local + server actions.

### 3.4 State stores — none in transcribe-md

- **No Zustand, Redux, Jotai, Recoil, Valtio, React Query, or SWR** in `apps/transcribe-md`.
- **No `createContext` providers** in `apps/transcribe-md/src`.
- The only app with Zustand is `apps/meddoc-pro`. If meddoc-pro is in scope, its Zustand stores are protected (locations not enumerated in this audit pass — grep `from "zustand"` in that app to enumerate).

### 3.5 Auth machinery

| File | Purpose | Protect because |
|---|---|---|
| `apps/transcribe-md/src/proxy.ts` | Next 16-renamed edge middleware. Uses `@/lib/auth.config` to gate `/dashboard/*`, `/visits/*`, `/settings/*`. | Renaming or deleting breaks all session-gated routes. |
| `apps/transcribe-md/src/lib/auth.config.ts` | Re-exports `authConfig` from `@meddoc/auth` (edge-safe; no Prisma). | Any edge runtime that touches Prisma will fail to deploy. |
| `apps/transcribe-md/src/lib/nextauth.ts` | Full Node-side NextAuth instance — Credentials provider + session.maxAge override. | Where login actually happens. |
| `apps/transcribe-md/src/lib/auth.ts` | `getSession()` wrapper — re-reads DB on each call to honour `isActive` revocation. Also exports `requireSession`. | Single-session enforcement + immediate revocation depend on this. |
| `apps/transcribe-md/src/app/admin/layout.tsx` | Admin gate: returns `notFound()` (not `redirect`) when caller lacks `Product.SUPER_ADMIN`. | Deliberate — exposes nothing to anonymous probing. **A reflexive "redirect to /login" change is a security regression.** |
| `apps/transcribe-md/src/lib/auth-tokens.ts` | Email-verification + password-reset token state machine. | Token-lifecycle bugs leak account access. |
| `packages/auth/src/{index,user-session}.ts` | Shared edge-safe config + `UserSession` Prisma helper for single-session. | Cross-app contract. |

### 3.6 Workers / sidecars

- `apps/transcribe-md/src/worker.ts` (entrypoint) + `worker-sentry.ts` + `src/worker/` directory:
  - `layers/01-transcribe.ts`, `01b-transcribe-dictation.ts`, `02-speaker-roles.ts`, `03-extract-entities.ts`, `04-generate-soap.ts`, `05-self-critique.ts`, `06-polish.ts`, `07a-icd-coding.ts`, `07b-cpt-coding.ts`, `07c-rx-drafting.ts`, `07d-referrals.ts`, `07e-patient-summary.ts`, `readability.ts`
  - `prompts/specialty-guidance.ts`
  - `cleanup/`, `error-categorize.ts`, `error-categorize.test.ts`, `retry-decision.ts`, `retry-decision.test.ts`, `layer-skip.ts`
- Runs as the `transcribe-md-worker` Docker service (separate `Dockerfile.worker`).
- Pulls jobs off the shared `transcribe-md` BullMQ queue. **Frontend never calls the worker directly — only via API routes / status polls.**
- `WORKER.md` at the app root documents the pipeline.

### 3.7 DB schema

- `packages/db/prisma/schema.prisma` — **1,980 lines, 28 models**.
- 41 migration folders.
- Models the remodel must NOT reshape (FK or required fields): `Practice`, `User`, `Account`, `Session`, `VerificationToken`, `AuthToken`, `AccountDeletion`, `Patient`, `Document`, `AuditLog`, `Appointment`, `Allergy`, `Medication`, `Task`, `BillingEvent`, `SessionLog`, `ApiUsageLog`, `ApiUsage`, `AiCall`, `TranscribeMdPatient`, `TranscribeVisit`, `VisitDelivery`, `DoctorEditPattern`, `UserSession`, `RxWarningOverride`, `ApiUsageEvent`, `ThreatResolution`, `HipaaFinding`.
- The CRM `Patient` and the transcribe-md `TranscribeMdPatient` are **distinct models** (legacy carve-out — see auto-memory note about both coexisting after T-M17.2). Server actions / API routes that mention "patient" must be checked for which one they hit.

### 3.8 AI pipeline (`packages/ai`)

- `model-client.ts` — Anthropic + OpenAI dispatch (apps that use Anthropic only call through this).
- `deepgram-batch.ts` — Deepgram batch transcription.
- `embed.ts` — OpenAI embedding (text-embedding-3-small, dimension constant exported).
- `pricing.ts` — cost/cents conversions for billing event recording.
- `prompt-hash.ts` — `hashPrompt` for deterministic cache keys + audit reproducibility.
- `log.ts` — `logAiCall` (writes to `AiCall` table) + **`redactPhi`** (the canonical PHI scrubber — also referenced in `sentry.server.config.ts` and `sentry.edge.config.ts` of transcribe-md to scrub crash payloads).

`@meddoc/ai` is consumed by both `apps/transcribe-md` (worker + a few server-side helpers) and `apps/meddoc-pro` (Doc Editor + Clinical Notes).

### 3.9 PHI redaction utility

- `redactPhi` — exported from `@meddoc/ai`, defined in `packages/ai/src/log.ts`.
- Direct importers on disk: `packages/ai/src/index.ts`, `apps/marketing/src/app/security/page.tsx` (likely a security-page demo / screenshot), `apps/transcribe-md/sentry.server.config.ts`, `apps/transcribe-md/sentry.edge.config.ts`.
- The redactor must be invoked by every code path that logs user-supplied text. The remodel should not introduce new error-logging code paths that bypass it.

### 3.10 Tests covering the protected zone

See §5 for the full inventory. Key protective tests:
- Worker pipeline: `tests/worker/{ehr-formatters,edit-tracking,minio-orphans,auth-tokens,layer-skip,rate-limit,edit-distance,generators,readability,embed-mock}.test.ts`.
- E2E in transcribe-md: `tests/e2e/scenarios/{1-audio-upload-full,2-voice-dictation,3-text-to-soap,4-back-to-dashboard}.spec.ts` — full happy paths through the UI shell, will fail loudly on broken routes/selectors.
- Root-level e2e (`tests/automated/e2e/*`): cross-cutting (`product-separation.spec.ts`, `mobile-responsiveness.spec.ts`, `email-destination-guard.spec.ts`, `soap-determinism.spec.ts`, `password-policy.spec.ts`, `rate-limiting.spec.ts`, `full-visit-flow.spec.ts`).

---

## 4. Seam contracts (the API between #2 and #3)

The new frontend must consume these byte-for-byte.

### 4.1 Type definitions (Zod-defined, traveling across server↔client)

| Type / file | Purpose |
|---|---|
| `packages/types/src/soap.ts` → `SoapNoteSchema`, `AssessmentItemSchema`, `ConfidenceLevel`, `SoapNote` | The SOAP note shape — every visit's main payload. AI output must validate against this before persisting. The doctor's editor reads and writes it. |
| `packages/types/src/soap-render.ts` | Render helpers (text/markdown projections of a SOAP note). |
| `apps/transcribe-md/src/lib/visit-export.ts` → `VisitExportData` | Shape passed to clipboard/docx/email/pdf exporters. |
| `apps/transcribe-md/src/lib/dashboard-pagination.ts` → `DashboardCursor`, `LoadMoreVisitsResult`, `DASHBOARD_PAGE_SIZE` | Cursor-paginated visits feed for the dashboard. |
| `apps/transcribe-md/src/lib/patients-pagination.ts` + `patients-query.ts` | Same pattern for patients. |
| `apps/transcribe-md/src/lib/ehr-formatters.ts` → `sectionSoap`, `sectionCodes`, `sectionRx`, `sectionExtras` | Section formatters consumed by `visit-ready-view.tsx` + the Copy buttons. |
| `apps/transcribe-md/src/app/visits/[id]/visit-ready-view.tsx` → exports `Utterance`, `SpeakerInfo` types | Speaker-attribution UI types (the diarized transcript view). |

### 4.2 Server-action signatures (the actual call sites)

The 11 `'use server'` files listed in §3.2 expose the runtime contract. The new frontend can re-implement the visual layer only if it calls each action with the same argument shape and consumes the same return type. Top-of-file imports show the shapes (e.g. `createVisitAction(formData: FormData): Promise<void>` — uses native FormData; redirects on success).

### 4.3 No tRPC, no GraphQL, no openapi.json

This codebase has no formal API contract document. The seam is the union of (a) the Zod schemas, (b) the action signatures, and (c) the JSON shapes API routes return. Anyone remodeling has to read each protected file to know what props the new page expects.

### 4.4 No `lib/api` adapter layer

A grep for `apps/transcribe-md/src/lib/api*` returns nothing. Pages call server actions or do `fetch('/api/...')` inline (e.g. progress polling in `visit-ready-view.tsx`). There is no centralized API client to refactor — the remodel will need to either preserve the inline pattern or introduce an adapter layer (which is itself a refactor outside the "frontend remodel" scope).

---

## 5. Existing tests

### 5.1 Test-file inventory (39 files)

**`apps/transcribe-md/`:**

| File | Scope | Risk to remodel |
|---|---|---|
| `src/lib/deepgram-vocabulary.test.ts` | Vocabulary boost list correctness | None (lib-only) |
| `src/worker/error-categorize.test.ts` | Worker error-class mapping | None |
| `src/worker/retry-decision.test.ts` | Retry-policy logic | None |
| `tests/worker/ehr-formatters.test.ts` | EHR section formatters | **Medium** — frontend imports `ehr-formatters.ts` for the Copy buttons; if the remodel changes copied-text shape it breaks here |
| `tests/worker/edit-tracking.test.ts` | SOAP edit-distance tracking | None |
| `tests/worker/minio-orphans.test.ts` | MinIO cleanup | None |
| `tests/worker/auth-tokens.test.ts` | Verification token state machine | None |
| `tests/worker/layer-skip.test.ts` | Pipeline layer skip rules | None |
| `tests/worker/rate-limit.test.ts` | Redis rate limiter | None |
| `tests/worker/edit-distance.test.ts` | Edit-distance util | None |
| `tests/worker/generators.test.ts` | DOCX/PDF generators | None |
| `tests/worker/readability.test.ts` | Reading-level scoring | None |
| `tests/worker/embed-mock.test.ts` | Embed mocking | None |
| `src/components/rx/__tests__/rx-warning-card.test.tsx` | RTL test of `rx-warning-card.tsx` | **High** — exact selector / role assertions; will break if the remodel touches this component (and the user said "no UI changes to backend logic" — Rx warning UI is a borderline case) |
| `tests/e2e/scenarios/1-audio-upload-full.spec.ts` | Full flow: signup → upload → wait for ready → review | **HIGH** — exercises every screen of the remodel |
| `tests/e2e/scenarios/2-voice-dictation.spec.ts` | Voice-dictation flow | **HIGH** |
| `tests/e2e/scenarios/3-text-to-soap.spec.ts` | Text-input flow | **HIGH** |
| `tests/e2e/scenarios/4-back-to-dashboard.spec.ts` | Navigation contract | **HIGH** |

**Root-level (`tests/automated/e2e/*`):**

| File | Scope | Risk |
|---|---|---|
| `email-destination-guard.spec.ts` | PHI-safety: emails go only to allowed addresses | Medium (form-driven) |
| `soap-determinism.spec.ts` | Same input → same output | Low (worker-driven) |
| `full-visit-flow.spec.ts` | End-to-end happy path | **HIGH** |
| `password-policy.spec.ts` | Password complexity enforcement | Medium |
| `product-separation.spec.ts` | meddoc-pro ↔ transcribe-md tenancy isolation | Medium |
| `mobile-responsiveness.spec.ts` | Mobile breakpoints | **HIGH** for a visual remodel |
| `rate-limiting.spec.ts` | Rate-limit header propagation | Low |

**`apps/meddoc-pro/`:** 9 unit tests + 5 e2e (`add-patient-form`, `auth`, `chart-id`, `tenancy`, `assistant`). All meddoc-pro-scoped — relevant only if the legacy CRM is in scope.

### 5.2 Playwright config posture

- Both Playwright configs run **Chromium-only**, **workers=1** (BullMQ concurrency races), 120 s timeout.
- Tests run against a **live stack** (real Postgres, real MinIO, mocked AI calls via `MOCK_AI_CALLS=true`).
- A remodel breaking selectors will surface in CI; fixing them iteratively is the expected cost. Plan time for it.

---

## 6. CLAUDE.md / AGENTS.md observations

- `CLAUDE.md` is one line: `@AGENTS.md`.
- `AGENTS.md` carries a single, important instruction: **the Next.js shipped here is post-breaking-change ("NOT the Next.js you know") — read `node_modules/next/dist/docs/` before writing code, and heed deprecation notices.**
- The `proxy.ts` rename (instead of `middleware.ts`) is one expression of those breaking changes.
- `<App_Router_Conventions>` worth verifying for remodelers: `params` being awaited (Next 15+ feature), client/server boundaries, server actions, `headers()`/`cookies()` async, `force-dynamic` semantics, `revalidatePath` use in actions.
- `.claude/launch.json` defines a `meddoc-dev` runtime config (npm run dev, port 3000) — only for the meddoc-pro app.
- `.claude/settings.local.json` has a long allowlist of project-specific Bash commands; nothing relevant to the remodel.
- **Project auto-memory** (under `~/.claude/projects/-opt-meddoc-pro/memory/`, surfaced separately from this repo) carries additional guidance — the operator should consult it before starting; this audit didn't read those files.

> Nothing in CLAUDE.md / AGENTS.md contradicts a frontend remodel. The Next 16 advisory is the only sharp edge.

---

## 7. Risk register for the remodel (ranked)

1. **Redesign-already-in-progress collision.** `apps/transcribe-md/src/app/globals.css` already merges App-redesign-v1 tokens, `<AppFrame>` is built, the dashboard is on the new shell. The `/tmp/design_handoff_quillmd_app/` source directory is gone — there is no canonical spec on disk. **Any new remodel must first reconcile with what's already shipped.** Starting "from scratch" silently means reverting in-flight work.
2. **`pro.quillmd.com` is not what the user thinks.** The user described it as a marketing site; it's actually the legacy `meddoc-pro` CRM/EHR with a fully different stack (Zustand, blue/teal theme, framer-motion v12). **Confirm scope before touching anything.**
3. **`/admin/*` and `/app/*` share a Next.js app.** Caddy routes both `app.quillmd.com` and `admin.quillmd.com` to the same `transcribe-md` container. The "new app design" must not break the admin surface, and the admin gate uses `notFound()` deliberately — a reflexive "redirect to /login" change is a security regression.
4. **Tailwind v4 CSS-first config.** No `tailwind.config.ts`. Anyone on autopilot will look there, find nothing, and either create one (defeating the v4 design) or assume Tailwind isn't configured. The `@theme` directive in `globals.css` is the source of truth.
5. **`proxy.ts` not `middleware.ts`.** Next 16 renamed it. Adding a fresh `middleware.ts` will conflict; renaming `proxy.ts` will break the auth gate.
6. **Component duplication.** Top-level `patient-card.tsx` vs `dashboard/patient-card.tsx`; top-level `empty-state.tsx` vs `ui/empty-state.tsx`. Remodel must consolidate without breaking import sites — grep before deleting.
7. **`visits/[id]/` fan-out.** 16 colocated files under one route. Changing the page shell means re-wiring 6+ children that all import `@/lib/ehr-formatters`, `@/actions/soap`, and each other. Refactor as a unit.
8. **`framer-motion` version drift.** transcribe-md + marketing on ^11.11.11; meddoc-pro on ^12.38.0. v11 → v12 has API changes (motion → motion/react import path). Cross-app component sharing is currently impossible without aligning versions.
9. **Three.js in the critical path.** Orb components (`violet-orb`, `visit-orb`, `live-orb`, `shader-bg`) ship `@react-three/fiber` + `drei` + `three` (~hundreds of KB). Removing them shrinks the bundle materially; keeping them means the remodel inherits their performance budget.
10. **Server-action-only data flow.** No React Query / SWR / Context — every screen is server component → `'use client'` leaf calling actions via `useTransition`. The remodel **must preserve this pattern** unless it's prepared to introduce a new state library and rewrite every interaction. (Adding Zustand or React Query is a refactor, not a remodel.)
11. **The 1,324-line `globals.css` carries semantic CSS, not just tokens.** Class names like `.qm-app`, `.qm-*` are referenced by ported handoff markup. Removing the file or replacing it wholesale will break dashboard styling silently.
12. **PHI redactor invariant.** `redactPhi` is wired into Sentry init for both edge and node runtimes (`sentry.{edge,server}.config.ts`). The remodel must not introduce a new client-side error logger that bypasses it (e.g. swapping in a different observability SDK).

---

## 8. Suggested Agent Team composition

Sized to this codebase. 6 specialists.

| Agent | Owns | Concrete files / deliverables |
|---|---|---|
| **A1 — Design-system architect** | Reconciling the two coexisting token sets in `globals.css`; deciding which survives; documenting the canonical token names | `apps/transcribe-md/src/app/globals.css` reconciliation; new `docs/design/DESIGN_SYSTEM.md`; `<AppFrame>` / `<TopNav>` / `<IconRail>` / `<PageHeader>` reskin |
| **A2 — Core-app surface engineer** | Visit lifecycle screen — the heaviest UI in the app | `apps/transcribe-md/src/app/visits/[id]/*.tsx` (16 files); `visits/new/page.tsx`; `visits/[id]/record/recording-client.tsx`. Must preserve server-action signatures + types from §4 |
| **A3 — Dashboard + lists engineer** | Dashboard, patient list, visit list, command palette | `apps/transcribe-md/src/app/dashboard/page.tsx`; `app/patients/{page,[id]/page}.tsx`; `app/visits/page.tsx`; `components/dashboard/*`; `components/{patient-card,visit-card,command-palette}.tsx`; `lib/dashboard-pagination.ts` (read-only) |
| **A4 — Auth + settings engineer** | Auth screens, settings, post-signup verification flow | `app/{login,signup,check-email,forgot-password,reset-password,settings}/page.tsx`; `components/{user-menu,auth-shell}.tsx`. Must NOT touch `proxy.ts`, `lib/auth.{ts,config.ts,nextauth.ts}` |
| **A5 — Effects/animation engineer** | The orb/shader/glow component family + motion grammar | `components/{violet-orb,visit-orb,live-orb,shader-bg,animated-grid,glow-card,tilt-card,specular-button,gradient-text}.tsx`. Owns the framer-motion v11 → keep-or-upgrade decision and the Three.js performance budget |
| **A6 — QA / e2e custodian** | Keeping Playwright + Vitest green through the remodel | `apps/transcribe-md/tests/e2e/scenarios/*`; `tests/automated/e2e/*`; `components/rx/__tests__/rx-warning-card.test.tsx`. Updates selectors/test-ids in lockstep with each merged remodel PR |

If the user expands scope to `pro.quillmd.com`:
- **A7 — Legacy-CRM remodel engineer** — `apps/meddoc-pro/src/{app,components,lib}` + Zustand stores. **Don't fold this into A2/A3** — totally different app, different stack version, different palette.

If the user keeps marketing in scope:
- **A8 — Marketing-site engineer** — `apps/marketing/*`. Lighter than the others (10 static-ish pages). Ideally shares tokens with whatever A1 settles on.

---

## 9. Open questions for the user

1. **Scope (the most consequential).** Three apps, three answers needed:
   - `app.quillmd.com` (transcribe-md) — confirmed in scope.
   - `admin.quillmd.com` (`/admin/*` inside transcribe-md) — **in or out?** It rides the same Next.js app and the same shell components — splitting "yes app, no admin" is harder than it sounds because the chrome is shared.
   - `pro.quillmd.com` (`apps/meddoc-pro`, the legacy CRM) — **in or out?** This is the app the user mistakenly described as "marketing." It's a different stack (Zustand, blue/teal theme, framer-motion v12).
   - `quillmd.com` (`apps/marketing`) — **in or out?**

2. **Reconcile with the in-progress redesign.** `apps/transcribe-md/src/app/globals.css` and `app/dashboard/page.tsx` already carry "App-redesign-v1" / HANDOFF tokens ported from a `/tmp/design_handoff_quillmd_app/` directory that no longer exists. Three options:
   - **Continue** the existing redesign — operator must locate the original handoff docs (Figma? a previous git branch? a Google Drive?) before A1 starts.
   - **Restart** — explicitly revert the in-progress changes and define a new design system. Cleaner but wastes the existing work.
   - **Hybrid** — keep the App-redesign-v1 tokens as the foundation, layer new aesthetic on top.

3. **Design direction.** From scratch? From a public reference (Linear / Vercel / Resend / Raycast — the existing `globals.css` comment lists exactly that idiom)? From a Figma file the user has? From inspirations the agent team can browse via the Framelink + 21st.dev MCP servers installed today?

4. **Migration strategy.** A months-long remodel needs a delivery shape:
   - **Route-by-route swap** in place — fastest to merge, hardest to roll back.
   - **Parallel `/v2/*` routes** — easy A/B, but doubles the surface during the transition and complicates auth gating in `proxy.ts`.
   - **Feature flag** (env var or per-user) — best for an active customer base; needs a flag library not currently in the repo.
   - **Branch + bulk swap** — feasible since this is a single-engineer-style monorepo on `main`; risky for a multi-month branch.

5. **Branch / PR strategy.** Phase-based commits (the current style — "Phase 19", "T-M16.4", etc.) per `git log`? Or a long-lived `redesign` branch? Decide before A1 lands the first reskin or the first PR will define it implicitly.

6. **Testing budget.** Every UI test (4 transcribe-md e2e + 7 root-level e2e + 1 component RTL test) will need selector/test-id updates in lockstep with the remodel. Is A6 going to update them per-PR (slow but safe) or in one batch at the end (fast but flaky)?

7. **Tailwind v4 + `globals.css` posture.** Keep CSS-first (current) or migrate to `tailwind.config.ts` (back-compat with most third-party design systems and shadcn)? Affects A1 directly.

8. **Component library decision.** Stay on the hand-rolled `components/ui/` + Radix primitives? Adopt shadcn/ui (would generate a `components.json` and rewrite the `ui/` layer)? Adopt one of the shadcn-style libraries from the `ui-libraries-reference` skill installed today?

9. **Three.js + orbs.** Keep the visit-orb / violet-orb / live-orb / shader-bg family (current bundle cost), simplify them, or drop them? Affects A5's whole brief.

10. **`pro.quillmd.com`-specific (only if it's in scope).** Bring its `framer-motion` to v11 to match the others (downgrade) or bring transcribe-md + marketing up to v12 (upgrade)? Also: does the legacy CRM keep its blue/teal medical theme, or align with the dark/violet QuillMD brand?

---

## Appendix — Files referenced

| File | Why mentioned |
|---|---|
| `Caddyfile` | Subdomain routing |
| `docker-compose.yml` | Service topology |
| `package.json` (root) | npm-workspaces config |
| `tsconfig.base.json` | Shared TS config |
| `apps/transcribe-md/src/app/globals.css` | 1,324-line dual-token CSS — central design hazard |
| `apps/transcribe-md/src/app/layout.tsx` | Root layout, font wiring (Geist + 3-font handoff trio) |
| `apps/transcribe-md/src/app/admin/layout.tsx` | Admin gate using `notFound()` (security note) |
| `apps/transcribe-md/src/proxy.ts` | Edge auth middleware (Next 16 rename of middleware.ts) |
| `apps/transcribe-md/src/lib/auth.{ts,config.ts}`, `lib/nextauth.ts` | Auth machinery |
| `apps/transcribe-md/src/actions/*.ts` | 7 server-action files — the seam |
| `apps/transcribe-md/src/worker.ts`, `src/worker/layers/*.ts` | BullMQ pipeline (protected) |
| `packages/ai/src/log.ts`, `packages/ai/src/index.ts` | `redactPhi` + `logAiCall` |
| `packages/db/prisma/schema.prisma` | 1,980-line schema, 28 models (protected) |
| `packages/types/src/soap.ts`, `soap-render.ts` | SOAP Zod contract — primary type seam |
| `apps/meddoc-pro/src/app/globals.css` | The other (light/blue) design system |
| `apps/marketing/src/app/globals.css` | Derivative of transcribe-md tokens |
| `docs/design/rx_warning_handoff/` | The only design handoff still on disk |
| `AGENTS.md` | Next.js v16 advisory |
