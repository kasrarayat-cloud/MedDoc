// ============================================================================
// Scenario 20 — Note-format PHI gate at SAVE time (deterministic regex layer)
// ----------------------------------------------------------------------------
// 🔴 SAFETY-CRITICAL. The save-time PHI gate (applyPhiGate, regex layer — no
// LLM, runs on EVERY save incl. doctor edits) is the last line before a row is
// written. This exercises the REAL detectors (not a mock), env-free, so it runs
// in the normal suite:
//   • Structured PHI in a STRUCTURAL field (template name) → the save is
//     REJECTED and NO row is written. (PHI can never reach the DB.)
//   • Structured PHI in an optional DEFAULT-TEXT field → SCRUBBED (dropped) and
//     the save succeeds with the PHI absent from the persisted row.
//
// The parse-time LLM-scan rejection (MOCK_TEMPLATE_PHI_FLAG → RejectedState) is
// covered separately in scenario 23 (it needs an app-global env flag, so it
// runs in the dedicated `phi-reject` Playwright project).
// Gated on NOTE_FORMAT_E2E=1 (fresh build with the F7 mock fixtures).
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { gotoNoteFormat, parseToReview } from '../helpers/noteFormat';
import { getDoctorId, listTemplates, sectionsText } from '../helpers/noteTemplates';

const GATE = process.env.NOTE_FORMAT_E2E !== '1';
const GATE_MSG =
  'Needs an app image built with the note-format mock fixtures. Run with NOTE_FORMAT_E2E=1 against a fresh build.';

// A structured identifier the deterministic detector reliably catches (SSN
// shape: \d{3}-?\d{2}-?\d{4}). Not real PII.
const PHI_SSN = '123-45-6789';

test.afterEach(() => {
  cleanupTestUsers();
});

test('scenario 20: PHI in a STRUCTURAL field is rejected — no template saved (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  const { email } = await signupFreshUser(page, 's20a');
  const doctorId = getDoctorId(email);

  await gotoNoteFormat(page);
  await parseToReview(page);

  // The template NAME is a structural field — PHI there can't be safely
  // scrubbed, so the gate must REJECT the whole save.
  await page.locator('#nf-name').fill(`Clinic ${PHI_SSN}`);
  await page.getByRole('button', { name: /save & activate/i }).click();

  // Rejected: the editor surfaces "Could not save" and stays in review.
  await expect(page.getByText('Could not save')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/structural field/i)).toBeVisible();
  await expect(page.getByRole('button', { name: /save & activate/i })).toBeVisible();

  // SAFETY-CRITICAL: nothing carrying PHI was written.
  expect(listTemplates(doctorId)).toHaveLength(0);
});

test('scenario 20: PHI in a DEFAULT-TEXT field is scrubbed, not persisted (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  const { email } = await signupFreshUser(page, 's20b');
  const doctorId = getDoctorId(email);

  await gotoNoteFormat(page);
  await parseToReview(page);
  await page.locator('#nf-name').fill('Scrub Test Format');

  // The mock fixture's "Objective" section ships with a default, so its editor
  // is expanded. Inject PHI into that optional default-text field.
  const objectiveDefault = page.getByLabel('Default text for Objective');
  await expect(objectiveDefault).toBeVisible({ timeout: 10_000 });
  await objectiveDefault.fill(`Normal exam. Patient SSN ${PHI_SSN}.`);

  await page.getByRole('button', { name: /save & activate/i }).click();

  // Optional field → SCRUBBED (dropped) + flagged, the save SUCCEEDS.
  await expect(page.getByText('Format activated')).toBeVisible({ timeout: 10_000 });

  const rows = listTemplates(doctorId);
  expect(rows).toHaveLength(1);
  // The persisted sections must NOT contain the PHI — it was scrubbed.
  expect(sectionsText(rows[0].id)).not.toContain(PHI_SSN);
});
