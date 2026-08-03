'use client';

// ============================================================================
// ROUNDS — "New visit", the board's primary action.
// ----------------------------------------------------------------------------
// R2. The board had no way to start a visit. `/patients` had one, `/visits` had
// one, a patient's own page had two — and the screen a doctor actually lands on
// had none, so beginning the day meant navigating somewhere else first.
//
// THE LABEL IS "New visit" AND THAT IS NOT A STYLE CHOICE. SPEC.md's copy
// register: "actions keep their names end-to-end". `patients-roster.tsx:81`,
// `visits/page.tsx:181` and `patients/[id]/page.tsx:318` all say New visit and
// all point at `/visits/new`; a board button reading "Start a visit" or
// "Record" would be a fourth name for one action. The board's EMPTY state said
// exactly that ("Start a visit") and now says this.
//
// ⚠️ THE SHORTCUT IS REGISTERED BY EXACTLY ONE INSTANCE, and the prop exists
// only to enforce that. The board renders this twice — top bar and empty state
// — and two document-level listeners for one key means two navigations queued
// from one press. `RoundsChatDrawer` avoids the same trap by owning its own
// key; this one is opt-in per mount instead, because the second mount is a
// sibling rather than a child and cannot be detected from here.
//
// ⚠️ `isTypingTarget` IS LOAD-BEARING, NOT DEFENSIVE POLISH. The board's filter
// strip carries a real `<input>` search box (board-chrome.tsx). Without this
// guard, typing a patient's name containing "n" navigates the doctor off the
// board mid-search and loses the query. Copied deliberately from
// `chat-drawer.tsx:59-63` rather than re-derived, so the two behave the same.
// ============================================================================

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

/** Where a visit begins. The patient is picked or created inside that flow
 *  (`visits/new/patient-picker.tsx` — inline create posts `/api/patients`),
 *  which is why this is a plain link and not a modal of its own. */
export const NEW_VISIT_HREF = '/visits/new';

/** The summoning key. Plain verb in the label; the letter matches it. */
const SHORTCUT_KEY = 'n';

function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName.toLowerCase();
  return tag === 'input' || tag === 'textarea' || el.isContentEditable;
}

export interface RoundsNewVisitCtaProps {
  /**
   * Start the visit FOR THIS PATIENT — `/visits/new?patientId=…`, which the
   * route already honours by preselecting them and landing the doctor on
   * specialty/capture instead of "Who's this visit for?".
   *
   * ⚠️ THIS PROP EXISTS BECAUSE ITS ABSENCE WAS A REGRESSION I SHIPPED. R3.2
   * replaced `/patients/[id]`'s header link — which carried
   * `?patientId=${patient.id}` — with this shared component, and the component
   * hardcoded a bare `/visits/new`. The button therefore dropped the patient
   * and landed the doctor in create-a-patient, on the one page where the
   * patient is already known. The empty-state link on the same page still
   * carried the param, which is why only one of the two misbehaved.
   *
   * Optional, and omitted is correct on the board, the roster and `/visits` —
   * there is no patient in scope on any of them.
   */
  patientId?: string;
  /**
   * `bar` — the compact primary in the top bar.
   * `empty` — the larger invitation in the board's empty state.
   *
   * Same label, same href, same testid prefix; only the chrome differs.
   */
  variant?: 'bar' | 'empty';
  /** Register the document-level `n` shortcut. EXACTLY ONE mount may pass this. */
  withShortcut?: boolean;
}

export function RoundsNewVisitCta({
  variant = 'bar',
  withShortcut = false,
  patientId,
}: RoundsNewVisitCtaProps) {
  const router = useRouter();
  // One destination, computed once, so the link and the keyboard shortcut
  // cannot disagree about where the action goes.
  const href = patientId
    ? `${NEW_VISIT_HREF}?patientId=${encodeURIComponent(patientId)}`
    : NEW_VISIT_HREF;

  useEffect(() => {
    if (!withShortcut) return;
    function onKey(e: KeyboardEvent) {
      if (e.defaultPrevented) return;
      // Never steal a browser or OS combination — ⌘N / Ctrl-N open a window.
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (isTypingTarget(e.target)) return;
      if (e.key.toLowerCase() !== SHORTCUT_KEY) return;
      e.preventDefault();
      router.push(href);
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [withShortcut, router, href]);

  return (
    <Link
      href={href}
      data-testid={`rounds-new-visit-${variant}`}
      data-shortcut={withShortcut ? SHORTCUT_KEY : undefined}
      /* ⚠️ WRITTEN OUT, NOT INTERPOLATED, AND A GUARD MADE ME DO IT.
         This was `` `qm-rounds-newvisit qm-rounds-newvisit--${variant}` ``,
         which is shorter and invisible: `gate-c1d-auth`'s orphan check greps
         source for each DECLARED Rounds class as a literal, so both variant
         classes read as "declared in CSS, applied by nothing" and the guard
         reddened. It was right to. A class name assembled at runtime cannot be
         found by grep, which means the next person tracing a rule to its caller
         finds nothing and concludes the rule is dead — exactly how the
         `--color-linear-sage` census went stale behind a regex that could not
         see the shapes in the file. The cure is to make the code legible to the
         matcher, not to teach the matcher about template literals. */
      className={
        variant === 'bar'
          ? 'qm-rounds-newvisit qm-rounds-newvisit--bar'
          : 'qm-rounds-newvisit qm-rounds-newvisit--empty'
      }
    >
      {/* Decorative. The accessible name must stay exactly "New visit" so it
          matches the other three call sites for anyone navigating by label. */}
      <span aria-hidden className="qm-rounds-newvisit-plus">
        +
      </span>
      New visit
      {withShortcut ? (
        // Announced to nobody: a visual hint for a key that sighted mouse users
        // do not need and screen-reader users would hear as noise mid-label.
        // The listener above is the thing that makes it true, and it is
        // registered in the same component — the rail's orphaned "[E]" hint,
        // advertising a shortcut with no handler behind it, is the failure this
        // avoids by construction.
        <kbd aria-hidden className="qm-rounds-newvisit-kbd">
          {SHORTCUT_KEY.toUpperCase()}
        </kbd>
      ) : null}
    </Link>
  );
}
