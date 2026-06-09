// ============================================================================
// Scenario 9 — Editable SOAP note (inline edit + persistence).
// ----------------------------------------------------------------------------
// Phase 2 Batch 1. The v6 SOAP body is a click-to-edit affordance per section;
// editing opens a textarea over the FULL markdown blob and Esc/blur saves via
// saveSoapDraftAction. Asserts the edit renders AND survives a reload (i.e.
// it persisted server-side, not just in local state).
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { createReadyTextVisit } from '../helpers/visit-setup';

test.afterEach(() => {
  cleanupTestUsers();
});

test('SOAP edit: inline-editing a section persists + survives reload', async ({
  page,
}) => {
  await signupFreshUser(page, 'soap-edit');
  const visitId = await createReadyTextVisit(page, { patientName: 'Edit Patient' });

  await page.goto(`/visits/${visitId}`);
  await expect(page.getByText(/tension headache/i)).toBeVisible();

  const marker = 'QA-EDIT-MARKER-7f3a2b';
  // Click the first editable S/O/A/P section → opens the full-blob textarea.
  await page.getByRole('button', { name: 'Edit SOAP note' }).first().click();
  const editor = page.getByRole('textbox', { name: 'Edit SOAP note' });
  await expect(editor).toBeVisible();
  await editor.fill(`${await editor.inputValue()}\n\n${marker}`);
  // Esc saves (saveSoapDraftAction); the textarea closes + body re-renders.
  await editor.press('Escape');

  await expect(page.getByText(marker)).toBeVisible({ timeout: 10_000 });

  // Persisted server-side — survives a fresh load. The visit page recomputes the
  // E&M score before the SOAP body paints, so wait for the body to render
  // (a stable anchor) before asserting the persisted marker, and give it room.
  await page.reload();
  await expect(page.getByText(/tension headache/i)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(marker)).toBeVisible({ timeout: 15_000 });
});
