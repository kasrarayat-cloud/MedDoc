# A11y Testing — Contributor Guide

**Status**: Required CI check on every PR to `main`.  
**Owner**: Phase 3 Wave 1 (Subagent 5).  
**Scope**: Every Clinician-migrated route in `apps/transcribe-md`.

This document covers the automated accessibility (a11y) gate that runs on every pull request. The goal is to catch **critical** and **serious** WCAG 2.1 violations before they merge — exactly the bar that the manual merge-prep pass enforced before the Clinician remodel landed in `main`.

---

## What gets tested

The CI suite runs a Playwright + [axe-core](https://github.com/dequelabs/axe-core) sweep across:

| Layer | Coverage |
|---|---|
| Browser | Chromium (matches the existing E2E project — same engine, no per-browser flakes) |
| Viewports | Desktop 1440×900 and Mobile 390×844 |
| Routes | All 12 Clinician-migrated routes (see below) |
| Total tests | 12 routes × 2 viewports = **24 tests per PR** |
| axe-core ruleset | Default `axe.run(document)` — WCAG 2.0/2.1 A & AA rules |
| Pass criterion | **Zero critical, zero serious** violations |

### Route matrix

| # | Path | Auth | Notes |
|---|---|---|---|
| 1 | `/login` | none | Sign-in form |
| 2 | `/signup` | none | Account creation form |
| 3 | `/forgot-password` | none | Reset link request |
| 4 | `/reset-password` | none | Reset form (renders without token gracefully) |
| 5 | `/check-email` | none | Verification-link landing |
| 6 | `/dashboard` | user | Visit list + recent activity |
| 7 | `/visits` | user | Full visit list |
| 8 | `/visits/new` | user | Create-visit wizard (mode tiles) |
| 9 | `/visits/[id]` (READY) | user | Visit detail with editable SOAP |
| 10 | `/visits/[id]` (SIGNED) | user | Visit detail with locked / signed SOAP |
| 11 | `/visits/[id]` (PROCESSING) | user | Visit detail with progress UI |
| 12 | `/visits/[id]/record` | user | Voice / audio recording surface |

### Routes intentionally NOT in the matrix

| Path | Why |
|---|---|
| `/admin/*` | Needs SUPER_ADMIN promotion + JWT-refresh helper. Tracked as TODO for v1.1.0. |
| `/dev/rx-warnings` | Production build prunes `/dev/*` routes; CI runs against the production build. |
| `/` | Server redirect (`auth() ? /dashboard : /login`); axe can't run on a 307. The redirect targets are covered. |
| `/api/**` | Non-rendering endpoints; a11y rules don't apply. |
| `/settings`, `/patients` | Coverage to come in Phase 3 Wave 2. |

### What "critical / serious" means

axe-core categorises every violation by impact:

- **Critical** — blocks assistive technology entirely (e.g., `<button>` with no accessible name, missing `<html lang>`, color contrast that fails AA).
- **Serious** — substantially degrades the experience (e.g., form label not programmatically associated, `aria-*` referencing a non-existent ID).
- **Moderate** — annoying but workable (e.g., heading-order skip).
- **Minor** — best-practice, fix-on-sight.

The CI gate fails **only on critical and serious**. Moderate and minor violations are logged in the test output (search for `[a11y]`) so they don't disappear, but they don't block merge. This matches the manual merge-prep gate that signed off the Clinician remodel.

---

## How to run the suite locally

### Against the live VPS (full coverage including SIGNED + PROCESSING visit states)

```sh
# From /opt/meddoc-pro on the VPS, with the stack already up on :9020:
cd apps/transcribe-md
PW_BASE_URL=http://localhost:9020 npx playwright test --project=a11y
```

This uses the docker-compose channel (`docker compose exec postgres psql`) for visit-state seeding, so the READY/SIGNED/PROCESSING cells all run.

### Against a custom port (e.g., parallel-port build for merge-prep)

```sh
cd apps/transcribe-md
PW_BASE_URL=http://localhost:8766 npx playwright test --project=a11y
```

### Against a local dev server (no postgres exposure → SIGNED + PROCESSING auto-skip)

```sh
# Start the dev server in one terminal:
npm run dev -w transcribe-md   # listens on http://localhost:3011

# In another terminal, run the suite — visit-state tests skip cleanly:
cd apps/transcribe-md
PW_BASE_URL=http://localhost:3011 npx playwright test --project=a11y
```

The `READY` visit and all unauthenticated routes still get scanned. The `SIGNED` and `PROCESSING` tests print a skip reason explaining the seeding channel was unreachable.

### Running a single route while iterating

```sh
cd apps/transcribe-md
PW_BASE_URL=http://localhost:9020 \
  npx playwright test --project=a11y --grep 'visit-detail-ready'
```

---

## How to debug a failure

When the CI gate fails, the failing job's log will contain a block like:

```
3 blocking a11y violation(s) on /visits/new (viewport=desktop):
  [serious] label (2 nodes) — Form elements must have labels
    https://dequeuniversity.com/rules/axe/4.10/label
  [critical] color-contrast (1 node) — Elements must have sufficient color contrast against background
    https://dequeuniversity.com/rules/axe/4.10/color-contrast
  [serious] aria-valid-attr-value (4 nodes) — ARIA attributes must conform to valid values
    https://dequeuniversity.com/rules/axe/4.10/aria-valid-attr-value

Full violation count (incl. minor/moderate): 5.
Pass criterion: zero critical, zero serious — see docs/A11Y_TESTING.md.
```

### Step-by-step

1. **Find the rule** — every violation prints a stable axe rule ID (`label`, `color-contrast`, etc.) and a help URL into [Deque University](https://dequeuniversity.com/rules/axe/). Click through; each page has the WCAG criterion, code examples, and fix patterns.

2. **Find the offending node** — download the `a11y-playwright-report` artifact from the failed run (uploaded automatically on failure for 14 days). Open `index.html`; expand the failing test; scroll to the failure detail. Each node has its CSS selector + outerHTML so you know exactly which element to fix.

3. **Common fixes**:
   - **`label` / `form-field-multiple-labels`** — add an explicit `<label htmlFor="…">` or `aria-labelledby`.
   - **`color-contrast`** — bump the foreground/background contrast to at least 4.5:1 (text) or 3:1 (large text). Use a contrast checker like [coolors.co/contrast-checker](https://coolors.co/contrast-checker).
   - **`button-name` / `link-name`** — empty interactive element. Either add a visible label, an `aria-label`, or `<VisuallyHidden>` text.
   - **`aria-valid-attr-value`** — `aria-controls="…"` or `aria-labelledby="…"` references an ID that doesn't exist. Check for typos; if the target is conditionally rendered, render it before the attribute (or remove the attribute when the target's gone).
   - **`heading-order`** — an `<h3>` appears without an `<h2>` ancestor. Use a higher-level heading or restructure.
   - **`region`** — content sits outside any landmark (`<main>`, `<nav>`, `<header>`, `<aside>`, `<footer>`). Wrap in the right landmark.

4. **Re-run locally** with `--grep` on just the failing route:

   ```sh
   cd apps/transcribe-md
   PW_BASE_URL=http://localhost:9020 \
     npx playwright test --project=a11y --grep 'visits-new' --headed
   ```

   `--headed` is useful when a violation is conditional (e.g., visible only when a modal is open and the modal opens automatically on page-load).

5. **Confirm the fix** — once you've shipped the change, the next push to the PR re-runs the gate.

---

## When this CI suite is allowed to be skipped

**Never.** It is a required check.

The gate exists because regressing a critical/serious a11y violation breaks assistive-tech users in production — no automated runtime check catches these once they ship, and a clinical product that's unusable for clinicians with disabilities is a legal + ethical problem, not just a quality problem.

If a PR genuinely cannot pass the gate (e.g., it ports a third-party widget that violates a rule we can't fix immediately), the path forward is **not** `git commit --no-verify` or workflow disablement. The path is:

1. Open a tracking issue in the repo with the violation IDs and affected routes.
2. Add a per-rule `axe.configure()` skip in `apps/transcribe-md/tests/e2e/a11y.spec.ts` with a code comment that points at the issue and a deadline for fixing.
3. Get explicit sign-off from a maintainer in the PR review.

The skip is then visible to every future contributor reading the spec, and the issue makes sure it doesn't disappear.

---

## How the suite is wired

| File | Role |
|---|---|
| `apps/transcribe-md/tests/e2e/a11y.spec.ts` | Playwright spec — the route matrix + axe-core injection + assertion logic. |
| `apps/transcribe-md/tests/e2e/helpers/seedVisitStates.ts` | Direct-SQL helper that seeds READY/SIGNED/PROCESSING visits via `psql` (CI) or `docker compose exec postgres psql` (local VPS). |
| `apps/transcribe-md/tests/e2e/helpers/signup.ts` | Existing UI signup helper — reused for the a11y user. |
| `apps/transcribe-md/tests/e2e/helpers/cleanup.ts` | Existing prefix-scoped DELETE — wipes `qa-e2e-*` users (a11y users use the same prefix via `uniqueTestEmail('a11y')`). |
| `apps/transcribe-md/playwright.config.ts` | Defines the `a11y` Playwright project (matched only via `--project=a11y`). |
| `.github/workflows/a11y.yml` | The CI workflow that boots postgres + redis services, builds the app, runs the spec, and uploads reports on failure. |

### How axe-core is loaded

The spec injects axe-core 4.10.0 via a `<script src="https://cdn.jsdelivr.net/npm/axe-core@4.10.0/axe.min.js">` tag at test time — same approach used by the merge-prep runner that proved the pattern.

If the CDN ever fails (corporate proxy, outage), the test reports a clear `axe-core CDN load failed` error. The fallback is to add `axe-core` as an npm devDep:

```sh
npm i -D axe-core -w transcribe-md
```

…and switch the spec's `runAxeViolations` to import the local `axe-core/axe.min.js` and inject its source via `page.evaluate(() => { /* axe.js source */ })`. This is intentionally **not** the default because it adds ~1MB to `node_modules` for every developer, while the CDN approach has worked reliably in every test environment we've tried.

---

## Maintenance

- **Adding a new route**: append a `RouteSpec` to the `ROUTES` array in `a11y.spec.ts`. The spec's nested loop generates 2× tests automatically (one per viewport).
- **Adding a new viewport**: append to the `VIEWPORTS` array in `a11y.spec.ts`. All routes get the new viewport coverage automatically.
- **Bumping axe-core**: change the `AXE_CDN_URL` constant. Run `--project=a11y` locally before merging — a major axe version (e.g., 4 → 5) can introduce new rules that surface previously-passing pages.
- **Bumping Playwright**: the workflow's Playwright-browser cache key includes `@playwright/test`'s pinned version, so a bump invalidates the cache cleanly. No manual cache bust needed.

---

## Reference

- WCAG 2.1 AA: https://www.w3.org/WAI/WCAG21/quickref/?versions=2.1&levels=aa
- axe-core rule list: https://dequeuniversity.com/rules/axe/4.10
- Phase 3 Wave 1 plan: see the project tracker (Subagent 5: A11y CI Integration).
