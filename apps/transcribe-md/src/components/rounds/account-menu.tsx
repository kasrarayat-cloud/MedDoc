'use client';

// ============================================================================
// ROUNDS — the account menu.  Name → Settings · Sign out.
// ----------------------------------------------------------------------------
// ⚠️ THIS EXISTS BECAUSE THE ROUNDS SKIN SHIPPED WITHOUT A WAY TO SIGN OUT.
//
// Measured on the live flag-ON DOM, 2026-08-03:
//
//   /board     signOutControl: 0   accountish: []
//   /patients  signOutControl: 0   accountish: []
//   /settings  signOutControl: 2   (settings/session-panel.tsx:73 and :118)
//
// The legacy shells (`components/ui/top-nav.tsx:298`, `sidebar-c3.tsx:89`) both
// carried an account menu with Sign out in it. R1 gave Rounds its own shell and
// those two became unreachable under the flag — but the bar it replaced them
// with rendered the clinician's name as a plain <span>. So from 2026-08-02 the
// only way out of the product was Settings → Sessions, and nothing said so.
//
// It was never a lockout: Settings is in the nav the whole time. It is a
// REGRESSION IN AFFORDANCE, and on a shared clinical workstation that is not a
// style question — the cost of not finding sign-out is the next clinician
// inheriting the last one's session.
//
// Nobody noticed for two days because the only thing exercising it was
// `tests/e2e/helpers/auth.ts:51`, which clicks `role=button name=/account menu/i`
// — and that helper had been failing since the flip, inside the 21 failures the
// default pack shows against a flag-ON build. A test that has been red long
// enough stops being read as a signal.
//
// WHY A REAL <button> AND NOT <details>/<summary>:
// the Rounds overflow menus use `<details>`, and copying that here was the
// obvious move. It was rejected for two reasons, both of which matter more than
// consistency:
//   1. `<summary>`'s mapping to role=button is a browser/AAM detail. The one
//      consumer that must find this control queries BY ROLE. Betting the
//      sign-out affordance on an implicit mapping is how it goes missing again.
//   2. `<details>` does not close on Escape and does not close on outside
//      click. For a disclosure of extra buttons that is a shrug; for the menu
//      holding "Sign out" on a shared workstation, a menu that stays open
//      behind you is the wrong default.
// The visual anatomy is still the Rounds one — same tokens, same radius, same
// ⋯-less quiet trigger; only the mechanics are explicit.
// ============================================================================

import { useCallback, useEffect, useId, useRef, useState } from 'react';
import Link from 'next/link';
import { signOut } from 'next-auth/react';

export function RoundsAccountMenu({ userName }: { userName: string }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const menuId = useId();

  const close = useCallback((refocus: boolean) => {
    setOpen(false);
    // Focus goes BACK to the trigger on Escape / after an action, or it lands
    // on <body> and the next Tab restarts from the top of the document. That
    // is the standard menu-button contract and the reason this is not a
    // <details>.
    if (refocus) triggerRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close(true);
    };
    const onPointer = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) close(false);
    };
    document.addEventListener('keydown', onKey);
    // `pointerdown`, not `click`: a click that starts inside and ends outside
    // should not count as an outside dismissal.
    document.addEventListener('pointerdown', onPointer);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('pointerdown', onPointer);
    };
  }, [open, close]);

  return (
    <div className="qm-rounds-account" ref={rootRef} data-testid="rounds-account">
      <button
        type="button"
        ref={triggerRef}
        // ⚠️ `helpers/auth.ts` finds this BY ACCESSIBLE NAME. Changing the
        // wording here breaks every authed E2E in the repo, which is a
        // feature: the sign-out control is not allowed to disappear quietly
        // again. Same phrasing the legacy shells used, so the helper is a
        // legitimate consumer rather than a thing patched around the change.
        aria-label={`Account menu for ${userName}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        data-testid="rounds-account-trigger"
        className="qm-rounds-account-trigger"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="qm-rounds-account-who">{userName}</span>
        <span aria-hidden className="qm-rounds-account-caret" />
      </button>

      {open ? (
        <div
          id={menuId}
          role="menu"
          aria-label="Account"
          className="qm-rounds-account-menu"
          data-testid="rounds-account-menu"
        >
          <Link
            href="/settings"
            role="menuitem"
            className="qm-rounds-account-item"
            data-testid="rounds-account-settings"
            onClick={() => close(false)}
          >
            Settings
          </Link>
          <button
            type="button"
            role="menuitem"
            className="qm-rounds-account-item qm-rounds-account-item-exit"
            data-testid="rounds-account-signout"
            onClick={() => {
              // Same call the legacy shells made — `signOut` from
              // next-auth/react, callbackUrl `/login`. The server-side
              // UserSession revoke happens in the `signOut` EVENT
              // (`lib/nextauth.ts`), not here, so this stays a one-liner and
              // the revoke cannot be forgotten by a new caller.
              close(false);
              void signOut({ callbackUrl: '/login' });
            }}
          >
            Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}
