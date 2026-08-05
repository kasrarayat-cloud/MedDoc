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
  await closeChatEditor(page);
}

/**
 * Close the chat drawer and wait until it can no longer intercept a click.
 *
 * ⚠️ EVERY CALLER THAT OPENS THE DRAWER MUST CLOSE IT unless the test ends
 * there. The scrim covers the stage, so a caller that types an edit and then
 * reaches for the paper or the action rail will find its target present,
 * enabled, and permanently un-clickable.
 */
export async function closeChatEditor(page: Page): Promise<void> {
  const close = page.getByTestId('rounds-chat-close');
  await expect(close, 'the chat drawer has no close control').toBeVisible();
  await close.click();

  // ⚠️ WAIT ON THE SCRIM, NOT THE EDITOR — and the first version of this waited
  // on the editor, which is why two visit-doc tests still failed with
  // "28 × waiting for element to be visible, enabled and stable" on
  // `rounds-review-sign`. The rail was THERE the whole time; it was covered.
  //
  // `rounds-chat-scrim` is `position: fixed; inset: 0` and `createPortal`'d to
  // <body> (chat-drawer.tsx:165-170), so it overlays the entire stage including
  // the action rail. `chat-editor` hiding says the DRAWER is going; it says
  // nothing about when the scrim has left the hit-testing tree. Anything that
  // clicks the rail immediately afterwards races it.
  //
  // Asserted by COUNT rather than visibility: the node is portalled and
  // conditionally rendered (`{open ? … : null}`), so "gone" means detached, and
  // `toBeHidden` would also pass on a still-present node that merely became
  // invisible mid-transition.
  await expect(
    page.getByTestId('rounds-chat-scrim'),
    'the chat scrim is still in the tree — it covers the action rail and will ' +
      'swallow the next click',
  ).toHaveCount(0, { timeout: 15_000 });
  await expect(page.getByTestId('chat-editor')).toHaveCount(0, { timeout: 15_000 });
}
