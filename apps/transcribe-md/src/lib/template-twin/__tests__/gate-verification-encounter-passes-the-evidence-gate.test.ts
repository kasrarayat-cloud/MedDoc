import { describe, expect, it, vi } from 'vitest';
import { assertTemplateTwinSyntheticEvidencePhiFree } from '../synthetic-evidence-gate';
import {
  deriveVerificationEncounter,
  narrativeSentence,
  VERIFICATION_ENCOUNTER,
  type EncounterSourceField,
} from '../verification-encounter';

/**
 * ⚠️ THE GUARD THAT WAS MISSING, AND ITS ABSENCE WAS THE WHOLE DEFECT.
 *
 * Every unit suite around certification mocks `runTemplateTwinSyntheticTest`
 * wholesale. That is reasonable — it is slow and it calls a model — but it
 * means NOTHING in 3800 tests ever fed `VERIFICATION_ENCOUNTER` to the gate
 * that actually inspects it.
 *
 * The gate requires an explicit synthetic marker and throws
 * `SYNTHETIC_EVIDENCE_REJECTED` **before any model call** when it is absent.
 * `VERIFICATION_ENCOUNTER` carried no such marker, so the round-trip proof
 * could never pass — no template could certify by ANY path, in ANY
 * environment. Found by the QA walk, not by the suite.
 *
 * This calls the REAL gate. It does not re-implement the regex: a copied
 * predicate drifts from its original the day either one changes, and then the
 * guard passes while the product refuses.
 */
const cleanScan = {
  complete: vi.fn(async () => ({
    appearsExplicitlySynthetic: true,
    anyUncertain: false,
    directIdentifierClasses: [] as string[],
  })),
};

const ACTOR = { practiceId: 'p1', userId: 'u1' };

describe('VERIFICATION_ENCOUNTER vs the synthetic-evidence gate', () => {
  it('passes the gate the certification path actually runs it through', async () => {
    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        encounterText: VERIFICATION_ENCOUNTER,
        ...ACTOR,
        client: cleanScan as never,
      }),
    ).resolves.toBeUndefined();
  });

  it('⚠️ MUTATION PROOF: strip the synthetic label and the gate REFUSES', async () => {
    // The partial edit a tired person actually makes: dropping the label line
    // while leaving the clinical content intact. Not a total inverse.
    const withoutLabel = VERIFICATION_ENCOUNTER.split(' ')
      .filter((w) => !/synthetic|fictional|example|test/i.test(w))
      .join(' ');
    expect(withoutLabel.length).toBeGreaterThan(50); // still substantial text

    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        encounterText: withoutLabel,
        ...ACTOR,
        client: cleanScan as never,
      }),
    ).rejects.toThrow();
  });

  it('the refusal happens BEFORE any model call — it is deterministic', async () => {
    const spy = { complete: vi.fn() };
    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        encounterText: 'Bilateral lower extremity venous reflux study, standing.',
        ...ACTOR,
        client: spy as never,
      }),
    ).rejects.toThrow();
    // If this ever calls the model, the gate has become environment-dependent
    // and a green here would stop meaning anything in production.
    expect(spy.complete).not.toHaveBeenCalled();
  });
});

/* ──────────────────────────────────────────────────────────────────────────
 * #312 — THE DERIVED ENCOUNTER NAMES A ROLE, NEVER A PERSON.
 * ──────────────────────────────────────────────────────────────────────────
 *
 * ⚠️ MEASURED, NOT IMAGINED. Certifying the owner's re-issued consult form was
 * REFUSED by this gate. Ruling #312 confirmed that form's `Referring MD` row as
 * dictated evidence, so the narrative generator's referrer sentence reached a
 * real certification for the first time — and that sentence named a fictional
 * physician. The model scan answered:
 *
 *   {"directIdentifierClasses":["referring provider name"],
 *    "appearsExplicitlySynthetic":true,"anyUncertain":true}
 *
 * The same derived encounter with the referrer as a ROLE was run through the
 * REAL gate before this arm was written: [] / true / false, GATE PASSED.
 *
 * ⚠️ WHAT THIS BLOCK CAN AND CANNOT SAY. The model scan cannot run in CI, so it
 * pins the deterministic half: the generated text carries no title-plus-name
 * shape anywhere, it still carries the referrer sentence (so the `Referring MD`
 * control still has a dictated value to fill from), and it clears the gate's
 * own pre-model checks. The sentence is pinned VERBATIM because the real-gate
 * proof was made on exactly that text; changing it means re-running the real
 * gate, and this block reddening is how the next author finds that out.
 */

const REFERRER_CONCEPT = 'visit_metadata.referring_physician';

/** A courtesy title followed by a capitalised word — "Dr. Alan Whitfield",
 *  "Dr Ramirez", "Mrs. Osei". One capitalised word is enough: a surname alone
 *  is still a person. */
const TITLED_PERSON = /\b(?:Dr|Doctor|Mr|Mrs|Ms|Miss|Prof|Professor)\.?\s+[A-Z][A-Za-z'’-]+/;

/** Two adjacent capitalised words — a bare "Alan Whitfield". Applied to the
 *  referrer sentence only, which is where a name would go; across the whole
 *  text a sentence-initial capital would make it noisy rather than strict. */
const BARE_FULL_NAME = /\b[A-Z][a-z'’-]+\s+[A-Z][a-z'’-]+\b/;

/** A consult-shaped field set: the owner's `Referring MD` row beside the other
 *  narrative families the generator speaks to, so the scan reads everything a
 *  consult certification dictates, not the referrer line alone. */
const CONSULT_WITH_REFERRER: EncounterSourceField[] = [
  { originalLabel: 'Referring MD', clinicalConcept: REFERRER_CONCEPT },
  { originalLabel: 'Chief Complaint', clinicalConcept: 'chief_complaint' },
  { originalLabel: 'Onset', clinicalConcept: 'hpi.onset' },
  { originalLabel: 'PMH', clinicalConcept: 'past_medical_history' },
  { originalLabel: 'PSH', clinicalConcept: 'past_surgical_history' },
  { originalLabel: 'Family History', clinicalConcept: 'family_history' },
  { originalLabel: 'Social History', clinicalConcept: 'social_history' },
  { originalLabel: 'Marital', clinicalConcept: 'social_history.marital_status' },
  { originalLabel: 'Total minutes', clinicalConcept: 'total_time_minutes' },
  { originalLabel: 'Medications', clinicalConcept: 'medication' },
  { originalLabel: 'Allergies', clinicalConcept: 'allergy' },
  { originalLabel: 'Abdomen', clinicalConcept: 'exam.abdomen' },
  { originalLabel: 'Assessment', clinicalConcept: 'assessment' },
  { originalLabel: 'Plan', clinicalConcept: 'plan' },
];

function derivedText(fields: EncounterSourceField[]): string {
  const out = deriveVerificationEncounter(fields);
  if (!out.ok) throw new Error(`expected a derived encounter, got refusal: ${out.reason}`);
  return out.text;
}

describe('#312 — the derived consult encounter names a ROLE, never a person', () => {
  it('the referrer sentence is the one the REAL gate passed — pinned verbatim', () => {
    expect(narrativeSentence(REFERRER_CONCEPT)).toBe(
      'The patient was referred by their primary care physician for further evaluation.',
    );
  });

  it('⚠️ the derived encounter carries NO titled or full personal name, anywhere', () => {
    const text = derivedText(CONSULT_WITH_REFERRER);
    // NON-VACUITY: every row in the set contributed its own sentence, so the
    // scan below read the whole consult dictation rather than a fragment.
    for (const f of CONSULT_WITH_REFERRER) {
      const sentence = narrativeSentence(f.clinicalConcept!);
      expect([f.clinicalConcept, sentence !== null && text.includes(sentence)]).toEqual([
        f.clinicalConcept,
        true,
      ]);
    }
    expect(text.match(TITLED_PERSON)).toBeNull();
    expect(narrativeSentence(REFERRER_CONCEPT)!.match(BARE_FULL_NAME)).toBeNull();
  });

  it('⚠️ AND IT STILL DICTATES A REFERRER, so the Referring MD control has a value to fill from', () => {
    const text = derivedText(CONSULT_WITH_REFERRER);
    const sentence = narrativeSentence(REFERRER_CONCEPT);
    expect(sentence).not.toBeNull();
    expect(text).toContain(sentence!);
    // The cue the extractor's referrer field keys on: who REFERRED the patient.
    expect(sentence!).toMatch(/\breferred by\b/);
    // And it is there because of the row, not by accident — drop the row and
    // the sentence goes with it.
    const without = derivedText(
      CONSULT_WITH_REFERRER.filter((f) => f.clinicalConcept !== REFERRER_CONCEPT),
    );
    expect(without).not.toContain(sentence!);
  });

  it('clears the gate’s deterministic stage and REACHES the model scan', async () => {
    const scan = {
      complete: vi.fn(async () => ({
        appearsExplicitlySynthetic: true,
        anyUncertain: false,
        directIdentifierClasses: [] as string[],
      })),
    };
    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        encounterText: derivedText(CONSULT_WITH_REFERRER),
        ...ACTOR,
        client: scan as never,
      }),
    ).resolves.toBeUndefined();
    // Reaching the scan is the point: a deterministic refusal never calls it.
    expect(scan.complete).toHaveBeenCalledTimes(1);
  });

  it('⚠️ NON-VACUITY: the patterns catch the sentence the real gate REFUSED', () => {
    // The exact text the gate refused. Kept here, and only here, as the control
    // that proves the two patterns above can fail.
    const refused = 'The patient was referred by Dr. Alan Whitfield for further evaluation.';
    expect(TITLED_PERSON.test(refused)).toBe(true);
    expect(TITLED_PERSON.test('She was referred by Dr Ramirez.')).toBe(true);
    expect(BARE_FULL_NAME.test('The patient was referred by Alan Whitfield for evaluation.')).toBe(
      true,
    );
  });
});
