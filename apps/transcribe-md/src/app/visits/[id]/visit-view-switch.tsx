'use client';

// ============================================================================
// VisitViewSwitch — F8-S2. THE SMALLEST NAVIGATION PRIMITIVE THAT WORKS.
// ----------------------------------------------------------------------------
// Ruling #153(a)/(b): the coding surface lives ON THE VISIT PAGE, reached
// through "a segmented `Note | Coding` control, or an equivalent two-view
// switch, on the visit's paper". NEVER a separate route, and NEVER by
// re-reaching the V2 tab strip — both refused explicitly, so silence here
// cannot be read as permission.
//
// Ruling #153(c): STRUCTURE NOW, STYLE THEN. The Phase-1 redesign restyles
// this later, so a considered visual treatment built today is work thrown
// away. "Minimal" is the ruling, not a shortcut.
//
// ============================================================================
// ⚠️ THE ONE THING THIS FILE EXISTS TO GET RIGHT: IT HIDES, IT NEVER UNMOUNTS.
// ============================================================================
//
// `visit-ready-view.tsx` states the constraint in its own words, at the point
// where the paper is passed to the Rounds stage:
//
//   > The SAME `paper` node passes through the sheet slot. It is never keyed
//   > and never conditionally mounted: `ReviewDocumentView` holds the
//   > in-session E/M confirm in LOCAL STATE, so anything that changed its React
//   > identity would silently re-block Sign and read as a flaky gate.
//
// The obvious implementation of a two-view switch is
// `{view === 'note' ? note : coding}`. That UNMOUNTS the paper the moment the
// doctor looks at coding. Concretely, and this is the walk a real user takes:
//
//   1. doctor confirms the E/M level      -> in-session confirm held in state
//   2. doctor switches to Coding          -> paper unmounts, state destroyed
//   3. doctor switches back to Note       -> paper remounts, confirm GONE
//   4. Sign is blocked again, with no explanation and nothing to click
//
// A clinician would read step 4 as the app losing their work, and there is no
// error, no log line, and nothing for a gate to catch. So both panels stay
// mounted for the lifetime of the visit view and only their VISIBILITY moves.
//
// ⚠️ AND VISIBILITY IS SET TWO WAYS ON PURPOSE, WHICH IS NOT BELT-AND-BRACES:
//
//   · `hidden`             — the semantic half. Removes the panel from the
//                            accessibility tree and from sequential focus, so
//                            a screen reader does not narrate a whole second
//                            document sitting behind the one on screen.
//   · inline `display:none`— the mechanical half. `hidden` is UA-stylesheet
//                            `display:none`, which ANY author rule with higher
//                            specificity silently defeats — and the paper is
//                            wrapped in layout containers that set `display`.
//                            An inline style outranks a stylesheet rule, so the
//                            panel is actually gone rather than merely claimed
//                            to be.
//
// Either alone has a real failure mode: `hidden` alone can leave the panel
// VISIBLE while telling assistive tech it is not there — the worst of the two
// wrong answers.
// ============================================================================

import { useCallback, useId, useRef, useState } from 'react';

export type VisitView = 'note' | 'coding';

const VIEWS: ReadonlyArray<{ id: VisitView; label: string }> = [
  { id: 'note', label: 'Note' },
  { id: 'coding', label: 'Coding' },
];

export interface VisitViewSwitchProps {
  /** The paper. Mounted for the lifetime of this component — see the header. */
  note: React.ReactNode;
  /** The coding surface. Also permanently mounted, for symmetry and because it
   *  holds its own pending-request state while a decision is in flight. */
  coding: React.ReactNode;
}

export function VisitViewSwitch({ note, coding }: VisitViewSwitchProps) {
  const [view, setView] = useState<VisitView>('note');
  const base = useId();
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  const tabId = (v: VisitView) => `${base}-tab-${v}`;
  const panelId = (v: VisitView) => `${base}-panel-${v}`;

  // ⚠️ ARROW KEYS ARE NOT OPTIONAL DECORATION ON `role="tab"`.
  // A screen-reader user who meets a tablist expects Left/Right to move
  // between tabs; the roving `tabIndex` below means Tab alone reaches only the
  // ACTIVE tab, which is the correct pattern and is also what makes the arrow
  // keys load-bearing rather than a nicety. Shipping the role without the
  // behaviour would be a half-implemented pattern that still passes axe —
  // axe checks the roles are coherent, not that the widget works.
  const onKeyDown = useCallback((e: React.KeyboardEvent<HTMLButtonElement>) => {
    const i = VIEWS.findIndex((v) => v.id === (e.currentTarget.dataset.view as VisitView));
    if (i < 0) return;
    let next = i;
    if (e.key === 'ArrowRight') next = (i + 1) % VIEWS.length;
    else if (e.key === 'ArrowLeft') next = (i - 1 + VIEWS.length) % VIEWS.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = VIEWS.length - 1;
    else return;
    e.preventDefault();
    const target = VIEWS[next].id;
    setView(target);
    tabRefs.current[target]?.focus();
  }, []);

  return (
    <div className="w-full" data-testid="visit-view-switch">
      <div
        role="tablist"
        aria-label="Visit views"
        data-testid="visit-view-tablist"
        className="mb-4 inline-flex rounded-lg p-0.5"
        style={{
          background: 'var(--rounds-surface-2)',
          border: '1px solid var(--rounds-line-1)',
        }}
      >
        {VIEWS.map((v) => {
          const active = v.id === view;
          return (
            <button
              key={v.id}
              ref={(el) => {
                tabRefs.current[v.id] = el;
              }}
              type="button"
              role="tab"
              data-view={v.id}
              data-testid={`visit-view-tab-${v.id}`}
              id={tabId(v.id)}
              aria-selected={active}
              aria-controls={panelId(v.id)}
              // Roving tabindex — the inactive tab is reachable by arrow key,
              // not by Tab. This is the pattern, not an accessibility saving.
              tabIndex={active ? 0 : -1}
              onClick={() => setView(v.id)}
              onKeyDown={onKeyDown}
              className="rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors"
              style={{
                background: active ? 'var(--rounds-accent)' : 'transparent',
                // `--rounds-on-accent` for the selected pill and
                // `--rounds-text-2` otherwise. Neither is a state token used
                // as text: the design contract records that `--rounds-em`,
                // `--rounds-ready` and `--rounds-signed` all FAIL AA as text
                // and need their `-text` variants. `--rounds-accent` is a fill
                // here, carrying `--rounds-on-accent` on top of it.
                color: active ? 'var(--rounds-on-accent)' : 'var(--rounds-text-2)',
              }}
            >
              {v.label}
            </button>
          );
        })}
      </div>

      {VIEWS.map((v) => {
        const active = v.id === view;
        return (
          <div
            key={v.id}
            role="tabpanel"
            id={panelId(v.id)}
            aria-labelledby={tabId(v.id)}
            data-testid={`visit-view-panel-${v.id}`}
            // ⚠️ BOTH, AND NEITHER IS REDUNDANT — see the header.
            hidden={!active}
            style={{ display: active ? undefined : 'none' }}
          >
            {v.id === 'note' ? note : coding}
          </div>
        );
      })}
    </div>
  );
}
