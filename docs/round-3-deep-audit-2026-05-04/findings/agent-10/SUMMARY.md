# Agent 10 — UX, A11y, Mobile · Summary

## Severity counts
**P0: 0 · P1: 4 · P2: 6 · P3: 5 · Total: 15**

## Top 3 findings
1. **A10-P1-001** — axe-core's `color-contrast` rule is globally suppressed in `apps/transcribe-md/tests/e2e/a11y.spec.ts:113-119` via a hard-coded `KNOWN_NON_BLOCKING_RULE_IDS = Set(['color-contrast'])`. R2's "axe baseline cleared" claim was procedural — the rule still fails on the live UI. `--color-linear-text-3: #6c737f` (~4.0:1 on bg) and `--color-linear-text-4: #4b5159` (~2.4:1) appear at **480 call sites** across both apps. Single-line CSS lift to `#8b929c` (matching marketing's already-passing token) closes all 480 transparently. Highest-leverage fix in the audit.
2. **A10-P1-002** — Skip-to-content link is non-functional. `app/layout.tsx:81` sets `href="#main"` but **no element anywhere in `apps/transcribe-md/src/` has `id="main"`**. WCAG 2.4.1 Level A failure shipped. Fix: add `id="main" tabIndex={-1}` to `<main>` in `components/ui/app-frame.tsx` plus 2-3 outside-AppFrame pages (`visits/[id]/loading.tsx`, `not-found.tsx`, `admin/layout.tsx`).
3. **A10-P1-004** — Transcript-tab Play / Skip-back / Skip-forward audio buttons all have `tabIndex={-1}` (`app/visits/[id]/transcript-tab.tsx:329, 337, 345`). Keyboard-only and screen-reader doctors cannot operate transcript audio. WCAG 2.1.1 Level A.

## Other P1
- A10-P1-003 — Marketing site has no skip link at all on any of 11 public pages; `/hipaa`, `/privacy`, `/security` themselves fail Level A.

## Coverage
- transcribe-md: every route under `app/` (auth flows, dashboard, /visits, /visits/new, /visits/[id]/* including processing-state/visit-ready/sign-and-send/soap-editor/transcript-tab/extras-tab/codes-tab/rx-tab/record, /settings, /patients, /admin, /not-found, /error)
- marketing: every route + every component in `components/home/`
- Cross-cutting: both `app/layout.tsx`, `globals.css` (~4000 lines), `landing.css`, Tailwind v4 `@theme`, `playwright.config.ts`, `tests/e2e/a11y.spec.ts`, `next.config.ts`. No live screenshots.

## Positives
1. `*:focus-visible` is set globally with sage outline + offset (`globals.css:124`); `prefers-reduced-motion` is honoured in 3+ places.
2. `qm-tap-44`/`qm-tap-44-input` enforces 44 px mobile floor + 16 px font-size to suppress iOS Safari auto-zoom.
3. Error copy is actionable, specific, non-blamy throughout — e.g., "An account with this email exists. Sign in instead." (`actions/auth.ts:333`); "This account is for MedDoc Pro, not TranscribeMD" with one-click cross-app link (`auth.ts:221`); file-size error reports computed value.
4. autoComplete attrs correct on every auth field; Radix Dialog gives free focus trap + Esc + aria on every modal; `<AuthFieldError role="alert">` pattern wired correctly.
5. EmptyState component (`components/ui/empty-state.tsx`) is well-designed and used consistently for first-run states.

## Cross-domain hooks
- **Agent 12 (visual/brand)**: A10-P3-002 — text-3 token drifts between apps (#6c737f vs #8b929c).
- **Agent 06 (clinical safety)**: A10-P2-002 (no print stylesheet) — printed SOAP fidelity may be a chart-of-record concern.
- **Agent 12 (security/HIPAA)**: A10-P1-003 — `/hipaa` and `/security` marketing pages themselves fail WCAG 2.4.1.
- **Agent 11 (testing/CI)**: A10-P1-001 root cause is in `a11y.spec.ts`; suppression should have a removal-by-date CI annotation.
- **Agent 09 (perf)**: A10-P2-005 (submit-only validation) gets worse on slow networks.
- **Agent 12 (release readiness)**: all four P1s are pre-pilot blockers; A10-P1-001 + A10-P1-002 must close before regression matrix can claim WCAG 2.1 AA.
