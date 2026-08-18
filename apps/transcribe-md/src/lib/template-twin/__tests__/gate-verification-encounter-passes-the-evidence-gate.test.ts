import { describe, expect, it, vi } from 'vitest';
import { assertTemplateTwinSyntheticEvidencePhiFree } from '../synthetic-evidence-gate';
import { VERIFICATION_ENCOUNTER } from '../verification-encounter';

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
