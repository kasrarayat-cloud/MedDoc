// ============================================================================
// Screen 3 — the gate flow. What it must NOT know, and what it must not fake.
// ----------------------------------------------------------------------------
// The interesting assertions here are negative. This component's whole claim is
// that it composes gates it does not own: the steps come from the gate array,
// the clinical controls arrive by portal, and nothing in the file knows what a
// specialty is. So most of these tests check that something is ABSENT.
// ============================================================================

import { readFileSync } from 'node:fs';

import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import type { SignGate } from '@/lib/sign-gates';
import { RoundsGateFlow } from '../gate-flow';

const RX = (unresolved: number): SignGate => ({
  id: 'rx',
  unresolved,
  serverEnforced: true,
});
const EM = (unresolved: number): SignGate => ({
  id: 'em',
  unresolved,
  serverEnforced: true,
});
const ATTEST = (unresolved = 1): SignGate => ({
  id: 'attestation',
  unresolved,
  serverEnforced: false,
});

function renderFlow(
  over: Partial<React.ComponentProps<typeof RoundsGateFlow>> = {}
) {
  const gates = over.gates ?? [RX(1), EM(1), ATTEST()];
  return render(
    <RoundsGateFlow
      open
      gates={gates}
      n={gates.reduce((s, g) => s + g.unresolved, 0)}
      step={gates[0]?.id ?? null}
      onStepChange={() => {}}
      onClose={() => {}}
      attested={false}
      onAttestedChange={() => {}}
      patientLabel="A Patient"
      visitDateLabel="2026-07-30"
      {...over}
    />
  );
}

describe('the steps ARE the gate array', () => {
  it('renders one step per applicable gate, in the server’s order', () => {
    renderFlow();
    const steps = screen.getByTestId('rounds-gate-steps');
    expect(steps.children).toHaveLength(3);
    expect(screen.getByTestId('rounds-gate-step-rx')).toBeTruthy();
    expect(screen.getByTestId('rounds-gate-step-em')).toBeTruthy();
    expect(screen.getByTestId('rounds-gate-step-attestation')).toBeTruthy();
  });

  it('AN IMAGING VISIT HAS NO E/M STEP — absent, not disabled, not empty', () => {
    // The invariant, expressed where it can be broken. This component never
    // asks whether E/M applies; the gate is simply not in the array. So the
    // test asserts there is no E/M chrome AT ALL — not that it is hidden.
    renderFlow({ gates: [ATTEST()], step: 'attestation' });

    expect(screen.getByTestId('rounds-gate-steps').children).toHaveLength(1);
    expect(screen.queryByTestId('rounds-gate-step-em')).toBeNull();
    expect(screen.queryByTestId('rounds-gate-host-em')).toBeNull();
    expect(screen.queryByTestId('rounds-gate-summary-em')).toBeNull();
    expect(document.body.textContent).not.toMatch(/documentation level/i);
  });

  it('only the ACTIVE step gets a host — the others stay where they are', () => {
    // One host at a time, because the live gate is a single DOM subtree that
    // gets ADOPTED into it. Two hosts would be two homes for one node.
    renderFlow({ step: 'rx' });
    expect(screen.getByTestId('rounds-gate-host-rx')).toBeTruthy();
    expect(screen.queryByTestId('rounds-gate-host-em')).toBeNull();
    expect(screen.queryByTestId('rounds-gate-host-attestation')).toBeNull();
  });

  it('renders NO clinical control of its own — the host is empty', () => {
    // Empty in isolation: the real gate is adopted in from the paper at
    // runtime. If this component ever grows its own override button or level
    // card, the gate logic has a second home and the two will drift.
    const { container } = renderFlow({ step: 'rx' });
    expect(screen.getByTestId('rounds-gate-host-rx').childNodes).toHaveLength(0);
    expect(container.querySelector('textarea')).toBeNull();
    expect(container.querySelector('[data-testid^="review-doc-"]')).toBeNull();
  });
});

describe('Gate 2 on a QUIET visit — never dropped, never counted', () => {
  // The ruling, expressed at the surface that could break it. E/M is the
  // designed sole billing surface: it shows the code, the complexity and the
  // rationale, and it carries the adjust-level flow. So it must EXIST wherever
  // the specialty applies — even when nothing has changed and nothing blocks.
  //
  // The two failures this guards against are opposite and both plausible:
  // dropping the step because it counts zero (the doctor loses the only place
  // the level can be reviewed or changed), or counting it because it is shown
  // (the padlock claims a blocker POST /sign does not have).
  const QUIET = [EM(0), ATTEST()];

  it('the step EXISTS in the sequence', () => {
    renderFlow({ gates: QUIET, step: 'em' });
    expect(screen.getByTestId('rounds-gate-step-em')).toBeTruthy();
    expect(screen.getByTestId('rounds-gate-steps').children).toHaveLength(2);
  });

  it('and it still HOSTS the billing surface — that is what it is for', () => {
    renderFlow({ gates: QUIET, step: 'em' });
    expect(screen.getByTestId('rounds-gate-host-em')).toBeTruthy();
  });

  it('but it does not block: no lock, and Next advances', () => {
    const onStepChange = vi.fn();
    renderFlow({ gates: QUIET, step: 'em', onStepChange });

    expect(screen.queryByTestId('rounds-gate-lock')).toBeNull();
    expect(screen.getByTestId('rounds-gate-next')).toHaveProperty('disabled', false);
    fireEvent.click(screen.getByTestId('rounds-gate-next'));
    expect(onStepChange).toHaveBeenCalledWith('attestation');
  });

  it('and it contributes nothing to the count on the flow', () => {
    renderFlow({ gates: QUIET, step: 'em' });
    expect(screen.getByTestId('rounds-gate-n').getAttribute('data-blockers')).toBe('1');
  });

  it('NEGATIVE CONTROL — an unacknowledged change DOES block the same step', () => {
    // Without this, "never blocks" would be satisfied by a step that can never
    // block at all, and the server refusal would arrive unannounced.
    renderFlow({ gates: [EM(1), ATTEST()], step: 'em' });
    expect(screen.getByTestId('rounds-gate-lock')).toBeTruthy();
    expect(screen.getByTestId('rounds-gate-next')).toHaveProperty('disabled', true);
  });

  it('the summary row says cleared, not absent', () => {
    renderFlow({ gates: QUIET, step: 'attestation' });
    const row = screen.getByTestId('rounds-gate-summary-em');
    expect(row.getAttribute('data-cleared')).toBe('true');
  });
});

describe('locked until clear', () => {
  it('shows the lock and disables Next while the step still blocks', () => {
    renderFlow({ gates: [RX(2), ATTEST()], step: 'rx' });
    expect(screen.getByTestId('rounds-gate-lock')).toBeTruthy();
    expect(screen.getByTestId('rounds-gate-next')).toHaveProperty('disabled', true);
  });

  it('NEGATIVE CONTROL — a cleared step advances', () => {
    const onStepChange = vi.fn();
    renderFlow({ gates: [RX(0), ATTEST()], step: 'rx', onStepChange });

    expect(screen.queryByTestId('rounds-gate-lock')).toBeNull();
    const next = screen.getByTestId('rounds-gate-next');
    expect(next).toHaveProperty('disabled', false);
    fireEvent.click(next);
    expect(onStepChange).toHaveBeenCalledWith('attestation');
  });

  it('a blocked step cannot advance even if the button is clicked', () => {
    const onStepChange = vi.fn();
    renderFlow({ gates: [RX(1), ATTEST()], step: 'rx', onStepChange });
    fireEvent.click(screen.getByTestId('rounds-gate-next'));
    expect(onStepChange).not.toHaveBeenCalled();
  });
});

describe('the attestation step', () => {
  it('summarises ONLY the gates that applied', () => {
    // A "cleared" row for a gate that never existed is a claim about work
    // nobody did.
    renderFlow({ gates: [RX(0), ATTEST()], step: 'attestation' });
    expect(screen.getByTestId('rounds-gate-summary-rx')).toBeTruthy();
    expect(screen.queryByTestId('rounds-gate-summary-em')).toBeNull();
    // Attestation does not summarise itself — it is the step you are on.
    expect(screen.queryByTestId('rounds-gate-summary-attestation')).toBeNull();
  });

  it('names the patient and the date in the attestation sentence', () => {
    renderFlow({ gates: [ATTEST()], step: 'attestation' });
    const label = screen.getByTestId('rounds-gate-attest').closest('label');
    expect(label?.textContent).toContain('A Patient');
    expect(label?.textContent).toContain('2026-07-30');
  });

  it('SAYS the server does not check it — because signGates says so', () => {
    // attestation is serverEnforced: false and the sign route has no such
    // field. A UI that implied otherwise would be making a promise nobody
    // keeps, on the screen whose job is to be believed.
    renderFlow({ gates: [ATTEST()], step: 'attestation' });
    expect(screen.getByTestId('rounds-gate-attest-note').textContent).toMatch(
      /server does not check/i
    );
  });

  it('carries the addendum footer', () => {
    renderFlow({ gates: [ATTEST()], step: 'attestation' });
    expect(document.body.textContent).toMatch(/later changes require a dated addendum/i);
  });
});

describe('the imaging E/M anomaly', () => {
  it('names the state and refuses to host a signature', () => {
    // No E/M gate exists (the invariant is absolute) but the sign route is not
    // specialty-conditioned and WILL refuse. Rendering a clean zero here would
    // walk the doctor into a 400 they were not warned about.
    renderFlow({ gates: [ATTEST()], step: 'attestation', emArtifact: true });

    expect(screen.getByTestId('rounds-gate-em-artifact')).toBeTruthy();
    expect(screen.queryByTestId('rounds-gate-host-attestation')).toBeNull();
    expect(screen.queryByTestId('rounds-gate-attest')).toBeNull();
  });

  it('NEGATIVE CONTROL — without the artifact the signature host exists', () => {
    renderFlow({ gates: [ATTEST()], step: 'attestation' });
    expect(screen.queryByTestId('rounds-gate-em-artifact')).toBeNull();
    expect(screen.getByTestId('rounds-gate-host-attestation')).toBeTruthy();
  });
});

describe('dialog posture', () => {
  it('declares itself modal, because it visually blocks the page', () => {
    // A landmark that lies is worse than no landmark — the strip already had
    // that bug once with a <nav> containing no links.
    renderFlow();
    const dlg = screen.getByTestId('rounds-gate-flow');
    expect(dlg.getAttribute('role')).toBe('dialog');
    expect(dlg.getAttribute('aria-modal')).toBe('true');
  });

  it('Escape closes', () => {
    const onClose = vi.fn();
    renderFlow({ onClose });
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('renders nothing at all when closed', () => {
    const { container } = renderFlow({ open: false });
    expect(container.firstChild).toBeNull();
  });
});

describe('it does not know what a specialty is, and must not learn', () => {
  // "Only applicable gates exist" is decided ONCE, on the server, by the single
  // switch, and reaches this component as a shorter array. The moment this file
  // asks the question itself there are two answers to keep in step — which is
  // exactly how a display label once reached an id comparator and silently made
  // every imaging visit compute an office E/M level.
  //
  // The banned tokens are assembled from fragments rather than written out: the
  // repo's other guards are source greps, and a test that spells the forbidden
  // string is a test that trips its own siblings. (A2 defect 2, twice paid for.)
  // A path from the vitest root, matching how the repo's other source guards
  // read files — `import.meta.url` is not a file URL under this config.
  const SRC = readFileSync('src/components/rounds/gate-flow.tsx', 'utf8');

  const banned = [
    ['ultrasound', 'SpecialtyEnabled'].join(''),
    ['isImagingReport', 'Specialty'].join(''),
    ['emApplies', 'ToSpecialty'].join(''),
    ['specialty', 'Id'].join(''),
  ];

  it('names no specialty predicate', () => {
    for (const token of banned) {
      expect(SRC, `gate-flow.tsx contains ${token}`).not.toContain(token);
    }
  });

  it('branches on no gate id of its own except the one that owns the signature', () => {
    // `attestation` appears because the last step carries the checkbox and the
    // signing bar — that is a step's own chrome, not a clinical decision.
    // `rx` and `em` must never be branched on: they arrive as data.
    expect(SRC).not.toContain("=== 'rx'");
    expect(SRC).not.toContain("=== 'em'");
  });

  it('NEGATIVE CONTROL — the matcher can find a token that IS present', () => {
    // Without this, a typo in the URL or an empty read would pass every
    // assertion above by finding nothing anywhere.
    expect(SRC.length).toBeGreaterThan(1000);
    expect(SRC).toContain('rounds-gate-flow');
  });
});
