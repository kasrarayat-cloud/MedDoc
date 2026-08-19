import { describe, expect, it } from 'vitest';
import {
  deriveVerificationEncounter,
  VERIFICATION_ENCOUNTER,
  MIN_CERTIFIED_FILLED_FIELDS,
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
    { originalLabel: l, clinicalConcept: 'measurement.diameter' },
    { originalLabel: 'REFLUX TIME (ms)', clinicalConcept: 'measurement.reflux_time' },
  ]),
  { originalLabel: 'CLINICAL INDICATIONS: Choose an item.', clinicalConcept: 'chief_complaint' },
  { originalLabel: 'Address', clinicalConcept: null },
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
    expect(addressed).toBeGreaterThanOrEqual(MIN_CERTIFIED_FILLED_FIELDS);
    expect(MIN_CERTIFIED_FILLED_FIELDS).toBe(10); // the threshold is NOT lowered
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
      { originalLabel: 'Subjective', clinicalConcept: 'chief_complaint' },
      { originalLabel: 'Assessment', clinicalConcept: 'assessment' },
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

/**
 * ⚠️ THE ARMS THE FIRST VERSION DID NOT HAVE, AND THEIR ABSENCE WAS THE DEFECT.
 *
 * The shipped test asserted the encounter's TEXT SHAPE — 20 diameter phrases, 20
 * reflux phrases, both branches present — and every arm passed while only EIGHT
 * distinct reflux values existed across those twenty cells.
 *
 * `bridge-evidence.ts:183` refuses a cell whose candidate facts disagree on side
 * (`sides.size > 1` -> `ambiguous_laterality`), and that check runs BEFORE the
 * row's own laterality can break the tie. So two legs sharing a number is not a
 * cosmetic dullness — it makes the cell UNFILLABLE. Measured downstream: 14 of
 * 20 reflux cells refused.
 *
 * A count of phrases is not a measure of whether any of them can address a cell.
 */
describe('every dictated value is globally unique — the cross-leg collision', () => {
  const text = deriveVerificationEncounter(ownersForm());
  const rows = [...text.matchAll(
    /(Right|Left) (.+?): diameter (\d+\.\d+) millimeters, reflux time (\d+\.\d+) seconds/g,
  )].map((m) => ({ side: m[1], vessel: m[2], diameter: m[3], reflux: m[4] }));

  it('the scan is non-vacuous — it found both legs of every vessel', () => {
    expect(rows.length).toBe(VESSELS.length * 2);
  });

  it('⚠️ NO VESSEL CARRIES THE SAME REFLUX VALUE ON BOTH LEGS', () => {
    const byVessel = new Map<string, string[]>();
    for (const r of rows) byVessel.set(r.vessel, [...(byVessel.get(r.vessel) ?? []), r.reflux]);
    const tied = [...byVessel.entries()].filter(([, v]) => v.length === 2 && v[0] === v[1]);
    expect(tied.map(([v]) => v), 'these cells can never fill — ambiguous_laterality').toEqual([]);
  });

  it('reflux values are distinct across the WHOLE encounter, not just per leg', () => {
    const refl = rows.map((r) => r.reflux);
    expect(new Set(refl).size).toBe(refl.length);
  });

  it('diameters are distinct across the whole encounter too', () => {
    const d = rows.map((r) => r.diameter);
    expect(new Set(d).size).toBe(d.length);
  });

  it('a value is never shared BETWEEN the diameter and reflux vocabularies', () => {
    // A reflux number equal to a diameter number invites the matcher to bind the
    // wrong quantity to a cell.
    const d = new Set(rows.map((r) => Number(r.diameter)));
    for (const r of rows) expect(d.has(Number(r.reflux))).toBe(false);
  });

  it('competence still straddles the 0.5s cutoff, so both branches are real', () => {
    const comp = rows.filter((r) => Number(r.reflux) < 0.5);
    const incomp = rows.filter((r) => Number(r.reflux) >= 0.5);
    expect(comp.length).toBeGreaterThan(0);
    expect(incomp.length).toBeGreaterThan(0);
  });
});

describe('a NON-venous form never receives a venous narrative', () => {
  /**
   * ⚠️ THE ONLY FINDING OF THE SET THAT COULD PUT INVENTED CLINICAL CONTENT INTO
   * A STORED ARTIFACT. The generator writes reflux times, competence verdicts and
   * a "no deep vein thrombosis" negative. Emitted for a thyroid or obstetric form
   * that merely carries measurement rows, that is fabrication.
   */
  it('a thyroid measurement form falls back to the generic encounter', () => {
    const thyroid: EncounterSourceField[] = [
      { originalLabel: 'Right thyroid lobe', clinicalConcept: 'measurement.length' },
      { originalLabel: 'Left thyroid lobe', clinicalConcept: 'measurement.length' },
      { originalLabel: 'Isthmus', clinicalConcept: 'measurement.depth' },
    ];
    const out = deriveVerificationEncounter(thyroid);
    expect(out).toBe(VERIFICATION_ENCOUNTER);

    // ⚠️ WHAT THIS ARM ASSERTS, PRECISELY: no measurement is DICTATED ABOUT THIS
    // FORM'S OWN ROWS. It deliberately does NOT assert the output is free of the
    // word "reflux" — an earlier draft of this arm did, and failed, because the
    // fallback constant is itself a venous encounter.
    //
    // ⚠️ AND THAT IS AN HONEST, PRE-EXISTING LIMIT, RECORDED RATHER THAN HIDDEN:
    // a non-venous template still certifies against a venous generic dictation.
    // It was true before F5-c for EVERY template and F5-c does not worsen it —
    // but it means a thyroid form's proof fills nothing and refuses at the gate,
    // which is the safe direction. Fixing it needs a per-specialty generic
    // encounter and is not in this change.
    expect(out).not.toMatch(/thyroid lobe: diameter/i);
    expect(out).not.toMatch(/Isthmus: diameter/i);
  });

  it('the venous form still qualifies — the guard is not simply off', () => {
    expect(deriveVerificationEncounter(ownersForm())).not.toBe(VERIFICATION_ENCOUNTER);
  });
});

describe('a large form degrades in LENGTH, never into a security-shaped refusal', () => {
  it('stays under the evidence gate\'s scan window for a 200-row form', () => {
    const huge: EncounterSourceField[] = Array.from({ length: 200 }, (_, i) => ({
      originalLabel: `GSV segment ${i} at the Proximal Thigh`,
      clinicalConcept: 'measurement.diameter',
    }));
    const out = deriveVerificationEncounter(huge);
    expect(out.length).toBeLessThan(12_000);
    // and it is still a real dictation, not the fallback
    expect(out).not.toBe(VERIFICATION_ENCOUNTER);
    const n = (out.match(/diameter \d+\.\d+ millimeters/g) ?? []).length;
    expect(n).toBeGreaterThanOrEqual(MIN_CERTIFIED_FILLED_FIELDS);
  });
});

describe('the whole measurement family is enumerated, not a hand-kept pair', () => {
  it('a velocity-based venous form is still dictated', () => {
    const velocity: EncounterSourceField[] = [
      { originalLabel: 'GSV at the SFJ', clinicalConcept: 'measurement.velocity' },
      { originalLabel: 'SSV at the SPJ', clinicalConcept: 'measurement.velocity' },
    ];
    expect(deriveVerificationEncounter(velocity)).not.toBe(VERIFICATION_ENCOUNTER);
  });
});
