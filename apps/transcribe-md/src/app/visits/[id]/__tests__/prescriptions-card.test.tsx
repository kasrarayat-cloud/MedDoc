// ============================================================================
// The restored medication list — and the invariant it exists to hold.
// ----------------------------------------------------------------------------
// ⚠️ THE DEFECT THIS PINS IS A DIVERGENCE, NOT A MISSING CARD. Owner ruling
// #109 deleted a component that had TWO jobs — prescription SAFETY (which the
// ruling names) and the drafted MEDICATION LIST (which it does not). Deleting
// the whole thing left the export still printing a MEDICATIONS block into the
// signed PDF, DOCX and EHR clipboard while no screen showed it.
//
// So the property under test is: WHAT THE EXPORT PRINTS, THE DOCTOR SAW. Every
// test below is about that, not about a card being pretty.
// ============================================================================

import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import { enclosingOpenTags } from './jsx-enclosing';

import {
  PrescriptionsCard,
  hasDraftedPrescriptions,
  draftedPrescriptions,
} from '../prescriptions-card';

const ONE_RX = {
  prescriptions: [
    {
      drug: 'Amoxicillin',
      strength: '500 mg',
      form: 'capsule',
      sig: 'Take 1 capsule by mouth three times daily for 10 days',
      quantity: '30',
      refills: '0',
    },
  ],
  warnings: [{ severity: 'critical', rx_drug: 'Amoxicillin', message: 'interaction' }],
};

describe('the drafted medication list is SHOWN, because the export prints it', () => {
  it('renders every field the exported MEDICATIONS block carries', () => {
    // `rxSection()` in ehr-formatters emits drug/strength, sig, quantity and
    // refills. Each one is asserted here BY VALUE, because the failure being
    // prevented is content reaching a signed record unseen — a card that
    // rendered the drug and dropped the sig would still be that failure.
    render(<PrescriptionsCard rx={ONE_RX} />);
    const card = screen.getByTestId('review-doc-prescriptions');
    expect(card.textContent).toContain('Amoxicillin');
    expect(card.textContent).toContain('500 mg');
    expect(card.textContent).toContain('three times daily');
    expect(card.textContent).toContain('30');
    expect(card.textContent).toContain('0');
  });

  it('⚠️ SHOWS THE MEDICATIONS AND NONE OF THE SAFETY SURFACE', () => {
    // The fixture carries a CRITICAL warning. That is the point: the ruling
    // deleted the safety surface, so a critical warning must produce no
    // heading, no alarm, no severity, and above all no override control.
    render(<PrescriptionsCard rx={ONE_RX} />);
    const card = screen.getByTestId('review-doc-prescriptions');
    expect(card.textContent).toContain('Amoxicillin');   // …the positive half
    expect(card.textContent).not.toMatch(/prescription safety/i);
    expect(card.textContent).not.toMatch(/interaction|critical|override|warning/i);
    expect(screen.queryByRole('button')).toBeNull();
    expect(card.className).not.toMatch(/qm-warn|qm-lin-rx/);
  });

  it('a WARNING alone opens nothing — only prescriptions do', () => {
    // The deleted surface rendered on `prescriptions OR warnings`. Keeping the
    // warnings arm would resurrect a card whose only content is a warning,
    // which is the surface the ruling deleted, wearing a new testid.
    expect(hasDraftedPrescriptions({ warnings: [{ severity: 'critical' }] })).toBe(false);
    const { container } = render(
      <PrescriptionsCard rx={{ warnings: [{ severity: 'critical' }] }} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders NOTHING when there is nothing prescribed', () => {
    // Not an empty frame, not "no medications" — nothing. A heading over an
    // empty panel was a real defect on the deleted surface and must not return.
    for (const blob of [null, undefined, {}, { prescriptions: [] }]) {
      const { container } = render(<PrescriptionsCard rx={blob} />);
      expect(container.firstChild).toBeNull();
    }
  });

  it('a MALFORMED payload renders nothing rather than throwing', () => {
    // Model output persisted as jsonb. A bad payload must not take the whole
    // pre-sign review surface down with it.
    for (const bad of [42, 'nonsense', { prescriptions: 'no' }, { prescriptions: [] }]) {
      expect(() => draftedPrescriptions(bad)).not.toThrow();
      const { container } = render(<PrescriptionsCard rx={bad} />);
      expect(container.firstChild).toBeNull();
    }
  });

  it('⚠️ A ROW THE EXPORT WOULD PRINT IS RENDERED, however thin it is', () => {
    // ⚠️ THIS TEST CHANGED MEANING, AND THE CHANGE IS THE SAFER DIRECTION.
    // `{ prescriptions: [null, {}] }` used to be listed above as "malformed,
    // renders nothing", because the card filtered `typeof p.drug === 'string'`.
    // The field-parity arm in `gate-exported-medications-are-seen` showed that
    // filter was a DEFECT: the export's payload builder has no such check, so
    // a `drug`-less row was printed into the signed PDF and dropped from the
    // card — an unseen medication with every presence assertion green.
    //
    // Now it renders, and says what is wrong with it. A doctor can act on
    // "this row has no drug name"; they cannot act on a row that is not there.
    render(<PrescriptionsCard rx={{ prescriptions: [null, {}] }} />);
    expect(screen.getByTestId('review-doc-prescriptions')).toBeTruthy();
    expect(screen.getByTestId('review-doc-rx-unnamed')).toBeTruthy();
    // The `null` entry is still dropped — it cannot be rendered at all, and the
    // export cannot print it either.
    expect(screen.getAllByTestId('review-doc-rx-unnamed')).toHaveLength(1);
  });

  it('the action tag is shown for every non-new action, and never for new', () => {
    // The export appends `[DISCONTINUE]` and friends to the signed record
    // (`visit-export.ts:415-418`). A card without it renders a stop order
    // identically to a new start — worse than omitting the list, because it
    // says the opposite of the record being signed.
    render(
      <PrescriptionsCard
        rx={{
          prescriptions: [
            { drug: 'Warfarin', action: 'discontinue' },
            { drug: 'Lisinopril', action: 'new' },
          ],
        }}
      />,
    );
    const tags = screen.getAllByTestId('review-doc-rx-action');
    expect(tags).toHaveLength(1);
    expect(tags[0].textContent).toBe('DISCONTINUE');
  });

  it('an absent quantity is an em-dash, NEVER a fabricated 0', () => {
    // "Refills: 0" and "the model did not say" are different clinical claims,
    // and only one of them is true.
    render(<PrescriptionsCard rx={{ prescriptions: [{ drug: 'Lisinopril' }] }} />);
    const card = screen.getByTestId('review-doc-prescriptions');
    expect(card.textContent).toContain('—');
    expect(card.textContent).not.toMatch(/Qty 0|Refills 0/);
  });
});

// ============================================================================
// THE ROUNDS BRIDGE — the same both-directions guard `EmLevelCard` carries.
//
// ⚠️ THIS CARD IS THE REASON THE GUARD HAD TO BECOME A CENSUS. It was born
// during R5, AFTER R4b enumerated the `.qm-rdoc-gate` family and fixed the one
// member that existed. It then shipped unhosted and rendered CREAM directly
// above the panel R4b had just made dark — found by the owner in a screenshot,
// not by any check. The class-wide derivation lives in
// `src/lib/__tests__/gate-rdoc-gate-hosts.test.ts`; these two arms pin THIS
// component's half of the contract at the point somebody would edit it.
// ============================================================================
describe('PrescriptionsCard — the Rounds bridge', () => {
  it('carries qm-rounds-host itself, so every mount inherits the retint', () => {
    render(<PrescriptionsCard rx={ONE_RX} />);
    const card = screen.getByTestId('review-doc-prescriptions');
    expect(
      card.classList.contains('qm-rounds-host'),
      'the medication list lost its Rounds bridge — it will paint legacy amber ' +
        'and render as a cream panel on a dark route, which is exactly what the ' +
        'owner found beside the E/M card',
    ).toBe(true);
    // …and still the quiet gate frame: the bridge retints, it does not restyle.
    expect(card.classList.contains('qm-rdoc-gate')).toBe(true);
    expect(card.classList.contains('qm-rdoc-gate-quiet')).toBe(true);
  });

  it('NO CALLER supplies the bridge — it is not a per-caller list', () => {
    const view = readFileSync('src/app/visits/[id]/review-document-view.tsx', 'utf8');
    const code = view.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/^\s*\/\/.*$/gm, ' ');
    // NON-VACUITY: the comment stripper must leave the mount behind.
    expect(code).toContain('<PrescriptionsCard');

    // ⚠️ THE WINDOW LOOKS BOTH WAYS. A one-directional window cannot see a
    // PARENT, and a wrapper — `<div className="qm-rounds-host">
    // <PrescriptionsCard` — is the actual shape of the regression. The
    // EmLevelCard arm shipped forward-only first and stayed green through
    // exactly that mutation until it was widened backwards.
    // ⚠️ ANCESTORS, NOT A CHARACTER WINDOW. This arm used to slice ±400 chars
    // around the mount. That heuristic cannot tell a WRAPPER from a NEIGHBOUR,
    // and on 2026-08-14 it reported a wrapper that does not exist the moment
    // `review-document-view` gained two inline gate panels that correctly carry
    // their own bridge. Proximity in source is not parenthood; the tag stack is.
    const at = code.indexOf('<PrescriptionsCard');
    expect(
      enclosingOpenTags(code, at),
      'a caller supplies the Rounds bridge — the treatment has moved back to a ' +
        'hand-kept per-caller list, and the next mount is the one nobody remembers',
    ).not.toContainEqual(expect.stringContaining('qm-rounds-host'));
  });
});
