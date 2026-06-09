// ============================================================================
// E2E helper — drive the "My Note Format" UI (Settings → note-format manager).
// ----------------------------------------------------------------------------
// Thin click helpers shared by the Batch-3 lifecycle specs. They mirror the
// real flow (entry → paste → "Read my format" → review editor), so the specs
// genuinely exercise the manager + the parse/save server actions rather than
// poking state. The parse LLM is mocked (MOCK_AI_CALLS), so a parsed note
// always resolves to the fixture template "[MOCK] General Follow-up" — the
// specs rename it via #nf-name to tell templates apart.
// ============================================================================

import { expect, type Page } from '@playwright/test';

/** A plain note. Content is irrelevant under MOCK (the fixture is returned
 *  regardless), but must be non-empty and free of angle-bracket tokens —
 *  parseNoteToTemplate rejects those as an injection attempt before the
 *  (mocked) LLM call. */
export const SAMPLE_NOTE = [
  'Follow-up visit.',
  'Subjective: doing well, no new complaints.',
  'Objective: vitals stable, exam unremarkable.',
  'Assessment: stable.',
  'Plan: continue current management, return in 3 months.',
].join('\n');

/** Navigate to the note-format manager (Settings, section id=note-format). */
export async function gotoNoteFormat(page: Page): Promise<void> {
  await page.goto('/settings');
}

/** From the ENTRY view (paste box visible), paste a note and parse it, landing
 *  on the review editor. Asserts the editor rendered (Save & activate visible).
 *  A fresh user with no templates opens directly on the entry view; after a
 *  template exists, call bringANote() first to reopen entry. */
export async function parseToReview(page: Page, note: string = SAMPLE_NOTE): Promise<void> {
  await page.getByLabel('Paste a note').fill(note);
  await page.getByRole('button', { name: /read my format/i }).click();
  await expect(page.getByRole('button', { name: /save & activate/i })).toBeVisible({
    timeout: 15_000,
  });
}

/** From the HOME view (template list), open the entry view so a new note can be
 *  brought in. Asserts the paste box is visible. */
export async function bringANote(page: Page): Promise<void> {
  await page.getByRole('button', { name: /bring a note/i }).click();
  await expect(page.getByLabel('Paste a note')).toBeVisible({ timeout: 10_000 });
}

/** Wait for the manager to settle back on the HOME view after a save/activate.
 *  The action's router.refresh() repopulates the server-rendered list
 *  asynchronously (the scenario-5 flake class), so callers that assert the LIST
 *  should reload() after this; DB assertions need only the success signal. */
export async function expectHome(page: Page): Promise<void> {
  await expect(page.getByRole('button', { name: /bring a note/i })).toBeVisible({
    timeout: 15_000,
  });
}
