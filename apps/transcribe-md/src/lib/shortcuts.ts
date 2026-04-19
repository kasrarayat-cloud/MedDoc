'use client';

import { useEffect, useRef } from 'react';

export interface ShortcutHandler {
  /** The key to listen for, e.g. 'k', 'n', 'Escape', '/'. Case-insensitive. */
  key: string;
  /** Require the command/control modifier (⌘ on macOS, Ctrl elsewhere). */
  meta?: boolean;
  /** Require shift to be held. */
  shift?: boolean;
  onFire: (e: KeyboardEvent) => void;
}

/**
 * Returns true when focus is currently inside an element where the user
 * is actively typing. We DON'T want shortcuts like "n" or "/" to fire
 * while they're filling in a name field or a password.
 */
function focusInTypingTarget(): boolean {
  if (typeof document === 'undefined') return false;
  const el = document.activeElement;
  if (!el) return false;
  const tag = el.tagName.toLowerCase();
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
  if ((el as HTMLElement).isContentEditable) return true;
  // Radix Select's trigger is role=combobox; the trigger itself is fine
  // to receive plain keys (Radix handles arrow nav internally) so we
  // don't treat combobox as typing.
  return false;
}

/**
 * Register one keyboard shortcut for the lifetime of the component.
 * Fires on keydown, respects typing fields, swallows the event only
 * when it matches (so unhandled keys keep their browser defaults).
 *
 * Usage:
 *   useShortcut({ key: 'k', meta: true, onFire: () => setOpen(true) });
 */
export function useShortcut(handler: ShortcutHandler) {
  // Stash the latest handler in a ref so the effect can stay subscribed
  // once per mount — avoids re-registering every render when the
  // onFire closure changes. The ref update is done in a passive effect
  // (React 19's recommended pattern for "latest value" refs; writing
  // during render trips the react-hooks/refs lint).
  const ref = useRef(handler);
  useEffect(() => {
    ref.current = handler;
  });

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const { key, meta, shift, onFire } = ref.current;
      if (e.key.toLowerCase() !== key.toLowerCase()) return;
      const metaPressed = e.metaKey || e.ctrlKey;
      if (meta && !metaPressed) return;
      if (!meta && metaPressed) return;
      if (shift && !e.shiftKey) return;
      if (!shift && e.shiftKey) return;
      // Don't hijack typing unless the shortcut is explicitly modifier-
      // scoped (Cmd+K should still work when focused in an input).
      if (!meta && focusInTypingTarget()) return;
      e.preventDefault();
      onFire(e);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);
}

/** Convenience: register several shortcuts in one call. The subscription
 *  survives re-renders via a latest-handlers ref; the effect re-binds
 *  only when the shortcut *shape* changes (detected via sig). */
export function useShortcuts(handlers: ShortcutHandler[]) {
  const sig = handlers
    .map((h) => `${h.meta ? 'M-' : ''}${h.shift ? 'S-' : ''}${h.key}`)
    .join(',');
  const ref = useRef(handlers);
  useEffect(() => {
    ref.current = handlers;
  });

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      for (const h of ref.current) {
        if (e.key.toLowerCase() !== h.key.toLowerCase()) continue;
        const metaPressed = e.metaKey || e.ctrlKey;
        if (h.meta && !metaPressed) continue;
        if (!h.meta && metaPressed) continue;
        if (h.shift && !e.shiftKey) continue;
        if (!h.shift && e.shiftKey) continue;
        if (!h.meta && focusInTypingTarget()) continue;
        e.preventDefault();
        h.onFire(e);
        return;
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [sig]);
}

/** Platform-aware formatted string for the command modifier — "⌘K" on
 *  macOS, "Ctrl+K" everywhere else. Used in the palette footer + Navbar
 *  search-hint button. */
export function formatCommandKey(key: string): string {
  if (typeof navigator === 'undefined') return `Ctrl+${key.toUpperCase()}`;
  const isMac = /Mac|iPhone|iPad|iPod/.test(navigator.platform);
  return isMac ? `⌘${key.toUpperCase()}` : `Ctrl+${key.toUpperCase()}`;
}
