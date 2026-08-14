// ============================================================================
// Screen 4 — what it must never claim.
// ----------------------------------------------------------------------------
// The safety trail's whole promise is "only what applied", so most of these
// assertions are about ABSENCE: a card that is not rendered is the screen saying
// that step did not happen. The failure mode this guards is the comfortable one
// — inferring that because a visit is signed, its gates must have been cleared,
// and drawing a green tick on a step nothing recorded.
// ============================================================================

import { readFileSync } from 'node:fs';

import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import type { StageIdentity, StageQueuePosition } from '@/lib/rounds/stage-data';
import type { SignedTrail } from '@/lib/rounds/stage-view-model';
import { RoundsSigned } from '../signed';

const IDENTITY: StageIdentity = {
  visitId: 'v1',
  patientLabel: 'A Patient',
  mrn: 'MRN-1',
  ageYears: 54,
  dob: '1972-03-14',
  reason: 'Asthma review',
  recordedAtIso: '2026-07-30T10:00:00.000Z',
  durationLabel: '6m 03s',
};

const EMPTY_QUEUE: StageQueuePosition = {
  position: null,
  total: 0,
  nextVisitId: null,
  prevVisitId: null,
  headVisitId: null,
};

const NO_TRAIL: SignedTrail = {
  emAcknowledgedAt: null,
};

function renderSigned(
  over: Partial<React.ComponentProps<typeof RoundsSigned>> = {}
) {
  return render(
    <RoundsSigned
      status="SIGNED"
      signedAt="2026-07-30T12:00:00.000Z"
      identity={IDENTITY}
      queue={EMPTY_QUEUE}
      trail={NO_TRAIL}
      signedByLabel="Dr Example"
      emCode="99213"
      {...over}
    >
      <article data-testid="the-signed-paper">the note</article>
    </RoundsSigned>
  );
}

describe('the safety trail shows ONLY what applied', () => {
  it('renders NO trail at all when nothing was recorded', () => {
    // Not an empty box, not "no safety steps" — nothing. A visit with no level
    // change had no safety step to log, and the screen must not imply it looked
    // and found none.
    renderSigned();
    expect(screen.queryByTestId('rounds-signed-trail')).toBeNull();
    expect(screen.queryByTestId('rounds-signed-trail-em')).toBeNull();
  });

  it('renders the E/M card ONLY from a real acknowledgement timestamp', () => {
    renderSigned({
      trail: { emAcknowledgedAt: '2026-07-30T11:59:00.000Z' },
    });
    expect(screen.getByTestId('rounds-signed-trail-em')).toBeTruthy();
  });

  // ⚠️ POSITIVE CONTROL FOR THE DELETION — owner ruling #109. Two tests that
  // asserted the Rx trail card RENDERED (from a real override count, and
  // singularised) were removed; this one asserts it can no longer render at
  // all. Deleting the positive assertions alone would leave nothing watching a
  // half-applied removal.
  it('NEVER renders an Rx card — the surface that produced the rows is gone', () => {
    renderSigned({ trail: { emAcknowledgedAt: '2026-07-30T11:59:00.000Z' } });
    expect(screen.queryByTestId('rounds-signed-trail-rx')).toBeNull();
    expect(document.body.textContent).not.toMatch(/interaction/i);
  });

  it('NEVER renders an attestation card — nothing persists it', () => {
    // Attestation has no column, no audit action, and no field in the sign body
    // schema; `signGates` marks it serverEnforced:false for that reason, and the
    // only signal is a useState that dies with the page. A tick here would
    // re-assert on every reload a fact nothing recorded — and would contradict
    // Screen 3, which tells the doctor the server does not check it.
    //
    // Asserted against BOTH trail shapes, so this cannot pass merely because the
    // trail happened to be empty.
    for (const trail of [
      NO_TRAIL,
      { emAcknowledgedAt: '2026-07-30T11:00:00.000Z' },
    ]) {
      const { unmount } = renderSigned({ trail });
      expect(screen.queryByTestId('rounds-signed-trail-attestation')).toBeNull();
      expect(document.body.textContent).not.toMatch(/attest/i);
      unmount();
    }
  });

  it('NEGATIVE CONTROL — the trail CAN render, so the absences above mean something', () => {
    renderSigned({
      trail: { emAcknowledgedAt: '2026-07-30T11:00:00.000Z' },
    });
    expect(screen.getByTestId('rounds-signed-trail').children).toHaveLength(1);
  });
});

describe('the lock banner', () => {
  it('names the patient, the signer and the moment', () => {
    renderSigned();
    expect(screen.getByTestId('rounds-signed-patient').textContent).toBe('A Patient');
    expect(screen.getByTestId('rounds-signed-by').textContent).toBe('Dr Example');
    expect(screen.getByTestId('rounds-signed-at').getAttribute('dateTime')).toBe(
      '2026-07-30T12:00:00.000Z'
    );
  });

  it('omits the level ENTIRELY when E/M does not apply', () => {
    // An imaging report has no office documentation level. Absent means absent —
    // not a row reading "n/a", not a blank slot. Rendering the label with no
    // value is how a surface starts implying the value is missing rather than
    // inapplicable.
    renderSigned({ emCode: null });
    expect(screen.queryByTestId('rounds-signed-em')).toBeNull();
    expect(document.body.textContent).not.toMatch(/documentation level/i);
  });

  it('NEGATIVE CONTROL — it renders the level when one applies', () => {
    renderSigned({ emCode: '99214' });
    expect(screen.getByTestId('rounds-signed-em').textContent).toBe('99214');
  });
});

describe('the paper and the footer', () => {
  it('passes the signed paper through untouched, and renders no note of its own', () => {
    const { container } = renderSigned();
    expect(screen.getByTestId('rounds-signed-paper')).toContainElement(
      screen.getByTestId('the-signed-paper')
    );
    expect(container.querySelector('textarea')).toBeNull();
    expect(container.querySelector('[contenteditable]')).toBeNull();
  });

  it('states the addendum rule as a SENTENCE, not a control', () => {
    // There is no addendum model, route or UI anywhere in the repo, so a link or
    // button would lead nowhere. The claim is true — the save actions refuse a
    // signed note and name addendum as the remedy — but the remedy does not
    // exist yet, and offering it would be the lie.
    renderSigned();
    const foot = screen.getByTestId('rounds-signed-addendum');
    expect(foot.textContent).toMatch(/corrections require a dated addendum/i);
    expect(foot.querySelector('a')).toBeNull();
    expect(foot.querySelector('button')).toBeNull();
  });
});

describe('the deck advance', () => {
  it('offers Continue when the queue has a head', () => {
    const onContinue = vi.fn();
    renderSigned({ onContinue });
    fireEvent.click(screen.getByTestId('rounds-signed-continue'));
    expect(onContinue).toHaveBeenCalled();
  });

  it('renders NOTHING when there is nothing left — not a disabled button', () => {
    // And emphatically not "all done for today": the queue is a 200-row window,
    // so a still-to-review visit outside it yields the same empty result. Honest
    // silence beats a completion claim the data cannot support.
    renderSigned({ onContinue: undefined });
    expect(screen.queryByTestId('rounds-signed-deck')).toBeNull();
    expect(screen.queryByTestId('rounds-signed-continue')).toBeNull();
    expect(document.body.textContent).not.toMatch(/all done|nothing left|caught up/i);
  });

  it('renders no queue COUNT — two surfaces counting differently is the trap', () => {
    // `queue.total` counts ready lanes over a 200-row window; /board's own
    // counter counts over a 20-row page. Both would be labelled "to review" and
    // they disagree for any doctor with more than 20 visits.
    renderSigned({
      queue: { ...EMPTY_QUEUE, total: 7, headVisitId: 'next-1' },
      onContinue: () => {},
    });
    // Asserted as the PHRASE, not the digit — a bare /7/ matches the `07` in
    // the signed-at timestamp, which is how a loose regex turns into a test
    // that fails for a reason it does not name.
    expect(document.body.textContent).not.toMatch(
      /\d+\s*(to review|remaining|left|encounters?)\b/i
    );
  });
});

describe('the strip is fed signedAt, never the gate set', () => {
  it('draws every node done with no blockers', () => {
    renderSigned();
    for (let i = 1; i <= 5; i++) {
      expect(
        screen.getByTestId(`rounds-strip-node-${i}`).getAttribute('data-stage-state')
      ).toBe('done');
    }
    const signed = screen.getByTestId('rounds-strip-signed');
    expect(signed.getAttribute('data-stage-state')).toBe('done');
    expect(signed.getAttribute('data-blockers')).toBe('0');
  });

  it('SOURCE GUARD — this component never passes gates or a non-zero n', () => {
    // The attestation gate reports unresolved:1 forever, because nothing sets
    // `attested` server-side. A Screen 4 that rendered the gate set would assert
    // "not attested" on a note the doctor has just signed.
    const SRC = readFileSync('src/components/rounds/signed.tsx', 'utf8');
    expect(SRC).toContain('n={0}');
    expect(SRC).not.toContain('gates={');
    // Control: the matcher is reading a real file.
    expect(SRC).toContain('rounds-signed-trail');
  });
});
