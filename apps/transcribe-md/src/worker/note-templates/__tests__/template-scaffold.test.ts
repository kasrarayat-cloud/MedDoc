import { describe, expect, it } from 'vitest';
import {
  buildTemplateScaffold,
  carrierReducedClaim,
  isFixedScaffoldLine,
  normForMatch,
} from '../template-scaffold';
import type { NoteTemplateSection } from '../system-default-template';

function section(key: string, defaultText: string | null): NoteTemplateSection {
  return {
    key, label: key, order: 1, formatHint: 'prose',
    styleInstructions: null, defaultText,
    defaultTextMode: defaultText ? 'scaffold_confirm' : 'omit_unless_supported',
    structure: null,
  };
}

// The two real WM_IOV shapes: a findings carrier + an impression carrier + fixed boilerplate.
const FINDINGS =
  'Right Leg:\n' +
  'The {{one of: great saphenous vein | small saphenous vein}} from the {{one of: saphenofemoral junction | mid thigh}} to the {{one of: mid thigh | distal calf}} was found to have had previous treatment {{one of: and is absent. | , however, there has been a recurrence.}}\n' +
  'Clinical correlation with the above findings is required.';
const IMPRESSION =
  'Right {{one of: great saphenous vein | small saphenous vein}} is {{one of: reflux positive. | is absent.}}\n' +
  'Left {{one of: great saphenous vein | small saphenous vein}} is {{one of: reflux positive. | is absent.}}';

const SCAFFOLD = buildTemplateScaffold([section('findings', FINDINGS), section('impression', IMPRESSION)]);

describe('buildTemplateScaffold', () => {
  it('separates fixed-scaffold lines from carriers', () => {
    expect(SCAFFOLD.fixedLines.has(normForMatch('Right Leg:'))).toBe(true);
    expect(SCAFFOLD.fixedLines.has(normForMatch('Clinical correlation with the above findings is required.'))).toBe(true);
    // carriers: findings (4 slots) + impression Right (2) + impression Left (2)
    expect(SCAFFOLD.carriers.length).toBe(3);
    expect(SCAFFOLD.carriers[0].slotCount).toBe(4);
    expect(SCAFFOLD.carriers[1].slotCount).toBe(2);
    expect(SCAFFOLD.carriers[2].slotCount).toBe(2);
  });
});

describe('isFixedScaffoldLine — exact match only', () => {
  it('matches a fixed line exactly (normalized)', () => {
    expect(isFixedScaffoldLine(SCAFFOLD, normForMatch('Right Leg:'))).toBe(true);
  });
  it('does NOT match a superstring (a real claim that merely contains the label)', () => {
    expect(isFixedScaffoldLine(SCAFFOLD, normForMatch('Right Leg: swelling and tenderness'))).toBe(false);
  });
});

describe('carrierReducedClaim — picks + laterality, boilerplate dropped', () => {
  it('reduces a filled findings carrier to its picks (no connective boilerplate)', () => {
    const line = 'The great saphenous vein from the saphenofemoral junction to the mid thigh was found to have had previous treatment, however, there has been a recurrence.';
    const reduced = carrierReducedClaim(SCAFFOLD, normForMatch(line));
    expect(reduced).not.toBeNull();
    expect(reduced).toContain('great saphenous vein');
    expect(reduced).toContain('saphenofemoral junction');
    expect(reduced).toContain('mid thigh');
    expect(reduced).toContain('recurrence');
    // connective boilerplate is DROPPED
    expect(reduced).not.toContain('was found to have had previous treatment');
  });

  it('keeps LATERALITY in the reduced claim (guards a right/left swap)', () => {
    const line = 'Right great saphenous vein is reflux positive.';
    const reduced = carrierReducedClaim(SCAFFOLD, normForMatch(line));
    expect(reduced).toBe('right great saphenous vein reflux positive');
    // A left line matches the LEFT carrier and its reduced claim CARRIES the
    // laterality "left" → the judge (given the left-normal transcript) can
    // reject a right-findings-under-left swap.
    const left = 'Left great saphenous vein is reflux positive.';
    expect(carrierReducedClaim(SCAFFOLD, normForMatch(left))).toBe('left great saphenous vein reflux positive');
  });

  it('returns null for a FABRICATED option that is not in the template (can never take the carrier path)', () => {
    const line = 'Right great saphenous vein is thrombosed with acute clot.';
    expect(carrierReducedClaim(SCAFFOLD, normForMatch(line))).toBeNull();
  });
});
