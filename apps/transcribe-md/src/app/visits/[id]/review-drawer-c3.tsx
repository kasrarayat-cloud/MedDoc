'use client';

// ============================================================================
// ReviewDrawerC3 — the "calm drawer" shell for the C3 SOAP-review skin.
// ----------------------------------------------------------------------------
// Renders ONE "N to review" pill in the chrome + a dismissible right drawer
// that holds every SECONDARY surface (AI suggestions, Rx safety, Codes,
// Extras, Input). The primary SOAP note + the single real Sign action stay
// in the main column (SoapEditor), untouched.
//
// This component is PRESENTATION ONLY. It renders whatever children the
// caller passes — the real, gate-bearing tab components (SuggestionsLane,
// RxTab, CodesTab, ExtrasTab, TranscriptTab) are passed in verbatim by
// visit-ready-view.tsx and keep all their own behavior. The drawer never
// touches sign / Rx-override / E/M / audit logic; it only opens and closes.
//
// A11y mirrors the /concepts/soap/c3-final mockup: role="dialog" +
// aria-modal, focus moves to Close on open, Tab is trapped, Esc closes and
// returns focus to the pill, the backdrop scrim closes on click, and the
// main content is inert while open (handled by the caller via the
// data-drawer-open hook + CSS).
// ============================================================================

import { useEffect, useId, useRef, useState, type ReactNode } from 'react';

export function ReviewDrawerC3({
  count,
  blockerHint,
  children,
}: {
  /** Number of attention items across the secondary surfaces. 0 → calm
   *  "Nothing to review" pill. */
  count: number;
  /** Optional header line — e.g. "All clear — ready to sign" or a
   *  "resolve before signing" nudge. Purely informational; the actual
   *  sign gating is enforced server-side + in the reused child components. */
  blockerHint?: ReactNode;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const drawerRef = useRef<HTMLElement>(null);
  const pillRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const labelId = useId();

  const close = () => {
    setOpen(false);
    // Return focus to the pill on the next frame (after React re-renders).
    requestAnimationFrame(() => pillRef.current?.focus());
  };

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        close();
        return;
      }
      if (e.key !== 'Tab' || !drawerRef.current) return;
      const nodes = drawerRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, textarea, select, [tabindex]:not([tabindex="-1"])'
      );
      const list = Array.from(nodes).filter(
        (el) => !(el as HTMLButtonElement).disabled && el.offsetParent !== null
      );
      if (list.length === 0) return;
      const first = list[0];
      const last = list[list.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
    };
    // close is stable enough here; deps intentionally minimal.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const pillLabel = count > 0 ? `${count} to review` : 'Nothing to review';

  return (
    <>
      <button
        ref={pillRef}
        type="button"
        className={`qm-c3-rev-pill ${count > 0 ? 'has' : 'clear'} qm-tap-44`}
        onClick={() => setOpen(true)}
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        {pillLabel}
      </button>

      {open && (
        <div className="qm-c3-rev-scrim" onClick={close} aria-hidden />
      )}
      <aside
        ref={drawerRef}
        className={`qm-c3-rev-drawer ${open ? 'open' : ''}`}
        role="dialog"
        aria-modal={open || undefined}
        aria-labelledby={labelId}
        inert={!open ? true : undefined}
      >
        <div className="qm-c3-rev-drawer-head">
          <div className="qm-c3-rev-drawer-title">
            <span id={labelId} className="qm-c3-rev-drawer-h">
              Review before signing
            </span>
            {blockerHint && (
              <span className="qm-c3-rev-drawer-hint">{blockerHint}</span>
            )}
          </div>
          <button
            ref={closeRef}
            type="button"
            className="qm-c3-rev-close qm-tap-44"
            onClick={close}
            aria-label="Close review panel"
          >
            Close ✕
          </button>
        </div>
        <div className="qm-c3-rev-drawer-body">{children}</div>
      </aside>
    </>
  );
}
