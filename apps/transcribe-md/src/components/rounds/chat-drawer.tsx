'use client';

// ============================================================================
// ROUNDS — Screen 2's chat drawer.
// ----------------------------------------------------------------------------
// The chat editor is THE ONLY EDIT PATH — an architecture invariant, not a
// layout preference. The paper is read-only at every breakpoint, so if the
// drawer cannot be opened the note cannot be edited at all. That makes this
// shell load-bearing in a way a drawer usually is not.
//
// IT WRAPS, IT DOES NOT REIMPLEMENT. `ChatEditorPanel` and its
// `chatEditVisitAction` are untouched; this supplies the summoning gesture,
// the focus contract and the tokens. A second chat implementation would be a
// second thing to keep in step with `saveNoteSectionAction`.
//
// THE SHORTCUT IS GUARDED. A bare single-key listener steals the key from any
// text field on the page — including this drawer's own composer, where typing
// "e" would re-trigger the opener. It is ignored when the event target is an
// input, a textarea or contenteditable, and when any modifier is held (so
// Ctrl+E, ⌘E and browser shortcuts still belong to the browser).
//
// FOCUS RETURNS TO THE TRIGGER on close. A drawer that drops focus to the
// document body leaves a keyboard user at the top of the page, which on this
// screen means re-tabbing past the whole note to get back to where they were.
// ============================================================================

import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

export interface RoundsChatDrawerProps {
  /** The existing `<ChatEditorPanel>`, passed through untouched. */
  children: React.ReactNode;
  /**
   * Called just before the drawer closes, so the caller can finish a pending
   * scroll-to-target against a stage the drawer is no longer covering.
   *
   * `onScrollTo` on the review view resolves an element and calls
   * `scrollIntoView`. With the chat OVER the stage, "took you to the E/M gate"
   * can scroll something the doctor cannot see — the exact lie that callback
   * exists to prevent. Close first, then scroll.
   */
  onBeforeClose?: () => void;
  /**
   * Called whenever the drawer opens or closes.
   *
   * The caller needs this to know whether DEFERRING a scroll is safe at all:
   * the only thing that flushes a deferred target is this drawer closing, so a
   * target recorded while it is shut would be stranded and then released on the
   * next unrelated close. Reporting the transition lets the caller scroll
   * immediately instead, and clear anything stale on the way in.
   */
  onOpenChange?: (open: boolean) => void;
  /** Open on mount. Only used by tests and by a deep link to the editor. */
  defaultOpen?: boolean;
}

/** The summoning key. Plain verb in the label; the letter matches it. */
const SHORTCUT_KEY = 'e';

function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName.toLowerCase();
  return tag === 'input' || tag === 'textarea' || el.isContentEditable;
}

export function RoundsChatDrawer({
  children,
  onBeforeClose,
  onOpenChange,
  defaultOpen = false,
}: RoundsChatDrawerProps) {
  const [open, setOpen] = useState(defaultOpen);
  // `document.body` does not exist while this renders on the server. Portalling
  // only after mount keeps the first client render identical to the server's,
  // which is what avoids a hydration mismatch on a route the doctor lands on.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const titleId = useId();

  const close = useCallback(() => {
    onBeforeClose?.();
    setOpen(false);
    onOpenChange?.(false);
    // Return focus to where it came from, on the next frame so the panel is
    // gone before the trigger takes it back.
    requestAnimationFrame(() => triggerRef.current?.focus());
  }, [onBeforeClose, onOpenChange]);

  // Summon. Bound to the document because the doctor may be anywhere on the
  // stage — reading the note, in the gate rail — when they decide to edit.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.defaultPrevented) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      if (e.key === 'Escape' && open) {
        e.preventDefault();
        close();
        return;
      }
      if (open) return;
      if (isTypingTarget(e.target)) return;
      if (e.key.toLowerCase() === SHORTCUT_KEY) {
        e.preventDefault();
        setOpen(true);
        onOpenChange?.(true);
      }
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, close, onOpenChange]);

  // Move focus INTO the panel when it opens, so the next Tab lands in the
  // composer rather than back in the page behind it.
  useEffect(() => {
    if (!open) return;
    const first = panelRef.current?.querySelector<HTMLElement>(
      'textarea, input, button, [tabindex]:not([tabindex="-1"])'
    );
    first?.focus();
  }, [open]);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        data-testid="rounds-chat-trigger"
        className="qm-rounds-chat-trigger"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => {
          setOpen(true);
          onOpenChange?.(true);
        }}
      >
        Edit with chat
        <kbd aria-hidden className="qm-rounds-kbd">
          E
        </kbd>
      </button>

      {/* ⚠️ THE OVERLAY IS PORTALLED TO <body>, AND THAT IS WHAT UNBLOCKS R3.3.
          `rounds-tokens.css` records a pinned action rail built and REVERTED in
          one item. The cause was here, not there: this drawer renders INSIDE
          the rail and its scrim is `position: fixed; inset: 0`. A positioned
          rail becomes an ancestor of both — with `z-index` a stacking context
          that traps them, and with `backdrop-filter` a containing block for
          `position: fixed` descendants outright. Either way
          `rounds-chat-close` reported "visible, enabled and stable" and
          swallowed every click, a failure that names the drawer and never the
          rail. That note ends: "it needs the drawer lifted out of the rail
          first". This is the lift.

          ⚠️ AND IT IS NOT THE PORTAL DEFECT R2 RECORDED. `gate-flow.tsx` warns
          that `createPortal(node, host)` and a bare node are different element
          TYPES to React, so FLIPPING between them remounts and un-clears a
          gate. Nothing flips here: the overlay is already `{open ? … : null}`,
          so it mounts and unmounts on every open/close and holds no state a
          remount could lose. The TRIGGER — which owns the keydown listener and
          the focus return — stays in the rail, unmoved. */}
      {open && mounted
        ? createPortal(
            <>
              <div
                aria-hidden
                data-testid="rounds-chat-scrim"
                className="qm-rounds-chat-scrim"
                onClick={close}
              />
              <div
                ref={panelRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby={titleId}
                data-testid="rounds-chat-drawer"
                className="qm-rounds-chat-drawer"
              >
                <div className="qm-rounds-chat-head">
                  <h2 id={titleId} className="qm-rounds-chat-title">
                    Edit with chat
                  </h2>
                  <button
                    type="button"
                    onClick={close}
                    data-testid="rounds-chat-close"
                    className="qm-rounds-chat-close"
                  >
                    Close
                  </button>
                </div>
                {children}
              </div>
            </>,
            document.body,
          )
        : null}
    </>
  );
}
