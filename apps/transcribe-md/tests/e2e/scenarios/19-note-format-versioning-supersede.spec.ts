// ============================================================================
// Scenario 19 — Note-format versioning · supersession · per-encounter scoping
// ----------------------------------------------------------------------------
// The correctness core of the feature, and the place a real bug would be
// loudest (two live templates for one doctor+encounter, or an edit silently
// mutating the live row). Each test drives the real UI, then asserts the
// committed `note_templates` rows:
//   • Editing an ACTIVE template forks a NEW VERSION (v+1) and supersedes the
//     prior (old row → inactive, history kept).
//   • Activating a NEW template for the same slot supersedes the prior active —
//     exactly one active per (doctor, encounterType) at all times.
//   • Distinct encounter types hold their own active template independently.
//   • Deleting the active template reverts that encounter type to the system
//     default SOAP (no active custom row → resolveActiveTemplate falls back).
//
// maxActivePerSlot() is asserted == 1 throughout: the direct check that the
// partial-unique invariant (a supersession bug) can never slip past.
// Gated on NOTE_FORMAT_E2E=1 (fresh build with the F7 mock fixtures).
// ============================================================================

import { expect, test, type Page } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import {
  bringANote,
  expectHome,
  gotoNoteFormat,
  parseToReview,
} from '../helpers/noteFormat';
import {
  countActive,
  getDoctorId,
  listTemplates,
  maxActivePerSlot,
} from '../helpers/noteTemplates';

const GATE = process.env.NOTE_FORMAT_E2E !== '1';
const GATE_MSG =
  'Needs an app image built with the note-format mock fixtures. Run with NOTE_FORMAT_E2E=1 against a fresh build.';

test.afterEach(() => {
  cleanupTestUsers();
});

/** Parse → name → (optional) encounter → Save & activate, from the entry view. */
async function activateNew(page: Page, name: string, encounter?: string): Promise<void> {
  await parseToReview(page);
  await page.locator('#nf-name').fill(name);
  if (encounter) await page.locator('#nf-enc').selectOption(encounter);
  await page.getByRole('button', { name: /save & activate/i }).click();
  await expect(page.getByText('Format activated')).toBeVisible({ timeout: 10_000 });
}

test('scenario 19: editing an ACTIVE template forks a new version + supersedes (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  const { email } = await signupFreshUser(page, 's19a');
  const doctorId = getDoctorId(email);

  await gotoNoteFormat(page);
  await activateNew(page, 'Versioned V1');

  let rows = listTemplates(doctorId);
  expect(rows).toHaveLength(1);
  const v1Id = rows[0].id;
  expect(rows[0].version).toBe(1);
  expect(rows[0].status).toBe('active');

  // Edit the live (active) template → new version, prior superseded.
  await expectHome(page);
  await page.reload();
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(page.locator('#nf-name')).toHaveValue('Versioned V1', { timeout: 10_000 });
  await page.locator('#nf-name').fill('Versioned V2');
  await page.getByRole('button', { name: /save & activate/i }).click();
  await expect(page.getByText('Format activated')).toBeVisible({ timeout: 10_000 });

  rows = listTemplates(doctorId);
  expect(rows).toHaveLength(2); // history preserved
  const active = rows.filter((r) => r.status === 'active');
  const inactive = rows.filter((r) => r.status === 'inactive');
  expect(active).toHaveLength(1);
  expect(active[0].version).toBe(2); // bumped
  expect(active[0].name).toBe('Versioned V2');
  expect(active[0].id).not.toBe(v1Id); // forked, not mutated
  expect(inactive).toHaveLength(1);
  expect(inactive[0].id).toBe(v1Id); // original row untouched, superseded
  expect(inactive[0].version).toBe(1);
  expect(maxActivePerSlot(doctorId)).toBe(1); // invariant

  await page.reload();
  await expect(page.getByText(/· v2/)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/Active ·/)).toBeVisible();
});

test('scenario 19: activating a new template supersedes the prior active — one active per slot (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  const { email } = await signupFreshUser(page, 's19b');
  const doctorId = getDoctorId(email);

  await gotoNoteFormat(page);
  await activateNew(page, 'Cardio A', 'cardiology');
  expect(countActive(doctorId, 'cardiology')).toBe(1);

  await expectHome(page);
  await page.reload();
  await bringANote(page);
  await activateNew(page, 'Cardio B', 'cardiology');

  const cardio = listTemplates(doctorId).filter((r) => r.encounterType === 'cardiology');
  expect(cardio).toHaveLength(2);
  const activeC = cardio.filter((r) => r.status === 'active');
  const inactiveC = cardio.filter((r) => r.status === 'inactive');
  expect(activeC).toHaveLength(1);
  expect(activeC[0].name).toBe('Cardio B');
  expect(inactiveC).toHaveLength(1);
  expect(inactiveC[0].name).toBe('Cardio A');
  expect(countActive(doctorId, 'cardiology')).toBe(1); // exactly one active
  expect(maxActivePerSlot(doctorId)).toBe(1); // invariant holds
});

test('scenario 19: distinct encounter types each hold their own active template (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  const { email } = await signupFreshUser(page, 's19c');
  const doctorId = getDoctorId(email);

  await gotoNoteFormat(page);
  await activateNew(page, 'Cardio Fmt', 'cardiology');

  await expectHome(page);
  await page.reload();
  await bringANote(page);
  await activateNew(page, 'Derm Fmt', 'dermatology');

  // Both active — separate (doctor, encounterType) slots, independent.
  expect(countActive(doctorId, 'cardiology')).toBe(1);
  expect(countActive(doctorId, 'dermatology')).toBe(1);
  const active = listTemplates(doctorId).filter((r) => r.status === 'active');
  expect(active).toHaveLength(2);
  expect(active.map((r) => r.encounterType).sort()).toEqual(['cardiology', 'dermatology']);
  expect(maxActivePerSlot(doctorId)).toBe(1); // one active PER slot, across two slots
});

test('scenario 19: deleting the active template reverts the encounter type to default SOAP (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  const { email } = await signupFreshUser(page, 's19d');
  const doctorId = getDoctorId(email);

  await gotoNoteFormat(page);
  await activateNew(page, 'To Be Removed', 'cardiology');
  expect(countActive(doctorId, 'cardiology')).toBe(1);

  // There is no standalone "deactivate" control — reverting an encounter type to
  // the standard SOAP format is done by deleting the active custom template.
  await expectHome(page);
  await page.reload();
  await page.getByRole('button', { name: 'Delete To Be Removed' }).click();
  await expect(page.getByText('Format deleted')).toBeVisible({ timeout: 10_000 });

  // No active custom row for cardiology → resolveActiveTemplate falls back to the
  // system default (proven end-to-end in scenario 22).
  expect(countActive(doctorId, 'cardiology')).toBe(0);
  expect(listTemplates(doctorId)).toHaveLength(0);

  await page.reload();
  await expect(page.getByText('To Be Removed')).toBeHidden();
});
