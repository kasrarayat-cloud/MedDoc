// ============================================================================
// The stage composes; it does not render the note, and it does not edit it.
// ----------------------------------------------------------------------------
// Two invariants carry the weight here and both fail SILENTLY if they break:
//
//   - the sheet is a SLOT. If this component ever grew its own note renderer,
//     the read-only guarantee would have a second place to leak from and the
//     existing guard (review-read-only-paper) would not be looking at it.
//   - the vitals slot is RESERVED AND EMPTY. A filled one looks better and is
//     the one thing this screen must never do — L3 has no vitals shape, so
//     anything in there is invented.
// ============================================================================

import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import { RoundsStage } from '../stage';
import { signGates } from '@/lib/sign-gates';
import { toQueuePosition, toStageIdentity } from '@/lib/rounds/stage-data';

const identity = toStageIdentity({
  id: 'v2',
  patientName: 'Aisha Rahman',
  patientExternalId: 'MRN-4471',
  chiefComplaint: 'Chest pain on exertion',
  createdAt: '2026-07-30T09:15:00.000Z',
  audioDurationSec: 363,
});

const QUEUE = ['v1', 'v2', 'v3'];

const clean = signGates({
  specialty: 'primary-care',
  emPendingChange: null,
});

function renderStage(over: Partial<React.ComponentProps<typeof RoundsStage>> = {}) {
  return render(
    <RoundsStage
      status="READY"
      identity={identity}
      queue={toQueuePosition('v2', QUEUE)}
      gates={clean.gates}
      n={clean.n}
      {...over}
    >
      <article data-testid="the-paper">the note</article>
    </RoundsStage>
  );
}

describe('composition', () => {
  it('puts the strip above the sheet and passes the paper through untouched', () => {
    renderStage();
    expect(screen.getByTestId('rounds-pipeline-strip')).toBeTruthy();
    expect(screen.getByTestId('rounds-stage-identity')).toBeTruthy();
    // The slot renders exactly what it was given.
    expect(screen.getByTestId('rounds-sheet')).toContainElement(
      screen.getByTestId('the-paper')
    );
    expect(screen.getByTestId('the-paper').textContent).toBe('the note');
  });

  it('contributes NO main landmark — AppFrame already owns the only one', () => {
    // The sheet wrapper was a `<main>`. Every route is already inside
    // AppFrame's `<main id="main">`, so wiring this to /visits/[id] would have
    // put two main landmarks on the page — an axe violation introduced by the
    // wiring, not by the component, and invisible in a screenshot.
    //
    // It is also load-bearing beyond a11y: the sign bar is `position: sticky`
    // against AppFrame's main, and a nearer landmark ancestor is how a sticky
    // control silently stops sticking.
    //
    // /board avoids the same trap by letting RoundsBoardChrome own the only
    // one. Pinned here so it cannot be "simplified" back to semantic-looking
    // markup.
    const { container } = renderStage();
    expect(container.querySelector('main')).toBeNull();
    // …and the class that carries the layout is still there, so this is a
    // landmark change and not a deletion.
    expect(container.querySelector('.qm-rounds-sheet-wrap')).toBeTruthy();
  });

  it('reports the chat drawer opening and closing, so a deferred scroll is safe', () => {
    // Deferring is only safe while something is guaranteed to flush, and the
    // only flusher is the close. Without this transition the caller cannot
    // tell "the drawer is over the sheet, defer" from "the drawer is shut, a
    // recorded target will never be released" — and the second one strands a
    // scroll that then fires on the next unrelated close.
    const seen: boolean[] = [];
    renderStage({
      chat: <div data-testid="the-chat">chat</div>,
      onChatOpenChange: (open: boolean) => seen.push(open),
    });

    fireEvent.click(screen.getByTestId('rounds-chat-trigger'));
    expect(seen).toEqual([true]);

    fireEvent.click(screen.getByTestId('rounds-chat-close'));
    expect(seen).toEqual([true, false]);
  });

  it('the recorded time is NOT formatted during render — it would mismatch on hydration', () => {
    // `formatLocalDateTime` is toLocale*(undefined, …): the container's
    // timezone on the server, the browser's on hydration. This component is
    // server-rendered, so formatting inline produced a React hydration error on
    // every stage load and a visibly wrong time until the client render landed.
    //
    // <LocalTime> renders a placeholder via getServerSnapshot and formats only
    // on the client. Asserting the <time dateTime=…> wrapper is how this stays
    // fixed: a revert to inline formatting produces a bare string with no
    // element to find.
    const { container } = renderStage();
    const cell = screen.getByTestId('rounds-stage-recorded');
    const time = cell.querySelector('time');
    expect(time).not.toBeNull();
    expect(time!.getAttribute('dateTime')).toBe(identity.recordedAtIso);
    expect(container).toBeTruthy();
  });

  it('the sheet keeps the 820px paper class — a parity invariant', () => {
    renderStage();
    expect(screen.getByTestId('rounds-sheet').className).toContain('rounds-paper');
  });

  it('renders NO note content of its own', () => {
    // If the stage ever renders the note itself there are two renderers and
    // only one is guarded.
    const { container } = render(
      <RoundsStage
        status="READY"
        identity={identity}
        queue={toQueuePosition('v2', QUEUE)}
        gates={clean.gates}
        n={clean.n}
      >
        {null}
      </RoundsStage>
    );
    expect(container.querySelector('[data-testid="rounds-sheet"]')!.textContent).toBe('');
  });
});

describe('the vitals slot is reserved and EMPTY', () => {
  it('exists', () => {
    renderStage();
    expect(screen.getByTestId('rounds-vitals-slot')).toBeTruthy();
  });

  it('contains nothing — parked, never faked', () => {
    renderStage();
    const slot = screen.getByTestId('rounds-vitals-slot');
    expect(slot.textContent).toBe('');
    expect(slot.children).toHaveLength(0);
    expect(slot.getAttribute('data-parked')).toBe('true');
  });
});

describe('THE CRITICAL BAND IS GONE — owner ruling #109', () => {
  // Replaces three tests that asserted the band appeared, singularised, and
  // stayed away at zero. The band pointed at "Gate 1", which no longer exists,
  // so the POSITIVE control is now that nothing draws it under any input.
  it('never draws, and no stage text names an interaction', () => {
    renderStage({});
    expect(screen.queryByTestId('rounds-critical-band')).toBeNull();
    expect(document.body.textContent).not.toMatch(/critical interaction/i);
    // …and it does not merely fail to mention Gate 1 — there is no Gate 1.
    expect(document.body.textContent).not.toMatch(/Gate 1/);
  });
});

describe('the action rail', () => {
  it('the primary carries the same count as the padlock', () => {
    const blocked = signGates({
      specialty: 'primary-care',
      emPendingChange: { from: '99213', to: '99214', cause: 'note_edited', at: '2026-07-30T00:00:00Z' },
    });
    renderStage({ gates: blocked.gates, n: blocked.n });
    const btn = screen.getByTestId('rounds-review-sign');
    expect(btn.getAttribute('data-blockers')).toBe(String(blocked.n));
    expect(btn.textContent).toContain(String(blocked.n));
    // and the strip agrees, because both were handed the same n
    expect(
      screen.getByTestId('rounds-strip-signed').getAttribute('data-blockers')
    ).toBe(String(blocked.n));
  });

  it('drops the count when there is nothing blocking', () => {
    renderStage({ n: 0 });
    expect(screen.getByTestId('rounds-review-sign').textContent).toBe(
      'Review & sign'
    );
  });

  it('NEGATIVE CONTROL — a different n renders a different label', () => {
    const { unmount } = renderStage({ n: 1 });
    expect(screen.getByTestId('rounds-review-sign').textContent).toContain(
      '1 blocker'
    );
    unmount();
    renderStage({ n: 4 });
    expect(screen.getByTestId('rounds-review-sign').textContent).toContain(
      '4 blockers'
    );
  });

  it('is a BUTTON, never a form — the sign route is a JSON API', () => {
    // A <form action> against a JSON route navigates the browser to the raw
    // response. The click looks like it worked and the screen vanishes.
    renderStage();
    const btn = screen.getByTestId('rounds-review-sign');
    expect(btn.tagName).toBe('BUTTON');
    expect(btn.getAttribute('type')).toBe('button');
    expect(btn.closest('form')).toBeNull();
  });

  it('a signed visit cannot be signed again', () => {
    renderStage({ signedAt: '2026-07-30T10:00:00Z', status: 'SIGNED' });
    expect(
      (screen.getByTestId('rounds-review-sign') as HTMLButtonElement).disabled
    ).toBe(true);
    expect(screen.queryByTestId('rounds-skip')).toBeNull();
  });

  it('Skip appears only when the caller supplies one', () => {
    renderStage({ onSkip: vi.fn() });
    expect(screen.getByTestId('rounds-skip')).toBeTruthy();
  });
});

describe('the next-up peek', () => {
  it('offers both neighbours in the middle of the queue', () => {
    renderStage();
    expect(screen.getByTestId('rounds-peek-prev').getAttribute('href')).toBe(
      '/visits/v1'
    );
    expect(screen.getByTestId('rounds-peek-next').getAttribute('href')).toBe(
      '/visits/v3'
    );
    expect(screen.getByTestId('rounds-queue-position').textContent).toContain(
      '2 of 3 to review'
    );
  });

  it('offers no next at the end of the queue', () => {
    renderStage({ queue: toQueuePosition('v3', QUEUE) });
    expect(screen.queryByTestId('rounds-peek-next')).toBeNull();
    expect(screen.getByTestId('rounds-peek-prev')).toBeTruthy();
  });

  it('a visit outside the queue shows no position at all', () => {
    renderStage({ queue: toQueuePosition('gone', QUEUE) });
    expect(screen.queryByTestId('rounds-queue-position')).toBeNull();
  });

  it('marks the current dot, and only that one', () => {
    renderStage();
    const dots = Array.from(
      screen.getByTestId('rounds-queue-position').querySelectorAll('.qm-rounds-queue-dot')
    );
    expect(dots).toHaveLength(3);
    expect(dots.map((d) => d.getAttribute('data-current'))).toEqual([
      'false',
      'true',
      'false',
    ]);
  });
});

describe('the chat drawer is the only edit path', () => {
  it('is closed until summoned', () => {
    renderStage({ chat: <div data-testid="the-chat">chat</div> });
    expect(screen.queryByTestId('rounds-chat-drawer')).toBeNull();
    expect(screen.getByTestId('rounds-chat-trigger')).toBeTruthy();
  });

  it('the button opens it', () => {
    renderStage({ chat: <div data-testid="the-chat">chat</div> });
    fireEvent.click(screen.getByTestId('rounds-chat-trigger'));
    expect(screen.getByTestId('rounds-chat-drawer')).toBeTruthy();
    expect(screen.getByTestId('the-chat')).toBeTruthy();
  });

  it('the keyboard shortcut opens it', () => {
    renderStage({ chat: <div data-testid="the-chat">chat</div> });
    fireEvent.keyDown(document, { key: 'e' });
    expect(screen.getByTestId('rounds-chat-drawer')).toBeTruthy();
  });

  it('the shortcut is IGNORED while typing — it would steal the composer’s key', () => {
    renderStage({ chat: <textarea data-testid="composer" /> });
    const input = document.createElement('input');
    document.body.appendChild(input);
    fireEvent.keyDown(input, { key: 'e' });
    expect(screen.queryByTestId('rounds-chat-drawer')).toBeNull();
    input.remove();
  });

  it('a modifier belongs to the browser, not to us', () => {
    renderStage({ chat: <div>chat</div> });
    fireEvent.keyDown(document, { key: 'e', metaKey: true });
    fireEvent.keyDown(document, { key: 'e', ctrlKey: true });
    expect(screen.queryByTestId('rounds-chat-drawer')).toBeNull();
  });

  it('Escape closes it', () => {
    renderStage({ chat: <div>chat</div> });
    fireEvent.click(screen.getByTestId('rounds-chat-trigger'));
    expect(screen.getByTestId('rounds-chat-drawer')).toBeTruthy();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByTestId('rounds-chat-drawer')).toBeNull();
  });

  it('is a real dialog to a screen reader', () => {
    renderStage({ chat: <div>chat</div> });
    fireEvent.click(screen.getByTestId('rounds-chat-trigger'));
    const d = screen.getByTestId('rounds-chat-drawer');
    expect(d.getAttribute('role')).toBe('dialog');
    expect(d.getAttribute('aria-modal')).toBe('true');
    expect(d.getAttribute('aria-labelledby')).toBeTruthy();
  });

  it('the trigger reports its state', () => {
    renderStage({ chat: <div>chat</div> });
    const t = screen.getByTestId('rounds-chat-trigger');
    expect(t.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(t);
    expect(screen.getByTestId('rounds-chat-trigger').getAttribute('aria-expanded')).toBe(
      'true'
    );
  });

  it('no chat means no trigger — not a dead button', () => {
    renderStage();
    expect(screen.queryByTestId('rounds-chat-trigger')).toBeNull();
  });

  it('onChatBeforeClose reaches the drawer and fires BEFORE it closes', () => {
    // The seam exists so the route wiring can finish a scroll against a stage
    // the drawer is no longer covering. If it never fires, "took you to the
    // E/M gate" scrolls something the doctor cannot see — and the handler
    // looks wired while doing nothing, which is worse than not having one.
    const spy = vi.fn(() => {
      expect(screen.queryByTestId('rounds-chat-drawer')).not.toBeNull();
    });
    renderStage({ chat: <div>chat</div>, onChatBeforeClose: spy });
    fireEvent.click(screen.getByTestId('rounds-chat-trigger'));
    fireEvent.click(screen.getByTestId('rounds-chat-close'));
    expect(spy).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId('rounds-chat-drawer')).toBeNull();
  });

  it('NEGATIVE CONTROL — without the prop, closing still works and calls nothing', () => {
    renderStage({ chat: <div>chat</div> });
    fireEvent.click(screen.getByTestId('rounds-chat-trigger'));
    fireEvent.click(screen.getByTestId('rounds-chat-close'));
    expect(screen.queryByTestId('rounds-chat-drawer')).toBeNull();
  });

  it('the scrim and Escape close through the same path', () => {
    const spy = vi.fn();
    renderStage({ chat: <div>chat</div>, onChatBeforeClose: spy });
    fireEvent.click(screen.getByTestId('rounds-chat-trigger'));
    fireEvent.click(screen.getByTestId('rounds-chat-scrim'));
    expect(spy).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByTestId('rounds-chat-trigger'));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(spy).toHaveBeenCalledTimes(2);
  });
});

describe('the paper stays read-only', () => {
  it('the stage contributes no edit affordance of its own', () => {
    const { container } = renderStage({ chat: <div>chat</div> });
    for (const id of [
      'section-edit-',
      'section-textarea-',
      'section-save-',
    ]) {
      expect(container.querySelector(`[data-testid^="${id}"]`)).toBeNull();
    }
    // The only textarea reachable from this screen lives inside the drawer.
    expect(container.querySelector('.qm-rounds-sheet textarea')).toBeNull();
    expect(container.querySelector('.qm-rounds-sheet [contenteditable]')).toBeNull();
  });
});
