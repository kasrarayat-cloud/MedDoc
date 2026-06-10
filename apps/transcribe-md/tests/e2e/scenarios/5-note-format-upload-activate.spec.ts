// ============================================================================
// Scenario 5 — Note-format customization: paste → parse → review → activate
// ----------------------------------------------------------------------------
// The F7 payoff (full-qa-20260604T202447Z). parseNoteToTemplate() makes two
// AI calls (tm_template_parse + tm_template_phi_scan); with the MOCK fixtures
// added in packages/ai/src/mock.ts the whole upload→parse→review→activate flow
// runs deterministically under MOCK_AI_CALLS=true — no real AI, no tokens.
//
// GATED ON PURPOSE. This spec needs the app image to CONTAIN those mock
// fixtures. The committed qa stack (docker-compose.qa.yml) runs the *prebuilt*
// `meddoc-pro-transcribe-md:latest` image, which predates the fixtures — so on
// that image the parse would throw and this spec would falsely fail. It is
// therefore skipped unless NOTE_FORMAT_E2E=1, which you set when running against
// an image built from this source (a fresh CI/standalone build). The fixtures
// themselves are validated in-process against the real Zod schemas
// (note-template-schema.ts) on every change.
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';

// A plain, representative note. Content is irrelevant under MOCK (the fixture is
// returned regardless), but it must be non-empty and free of angle-bracket
// delimiter tokens — parseNoteToTemplate rejects those as an injection attempt
// BEFORE the (mocked) LLM call.
const SAMPLE_NOTE = [
  'Follow-up visit.',
  'Subjective: doing well, no new complaints.',
  'Objective: vitals stable, exam unremarkable.',
  'Assessment: stable.',
  'Plan: continue current management, return in 3 months.',
].join('\n');

test.afterEach(() => {
  cleanupTestUsers();
});

test('scenario 5: note-format paste → parse → review → activate (MOCK)', async ({
  page,
}) => {
  test.skip(
    process.env.NOTE_FORMAT_E2E !== '1',
    'Needs an app image built with the F7 note-format mock fixtures (the prebuilt qa image predates them). Run with NOTE_FORMAT_E2E=1 against a fresh build.',
  );

  await signupFreshUser(page, 's5');

  // The note-format manager lives in /settings (section id="note-format"). A
  // fresh user has no templates, so it opens in the "entry" (bring-a-note) view.
  await page.goto('/settings');
  await page.getByLabel('Paste a note').fill(SAMPLE_NOTE);
  await page.getByRole('button', { name: /read my format/i }).click();

  // Parse (mocked) resolves into the review editor.
  await expect(
    page.getByRole('button', { name: /save & activate/i }),
  ).toBeVisible({ timeout: 15_000 });
  // The mock fixture's template name is pre-filled in the review editor.
  await expect(page.locator('#nf-name')).toHaveValue('[MOCK] General Follow-up');

  await page.getByRole('button', { name: /save & activate/i }).click();

  // Save & activate persists the template, then the manager swaps to its 'home'
  // view via client state (setView) while router.refresh() repopulates the
  // server-rendered template LIST asynchronously. Assert we reached home, then
  // RELOAD to force a deterministic server render of the persisted+activated
  // template — otherwise the list assertion races the refresh (flaked under CI
  // load once the suite grew in Batch 1; the save itself is confirmed by
  // reaching the home view).
  await expect(page.getByRole('button', { name: /bring a note/i })).toBeVisible({
    timeout: 15_000,
  });
  await page.reload();
  await expect(page.getByText('[MOCK] General Follow-up')).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(/Active ·/)).toBeVisible();
});

test('scenario 5: the live sample-note preview renders in the parsed format (synthetic) + never blocks activate (MOCK)', async ({
  page,
}) => {
  test.skip(
    process.env.NOTE_FORMAT_E2E !== '1',
    'Needs an app image built with the note-format mock fixtures. Run with NOTE_FORMAT_E2E=1 against a fresh build.',
  );

  await signupFreshUser(page, 's5p');

  await page.goto('/settings');
  await page.getByLabel('Paste a note').fill(SAMPLE_NOTE);
  await page.getByRole('button', { name: /read my format/i }).click();

  // Review editor reached.
  await expect(
    page.getByRole('button', { name: /save & activate/i }),
  ).toBeVisible({ timeout: 15_000 });

  // The live sample panel is present + CLEARLY LABELLED synthetic, so no doctor
  // mistakes it for a real patient's note.
  await expect(page.getByText('Sample note in your format')).toBeVisible();
  await expect(page.getByText(/demo visit · synthetic/i)).toBeVisible();
  await expect(page.getByText(/not a real patient/i)).toBeVisible();

  // The sample auto-generates after parse and renders a real note (under MOCK,
  // the canned SOAP) — i.e. it actually rendered output, not stuck on loading.
  await expect(
    page.getByText('[MOCK] Patient reports mild tension headache', { exact: false }),
  ).toBeVisible({ timeout: 15_000 });

  // ADDITIVE: the preview never gates the action bar — Save & activate works,
  // and the template persists + activates exactly as without the preview.
  await page.getByRole('button', { name: /save & activate/i }).click();
  await expect(page.getByRole('button', { name: /bring a note/i })).toBeVisible({
    timeout: 15_000,
  });
  await page.reload();
  await expect(page.getByText('[MOCK] General Follow-up')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/Active ·/)).toBeVisible();
});
