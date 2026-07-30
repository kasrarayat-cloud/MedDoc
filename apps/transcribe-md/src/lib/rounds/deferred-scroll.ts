// ============================================================================
// ROUNDS — close the drawer, THEN scroll. Not the other way round.
// ----------------------------------------------------------------------------
// The chat can say "took you to the E/M gate". On the old skin that scroll ran
// against a page the doctor could already see. On Screen 2 the chat is a drawer
// OVER the stage, so a scroll issued while it is open moves something behind an
// overlay: the message is true, the handler ran, and nothing visible happened.
//
// `RoundsChatDrawer.close()` calls `onBeforeClose?.()` and THEN `setOpen(false)`
// (chat-drawer.tsx), so the callback fires while the drawer is still mounted.
// A synchronous scroll there is the lie. The target is therefore recorded on
// the way in and released by the caller's scheduler once React has unmounted
// the overlay.
//
// WHY THIS IS ITS OWN MODULE: a handler that fires and does nothing passes
// every test that only asserts it fired. Isolating the ordering behind an
// injected scroller is what lets a unit test watch it fail — the component
// version cannot be tested without a browser, and the browser test is the one
// that took ~25 minutes to diagnose last time something like this went wrong.
// ============================================================================

export interface DeferredScroll {
  /** Remember where to go. Safe to call repeatedly; the last target wins. */
  record(target: string): void;
  /** Release the recorded target, at most once. No target ⇒ nothing happens. */
  flush(): void;
  /**
   * Throw the recorded target away without scrolling.
   *
   * DEFERRING IS ONLY SAFE WHILE SOMETHING IS GUARANTEED TO FLUSH. The only
   * flusher is the drawer closing, so a target recorded when the drawer is
   * already shut is STRANDED — and worse than stranded, because it survives in
   * the ref and fires on the next unrelated close, scrolling the page for no
   * action the doctor took.
   *
   * That is reachable: `ChatEditorPanel.send` is async and its continuation is
   * not cancelled on unmount, so a reply that lands after the doctor pressed
   * Escape still calls `onScrollTo`. The caller now scrolls immediately in that
   * case; this exists so opening the drawer also clears anything left over —
   * belt and braces, because a silent stale scroll during a clinical review is
   * exactly the "handler that fires and does nothing" class in reverse.
   */
  discard(): void;
  /** For assertions and for deciding whether to defer at all. */
  pending(): string | null;
}

/**
 * @param scrollTo  performs the actual scroll. Injected so a test can watch it.
 * @param schedule  defers to after the overlay is gone. The component passes a
 *                  DOUBLE `requestAnimationFrame`: one frame for React to
 *                  unmount the drawer, and a second because the drawer also
 *                  returns focus to its trigger on a single frame — and the
 *                  browser may scroll that trigger into view. Ours must land
 *                  last or the doctor ends up looking at the button they just
 *                  pressed.
 */
export function createDeferredScroll(
  scrollTo: (target: string) => void,
  schedule: (fn: () => void) => void
): DeferredScroll {
  let target: string | null = null;

  return {
    record(next: string) {
      target = next;
    },
    discard() {
      target = null;
    },
    pending() {
      return target;
    },
    flush() {
      const next = target;
      // Cleared BEFORE scheduling, not inside the callback. A second flush
      // before the frame runs must not queue the same scroll twice — the
      // doctor would see the page jump, settle, and jump again.
      target = null;
      if (next === null) return;
      schedule(() => scrollTo(next));
    },
  };
}
