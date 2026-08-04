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
  // ⚠️ WAS `page.goto('/settings')`, AND THAT BROKE THE MOMENT THE REQUIRED
  // PACK STARTED BUILDING THE SHIPPED PRODUCT (F-ret.1, 2026-08-04).
  //
  // Under the production flag set the settings shell opens on the `profile`
  // section and every other panel keeps the `hidden` attribute
  // (`settings-sections-c3.tsx:76`). The note-format manager is therefore
  // MOUNTED BUT INVISIBLE, so `getByLabel('Paste a note').fill(...)` waits on
  // an element that is in the DOM and will never become visible — a 15s action
  // timeout that reads as a broken form. It took out eleven tests across four
  // specs at once, and every one of them arrived here.
  //
  // `/settings/note-format` is a real route that renders
  // `<SettingsPage initialSection="note-format" />` — the same shell with that
  // section ACTIVE. It is also how a doctor actually reaches this screen from
  // the Rounds nav, so the test now walks the product's own path rather than a
  // page that happened to render everything at once under the old skin.
  await page.goto('/settings/note-format');

  // ⚠️ ASSERT THE SECTION, NOT A VIEW'S CONTROL. The first version of this
  // waited for `#nf-paste`, which exists only on the ENTRY view — so it threw
  // the moment a caller navigated here with a template already saved, where
  // the manager shows its HOME view instead. That is a probe that is too
  // strict, which is a defect in the probe rather than a finding: it reported
  // "the manager is not visible" about a manager that was perfectly visible.
  //
  // The claim this helper actually makes is "the note-format SECTION is open",
  // and that holds on every view. Whatever renders inside it is the caller's
  // business.
  await expect(
    page.locator('#note-format'),
    'the note-format section did not open on /settings/note-format — it is ' +
      'still `hidden`, so every control inside it would time out invisible',
  ).toBeVisible({ timeout: 15_000 });
}

/** From the ENTRY view (paste box visible), paste a note and parse it, landing
 *  on the review editor. Asserts the editor rendered (Save & activate visible).
 *  A fresh user with no templates opens directly on the entry view; after a
 *  template exists, call bringANote() first to reopen entry. */
export async function parseToReview(page: Page, note: string = SAMPLE_NOTE): Promise<void> {
  await page.getByLabel('Paste a note').fill(note);
  await page.getByRole('button', { name: /read my format/i }).click();

  // ⚠️ THE REVIEW EDITOR IS ONE CLICK DEEPER THAN IT USED TO BE, AND THAT WAS
  // ESTABLISHED BY DRIVING THE PRODUCT, NOT BY READING IT.
  //
  // Flag-OFF, a parse landed straight on `template-review-editor`
  // ("Save & activate", `.qm-tpl-actionbar`). Under the production flag set it
  // lands on the upload-flow CONFIRM step instead — "Looks right — use this
  // format" / "Something's off" (`upload-flow.tsx:320`). Both entry modes were
  // driven on the production-shaped image to settle it:
  //
  //     PASTE  → uploadConfirm=true  reviewEditor=false
  //     UPLOAD → uploadConfirm=true  reviewEditor=false
  //     …then "Something's off" → reviewEditor=TRUE
  //
  // So BOTH components are live and neither is dead code. The confirm step is
  // the accept path; the review editor is the *edit* path, reached by saying
  // the parse is not right. This helper's contract is "land on the review
  // editor", so it takes that door.
  //
  // ⚠️ NO SHARED REGEX OVER BOTH LABELS. A locator matching
  // /(save & activate|looks right)/ would pass on EITHER surface and prove
  // neither — the exact failure the F-ret.1 triage's §5 warns about. Each step
  // is named exactly.
  const confirmStep = page.getByRole('button', { name: /something.s off/i });
  await expect(
    confirmStep,
    'the parse did not reach the confirm step — upload-flow did not render, so ' +
      'the review editor is unreachable',
  ).toBeVisible({ timeout: 30_000 });
  await confirmStep.click();

  await expect(
    page.getByRole('button', { name: /save & activate/i }),
    'clicked "Something\'s off" but the review editor never rendered',
  ).toBeVisible({ timeout: 15_000 });
}

/**
 * Open a template's overflow menu on the manager HOME view, and click one of
 * its actions.
 *
 * ⚠️ THIS EXISTS BECAUSE TWO CAPABILITIES MOVED AND THREE SPECS EACH LOOKED
 * FOR THEM WHERE THEY USED TO BE.
 *
 * Flag-OFF the template card carried `Edit` and `Duplicate <name>` as top-level
 * buttons. Under the production flag set the card shows
 * `Replace · Delete · ⋯`, and the two actions live inside the overflow:
 *
 *     Edit                      → "Advanced editor"
 *     Duplicate <name>          → "Duplicate"
 *
 * Established by DRIVING the production-shaped build, not by reading: the
 * overflow was opened and its contents dumped. Both capabilities are LIVE —
 * they are one click deeper, not gone — so the specs are re-pointed rather
 * than retired.
 *
 * ⚠️ AND THE TRIGGER CANNOT BE FOUND BY ITS TEXT. Its label is `⋯` but its
 * ACCESSIBLE NAME is `More actions for <template name>` (an aria-label), so
 * `getByRole('button', { name: '⋯' })` resolves to nothing — which is exactly
 * how the first probe concluded there was no overflow at all. Query the
 * accessible name.
 */
export async function templateAction(
  page: Page,
  action: 'Advanced editor' | 'Duplicate',
): Promise<void> {
  const trigger = page.getByRole('button', { name: /^more actions for /i });
  await expect(
    trigger.first(),
    'no template overflow menu on the manager home — the card did not render, ' +
      'or its actions moved again',
  ).toBeVisible({ timeout: 15_000 });
  await trigger.first().click();

  // ⚠️ `menuitem`, NOT `button`. The elements are `<button role="menuitem">`
  // (`data-testid="template-row-overflow-menu"`), and an EXPLICIT role
  // overrides the implicit one — so `getByRole('button', …)` can never match
  // them however right the name is. The first version of this helper used
  // `button` and failed with "the overflow opened but has no Advanced editor
  // action" while the menu was open and the item plainly present.
  const item = page.getByRole('menuitem', { name: action, exact: true });
  await expect(
    item.first(),
    `the overflow opened but has no "${action}" action`,
  ).toBeVisible({ timeout: 10_000 });
  await item.first().click();
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
