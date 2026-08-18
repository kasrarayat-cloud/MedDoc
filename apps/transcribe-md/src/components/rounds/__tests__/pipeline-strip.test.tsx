// ============================================================================
// The strip says where the note actually is, and what actually blocks it.
// ----------------------------------------------------------------------------
// The N arithmetic is unit-tested against the server's semantics in
// lib/__tests__/sign-gates. What these pin is the RENDERING contract — the
// parts a screenshot cannot check:
//
//   - each node carries its own state, POSITIONALLY (a strip that rendered
//     every node identical would still "look right" in a screenshot)
//   - READY does not draw the Ready node as done
//   - the Signed node is padlocked with the count, and un-padlocks when signed
//   - an imaging visit's strip never says "documentation level"
//   - the state is in the accessible NAME, not only in colour
// ============================================================================

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import { RoundsPipelineStrip } from '../pipeline-strip';
import { signGates } from '@/lib/sign-gates';
import { ROUNDS_STAGES } from '@/lib/rounds/stages';

const stateOf = (n: number) =>
  screen.getByTestId(`rounds-strip-node-${n}`).getAttribute('data-stage-state');

/** Build gates through the REAL model, never hand-rolled — a fixture that
 *  cannot be produced by the production path proves nothing about it. */
const gatesFor = (over: Parameters<typeof signGates>[0]) => signGates(over);

describe('node positioning', () => {
  it('READY marks stages 1-4 done and stage 5 CURRENT — not done', () => {
    // completedStageCount('READY') is 5, which would tick every node including
    // the one the doctor is standing on. That is the bug this asserts against.
    render(<RoundsPipelineStrip status="READY" n={0} />);
    expect(stateOf(1)).toBe('done');
    expect(stateOf(2)).toBe('done');
    expect(stateOf(3)).toBe('done');
    expect(stateOf(4)).toBe('done');
    expect(stateOf(5)).toBe('current');
  });

  it('NOW REVIEWING appears exactly once, on the current node', () => {
    render(<RoundsPipelineStrip status="READY" n={0} />);
    const marks = screen.getAllByTestId('rounds-strip-now');
    expect(marks).toHaveLength(1);
    expect(screen.getByTestId('rounds-strip-node-5')).toContainElement(marks[0]!);
  });

  it('a SIGNED visit reads every stage done and no NOW REVIEWING', () => {
    render(
      <RoundsPipelineStrip status="SIGNED" signedAt="2026-07-30T10:00:00Z" n={0} />
    );
    for (const s of ROUNDS_STAGES) expect(stateOf(s.n)).toBe('done');
    expect(screen.queryByTestId('rounds-strip-now')).toBeNull();
  });

  it('renders exactly the five stages plus one Signed node', () => {
    const { container } = render(<RoundsPipelineStrip status="READY" n={0} />);
    const nodes = container.querySelectorAll('.qm-rounds-strip-node');
    expect(nodes).toHaveLength(ROUNDS_STAGES.length + 1);
  });

  it('the labels come from the shared stage mapping, not a local list', () => {
    render(<RoundsPipelineStrip status="READY" n={0} />);
    for (const s of ROUNDS_STAGES) {
      expect(screen.getByTestId(`rounds-strip-node-${s.n}`).textContent).toContain(
        s.label
      );
    }
  });
});

describe('the padlocked Signed node', () => {
  it('is locked and carries the count when there are blockers', () => {
    render(<RoundsPipelineStrip status="READY" n={3} />);
    const signed = screen.getByTestId('rounds-strip-signed');
    expect(signed.getAttribute('data-stage-state')).toBe('locked');
    expect(signed.getAttribute('data-blockers')).toBe('3');
    expect(screen.getByTestId('rounds-strip-blockers').textContent).toBe(
      '3 blockers before Signed'
    );
  });

  it('singularises one blocker', () => {
    render(<RoundsPipelineStrip status="READY" n={1} />);
    expect(screen.getByTestId('rounds-strip-blockers').textContent).toBe(
      '1 blocker before Signed'
    );
  });

  it('NEGATIVE CONTROL — a different N renders a different label', () => {
    // Without this, the assertions above pass against a component that always
    // prints the same sentence.
    const { unmount } = render(<RoundsPipelineStrip status="READY" n={2} />);
    expect(screen.getByTestId('rounds-strip-blockers').textContent).toContain('2');
    unmount();
    render(<RoundsPipelineStrip status="READY" n={7} />);
    expect(screen.getByTestId('rounds-strip-blockers').textContent).toContain('7');
  });

  it('shows no blocker label at zero, and still reads locked', () => {
    render(<RoundsPipelineStrip status="READY" n={0} />);
    expect(screen.queryByTestId('rounds-strip-blockers')).toBeNull();
    expect(
      screen.getByTestId('rounds-strip-signed').getAttribute('data-stage-state')
    ).toBe('locked');
  });

  it('un-padlocks once signed', () => {
    render(
      <RoundsPipelineStrip status="SIGNED" signedAt="2026-07-30T10:00:00Z" n={0} />
    );
    const signed = screen.getByTestId('rounds-strip-signed');
    expect(signed.getAttribute('data-stage-state')).toBe('done');
    expect(signed.textContent).not.toContain('🔒');
    expect(screen.queryByTestId('rounds-strip-blockers')).toBeNull();
  });

  it('names WHICH gates are outstanding in the accessible name', () => {
    const set = gatesFor({
      specialty: 'primary-care',
      templateSections: null,
      // ruling #126 — no note body here, so the note-text fallback cannot fire
      // and these arms assert exactly what they asserted before it existed.
      noteText: '',
      emPendingChange: { from: '99213', to: '99214', cause: 'note_edited', at: '2026-07-30T00:00:00Z' },
    });
    render(
      <RoundsPipelineStrip status="READY" gates={set.gates} n={set.n} />
    );
    const name = screen
      .getByTestId('rounds-strip-signed')
      .getAttribute('aria-label')!;
    expect(name).toContain('documentation level');
    expect(name).toContain('attestation');
  });

  it('a satisfied gate is not named as a blocker', () => {
    const set = gatesFor({
      specialty: 'primary-care',
      templateSections: null,
      // ruling #126 — no note body here, so the note-text fallback cannot fire
      // and these arms assert exactly what they asserted before it existed.
      noteText: '',
      emPendingChange: null,
      attested: true,
    });
    render(<RoundsPipelineStrip status="READY" gates={set.gates} n={set.n} />);
    const name = screen
      .getByTestId('rounds-strip-signed')
      .getAttribute('aria-label')!;
    expect(name).not.toContain('documentation level');
    expect(name).not.toContain('attestation');
    expect(set.n).toBe(0);
  });
});

describe('imaging never grows an E/M term', () => {
  const prior = process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY;
  beforeEach(() => {
    process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY = 'true';
  });
  afterEach(() => {
    if (prior === undefined) delete process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY;
    else process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY = prior;
  });

  it('the strip says nothing about a documentation level', () => {
    const set = gatesFor({
      specialty: 'ultrasound',
      templateSections: null,
      // ruling #126 — no note body here, so the note-text fallback cannot fire
      // and these arms assert exactly what they asserted before it existed.
      noteText: '',
      emPendingChange: null,
    });
    const { container } = render(
      <RoundsPipelineStrip status="READY" gates={set.gates} n={set.n} />
    );
    expect(container.textContent).not.toMatch(/documentation level|E\/M/i);
    expect(
      screen.getByTestId('rounds-strip-signed').getAttribute('aria-label')
    ).not.toContain('documentation level');
  });

  it('NEGATIVE CONTROL — a primary-care visit with a pending change DOES name it', () => {
    // Without this, the test above passes against a strip that never names any
    // gate at all.
    const set = gatesFor({
      specialty: 'primary-care',
      templateSections: null,
      // ruling #126 — no note body here, so the note-text fallback cannot fire
      // and these arms assert exactly what they asserted before it existed.
      noteText: '',
      emPendingChange: {
        from: '99213',
        to: '99214',
        cause: 'note_edited',
        at: '2026-07-30T00:00:00Z',
      },
    });
    render(<RoundsPipelineStrip status="READY" gates={set.gates} n={set.n} />);
    expect(
      screen.getByTestId('rounds-strip-signed').getAttribute('aria-label')
    ).toContain('documentation level');
  });

  it('an imaging visit holding office E/M state is NAMED, not silently zeroed', () => {
    const set = gatesFor({
      specialty: 'ultrasound',
      templateSections: null,
      // ruling #126 — no note body here, so the note-text fallback cannot fire
      // and these arms assert exactly what they asserted before it existed.
      noteText: '',
      emPendingChange: {
        from: '99213',
        to: '99214',
        cause: 'note_edited',
        at: '2026-07-30T00:00:00Z',
      },
    });
    render(
      <RoundsPipelineStrip
        status="READY"
        gates={set.gates}
        n={set.n}
        emArtifact={set.emArtifact}
      />
    );
    expect(screen.getByTestId('rounds-strip-em-artifact')).toBeTruthy();
  });

  it('NEGATIVE CONTROL — a clean visit shows no artifact warning', () => {
    render(<RoundsPipelineStrip status="READY" n={0} emArtifact={false} />);
    expect(screen.queryByTestId('rounds-strip-em-artifact')).toBeNull();
  });
});

describe('accessibility contract', () => {
  it('every node states done/current/pending in words, not only in colour', () => {
    render(<RoundsPipelineStrip status="READY" n={0} />);
    expect(screen.getByTestId('rounds-strip-node-1').getAttribute('aria-label'))
      .toContain('done');
    expect(screen.getByTestId('rounds-strip-node-5').getAttribute('aria-label'))
      .toContain('now reviewing');
  });

  it('carries no table/list-item ARIA that needs a parent it does not have', () => {
    // role="row"/"columnheader" without a table ancestor was an axe CRITICAL on
    // the board. A strip is a diagram; it gets a nav landmark and nothing else.
    const { container } = render(<RoundsPipelineStrip status="READY" n={0} />);
    expect(container.querySelectorAll('[role="row"]')).toHaveLength(0);
    expect(container.querySelectorAll('[role="columnheader"]')).toHaveLength(0);
    expect(container.querySelectorAll('[role="progressbar"]')).toHaveLength(0);
    expect(screen.getByTestId('rounds-pipeline-strip').getAttribute('aria-label'))
      .toBe('Note progress');
  });

  it('is NOT a nav landmark — it contains no links to navigate to', () => {
    // A nav landmark promises somewhere to go. A reader cycling landmarks
    // would arrive in a diagram and find nothing actionable.
    const { container } = render(<RoundsPipelineStrip status="READY" n={0} />);
    expect(container.querySelector('nav')).toBeNull();
    expect(container.querySelectorAll('a')).toHaveLength(0);
    const strip = screen.getByTestId('rounds-pipeline-strip');
    expect(strip.tagName).toBe('DIV');
    expect(strip.getAttribute('role')).toBe('group');
  });

  it('the NOW REVIEWING label itself never animates', () => {
    // axe samples mid-cycle; text at 35% opacity really is unreadable at that
    // instant. Motion belongs on the dot.
    render(<RoundsPipelineStrip status="READY" n={0} />);
    const now = screen.getByTestId('rounds-strip-now');
    expect(now.className).not.toMatch(/pulse|blink|animate/i);
    expect(now.getAttribute('style') ?? '').not.toMatch(/animation/i);
  });

  it('decorative marks are hidden from the accessible tree', () => {
    const { container } = render(<RoundsPipelineStrip status="READY" n={2} />);
    for (const dot of Array.from(container.querySelectorAll('.qm-rounds-strip-dot'))) {
      expect(dot.getAttribute('aria-hidden')).toBe('true');
    }
  });
});

describe('a signed visit whose status column still says READY (regression)', () => {
  // THE ROW SHAPE IS REAL, not hypothetical. `kindOf` in board-data keys on
  // `status === 'SIGNED' || signedAt`; there is a stage-queue test named
  // "EXCLUDES a signed visit whose status column still says READY"; `isSigned`
  // in the review view accepts it; and tests/e2e/helpers/seedVisitStates.ts
  // inserts exactly it.
  //
  // The strip used to ask only the status column. `stageOf('READY')` is stage 5
  // — not null — so node 5 drew as CURRENT while the Signed node beside it drew
  // a ✓: one track claiming "still ready" and "signed" simultaneously. The BOARD
  // already handled this (`runTo: kind === 'signed' ? 5`); the strip did not, so
  // one journey rendered two ways on two surfaces.
  const SIGNED_AT = '2026-07-30T10:00:00.000Z';

  it('draws every stage node done, and none current', () => {
    render(<RoundsPipelineStrip status="READY" signedAt={SIGNED_AT} n={0} />);

    for (let i = 1; i <= 5; i++) {
      expect(
        screen.getByTestId(`rounds-strip-node-${i}`).getAttribute('data-stage-state'),
        `node ${i}`,
      ).toBe('done');
    }
    // NOW REVIEWING is the tell: it renders on the current node, and a signed
    // note has none.
    expect(screen.queryByTestId('rounds-strip-now')).toBeNull();
  });

  it('and the Signed node reads done with no blockers', () => {
    render(<RoundsPipelineStrip status="READY" signedAt={SIGNED_AT} n={0} />);
    const signed = screen.getByTestId('rounds-strip-signed');
    expect(signed.getAttribute('data-stage-state')).toBe('done');
    expect(signed.getAttribute('data-blockers')).toBe('0');
  });

  it('NEGATIVE CONTROL — the SAME status without signedAt still draws node 5 current', () => {
    // Without this, "always all done" would satisfy both assertions above and
    // the strip would stop tracking progress entirely.
    render(<RoundsPipelineStrip status="READY" signedAt={null} n={2} />);
    expect(
      screen.getByTestId('rounds-strip-node-5').getAttribute('data-stage-state'),
    ).toBe('current');
    expect(screen.getByTestId('rounds-strip-now')).toBeTruthy();
  });
});
