// ============================================================================
// Scenario 22 — Active-template resolution for a visit (Phase-1 wiring)
// ----------------------------------------------------------------------------
// Proves the worker actually RESOLVES a doctor's active note template when it
// generates a visit's SOAP, and records its provenance. The worker calls
// resolveActiveTemplate(doctorId, visit.specialty) before L4 and persists the
// chosen template's id + version onto the visit (TranscribeVisit.noteTemplateId
// / noteTemplateVersion). We drive a real visit through the (MOCK) pipeline to
// READY and assert that column.
//   • No custom template → resolves the seeded system default (tmpl_system_default_soap).
//   • An active catch-all custom template → the visit resolves IT, not the default.
//
// BOUNDARY: under MOCK the SOAP text is canned, so this proves the template was
// SELECTED, not the LLM's fidelity to it (that's the in-process layer proof).
// The encounterType *matching* logic is exhaustively covered by the unit test
// resolve-active-template.test.ts; here we prove the worker→resolve→persist
// wiring end-to-end. Gated on NOTE_FORMAT_E2E=1.
// ============================================================================

import { resolve } from 'node:path';

import { expect, test, type Page } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { createPatientAndContinue } from '../helpers/patient';
import { signupFreshUser } from '../helpers/signup';
import { waitForVisitStatus } from '../helpers/waitForReady';
import { getDoctorId, seedActiveTemplate, visitTemplate } from '../helpers/noteTemplates';

const GATE = process.env.NOTE_FORMAT_E2E !== '1';
const GATE_MSG =
  'Needs an app image built with the note-format mock fixtures. Run with NOTE_FORMAT_E2E=1 against a fresh build.';

const AUDIO_FIXTURE = resolve(__dirname, '../fixtures/audio/silence-3sec.mp3');
const SYSTEM_DEFAULT_ID = 'tmpl_system_default_soap';

test.afterEach(() => {
  cleanupTestUsers();
});

/** Create a visit via the audio-upload flow and run it to READY; returns the
 *  visit id. Mirrors scenario 1 (the proven pipeline-to-READY pattern). */
async function runAudioVisitToReady(page: Page): Promise<string> {
  await page.goto('/visits/new');
  await createPatientAndContinue(page);
  await page.getByRole('button', { name: /upload audio/i }).click();
  await page.waitForURL(/\/visits\/c[a-z0-9]{10,}/, { timeout: 15_000 });
  const visitId = new URL(page.url()).pathname.split('/').pop()!;
  await page.locator('input[type="file"]').first().setInputFiles(AUDIO_FIXTURE);
  await page.getByRole('button', { name: /upload & transcribe/i }).click();
  await waitForVisitStatus(page, visitId, 'READY');
  return visitId;
}

test('scenario 22: a visit with no custom template resolves the system default (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  await signupFreshUser(page, 's22a');
  const visitId = await runAudioVisitToReady(page);

  const ref = visitTemplate(visitId);
  expect(ref.noteTemplateId).toBe(SYSTEM_DEFAULT_ID);
  expect(ref.noteTemplateVersion).toBe(1);
});

test('scenario 22: a visit resolves the doctor’s active custom template (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  const { email } = await signupFreshUser(page, 's22b');
  const doctorId = getDoctorId(email);
  // An active catch-all template (encounterType = null) resolves for a visit of
  // any specialty — so this holds regardless of the new-visit form's default.
  const tmplId = seedActiveTemplate(doctorId, {
    name: 'My Catch-All Format',
    encounterType: null,
    version: 1,
  });

  const visitId = await runAudioVisitToReady(page);

  const ref = visitTemplate(visitId);
  // The doctor's active template was selected over the system default.
  expect(ref.noteTemplateId).toBe(tmplId);
  expect(ref.noteTemplateId).not.toBe(SYSTEM_DEFAULT_ID);
  expect(ref.noteTemplateVersion).toBe(1);
});
