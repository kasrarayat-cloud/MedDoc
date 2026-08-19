import { describe, expect, it } from 'vitest';
import {
  deriveVerificationEncounter,
  VERIFICATION_ENCOUNTER,
  LIFECYCLE_MIN_FILLED_FIELDS,
  type EncounterSourceField,
} from '../verification-encounter';
import { assertTemplateTwinSyntheticEvidencePhiFree } from '../synthetic-evidence-gate';

/**
 * F5-c — THE ENCOUNTER MUST EXERCISE THE FORM IT CERTIFIES.
 *
 * ⚠️ THE FIXTURE IS THE OWNER'S REAL FORM SHAPE, read from production on
 * 2026-08-19: 13 vessel rows per leg, each wanting a diameter and a reflux time,
 * three of them literal placeholders (`Saphenous Tributary Vein <<insert
 * location>>`). A fixture invented here would be the wrong-universe failure this
 * repository has paid for twice.
 */
const VESSELS = [
  'GSV at the SFJ',
  'GSV at the Proximal Thigh',
  'GSV at the Knee',
  'GSV Below Knee',
  'SSV at the SPJ',
  'SSV at the Proximal Calf',
  'AAGSV at the SFJ',
  'AAGSV at the Proximal Thigh',
  'PAGSV at the SFJ',
  'PAGSV at the Proximal Thigh',
];
const PLACEHOLDERS = [
  'Saphenous Tributary Vein &lt;&lt;insert location&gt;&gt;',
  'Saphenous Tributary Vein &lt;&lt;insert location&gt;&gt;',
  'Saphenous Tributary Vein &lt;&lt;insert location&gt;&gt;',
];

const ownersForm = (): EncounterSourceField[] => [
  ...[...VESSELS, ...PLACEHOLDERS].flatMap((l) => [
    { originalLabel: l, clinicalConcept: 'measurement.diameter', laterality: null },
    { originalLabel: 'REFLUX TIME (ms)', clinicalConcept: 'measurement.reflux_time', laterality: null },
  ]),
  { originalLabel: 'CLINICAL INDICATIONS: Choose an item.', clinicalConcept: 'chief_complaint', laterality: null },
  { originalLabel: 'Address', clinicalConcept: null, laterality: null },
];

describe('the derived encounter speaks to the template it certifies', () => {
  const text = deriveVerificationEncounter(ownersForm());

  it('names every real vessel segment, on BOTH legs', () => {
    for (const v of VESSELS) {
      expect(text, `missing: ${v}`).toContain(`Right ${v}`);
      expect(text, `missing: ${v}`).toContain(`Left ${v}`);
    }
  });

  it('⚠️ addresses at least the threshold the lifecycle gate enforces', () => {
    // The generic constant filled 7 against this form and was refused at >= 10.
    const addressed = VESSELS.length * 2;
    expect(addressed).toBeGreaterThanOrEqual(LIFECYCLE_MIN_FILLED_FIELDS);
    expect(LIFECYCLE_MIN_FILLED_FIELDS).toBe(10); // the threshold is NOT lowered
  });

  it('dictates a diameter AND a reflux time for each — a measurement CELL is required', () => {
    const diam = text.match(/diameter \d+\.\d+ millimeters/g) ?? [];
    const refl = text.match(/reflux time \d+\.\d+ seconds/g) ?? [];
    expect(diam.length).toBe(VESSELS.length * 2);
    expect(refl.length).toBe(VESSELS.length * 2);
  });

  it('⚠️ NEVER dictates a placeholder row — that would be inventing a finding', () => {
    expect(text).not.toContain('insert location');
    expect(text).not.toContain('<<');
    expect(text).not.toMatch(/Saphenous Tributary/);
  });

  it("the reflux column's unit HEADER is not mistaken for a vessel", () => {
    // 'REFLUX TIME (ms)' addresses no row; dictating it would produce a row
    // label that aligns with nothing.
    expect(text).not.toMatch(/Right REFLUX TIME/i);
    expect(text).not.toMatch(/Left REFLUX TIME/i);
  });

  it('exercises BOTH the competent and the incompetent branch', () => {
    expect(text).toMatch(/competent, within normal limits/);
    expect(text).toMatch(/; incompetent\./);
  });

  it('is DETERMINISTIC — two derivations are byte-identical', () => {
    expect(deriveVerificationEncounter(ownersForm())).toBe(text);
  });

  it('still passes the evidence gate that blocked everything before', async () => {
    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        encounterText: text,
        practiceId: 'p1',
        userId: 'u1',
        client: {
          complete: async () => ({
            appearsExplicitlySynthetic: true,
            anyUncertain: false,
            directIdentifierClasses: [] as string[],
          }),
        } as never,
      }),
    ).resolves.toBeUndefined();
  });

  it('stays inside the gate\'s 12,000-char scan window', () => {
    expect(text.length).toBeLessThan(12_000);
  });
});

describe('templates with nothing to enumerate fall back, not break', () => {
  it('a SOAP-shaped template gets the generic encounter', () => {
    const soap: EncounterSourceField[] = [
      { originalLabel: 'Subjective', clinicalConcept: 'chief_complaint', laterality: null },
      { originalLabel: 'Assessment', clinicalConcept: 'assessment', laterality: null },
    ];
    expect(deriveVerificationEncounter(soap)).toBe(VERIFICATION_ENCOUNTER);
  });

  it('an empty field set falls back rather than emitting a bare marker', () => {
    expect(deriveVerificationEncounter([])).toBe(VERIFICATION_ENCOUNTER);
  });

  it('⚠️ a form of ONLY placeholders falls back — it has no real anatomy', () => {
    const onlyPlaceholders: EncounterSourceField[] = PLACEHOLDERS.map((l) => ({
      originalLabel: l,
      clinicalConcept: 'measurement.diameter',
      laterality: null,
    }));
    expect(deriveVerificationEncounter(onlyPlaceholders)).toBe(VERIFICATION_ENCOUNTER);
  });
});
