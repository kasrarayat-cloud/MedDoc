// ============================================================================
// Scenario 23 — Note-format PARSE-time PHI rejection (RejectedState)
// ----------------------------------------------------------------------------
// 🔴 SAFETY-CRITICAL. The OTHER PHI layer (vs. scenario 20's save-time regex):
// the parse-time LLM PHI scan. When it can't confidently clear the parsed
// template (anyUncertain), the parse is rejected and the manager shows the calm
// RejectedState — nothing is ever saved.
//
// Under MOCK the LLM is canned and the mock keys on `purpose` only (it can't
// see the note text), so the rejection is triggered by the app-global env knob
// MOCK_TEMPLATE_PHI_FLAG=true (the #280 mechanism), which flips the mocked PHI
// scan to its FLAGGED variant. That env makes EVERY parse reject, so this spec
// runs in its own Playwright project (`phi-reject`) against an app instance
// started with the flag on — kept out of the main suite, where parses must
// succeed. Still gated on NOTE_FORMAT_E2E=1 (fresh build with the fixtures).
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { gotoNoteFormat, SAMPLE_NOTE } from '../helpers/noteFormat';
import { getDoctorId, listTemplates } from '../helpers/noteTemplates';

const GATE = process.env.NOTE_FORMAT_E2E !== '1';
const GATE_MSG =
  'Needs an app image built with the note-format mock fixtures, started with MOCK_TEMPLATE_PHI_FLAG=true. Run via the phi-reject project with NOTE_FORMAT_E2E=1.';

test.afterEach(() => {
  cleanupTestUsers();
});

test('scenario 23: parse-time PHI scan rejects → RejectedState, nothing saved (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  const { email } = await signupFreshUser(page, 's23');
  const doctorId = getDoctorId(email);

  await gotoNoteFormat(page);
  await page.getByLabel('Paste a note').fill(SAMPLE_NOTE);
  await page.getByRole('button', { name: /read my format/i }).click();

  // The flagged mock scan (anyUncertain=true) → fail-safe rejection, surfaced as
  // the RejectedState alert. The review editor is never reached.
  await expect(page.getByRole('alert')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/PHI scan could not confidently clear/i)).toBeVisible();
  await expect(page.getByRole('button', { name: /save & activate/i })).toBeHidden();

  // SAFETY-CRITICAL: the rejected note was never persisted.
  expect(listTemplates(doctorId)).toHaveLength(0);

  // The retry path returns to the entry view.
  await page.getByRole('button', { name: /remove patient details & try again/i }).click();
  await expect(page.getByLabel('Paste a note')).toBeVisible({ timeout: 10_000 });
});
