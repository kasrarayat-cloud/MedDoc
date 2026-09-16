// The shared synthetic-proof FRONT-HALF (ruling #326). BOTH the DOCX-twin proof
// (runTemplateTwinSyntheticTest) and the detected-form proof (certifyDetectedForm)
// call `deriveSyntheticEncounter`, so the ruled encounter handling and the
// synthetic-evidence PHI gate live in ONE place and cannot drift between them.
//
// This is a LIGHT module on purpose: it imports only the error class, the PHI
// gate, and node:crypto — no prisma, no fill-engine, no worker. That lets the
// detected-form certify reuse it without pulling the heavy synthetic-test graph,
// and lets it be unit-tested with just the PHI gate stubbed.
//
// Extract → project (extractEntities + projectEncounterFacts) are already shared
// standalone functions the callers compose after this.
import { createHash } from 'node:crypto';

import type { TemplateTwinActor } from './certification-lifecycle';
import { assertTemplateTwinSyntheticEvidencePhiFree } from './synthetic-evidence-gate';
import { TemplateTwinSyntheticTestError } from './synthetic-test-error';
import type { DerivedEncounter } from './verification-encounter';

/**
 * derive the synthetic encounter, gate it as synthetic (PHI), and content-hash
 * it. Pure — no persistence, no pin, no DOCX/detected-form specifics.
 */
export async function deriveSyntheticEncounter(input: {
  deriveEncounter: () => DerivedEncounter;
  actor: TemplateTwinActor;
  totalFields: number;
}): Promise<{ encounterText: string; encounterSha256: string }> {
  const derived = input.deriveEncounter();
  if (!derived.ok) {
    throw new TemplateTwinSyntheticTestError(
      'ENCOUNTER_NOT_DERIVABLE',
      'We could not generate a self-test that matches this form, so nothing was certified.',
      { blocking: [derived.reason], totalFields: input.totalFields },
    );
  }
  const encounterText = derived.text;
  // Gate the encounter before Layer 3 or storage so a mislabeled real encounter
  // is never persisted as a synthetic proof.
  try {
    await assertTemplateTwinSyntheticEvidencePhiFree({
      encounterText,
      practiceId: input.actor.practiceId,
      userId: input.actor.userId,
    });
  } catch {
    throw new TemplateTwinSyntheticTestError(
      'SYNTHETIC_EVIDENCE_REJECTED',
      'Use clearly labeled synthetic test evidence without patient identifiers.',
    );
  }
  const encounterSha256 = createHash('sha256').update(encounterText).digest('hex');
  return { encounterText, encounterSha256 };
}
