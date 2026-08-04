// ============================================================================
// Scenario 10 — Visit lifecycle: delete → trash → restore, and archive.
// ----------------------------------------------------------------------------
// Phase 2 Batch 1. Exercises VisitLifecycleActions:
//   - a READY visit → Delete (soft) → appears in the patient Trash tab → Restore
//   - a SIGNED visit → Archive → hidden from the active /visits list
// Signing is done via the API (no delivery) so the archive path reaches SIGNED
// without driving the export/clipboard machinery.
//
// ── F-ret.1 RE-POINT, 2026-08-04 ────────────────────────────────────────────
// NOTHING HERE IS RETIRED. `VisitLifecycleActions` still owns Delete, Restore
// and Archive; `POST /delete`, `/restore` and `/archive` are untouched. What
// moved is WHERE the controls hang and WHERE the app lands afterwards.
//
//  1. THE CONTROLS SIT IN A COLLAPSED DISCLOSURE UNDER ROUNDS.
//     `<details data-testid="rounds-visit-overflow">` — `stage.tsx:146` on an
//     unsigned visit, `signed.tsx:199` on a signed one — with no `open`
//     attribute. A closed `<details>` keeps its content out of the
//     accessibility tree, so every `getByRole('button', …)` in this file was
//     resolving against nothing. The tests now open it by clicking its own
//     `<summary>`. They never force it open with CSS, `evaluate` or an `open`
//     attribute: "collapsed until a deliberate click" is the recorded product
//     decision that took a destructive control out of stray-click range
//     (`stage.tsx:137-142`), and a test that defeats it stops measuring the
//     shipped product.
//     ⚠️ Flag-OFF there is NO disclosure — the same node renders in its own row
//     inside `#main` (`visits/[id]/page.tsx:473`, the `{!roundsChrome && (`
//     branch). `openVisitActions` therefore branches on the DOM, never on a
//     flag: `NEXT_PUBLIC_SKIN_ROUNDS` is inlined into the app bundle at
//     docker-build time and is NOT in the Playwright runner's environment, so a
//     test-side flag read answers `undefined` and would walk the wrong path on
//     the flag-ON image. Same reasoning as `helpers/home.ts` and
//     `helpers/sign.ts`.
//
//  2. BOTH CONFIRM HANDLERS PUSH THE SERVER-COMPUTED HOME.
//     `router.push(recoveryHref())` — `visit-lifecycle-actions.tsx:360` for
//     delete, `:297` for archive — which is `/board` under Rounds and
//     `/dashboard` otherwise. The two hardcoded `/\/dashboard$/` assertions are
//     now `expectAtHome`, which accepts both so a flag-OFF rollback image does
//     not turn this fix into a false red.
//
//  3. `getByRole('dialog')` IS GONE, and must not come back. Under Rounds the
//     gate flow (`gate-flow.tsx:228`) and the chat drawer (`chat-drawer.tsx:175`)
//     both carry `role="dialog"`, so the bare role query is ambiguous by
//     construction and can resolve against the wrong node. `ConfirmScaffold`
//     (`visit-lifecycle-actions.tsx:506`) has no testid, so its panel is
//     addressed by class + its own EXACT title instead — which is strictly more
//     specific than the old query, since it also pins the confirm copy.
//
// WHAT WOULD MAKE THE RE-POINTED ASSERTIONS FAIL (i.e. what they still buy):
//   - the disclosure shipping already-open, or not toggling  → the
//     open/closed pair around the summary click;
//   - the disclosure rendering EMPTY — the exact R2 defect shape, an `<details>`
//     that looks like a control and contains none → the scoped Delete/Archive
//     click, which is scoped INTO the disclosure and cannot fall back to some
//     other button on the page;
//   - Archive dropping off the signed screen again (PR #523's regression) → the
//     same scoped click, on `rounds-signed`'s copy of the disclosure;
//   - the confirm dialog not opening, or opening with the wrong copy → the
//     exact-title panel filter;
//   - the handler landing anywhere that is not the app's home → `expectAtHome`.
// ============================================================================

import { expect, test, type Locator, type Page } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { expectAtHome } from '../helpers/home';
import { signupFreshUser } from '../helpers/signup';
import { createPatientViaApi, createReadyTextVisit } from '../helpers/visit-setup';
import { signViaApi } from '../helpers/sign';

/**
 * Reveal the visit's lifecycle actions on WHICHEVER SKIN IS BUILT, and return
 * the container they live in so callers can scope into it.
 *
 * Rounds  → a collapsed `<details data-testid="rounds-visit-overflow">`. Opened
 *           here by clicking its `<summary>` — the same gesture a doctor makes.
 * Legacy  → no disclosure; the actions are already in the page's own row inside
 *           `#main` (`visits/[id]/page.tsx:473`). Nothing to open.
 *
 * Returning a SCOPE rather than clicking at page level is deliberate: "Archive"
 * names both the trigger inside the disclosure and the confirm button in the
 * portaled dialog, and "Delete" is a name a future page-level control could
 * easily reuse. A scoped query cannot silently resolve against the wrong one.
 */
async function openVisitActions(page: Page): Promise<Locator> {
  const overflow = page.getByTestId('rounds-visit-overflow');

  // Server-rendered into the initial HTML on both surfaces, so this `count()`
  // is answered by the document `goto` already waited for — no flag read.
  if (await overflow.count()) {
    const disclosure = overflow.first();

    // The COLLAPSED default is the product decision, not an accident. Asserting
    // it before the click is what stops this helper from quietly passing on a
    // build that shipped the destructive controls already exposed — and it is
    // what makes the `open === true` below evidence that OUR click did it.
    await expect(
      disclosure,
      'the Rounds lifecycle disclosure is already open — it is meant to ship ' +
        'collapsed (stage.tsx:137-142) so a destructive control costs a ' +
        'deliberate click',
    ).toHaveJSProperty('open', false);

    await disclosure.locator('summary').click();

    await expect(
      disclosure,
      'clicking the disclosure summary did not open it',
    ).toHaveJSProperty('open', true);

    return disclosure;
  }

  // Legacy build. `#main` is the single main landmark every AppFrame branch
  // renders (`ui/app-frame.tsx:81/110`, `rounds/app-frame-rounds.tsx:48`).
  //
  // ⚠️ PROVE WE ARE ACTUALLY ON THE LEGACY BUILD before returning it. Under
  // Rounds the disclosure ALWAYS renders on a READY / SIGNED / trashed visit
  // (`page.tsx:527` passes `lifecycleActions` unconditionally and
  // `VisitLifecycleActions` returns an element for every one of those states),
  // so "no disclosure" plus "a Rounds surface" is not a skin — it is this
  // helper having sampled a page that had not finished arriving, and the
  // resulting timeout twelve lines later would name the button rather than the
  // race. Fail here, with the cause.
  await expect(
    page.getByTestId('rounds-stage').or(page.getByTestId('rounds-signed')),
    'no rounds-visit-overflow disclosure, yet a Rounds visit surface is on the ' +
      'page — either the disclosure was dropped from a surface again (the R2 / ' +
      'PR #523 defect) or this helper read the DOM too early',
  ).toHaveCount(0);

  return page.locator('#main');
}

/**
 * The lifecycle confirm dialog, pinned by its own exact title.
 *
 * ⚠️ NOT `getByRole('dialog')` — see the header. `ConfirmScaffold` renders no
 * testid and is portaled to `<body>`, outside both `#main` and the disclosure,
 * so the class + title filter is what makes this unambiguous. If the panel
 * class is ever renamed this fails loudly at `visit-lifecycle-actions.tsx:508`,
 * which is the honest failure — it cannot degrade into matching the trigger.
 */
function confirmPanel(page: Page, title: string): Locator {
  return page
    .locator('.qm-lin-spotlight-panel')
    .filter({ has: page.getByRole('heading', { name: title, exact: true }) });
}

test.afterEach(() => {
  cleanupTestUsers();
});

test('lifecycle: delete a READY visit → trash → restore', async ({ page }) => {
  await signupFreshUser(page, 'v-del');
  const patient = await createPatientViaApi(page, 'Trash Patient');
  const visitId = await createReadyTextVisit(page, { patientId: patient.id });

  await page.goto(`/visits/${visitId}`);

  // WAS: `page.getByRole('button', { name: 'Delete', exact: true }).click()` at
  // page level. NOW: the same button, reached through the disclosure that holds
  // it under Rounds (`stage.tsx:146`) and scoped to it. Fails if the disclosure
  // is missing, does not open, or opens empty.
  const actions = await openVisitActions(page);
  await actions.getByRole('button', { name: 'Delete', exact: true }).click();

  // WAS: `expect(page.getByRole('dialog')).toBeVisible()`. That role is
  // ambiguous under Rounds and, worse, said nothing about WHICH dialog. This
  // pins the soft-delete confirm by its exact copy — a READY visit with input
  // must take the SOFT path, so a build that routed it to the hard-delete
  // dialog ("Delete this draft?") now fails here rather than silently
  // permanently deleting the visit and passing the rest of the test.
  const trashConfirm = confirmPanel(page, 'Move to trash?');
  await expect(trashConfirm).toBeVisible();
  await trashConfirm
    .getByRole('button', { name: 'Move to trash', exact: true })
    .click();

  // WAS: `toHaveURL(/\/dashboard$/)`. The handler pushes `recoveryHref()`
  // (`visit-lifecycle-actions.tsx:360`) → `/board` under Rounds, `/dashboard`
  // otherwise. `expectAtHome` accepts both and is anchored, so `/dashboard`
  // containing `board` cannot false-match. Fails if the confirm lands anywhere
  // else — including staying on the visit because the POST failed.
  await expectAtHome(page);

  // Gone from the active visit list.
  await page.goto('/visits');
  await expect(page.locator(`a[href="/visits/${visitId}"]`)).toHaveCount(0);

  // Present in the patient's Trash tab (the trashed card links back to the visit).
  await page.goto(`/patients/${patient.id}?tab=trash`);
  await expect(page.locator(`#main a[href="/visits/${visitId}"]`)).toBeVisible();

  // Restore from the visit page's trash banner → back in the active list.
  //
  // The wait below is load-bearing, not defensive. Restore is a CLIENT fetch:
  // the handler does `await fetch(POST /restore)` and only then router.refresh().
  // Playwright's click() resolves as soon as the click is DISPATCHED, so a bare
  // `click(); goto('/visits')` navigates while that POST is still in flight —
  // and navigating tears the page down, which aborts it. The visit then never
  // leaves the trash and the list assertion fails 10s later, pointing at the
  // list rather than at the restore that never happened.
  //
  // This was intermittent in CI and green locally: the race only loses when the
  // box is loaded enough for the POST to still be in flight one tick after the
  // click, which is exactly what parallel workers on a CI runner produce. That
  // made "re-run the job" look like a fix, so it stayed a flake instead of a bug.
  //
  // Waiting on the RESPONSE is the deterministic signal — it proves the server
  // committed before we navigate. Deliberately not the success toast: toasts
  // auto-dismiss (4s) and would reintroduce a timing dependency.
  await page.goto(`/visits/${visitId}`);

  // A trashed READY visit still renders the stage, so `TrashedBanner` — Restore
  // and Delete-permanently — arrives through the SAME disclosure slot as Delete
  // did (`visit-lifecycle-actions.tsx:85` → `page.tsx:527` → `stage.tsx:153`).
  // Re-opened here because this is a fresh document: the disclosure is
  // collapsed again, which the helper asserts.
  const trashedActions = await openVisitActions(page);

  const restored = page.waitForResponse(
    (r) =>
      r.url().includes(`/api/visits/${visitId}/restore`) &&
      r.request().method() === 'POST',
    { timeout: 15_000 },
  );
  // WAS: `/restore/i` at page level. Exact-and-scoped: `/restore/i` is a
  // substring match that would also accept a "Restore all" or a banner link,
  // and at page level it could resolve outside the lifecycle actions entirely.
  await trashedActions
    .getByRole('button', { name: 'Restore', exact: true })
    .click();
  expect((await restored).status()).toBe(200);

  await page.goto('/visits');
  await expect(page.locator(`a[href="/visits/${visitId}"]`)).toBeVisible({
    timeout: 10_000,
  });
});

test('lifecycle: archive a SIGNED visit → hidden from the active list', async ({
  page,
}) => {
  await signupFreshUser(page, 'v-arch');
  const visitId = await createReadyTextVisit(page, { patientName: 'Archive Patient' });

  // Sign via the API (no delivery destinations) so the visit reaches SIGNED.
  const signRes = await signViaApi(page, visitId);
  expect(
    signRes.ok(),
    `sign failed: ${signRes.status()} ${await signRes.text()}`,
  ).toBe(true);

  // ── POSITIVE CONTROL, added 2026-08-04 ──────────────────────────────────
  // "Hidden from the active list" is a claim about a set, and the closing
  // `toHaveCount(0)` never established that the visit was ever IN that set —
  // it would have read green against a /visits that errored, listed nothing,
  // or never contained a signed visit in the first place. `/visits` with no
  // filter excludes only `deletedAt`/`archivedAt` (`visits/page.tsx:107-108`),
  // so a SIGNED visit belongs here until it is archived.
  await page.goto('/visits');
  await expect(
    page.locator(`a[href="/visits/${visitId}"]`),
    'the signed visit is not in the active list BEFORE archiving, so the ' +
      'absence assertion at the end of this test would prove nothing',
  ).toBeVisible({ timeout: 10_000 });

  await page.goto(`/visits/${visitId}`);

  // SIGNED → the lifecycle offers Archive (trigger), then a confirm dialog.
  //
  // WAS: `page.getByRole('button', { name: 'Archive', exact: true }).click()`
  // at page level. Under Rounds a signed visit renders `RoundsSigned`, not
  // `RoundsStage` — and until PR #523 that component had NO actions slot, so
  // Archive was absent from the DOM on every signed note for a day. It now
  // hangs in the same collapsed disclosure as the stage's
  // (`signed.tsx:199`, same `data-testid`), which is why one helper serves
  // both surfaces. Scoped INTO the disclosure so this cannot pass by finding
  // some other "Archive" on the page.
  const actions = await openVisitActions(page);
  await actions.getByRole('button', { name: 'Archive', exact: true }).click();

  // WAS: `expect(page.getByRole('dialog')).toBeVisible()` then the confirm
  // scoped to that same ambiguous role. The panel is pinned by its exact title
  // instead; scoping the confirm button to it is still required, because the
  // trigger we just clicked carries the identical accessible name.
  const archiveConfirm = confirmPanel(page, 'Archive this visit?');
  await expect(archiveConfirm).toBeVisible();
  await archiveConfirm
    .getByRole('button', { name: 'Archive', exact: true })
    .click();

  // WAS: `toHaveURL(/\/dashboard$/)`. Same `recoveryHref()` push as the delete
  // path, from `visit-lifecycle-actions.tsx:297`.
  await expectAtHome(page);

  // Hidden from the active /visits list — and now meaningfully so, because the
  // positive control above proved it was listed a moment ago.
  await page.goto('/visits');
  await expect(page.locator(`a[href="/visits/${visitId}"]`)).toHaveCount(0);
});
