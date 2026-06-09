// ============================================================================
// Scenario 18 — Note-format DRAFT lifecycle (Batch 3)
// ----------------------------------------------------------------------------
// Extends scenario 5 (paste → parse → activate) into draft management:
//   • A parsed format saved as a DRAFT is not active, then ACTIVATING it from
//     the list makes it live.
//   • Editing an existing DRAFT updates it IN PLACE — same row, no new version,
//     still a draft (only editing an ACTIVE template forks a version; covered
//     in scenario 19).
//
// Asserts the committed DB row (status / version / id), not the async-
// repopulated list, so the router.refresh() timing that flaked scenario 5
// can't make these flaky. Gated on NOTE_FORMAT_E2E=1 (needs an image built with
// the F7 mock fixtures — same gate as scenario 5).
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { expectHome, gotoNoteFormat, parseToReview } from '../helpers/noteFormat';
import { countActive, getDoctorId, listTemplates } from '../helpers/noteTemplates';

const GATE = process.env.NOTE_FORMAT_E2E !== '1';
const GATE_MSG =
  'Needs an app image built with the note-format mock fixtures. Run with NOTE_FORMAT_E2E=1 against a fresh build.';

test.afterEach(() => {
  cleanupTestUsers();
});

test('scenario 18: draft saved → activated from the list (MOCK)', async ({ page }) => {
  test.skip(GATE, GATE_MSG);

  const { email } = await signupFreshUser(page, 's18a');
  const doctorId = getDoctorId(email);

  await gotoNoteFormat(page);
  await parseToReview(page);
  await page.locator('#nf-name').fill('Draft Format A');
  await page.getByRole('button', { name: /save as draft/i }).click();
  await expect(page.getByText('Draft saved')).toBeVisible({ timeout: 10_000 });

  // Committed as a DRAFT — present, not active.
  let rows = listTemplates(doctorId);
  expect(rows).toHaveLength(1);
  expect(rows[0].status).toBe('draft');
  expect(rows[0].version).toBe(1);
  expect(countActive(doctorId, null)).toBe(0);

  // It shows in the list as a Draft.
  await expectHome(page);
  await page.reload();
  await expect(page.getByText('Draft Format A')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText('Draft', { exact: true })).toBeVisible();

  // Activate it from the row → goes live.
  await page.getByRole('button', { name: 'Activate', exact: true }).click();
  await expect(page.getByText('Format activated')).toBeVisible({ timeout: 10_000 });

  rows = listTemplates(doctorId);
  expect(rows).toHaveLength(1);
  expect(rows[0].status).toBe('active');
  expect(countActive(doctorId, null)).toBe(1);

  await page.reload();
  await expect(page.getByText(/Active ·/)).toBeVisible({ timeout: 15_000 });
});

test('scenario 18: editing a DRAFT updates in place (no new version) (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  const { email } = await signupFreshUser(page, 's18b');
  const doctorId = getDoctorId(email);

  await gotoNoteFormat(page);
  await parseToReview(page);
  await page.locator('#nf-name').fill('Draft Editable');
  await page.getByRole('button', { name: /save as draft/i }).click();
  await expect(page.getByText('Draft saved')).toBeVisible({ timeout: 10_000 });

  const before = listTemplates(doctorId);
  expect(before).toHaveLength(1);
  const draftId = before[0].id;
  expect(before[0].version).toBe(1);

  // Re-open the draft, rename, save as draft again.
  await expectHome(page);
  await page.reload();
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(page.locator('#nf-name')).toHaveValue('Draft Editable', { timeout: 10_000 });
  await page.locator('#nf-name').fill('Draft Edited Name');
  await page.getByRole('button', { name: /save as draft/i }).click();
  await expect(page.getByText('Draft saved')).toBeVisible({ timeout: 10_000 });

  // Same row, updated in place — no fork, no version bump.
  const after = listTemplates(doctorId);
  expect(after).toHaveLength(1);
  expect(after[0].id).toBe(draftId);
  expect(after[0].version).toBe(1);
  expect(after[0].status).toBe('draft');
  expect(after[0].name).toBe('Draft Edited Name');
});

test('scenario 18: duplicating a template creates a draft copy, original untouched (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  const { email } = await signupFreshUser(page, 's18c');
  const doctorId = getDoctorId(email);

  await gotoNoteFormat(page);
  await parseToReview(page);
  await page.locator('#nf-name').fill('Original Format');
  await page.getByRole('button', { name: /save & activate/i }).click();
  await expect(page.getByText('Format activated')).toBeVisible({ timeout: 10_000 });
  expect(listTemplates(doctorId)).toHaveLength(1);

  // Duplicate from the row.
  await expectHome(page);
  await page.reload();
  await page.getByRole('button', { name: 'Duplicate Original Format' }).click();
  await expect(page.getByText('Duplicated as a draft')).toBeVisible({ timeout: 10_000 });

  // A new DRAFT copy (v1, "(copy)") exists; the original stays the lone active.
  const rows = listTemplates(doctorId);
  expect(rows).toHaveLength(2);
  const copy = rows.find((r) => r.name === 'Original Format (copy)');
  expect(copy).toBeTruthy();
  expect(copy?.status).toBe('draft');
  expect(copy?.version).toBe(1);
  const original = rows.find((r) => r.name === 'Original Format');
  expect(original?.status).toBe('active');
  expect(countActive(doctorId, null)).toBe(1); // the copy is a draft, not a second active
});
