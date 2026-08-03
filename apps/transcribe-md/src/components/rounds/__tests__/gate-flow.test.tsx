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
  // ⚠️ TRUE SINCE 2026-08-02. This fixture said `false`, which was correct when
  // it was written and stale from the moment the gate became server-enforced:
  // `sign-gates.ts` is `serverEnforced: true`, and `POST /sign` answers 400
  // ATTESTATION_REQUIRED without it. Nothing asserted the fixture's value, so
  // nothing reddened — but a fixture that models the server wrongly is how a
  // future test comes to "prove" behaviour the server does not have.
  serverEnforced: true,
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

  it('⚠️ SAYS THE SERVER REFUSES WITHOUT IT — because since 2026-08-02 it does', () => {
    // ⚠️ THIS ASSERTION WAS INVERTED, AND IT HELD A FALSE STATEMENT IN PLACE.
    //
    // It used to require `/server does not check/i`, which was correct when B2
    // wrote it: `signGates` marked the attestation `serverEnforced: false` and
    // the sign route had no such field. The UI said so out loud, deliberately,
    // so that anyone reconciling the strip's N against a 4xx knew which term
    // the route could not see. That honesty was right.
    //
    // On 2026-08-02 the gate became SERVER-ENFORCED — `sign-gates.ts` is now
    // `serverEnforced: true`, `POST /sign` answers 400 ATTESTATION_REQUIRED
    // without `attestation: { acknowledged: true }`, and the refusal writes a
    // `SIGN_BLOCKED_NO_ATTESTATION` audit row. The copy did not move with it,
    // and THIS TEST is why it could not: the stale sentence had a green check
    // standing behind it, so every run confirmed the claim was still there
    // rather than still true.
    //
    // A gate's UI text is part of the gate. Telling a doctor a clinical
    // safeguard is unenforced when it is enforced invites them to treat the
    // tick as paperwork — the precise failure the strengthening exists to stop.
    renderFlow({ gates: [ATTEST()], step: 'attestation' });
    const note = screen.getByTestId('rounds-gate-attest-note').textContent ?? '';
    expect(note).toMatch(/refused by the server/i);
    // AND the old claim is gone, not merely joined by the new one.
    expect(note).not.toMatch(/server does not check/i);
  });

  it('⚠️ the note cannot drift from `sign-gates.ts` again', () => {
    // The failure above was a UI sentence and a server fact disagreeing with
    // nothing watching the pair. This reads BOTH and refuses to let the copy
    // claim less than the route enforces. If a future change makes the
    // attestation advisory again, this reddens and the sentence gets rewritten
    // in the same commit — which is the only way the two stay honest.
    const gates = readFileSync('src/lib/sign-gates.ts', 'utf8');
    const attestBlock = gates.slice(gates.indexOf("id: 'attestation'"));
    const serverEnforced = /serverEnforced:\s*true/.test(
      attestBlock.slice(0, attestBlock.indexOf('}')),
    );
    expect(
      serverEnforced,
      'attestation is no longer serverEnforced — the Gate 3 note now overclaims',
    ).toBe(true);

    renderFlow({ gates: [ATTEST()], step: 'attestation' });
    expect(screen.getByTestId('rounds-gate-attest-note').textContent).toMatch(
      /refused by the server/i,
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
    expect(screen.queryByTestId('rounds-gate-attest')).toBeNull();
    // ⚠️ R2 — THE SIGNATURE ANCHOR ON THIS STEP IS A DIFFERENT ELEMENT NOW.
    // It used to be `rounds-gate-host-attestation`, the ADOPTION host that
    // `gate-flow` moved the paper's footer node into. The signature is a plain
    // React child today (`signbar`), so the anchor is
    // `rounds-gate-signbar-host` — and the adoption host is not rendered on
    // this step at all, because nothing adopts here any more.
    expect(screen.queryByTestId('rounds-gate-host-attestation')).toBeNull();
    expect(screen.queryByTestId('rounds-gate-signbar-host')).toBeNull();
  });

  it('NEGATIVE CONTROL — without the artifact the signature host exists', () => {
    // The negative control is what makes the assertion above mean anything: an
    // absence proves nothing unless the same probe can find a presence.
    // `renderFlow` must therefore SUPPLY a signbar, or this passes for the
    // wrong reason — no signature because none was offered.
    renderFlow({
      gates: [ATTEST()],
      step: 'attestation',
      signbar: <button data-testid="probe-sign">Sign &amp; Download</button>,
    });
    expect(screen.queryByTestId('rounds-gate-em-artifact')).toBeNull();
    expect(screen.getByTestId('rounds-gate-signbar-host')).toBeTruthy();
    expect(screen.getByTestId('probe-sign')).toBeTruthy();
    // And STILL no adoption host — the re-home did not simply rename one.
    expect(screen.queryByTestId('rounds-gate-host-attestation')).toBeNull();
  });

  it('⚠️ R2 — the adoption host exists for the two gates that ADOPT, and only those', () => {
    // The effect looks up `[data-gate-slot="rx"|"em"]` and nothing else. A host
    // rendered for a step that never adopts is a landmark advertising a
    // mechanism it does not participate in — which is how the next reader
    // concludes the adoption still covers three slots. Caught by the E2E pack
    // when the markup had not followed the effect.
    for (const g of [RX(1), EM(1)]) {
      const { unmount } = renderFlow({ gates: [g], step: g.id });
      expect(
        screen.getByTestId(`rounds-gate-host-${g.id}`),
        `${g.id} lost its adoption host — its live gate has nowhere to land`,
      ).toBeTruthy();
      unmount();
    }
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
    // signature — that is a step's own chrome, not a clinical decision.
    // The other two must never be branched on: they arrive as data.
    //
    // ⚠️ R2 — COMMENTS ARE STRIPPED FIRST, and that is a fix rather than a
    // loosening. This grepped the RAW source, so any prose explaining the ban
    // tripped it: R2's `ADOPTED_SLOTS` docstring described the rule, spelled
    // the comparison it forbids, and reddened this test while the code it
    // guards was clean. That is the same defect the sibling guard above already
    // dodges by assembling its tokens from fragments — and the third sighting
    // of "a source grep reading its own explanation" in this repo.
    // The ban itself is UNCHANGED; it now applies to code, which is all it ever
    // meant to cover.
    const code = SRC.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/^\s*\/\/.*$/gm, ' ');
    expect(code).not.toContain("=== 'rx'");
    expect(code).not.toContain("=== 'em'");
    expect(code).not.toContain('=== "rx"');
    expect(code).not.toContain('=== "em"');

    // NON-VACUITY: stripping is what makes this test weaker if it goes wrong.
    // A regex that ate the whole file would pass every assertion above, so
    // prove real code survived — and prove the stripper actually removed prose.
    expect(code, 'the comment stripper ate the source').toContain('ADOPTED_SLOTS');
    expect(code).toContain('RoundsGateFlow');
    expect(
      code.length,
      'stripping removed nothing — the guard is still reading comments',
    ).toBeLessThan(SRC.length);
  });

  it('NEGATIVE CONTROL — the matcher can find a token that IS present', () => {
    // Without this, a typo in the URL or an empty read would pass every
    // assertion above by finding nothing anywhere.
    expect(SRC.length).toBeGreaterThan(1000);
    expect(SRC).toContain('rounds-gate-flow');
  });
});
