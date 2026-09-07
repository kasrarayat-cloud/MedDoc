/**
 * ⚠️ NO ROS PATH MAY PUT A RAW MACHINE TOKEN INTO A DOCUMENT.
 *
 * The projector builds the CONCEPT from a closed-lexicon token, and 25 of the
 * 72 tokens carry an underscore. Before this arm, `early_satiety`,
 * `night_sweats` and `suicidal_ideation` reached the doctor's form as the
 * fact's VALUE — `status=supported`, `valid=true`, zero issues. Nothing on the
 * fill path spelled them back into words.
 *
 * ⚠️ AND TEACHING THE MODEL THE LEXICON MADE THIS MORE LIKELY, NOT LESS. The L3
 * prompt now instructs the model to emit the identifier exactly, so a COMPLIANT
 * model leaves `finding_verbatim` unset and the token would flow straight
 * through. The fix that closed the off-lexicon case did not close this one —
 * a fix can open the defect standing next to the one it repairs, and this arm
 * exists because that happened here.
 *
 * ⚠️ WHAT IS DELIBERATELY NOT DONE: a token-to-prose display map. Deciding that
 * a form should read "shortness of breath" where the lexicon says `dyspnea` is
 * a clinical wording judgement; it belongs to the owner and is filed for him
 * rather than taken. De-slugging is not that judgement — it restores the spaces
 * the identifier form removed and changes nothing else.
 */
import { describe, it, expect, vi } from 'vitest';

// The same two mocks the sibling ROS gates carry: `03-extract-entities` imports
// `@/lib/audit`, whose graph reaches next-auth and fails to resolve
// `next/server` under vitest. Without these the file does not IMPORT, and
// "no tests" is not a pass.
vi.mock('@meddoc/db', () => ({ default: {} }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { ExtractedEntities } from '../03-extract-entities';
import { projectEncounterFacts } from '@/lib/template-twin/encounter-facts';
import { ROS_SYSTEMS, symptomsFor, ROS_OTHER } from '@/lib/template-twin/ros-lexicon';

/** The value that would reach the document, driven through the SHIPPED chain. */
function valueFor(system: string, finding: string): string {
  const entities = ExtractedEntities.parse({
    chief_complaint: null,
    hpi: null,
    ros: [{ system, finding, polarity: 'affirmed', evidence_quote: 'the doctor said so' }],
  });
  const facts = projectEncounterFacts({
    mode: 'dictation',
    contextText: 'the doctor said so',
    // The L3 schema's output IS the snapshot shape the projector consumes; the
    // two are structurally identical and the cast is the seam between a parsed
    // zod type and the hand-written interface, exactly as the sibling gates do.
    entities: entities as unknown as Parameters<typeof projectEncounterFacts>[0]['entities'],
  });
  const ros = facts.find((f) => f.concept.startsWith('ros.'));
  expect(ros, `no ros fact projected for ${system}/${finding}`).toBeTruthy();
  return String(ros!.value);
}

describe('a ROS fact never carries a raw snake_case identifier into the document', () => {
  it('NON-VACUITY: the lexicon really does contain underscored tokens', () => {
    // Without this the sweep below is satisfied by a lexicon with no
    // underscores in it, which is not the lexicon that shipped.
    const underscored = ROS_SYSTEMS.flatMap((s) => symptomsFor(s).filter((t) => t.includes('_')));
    expect(underscored.length).toBeGreaterThanOrEqual(20);
  });

  it('⚠️ EVERY addressable token in the lexicon renders without an underscore', () => {
    const offenders: string[] = [];
    for (const system of ROS_SYSTEMS) {
      for (const token of symptomsFor(system)) {
        if (token === ROS_OTHER) continue;
        const value = valueFor(system, token);
        if (value.includes('_')) offenders.push(`${system}.${token} -> ${value}`);
      }
    }
    expect(
      offenders,
      `machine tokens reaching the document: ${offenders.slice(0, 5).join('; ')}`,
    ).toEqual([]);
  });

  it("the doctor's own words WIN over the de-slugged token", () => {
    // De-slugging is the fallback, not the rule. When the model reported prose,
    // that prose is what the document must carry.
    expect(valueFor('gastrointestinal', 'early satiety')).toBe('early satiety');
    expect(valueFor('constitutional', 'night sweats')).toBe('night sweats');
  });

  it('an OFF-LEXICON symptom carries the words, never the literal "other"', () => {
    expect(valueFor('gastrointestinal', 'belching')).toBe('belching');
  });

  it('DISCRIMINATION: de-slugging changes nothing but the underscores', () => {
    // The sweep above would also pass if every value were replaced by a
    // constant, or blanked. These say the clinical word survives intact.
    expect(valueFor('respiratory', 'dyspnea')).toBe('dyspnea');
    expect(valueFor('gastrointestinal', 'early_satiety')).toBe('early satiety');
  });
});
