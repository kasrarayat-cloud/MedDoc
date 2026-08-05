// ============================================================================
// Reaching the chat editor on the shipped surface.
// ----------------------------------------------------------------------------
// ⚠️ THE CHAT EDITOR IS BEHIND A DRAWER. Under Rounds the stage carries a
// trigger (`rounds-chat-trigger`) on the action rail; the editor itself is not
// in the DOM until the drawer opens. Any spec that does
//
//     await expect(page.getByTestId('chat-editor')).toBeVisible();
//
// on a freshly-loaded visit page is asserting against a legacy rendering where
// the editor sat inline. That is how `visit-document.spec.ts` failed five tests
// once F-ret.3 removed the skin flag and its pack stopped building the old skin.
//
// ⚠️ WHY A HELPER AND NOT THREE INLINE COPIES. This is the fourth site in the
// tree that needs the same three lines (`30-note-edit-persistence` has its own,
// and `visit-document` had three). A per-caller list is kept complete by hand,
// and hand-kept lists are wrong eventually — the R3.4 lesson, which this program
// has now re-learned in four different costumes.
// ============================================================================

import { expect, type Page } from '@playwright/test';

/**
 * Open the chat drawer and wait for the editor.
 *
 * Leaves the drawer OPEN — callers that go on to type into it need it that way.
 * Use `assertChatReachable` instead when the claim is only that the affordance
 * exists, because an open drawer overlays the stage and can swallow clicks a
 * later assertion depends on.
 */
export async function openChatEditor(page: Page): Promise<void> {
  const trigger = page.getByTestId('rounds-chat-trigger');
  await expect(
    trigger,
    'no chat trigger on the stage — the note has no edit path at all',
  ).toBeVisible({ timeout: 30_000 });
  await trigger.click();
  await expect(
    page.getByTestId('chat-editor'),
    'the chat drawer opened but carries no editor',
  ).toBeVisible({ timeout: 30_000 });
}

/**
 * Prove the chat edit path is reachable, then put the page back as it was.
 *
 * ⚠️ THIS OPENS THE DRAWER RATHER THAN JUST CHECKING THE TRIGGER, deliberately.
 * A visible trigger proves the door; it does not prove there is a room behind
 * it. The claim these call sites make — "chat is one of the things a doctor can
 * act on here" — is about the editor, so the editor is what gets asserted.
 *
 * It CLOSES afterwards because the drawer's scrim is a `<body>` portal that
 * overlays the stage, and the assertions that follow at these sites reach for
 * the gate stack and the signature.
 */
export async function assertChatReachable(page: Page): Promise<void> {
  await openChatEditor(page);
  const close = page.getByTestId('rounds-chat-close');
  await expect(close, 'the chat drawer has no close control').toBeVisible();
  await close.click();
  await expect(page.getByTestId('chat-editor')).toBeHidden({ timeout: 15_000 });
}
