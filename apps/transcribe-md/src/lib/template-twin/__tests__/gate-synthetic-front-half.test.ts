import { createHash } from 'node:crypto';

import { describe, it, expect, vi } from 'vitest';

// The synthetic-evidence PHI gate makes a model call; stub it so this pins the
// SHARED front-half's own logic (derive → sha), not the gate. The gate's real
// behaviour is covered by gate-verification-encounter-passes-the-evidence-gate.
vi.mock('../synthetic-evidence-gate', () => ({
  assertTemplateTwinSyntheticEvidencePhiFree: vi.fn(async () => {}),
}));

import { deriveSyntheticEncounter } from '../synthetic-front-half';

// Ruling #326: `deriveSyntheticEncounter` is the ONE shared front-half both the
// DOCX-twin proof and the detected-form proof run. The byte-identity gate that
// the DOCX proof is unchanged is the 45 synthetic-cert gates passing after the
// extraction; this pins the shared function's own contract so a future edit to
// it is caught here rather than in a re-cert.

const ACTOR = { practiceId: 'p1', userId: 'u1' } as never;
const TEXT =
  'Synthetic example encounter: screening colonoscopy to the cecum, adequate prep, no active bleeding.';

describe('deriveSyntheticEncounter — the shared #326 synthetic front-half', () => {
  it('returns the encounter text and a byte-stable content hash (sha256 of the text)', async () => {
    const r = await deriveSyntheticEncounter({
      deriveEncounter: () => ({ ok: true, text: TEXT }) as never,
      actor: ACTOR,
      totalFields: 5,
    });
    expect(r.encounterText).toBe(TEXT);
    // the extraction must compute exactly sha256(encounterText) — the same hash
    // the DOCX proof keys its pin on; any drift changes the certification key.
    expect(r.encounterSha256).toBe(createHash('sha256').update(TEXT).digest('hex'));
  });

  it('refuses a non-derivable encounter with ENCOUNTER_NOT_DERIVABLE, carrying totalFields', async () => {
    await expect(
      deriveSyntheticEncounter({
        deriveEncounter: () => ({ ok: false, reason: 'no_measurement_rows' }) as never,
        actor: ACTOR,
        totalFields: 7,
      }),
    ).rejects.toThrow(/self-test that matches this form/);
  });
});
