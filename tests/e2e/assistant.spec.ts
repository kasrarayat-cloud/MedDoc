import { test, expect, type Page } from '@playwright/test';

import { USERS, PATIENTS, TEST_PASSWORD } from '../fixtures/tenancy';

// ============================================================================
// GlobalAIAssistant — voice-only docked widget
// ----------------------------------------------------------------------------
// The assistant is voice-only. Tests cover the parts that don't depend on
// OpenAI / mic permissions:
//   1. Header button opens the docked panel
//   2. Cmd+K toggles globally
//   3. Panel is docked bottom-right (NOT a fullscreen modal) — patient
//      content underneath should remain visible
//
// The voice flow itself (record → transcribe → router → TTS) requires a
// live OpenAI key + mic permission and is verified manually.
// ============================================================================

async function signIn(page: Page, email: string, password: string) {
  await page.goto('/login');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL((url) => {
    const path = new URL(url).pathname;
    return path === '/dashboard' || path === '/system-admin';
  });
}

test.describe('GlobalAIAssistant', () => {
  test('Header button opens the voice panel with the orb visible', async ({ page }) => {
    await signIn(page, USERS.doctorA.email, TEST_PASSWORD);
    await page.goto(`/dashboard/patients/${PATIENTS.a1.id}`);

    await page.getByRole('button', { name: /open ai assistant/i }).click();

    const dialog = page.getByRole('dialog', { name: /ai assistant/i });
    await expect(dialog).toBeVisible();
    // Idle orb shows the "Tap to start" copy.
    await expect(dialog.getByText(/tap to start/i)).toBeVisible();
    // No chat input — assistant is voice-only.
    await expect(dialog.getByPlaceholder(/ask anything/i)).toHaveCount(0);
  });

  test('Cmd+K toggles the assistant globally', async ({ page }) => {
    await signIn(page, USERS.doctorA.email, TEST_PASSWORD);
    await page.goto(`/dashboard/patients/${PATIENTS.a1.id}`);

    await expect(page.getByRole('button', { name: /open ai assistant/i })).toBeVisible();
    await page.keyboard.press('Meta+k');
    const dialog = page.getByRole('dialog', { name: /ai assistant/i });
    await expect(dialog).toBeVisible();

    await page.keyboard.press('Meta+k');
    await expect(dialog).toBeHidden();
  });

  test('Panel is docked, not fullscreen — patient page stays visible behind it', async ({ page }) => {
    await signIn(page, USERS.doctorA.email, TEST_PASSWORD);
    await page.goto(`/dashboard/patients/${PATIENTS.a1.id}`);

    // Pick any patient-page element that's expected to be visible BEFORE
    // opening the assistant.
    const patientName = page.getByRole('heading', {
      name: new RegExp(`${PATIENTS.a1.firstName}.*${PATIENTS.a1.lastName}`, 'i'),
    });
    await expect(patientName).toBeVisible();

    await page.getByRole('button', { name: /open ai assistant/i }).click();
    const dialog = page.getByRole('dialog', { name: /ai assistant/i });
    await expect(dialog).toBeVisible();

    // Patient content should still be visible while the assistant is open
    // (no full-screen backdrop occluding it). The docked panel has a
    // bounded width — the patient-name heading is on a different axis.
    await expect(patientName).toBeVisible();
  });
});
