// ============================================================================
// Scenario 4 — Back-to-home navigation works from a visit page
// ----------------------------------------------------------------------------
// Regression for T-M8 Bug 4 (9e423df). The "Back to dashboard" link
// used to be a raw <Link> inside the server component; a stacking-
// context overlay or a subtle hydration glitch could eat the click.
// The fix extracted it into a client-component <a> with both href
// and an explicit router.push onClick, plus relative z-10 to ride
// above any overlay. This test clicks it and asserts navigation +
// that home correctly lists the visit we just created.
//
// ⚠️ 2026-08-04 — THE SUBJECT MOVED SHELLS. IT DID NOT RETIRE.
//
// Under Rounds the in-content breadcrumb this spec clicked is gated OFF
// (`src/app/visits/[id]/page.tsx:356` — `{!roundsChrome && (`), and the way home
// is the shared top bar's Board link (`src/components/rounds/top-bar.tsx:43-47`
// + `:104-117`, testid `rounds-nav-board`). T-M8 Bug 4's property is unchanged
// and still worth a test — *a real click on the real in-page affordance
// navigates, it is not eaten by an overlay* — only the element carrying it
// moved, out of `#main` and into a sibling header.
//
// Both affordances are named below because `NEXT_PUBLIC_SKIN_ROUNDS` is a
// BUILD-TIME fork the Playwright process cannot read (see helpers/home.ts), so
// one file has to hold on either image and a flag-OFF rollback build must not
// turn this re-point into a false red. The branch is taken off the DOM, never
// off a flag — the same rule helpers/sign.ts follows.
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { expectAtHome } from '../helpers/home';
import { createPatientAndContinue } from '../helpers/patient';
import { signupFreshUser } from '../helpers/signup';

test.afterEach(() => {
  cleanupTestUsers();
});

test('scenario 4: back-to-home navigates from a visit page', async ({
  page,
}) => {
  await signupFreshUser(page, 's4');

  // Create the cheapest visit we can — text mode, skip submission
  // and go straight to clicking Back. Layer 0 (/visits/new) sets a
  // default specialty from SPECIALTIES[0], so a mode-tile click is
  // valid even without opening the dropdown (T-M8 Bug 1 fix).
  await page.goto('/visits/new');
  // Step 1 (two-step flow): pick a patient so the capture-mode tiles render.
  await createPatientAndContinue(page);
  await page.getByRole('button', { name: /text to soap/i }).click();

  await page.waitForURL(/\/visits\/c[a-z0-9]{10,}/, { timeout: 15_000 });

  // Keep the id: the home-surface assertion at the bottom names THIS visit
  // rather than pattern-matching a patient name that any row could carry.
  const visitId = page.url().match(/\/visits\/(c[a-z0-9]{10,})/)?.[1];
  expect(
    visitId,
    'could not read a visit id out of the stage URL — the route shape changed',
  ).toBeTruthy();

  // ── The way home ──────────────────────────────────────────────────────────
  // WAS: `page.locator('#main').getByRole('link', { name: 'Dashboard', exact:
  // true })` — the Linear V1 breadcrumb (Dashboard › Patient › Visit). That
  // `#main` scope was deliberate and correct: the legacy shells hang their
  // sidebar / top nav OUTSIDE <main> (`components/ui/app-frame.tsx:75-119`), so
  // scoping was the only way to tell the breadcrumb's "Dashboard" apart from
  // the sidebar's identically-named nav link.
  //
  // NOW, on a Rounds build, that breadcrumb does not render at all
  // (`src/app/visits/[id]/page.tsx:356`) and home is reached from the shared
  // top bar, which is a SIBLING of #main, not a descendant of it
  // (`components/rounds/app-frame-rounds.tsx:42-50`). So on that branch THIS
  // ASSERTION IS NOW ABOUT THE TOP BAR — #main is dropped there on purpose, and
  // said out loud, not because the old scope was wrong.
  const topBarHome = page.getByTestId('rounds-nav-board');
  const breadcrumbHome = page
    .locator('#main')
    .getByRole('link', { name: 'Dashboard', exact: true });
  const home = topBarHome.or(breadcrumbHome);

  // EXACTLY ONE, not "at least one", and that is the non-vacuity guard on this
  // re-point. A Rounds build that lost its top bar has nothing to fall back on
  // — the breadcrumb is flag-gated off — so the count goes to 0 and the failure
  // lands here, naming what is missing, instead of surfacing later as an
  // anonymous click timeout. A build that somehow shipped both shells fails too.
  await expect(
    home,
    'no way home from the visit stage: expected EXACTLY ONE of the Rounds ' +
      'top-bar Board link (rounds-nav-board) or the legacy in-#main "Dashboard" ' +
      'breadcrumb. Zero means the shell shipped without a home affordance.',
  ).toHaveCount(1);

  // Which shell answered decides what home looks like, below.
  const roundsChrome = (await topBarHome.count()) === 1;

  // A real click on the real element IS the T-M8 Bug 4 regression. Never
  // page.goto() here — that would prove nothing about an overlay eating it.
  await home.click();

  // WAS: `toHaveURL(/\/dashboard$/)`. The app computes its own home with
  // `recoveryHref()` (`src/lib/recovery-href.ts:30-32`) — '/board' under Rounds,
  // '/dashboard' otherwise — so the destination is whatever the built image
  // says. HOME_URL_RE is anchored over both, because 'dashboard' contains
  // 'board' and this project has shipped that substring trap three times.
  await expectAtHome(page);

  if (roundsChrome) {
    // Rounds home is the BOARD, and the board lists VISITS, not patients: one
    // lane card per visit, an <a href="/visits/<id>"> carrying testid
    // `rounds-lane-card-<id>` (`components/rounds/board.tsx:158-184`), rendered
    // inside the board's own <main id="main"> (`board-chrome.tsx:244`) — so the
    // #main scope survives here, still doing the job it was written for:
    // keeping the top bar out of a content assertion.
    //
    // Addressed BY VISIT ID, which is strictly tighter than the patient-name
    // match it replaces. What would make it fail: the board not listing a
    // freshly created visit under its default 'active' filter — a new visit is
    // QUEUED (schema default) → lane kind 'recording' → 'active'
    // (`lib/rounds/board-data.ts:109-118` and `:171-173`). That is exactly the
    // "I recorded a visit and home shows nothing" regression.
    const card = page
      .locator('#main')
      .getByTestId(`rounds-lane-card-${visitId}`);
    await expect(card).toBeVisible({ timeout: 10_000 });

    // …and it is OUR patient on it. `patientLabel` falls back to the visit's
    // denormalised patientName and then to the literal 'Unnamed patient'
    // (`board-data.ts:127-128`), so a broken patient FK renders a card that
    // exists, is addressed by the right id, and is wrong — which the id check
    // alone would pass. Anchored regex on the card's own aria-label rather than
    // a text match: it is one element and one attribute, so there is no
    // substring slack ('QA Patient Two' and 'Unnamed patient' both fail) and no
    // parent/child ambiguity. The label is not a second source of truth — it
    // and the visible name span render the same `lane.patientLabel`
    // (`board.tsx:164` and `:198-209`).
    await expect(card).toHaveAttribute('aria-label', /^QA Patient, /);
  } else {
    // Legacy home is /dashboard, which groups visits BY PATIENT (no per-visit
    // anchors on the overview) — this branch is the original assertion,
    // unchanged. Match the patient *href* (not just the name) so it cannot
    // collide with a READY-only "drafts ready to sign" row that also carries
    // the patient name; scenario 4's draft never reaches READY, but scoping by
    // href keeps it unambiguous regardless.
    await expect(
      page
        .locator('#main')
        .locator('a[href^="/patients/"]', { hasText: 'QA Patient' }),
    ).toBeVisible({ timeout: 10_000 });
  }
});
