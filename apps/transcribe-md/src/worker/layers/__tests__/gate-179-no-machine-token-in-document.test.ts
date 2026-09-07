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
import {
  SAMPLE_PREVIEW_ENTITIES,
  SAMPLE_PREVIEW_TRANSCRIPT,
} from '@/worker/note-templates/sample-preview-transcript';

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
        // ⚠️ #218 — `other` IS NO LONGER SKIPPED. It used to `continue` here,
        // and that one line is why the literal word "other" reached a document
        // for a year: the sweep that claimed to stop machine tokens excluded
        // the only token that is PURELY a machine token. A guard that skips its
        // own hardest case is not a guard.
        const value = valueFor(system, token);
        if (value.includes('_')) offenders.push(`${system}.${token} -> ${value}`);
        // ⚠️ NARROWED, AND THE FIRST FORM OF THIS LINE WAS WRONG. It read
        // `value === token`, which flags `dizziness -> dizziness` — a token with
        // no underscore correctly printing itself. The identity check only means
        // anything for the escape hatch, which is a PURE machine token and must
        // never appear at all.
        if (token === ROS_OTHER && value !== '') {
          offenders.push(`${system}.${token} -> printed the escape hatch as "${value}"`);
        }
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

  it('⚠️ #218 — AND NOTHING IS REFUSED, NOT FILLED. The blank must never read as a value.', async () => {
    // ⚠️ THIS ARM EXISTS BECAUSE THE FIRST FIX OPENED THE DEFECT BESIDE THE ONE
    // IT CLOSED. Blanking stopped the token printing — and `''` then flowed
    // through as an ordinary string: the resolver minted `supported`, the
    // validator computed `populated = value !== null` and returned VALID with
    // zero issues, and the renderer emitted a **`filled`** proof over a control
    // it had just emptied, destroying the template's own placeholder prose.
    //
    // That is strictly worse than what it replaced. Printing `other` was wrong
    // and VISIBLE; a silent blank attested as filled is wrong and invisible, and
    // it also satisfies `fill-engine`'s `counts.filled > 0` — the only check
    // between a doctor and an empty document.
    const { deriveFieldValueFromFact } = await import('@/lib/template-twin/field-value-derivation');
    const field = { kind: 'narrative_text', allowedOptions: [] } as unknown as Parameters<
      typeof deriveFieldValueFromFact
    >[0];
    const factWith = (value: string) => ({ value }) as unknown as Parameters<typeof deriveFieldValueFromFact>[2];

    expect(deriveFieldValueFromFact(field, undefined, factWith(''))).toBeNull();
    expect(deriveFieldValueFromFact(field, undefined, factWith('   '))).toBeNull();
    // NON-VACUITY: a real value still derives, so the refusal is about emptiness
    // and not about narrative fields having stopped working.
    expect(deriveFieldValueFromFact(field, undefined, factWith('belching'))).toBe('belching');
  });

  it('⚠️ #218 — the BARE escape hatch prints NOTHING, not the word "other"', () => {
    // With no doctor-supplied words there is no finding to state. Saying
    // "other" is not a weaker answer than saying nothing; it is a wrong one,
    // and it arrives with status=supported and zero issues.
    expect(valueFor('neurologic', ROS_OTHER)).toBe('');
    expect(valueFor('gastrointestinal', ROS_OTHER)).toBe('');
  });

  it('⚠️ #218 — a REAL token filed under the WRONG system still de-slugs', () => {
    // The shape the previous arm could not construct: it swept
    // `system x symptomsFor(system)` only, so a token paired with a system that
    // does not carry it was outside the watched set entirely. The resolver
    // coerces the finding to `other` and seats the MODEL'S OWN TOKEN in
    // `finding_verbatim`, which then took the left branch of the `??` and
    // skipped the de-slugger.
    expect(valueFor('endocrine', 'weight_loss')).toBe('weight loss');
    expect(valueFor('general', 'night_sweats')).toBe('night sweats');
    expect(valueFor('ent', 'sore_throat')).toBe('sore throat');
  });

  it('⚠️ #218 — CROSS-SYSTEM SWEEP: no pairing of any system with any token prints an identifier', () => {
    const offenders: string[] = [];
    for (const system of ROS_SYSTEMS) {
      for (const other of ROS_SYSTEMS) {
        if (other === system) continue;
        for (const token of symptomsFor(other)) {
          if (!token.includes('_')) continue; // only underscored tokens can expose the defect
          const value = valueFor(system, token);
          if (value.includes('_')) offenders.push(`${system}/${token} -> ${value}`);
        }
      }
    }
    expect(
      offenders,
      `cross-system machine tokens reaching the document: ${offenders.slice(0, 5).join('; ')}`,
    ).toEqual([]);
  });

  it('⚠️ #218 — THE SHIPPED FIXTURE\'S OWN ROW: the sample preview carries no machine token', () => {
    // ⚠️ THE ARM HAS A REAL INPUT AND DID NOT NEED AN INVENTED ONE. The repo's
    // own demo data emits `{ system: 'neurologic', finding: 'other',
    // polarity: 'denied' }` with no `finding_verbatim` — the exact defect —
    // and this is the preview a doctor is shown in Settings.
    const facts = projectEncounterFacts({
      mode: 'dictation',
      contextText: SAMPLE_PREVIEW_TRANSCRIPT,
      entities: SAMPLE_PREVIEW_ENTITIES as unknown as Parameters<
        typeof projectEncounterFacts
      >[0]['entities'],
    });
    const ros = facts.filter((f) => f.concept.startsWith('ros.'));
    expect(ros.length, 'the fixture projected no ROS facts — the arm is vacuous').toBeGreaterThan(0);
    const bad = ros
      .map((f) => String(f.value))
      .filter((v) => v.includes('_') || v === ROS_OTHER);
    expect(bad, `machine tokens in the shipped sample preview: ${bad.join('; ')}`).toEqual([]);
  });
});
