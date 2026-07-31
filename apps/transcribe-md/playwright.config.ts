// ============================================================================
// Playwright config (T-M10) — E2E regression suite + Phase 3 a11y CI
// ----------------------------------------------------------------------------
// Tests run against a LIVE transcribe-md stack (real app, real Prisma, real
// MinIO). The transcribe-md-worker container must be running with
// MOCK_AI_CALLS=true so pipeline jobs complete with canned fixtures instead
// of hitting Deepgram / Anthropic. See tests/e2e/README.md for setup.
//
// Parallelism: workers=1 on purpose. BullMQ worker concurrency is capped
// at 2 by default, and four visits submitted in parallel often end up
// racing on the post-signup cookie + the dashboard refresh. Safer to go
// sequential than flaky.
//
// Browsers: Chromium only. Firefox/WebKit would triple CI time for no
// useful coverage — the TranscribeMD UI is a standard-library React app
// with no browser-specific quirks.
//
// Projects:
//   - chromium    → existing scenario suite (excludes a11y.spec.ts and the
//                   phi-reject spec, which needs a different app env).
//   - a11y        → opt-in a11y CI gate; runs ONLY a11y.spec.ts. Triggered
//                   from .github/workflows/a11y.yml via
//                   `playwright test --project=a11y`. The default
//                   `playwright test` invocation (no --project) runs only
//                   chromium so the existing CI doesn't double-run a11y.
//   - phi-reject  → note-format PARSE-time PHI rejection (scenario 23). Needs
//                   the app started with MOCK_TEMPLATE_PHI_FLAG=true (every
//                   parse then rejects), so it can't share the chromium run.
//                   Run explicitly via `playwright test --project=phi-reject`
//                   against an app instance recreated with that flag.
// ============================================================================

import { defineConfig, devices } from '@playwright/test';

const BASE_URL = process.env.PW_BASE_URL ?? 'http://localhost:9020';

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/*.spec.ts',
  globalSetup: './tests/e2e/global-setup.ts',
  globalTeardown: './tests/e2e/global-teardown.ts',

  // Each scenario creates a signup + visit + optional pipeline wait. With
  // mocks on the pipeline is fast but the UI round-trips + animations add
  // up; 120s gives comfortable headroom without hiding a hung-forever bug.
  timeout: 120_000,
  expect: { timeout: 10_000 },

  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,

  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],

  use: {
    baseURL: BASE_URL,
    // Collect screenshot + trace on first failure for post-mortem — the
    // VPS runs headless, there's no way to re-run with --headed on a CI
    // box and catch the same flake twice.
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15_000,
    navigationTimeout: 20_000,
  },

  projects: [
    {
      // Default project — existing scenario suite. Excludes a11y.spec.ts
      // so the a11y gate doesn't run twice (once here, once under the
      // a11y project below).
      name: 'chromium',
      // a11y → its own project; 23-…phi-parse-reject → the phi-reject project
      // (needs MOCK_TEMPLATE_PHI_FLAG=true, which would reject every parse);
      // 24-…rx-clinical-safety → the rx-safety project (needs MOCK_RX_WARNINGS=true,
      // whose critical warning would block every other spec's sign).
      testIgnore: [
        // The pre-sign document surface — its own flag-ON project below.
        '**/review-document.spec.ts',
        // The real-document preview — flag-ON project below; also STOPS the
        // converter mid-run, which no other spec should have to survive.
        '**/doc-preview.spec.ts',
        '**/visit-document.spec.ts',
        // ROUNDS Gate A — the board only exists on the flag-ON image built by
        // its own project below. Omitting it here is not a slow failure: the
        // default run reaches /board on a flag-OFF build, gets a 404, and reds
        // the required gate BEFORE the step that would have built the flag-ON
        // image ever runs — so the pack this line protects never executes at
        // all, and the gate reports "rounds E2E red" for the one reason that
        // has nothing to do with Rounds. Pinned by gate-flag-coverage.test.ts.
        '**/rounds-board.spec.ts',
        // ROUNDS Gate B — Screen 2. Same reasoning as the board above, with one
        // difference worth naming: /visits/[id] EXISTS with the flag off, so
        // this pack would not 404 — it would fail on missing Rounds testids
        // while the route rendered the old skin perfectly well. Slower to
        // diagnose, identical downstream damage.
        '**/rounds-stage.spec.ts',
        // ROUNDS Gate B — Screen 3. Same reasoning as the stage pack: the route
        // EXISTS with the flag off, so this would not 404 — it would fail on
        // missing Rounds testids while the old skin rendered perfectly well,
        // and take every downstream pack with it.
        '**/rounds-gates.spec.ts',
        // ROUNDS Gate B — Screen 4. Same reasoning again: /visits/[id] exists
        // flag-OFF, so this would fail on missing testids rather than 404,
        // taking every downstream pack with it.
        '**/rounds-signed.spec.ts',
        '**/rounds-a11y.spec.ts',
        '**/a11y.spec.ts',
        '**/23-note-format-phi-parse-reject.spec.ts',
        '**/24-rx-clinical-safety.spec.ts',
        '**/25-rx-override-correlation.spec.ts',
        '**/28-marketing-smoke.spec.ts',
        // Real-model eval specs (real tokens) — NEVER in the default/CI run.
        '**/*.eval.spec.ts',
      ],
      use: { ...devices['Desktop Chrome'] },
    },
    {
      // A11y CI gate — Phase 3 Wave 1 (Subagent 5). Runs the axe-core
      // sweep against every Clinician-migrated route at desktop +
      // mobile viewports. The spec itself instantiates per-test
      // contexts at the right size (1440×900 / 390×844), so the
      // project-level viewport is just a default.
      //
      // Triggered explicitly in .github/workflows/a11y.yml via
      // `npx playwright test --project=a11y`. NOT included in the
      // default `playwright test` run.
      name: 'a11y',
      testMatch: '**/a11y.spec.ts',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      // Note-format PARSE-time PHI rejection (scenario 23). Runs ONLY when
      // invoked with `--project=phi-reject`, against an app started with
      // MOCK_TEMPLATE_PHI_FLAG=true (see .github/workflows/e2e.yml + the qa
      // compose passthrough). Kept out of the default run so the flag-on app
      // env never rejects the happy-path parses the other specs depend on.
      name: 'phi-reject',
      testMatch: '**/23-note-format-phi-parse-reject.spec.ts',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      // Rx clinical-safety (scenarios 24 + 25). Runs ONLY via
      // `--project=rx-safety`, against an app started with MOCK_RX_WARNINGS=true
      // (the populated tm_rx_drafting fixture with a critical warning). Kept out
      // of the default run so that critical warning never blocks the other
      // specs' sign flows. Scenario 25 is the per-warning-correlation regression
      // (fix/rx-override-gate-correlation) and shares the same app env.
      name: 'rx-safety',
      testMatch: [
        '**/24-rx-clinical-safety.spec.ts',
        '**/25-rx-override-correlation.spec.ts',
      ],
      use: { ...devices['Desktop Chrome'] },
    },
    {
      // The pre-sign DOCUMENT surface (NEXT_PUBLIC_REVIEW_DOC_VIEW). Its own
      // project because the default chromium run builds the pre-C3 skin with
      // the flag OFF, where this surface does not exist — the pack would fail
      // the required gate for an environment reason rather than a real one.
      // Runs against an app built flag-ON, the same way phi-reject/rx-safety
      // run against their own fixture builds.
      name: 'review-doc',
      testMatch: ['**/review-document.spec.ts'],
      use: { ...devices['Desktop Chrome'] },
    },
    {
      // ROUNDS Gate A — the Board. Its own project because it needs the
      // flag-ON image (NEXT_PUBLIC_SKIN_ROUNDS=true), which no other pack
      // wants. With the flag off /board 404s, so this pack would fail for an
      // environment reason rather than a real one — same posture as review-doc
      // above.
      name: 'rounds-board',
      testMatch: ['**/rounds-board.spec.ts'],
      use: { ...devices['Desktop Chrome'] },
    },
    {
      // ROUNDS Gate B — Screen 2, the stage. Serialised: the queue tests seed
      // three visits for ONE doctor and assert their order relative to each
      // other, so a parallel worker seeding a fourth would change the answer
      // under them.
      name: 'rounds-stage',
      testMatch: ['**/rounds-stage.spec.ts'],
      fullyParallel: false,
      workers: 1,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      // ROUNDS Gate B — Screen 3, the sequential gate flow. Serialised: these
      // tests record real RxWarningOverride rows for one doctor and then assert
      // a blocker COUNT, so a parallel worker clearing another gate on the same
      // fixture would move the number under them.
      name: 'rounds-gates',
      testMatch: ['**/rounds-gates.spec.ts'],
      fullyParallel: false,
      workers: 1,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      // ROUNDS Gate B — Screen 4, signed & locked. Serialised: the deck-advance
      // test asserts which encounter is NEXT across a multi-visit fixture, so a
      // parallel worker signing another visit would move the queue head under
      // it.
      name: 'rounds-signed',
      testMatch: ['**/rounds-signed.spec.ts'],
      fullyParallel: false,
      workers: 1,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      // ROUNDS Gate B — axe across every Rounds surface, flag-ON. Axe has never
      // run against one: a11y.yml builds with plain `npm run build` and none of
      // the skin flags, so it has never seen the stage, the flow or the signed
      // screen. One test walking many states, so no parallelism to gain.
      name: 'rounds-a11y',
      testMatch: ['**/rounds-a11y.spec.ts'],
      fullyParallel: false,
      workers: 1,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      // Real-document preview (NEXT_PUBLIC_DOC_PREVIEW=true). Its own project
      // because one spec deliberately STOPS the converter sidecar to prove the
      // fallback — serialised so it cannot break a parallel spec.
      name: 'doc-preview',
      testMatch: ['**/doc-preview.spec.ts'],
      fullyParallel: false,
      workers: 1,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      // Phase 2 — the visit page as the document (NEXT_PUBLIC_VISIT_DOC_PAGE).
      // Its OWN project and its OWN image: the doc-preview build does not carry
      // this flag, so running these there would wait 120s for a surface that
      // was never compiled in and red the gate for an environment reason.
      // Serialised — one spec stops the converter sidecar on purpose.
      // The chat editor. Named *.eval.spec.ts because it burns REAL Anthropic
      // tokens on every run — that suffix is this repo's marker for the class,
      // and it is already excluded from the default gate above. Run it
      // deliberately, against a stack with a real key.
      name: 'chat-editor',
      testMatch: ['**/chat-editor.eval.spec.ts'],
      fullyParallel: false,
      workers: 1,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'visit-doc',
      testMatch: ['**/visit-document.spec.ts'],
      fullyParallel: false,
      workers: 1,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      // Marketing site smoke (scenario 28). Runs ONLY via `--project=marketing`
      // with MARKETING_E2E=1, against the marketing app (default :9010, its OWN
      // baseURL — distinct from the transcribe-md app the other projects hit).
      // Deliberately NOT wired into the required e2e CI gate (a 2nd full app
      // build for a static-page smoke would bloat the gate); validated locally
      // against a marketing container on the qa network. See docker-compose.qa.yml.
      name: 'marketing',
      testMatch: '**/28-marketing-smoke.spec.ts',
      use: {
        ...devices['Desktop Chrome'],
        baseURL: process.env.PW_MARKETING_URL ?? 'http://localhost:9010',
      },
    },
    {
      // Real-model model-evaluation specs (e.g. feat/fable5-eval). Runs ONLY via
      // `--project=real-model-eval` against an isolated qa stack on REAL keys
      // (MOCK_AI_CALLS=false) — they SPEND REAL TOKENS, so they are excluded
      // from the default run + the required CI gate, and additionally self-skip
      // unless REAL_MODEL_EVAL=1. Manual/operator-invoked only. Generous timeout:
      // real Fable/Opus pipeline runs are far slower than MOCK.
      name: 'real-model-eval',
      testMatch: '**/*.eval.spec.ts',
      timeout: 300_000,
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // No webServer block — the app is managed by docker compose; Playwright
  // just points at the running instance.
});
