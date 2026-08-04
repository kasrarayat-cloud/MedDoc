// ============================================================================
// Scenario 6 — Patient management: list, standalone create, detail, edit.
// ----------------------------------------------------------------------------
// Phase 2 Batch 1. Covers the patient surfaces beyond the visit-picker create
// that scenarios 1-5 already exercise:
//   - /patients list rendering + the name search
//     (2026-08-04: no longer an in-memory filter — the shipped roster runs a
//      220ms-debounced SERVER search via `usePatientsRoster`; see the re-point
//      note on the first test.)
//   - "standalone" create via POST /api/patients (there is intentionally no
//     dedicated create-patient UI — patients are created in the visit flow or
//     the API; this asserts the API path + that the list reflects it)
//   - /patients/[id] detail header + visit-history tab
//   - the Edit-patient dialog persisting a rename to the header
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { createPatientViaApi, createReadyTextVisit } from '../helpers/visit-setup';

test.afterEach(() => {
  cleanupTestUsers();
});

test('patients list: standalone-created patients render + name filter narrows', async ({
  page,
}) => {
  await signupFreshUser(page, 'p-list');
  const ada = await createPatientViaApi(page, 'Ada Lovelace');
  const bjarne = await createPatientViaApi(page, 'Bjarne Stroustrup');

  await page.goto('/patients');
  // Both standalone-created patients render as cards linking to their detail.
  await expect(page.locator(`a[href="/patients/${ada.id}"]`)).toBeVisible();
  await expect(page.locator(`a[href="/patients/${bjarne.id}"]`)).toBeVisible();

  // ── RE-POINT ─────────────────────────────────────────────────────────────
  // WAS: getByLabel('Filter patients by name') — the legacy card grid's input
  // (src/app/patients/patients-list-client.tsx:51), which /patients only
  // renders with BOTH skin flags off.
  // NOW: the shipped roster's search box, src/components/rounds/patients-roster.tsx
  //      :88-98 — aria-label 'Search patients' (:93), data-testid
  //      'rounds-patients-search' (:94). Locating by testid rather than by the
  //      new aria-label on purpose: 'Search patients' is ALSO the C3 list's
  //      label (app/patients/patients-list-c3.tsx:64), so getByLabel would
  //      silently pass against whichever of the two skins rendered, and this
  //      spec would stop being able to tell them apart.
  //
  // ⚠️ AND THE FILTER IS NO LONGER CLIENT-SIDE. `usePatientsRoster`
  // (src/lib/patients-roster.ts) debounces 220ms and calls the server
  // `searchPatientsAction`; the narrowing below is a round trip, absorbed by
  // Playwright's auto-retrying assertions rather than by a sleep.
  //
  // ⚠️ THE ORDERING TRICK BELOW WAS WRONG AND IS CORRECTED. An earlier version
  // of this comment claimed "Ada-visible first, so an empty/errored list cannot
  // read as the filter working". Under a DEBOUNCED server search that is exactly
  // backwards: for the first 220ms the roster still holds BOTH rows, so
  // `expect(ada).toBeVisible()` passes IMMEDIATELY — before any filtering has
  // happened — and then a search that errored and returned nothing satisfies
  // `expect(bjarne).toHaveCount(0)` too. Both assertions green, zero filtering.
  // A wrong "what would make this fail" note is worse than none.
  //
  // The honest form is a COUNT, which reds at 0 as loudly as at 2. Same shape
  // `rounds-r1.spec.ts:373-379` already uses on this component.
  //
  // WHAT WOULD MAKE THIS FAIL: the search input losing its testid; the server
  // returning the unfiltered roster (count 2); the search erroring or returning
  // nothing (count 0); the right count with the wrong row (the href assertions).
  const search = page.getByTestId('rounds-patients-search');

  // The name search narrows the roster to the match…
  await search.fill('Ada');
  await expect(
    page.getByTestId('rounds-patient-row'),
    'the debounced server search did not narrow to exactly one row — 0 means it ' +
      'errored or returned nothing, 2 means it did not filter at all',
  ).toHaveCount(1);
  await expect(page.locator(`a[href="/patients/${ada.id}"]`)).toBeVisible();
  await expect(page.locator(`a[href="/patients/${bjarne.id}"]`)).toHaveCount(0);

  // …and clearing it restores both. Bjarne first: he is the one the previous
  // step removed, so he is the assertion that can actually observe the restore.
  // (Ada never left the DOM, so asserting her first would pass on a search box
  // that had stopped responding entirely.)
  await search.fill('');
  await expect(page.locator(`a[href="/patients/${bjarne.id}"]`)).toBeVisible();
  await expect(page.locator(`a[href="/patients/${ada.id}"]`)).toBeVisible();
});

test('patient detail: header + stats + visit history reflect a real visit', async ({
  page,
}) => {
  await signupFreshUser(page, 'p-detail');
  const patient = await createPatientViaApi(page, 'Grace Hopper');
  const visitId = await createReadyTextVisit(page, { patientId: patient.id });

  await page.goto(`/patients/${patient.id}`);
  await expect(
    page.getByRole('heading', { name: 'Grace Hopper', level: 1 }),
  ).toBeVisible();
  // ── RE-POINT ─────────────────────────────────────────────────────────────
  // WAS: getByText('Total visits') — the <StatCard label="Total visits"> in the
  // four-tile grid. That grid is on the LEGACY return of
  // src/app/patients/[id]/page.tsx (the tile is at :547, reachable only with
  // skin-beta off); under the shipped skin the four vanity tiles collapsed into
  // the quiet one-line summary at :466-481. The label has no other source, so
  // the old assertion was looking for a string the shipped page never prints.
  //
  // NOW: that summary line, located by the `data-testid="patient-visit-summary"`
  // this change added to it, and asserted on its `data-visit-count` attribute
  // rather than on the sentence it renders. The sentence is copy — "1 visit ·
  // 0 signed · last 3m ago · 1 this Aug" — and the count is the fact the
  // retired stat tile was actually carrying.
  //
  // WHAT WOULD MAKE THIS FAIL: the summary line disappearing (no testid to
  // resolve); the page counting 0 visits for a patient that has one — i.e. the
  // exact regression the "Total visits" tile existed to catch — because
  // data-visit-count would read "0". A page that rendered the line but lost the
  // patient's visit does NOT pass this.
  const summary = page.getByTestId('patient-visit-summary');
  await expect(summary).toBeVisible();
  await expect(summary).toHaveAttribute('data-visit-count', '1');
  // …and the Visits history lists that same visit.
  // ⚠️ SCOPED PAST THE DUPLICATE. Under Rounds the patient page carries TWO
  // anchors to the same visit — the summary's "Open last note" shortcut
  // (`qm-rounds-btn-secondary`) and the history row itself (`qm-lin-row`) — so
  // a bare `#main a[href=…]` is a strict-mode violation. It is also the wrong
  // claim: "Open last note" is the SUMMARY's affordance, and this assertion is
  // about the HISTORY list. Naming the row is what keeps the two separable, so
  // losing the history while keeping the shortcut still reds.
  await expect(
    page.locator(`#main a.qm-lin-row[href="/visits/${visitId}"]`),
    'the visit is missing from the patient\'s history list (the summary\'s ' +
      '"Open last note" shortcut is a different control and does not cover it)',
  ).toBeVisible();
});

test('patient edit: rename via the Edit dialog persists to the header', async ({
  page,
}) => {
  await signupFreshUser(page, 'p-edit');
  const patient = await createPatientViaApi(page, 'Original Name');

  await page.goto(`/patients/${patient.id}`);
  await expect(
    page.getByRole('heading', { name: 'Original Name', level: 1 }),
  ).toBeVisible();

  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.locator('#edit-patient-name').fill('Renamed Patient');
  await page.getByRole('button', { name: /save changes/i }).click();

  // router.refresh() re-renders the server header with the new name.
  await expect(
    page.getByRole('heading', { name: 'Renamed Patient', level: 1 }),
  ).toBeVisible({ timeout: 10_000 });
  await expect(
    page.getByRole('heading', { name: 'Original Name', level: 1 }),
  ).toHaveCount(0);
});
