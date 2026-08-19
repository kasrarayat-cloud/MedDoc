/**
 * THE SYNTHETIC ENCOUNTER certification attests against.
 *
 * ⚠️ IT LIVES HERE, NOT IN THE ACTION, BECAUSE A `'use server'` FILE MAY EXPORT
 * ASYNC FUNCTIONS ONLY. Exporting this const from `template-twin-certify.ts`
 * made Next refuse to evaluate the module, and every page importing it would
 * have failed to render. `use-server-exports.test.ts` caught it — a guard that
 * exists precisely because this trap has been paid for before.
 *
 * ⚠️ AND IT IS ONE CONSTANT, SHARED. The manual certify action and the
 * auto-certify worker job both attest against THIS text. Two verification
 * encounters would mean the automatic path proved something the manual path
 * never did, and neither reader could say what their template actually passed.
 */
export const VERIFICATION_ENCOUNTER = [
  // ⚠️ THE FIRST LINE IS LOAD-BEARING, NOT A COMMENT ABOUT THE DATA.
  // `assertTemplateTwinSyntheticEvidencePhiFree` requires an EXPLICIT synthetic
  // marker — /\b(synthetic|fictional|mock(ed)?|test(ing)?( only)?|example)\b/i —
  // and throws `SYNTHETIC_EVIDENCE_REJECTED` **deterministically, before any
  // model call**, when it is absent. Without this line the round-trip proof can
  // never pass, so NO template can ever certify: not by the manual path, not by
  // the automatic one, and not in any environment.
  //
  // Found by the QA walk on 2026-08-18. The unit suites mock
  // `runTemplateTwinSyntheticTest` wholesale, so none of them ever reached this
  // gate. `gate-verification-encounter-passes-the-evidence-gate.test.ts` now
  // asserts the marker against the gate's OWN regex, imported rather than
  // copied — a second copy would drift from the first the day either changes.
  'Synthetic certification test encounter — fictional example data, no real patient.',
  'Bilateral lower extremity venous reflux study, standing, with distal augmentation.',
  'Indication: bilateral leg heaviness, aching, and visible varicosities.',
  'Right great saphenous vein 6.2 millimeters at the saphenofemoral junction with reflux time 3.4 seconds; incompetent.',
  'Right small saphenous vein competent, no reflux. Left great saphenous vein 4.8 millimeters, reflux 0.4 seconds, within normal limits.',
  'Deep venous system patent bilaterally, compressible, phasic, no deep vein thrombosis.',
].join(' ');

/* ──────────────────────────────────────────────────────────────────────────
 * F5-c — THE ENCOUNTER IS DERIVED FROM THE FORM IT CERTIFIES
 * ──────────────────────────────────────────────────────────────────────────
 *
 * ⚠️ WHY: the constant above certifies nothing on a real form. Measured on the
 * owner's production template (2026-08-19, real model, real backfill):
 *
 *     fillCoverage=false (7 filled, need >= 10 — the synthetic encounter must
 *     exercise a realistic fill, or the certificate attests a template whose
 *     fill path is dead)
 *
 * The form is an 80-field venous duplex report: 13 vessel rows per leg, each
 * wanting a DIAMETER and a REFLUX TIME. The generic encounter names three of
 * those segments, so seven cells filled and certification refused — correctly.
 *
 * ⚠️ THE THRESHOLD IS NEVER LOWERED. A certificate over a dead fill path is
 * exactly what that gate exists to refuse. The encounter is made richer; the
 * gate keeps its teeth.
 *
 * HOW THE FILL ACTUALLY HAPPENS, because the shape of this function follows
 * from it: the model writes a markdown TABLE, and `bridge-fill.ts` aligns each
 * generated row label against the IR row label by TOKEN SET (not substring —
 * "gsv sfj" must not match "aagsv sfj"). So the encounter must dictate the
 * segments BY THEIR OWN NAMES, and the names come from the compiled field set.
 */

/** The minimum the lifecycle gate requires. Named so the relationship between
 *  this generator and the gate is legible from here, and asserted by
 *  `gate-derived-encounter-exercises-the-form.test.ts`. */
export const LIFECYCLE_MIN_FILLED_FIELDS = 10;

export interface EncounterSourceField {
  originalLabel: string | null;
  clinicalConcept: string | null;
  laterality?: string | null;
}

/** Placeholder rows carry no anatomy — the customer form literally contains
 *  `Saphenous Tributary Vein <<insert location>>` three times per leg. Dictating
 *  a measurement for a location nobody named would be inventing a finding. */
const PLACEHOLDER = /<<.*?>>|&lt;&lt;.*?&gt;&gt;/;

const MEASUREMENT_CONCEPTS = new Set([
  'measurement.diameter',
  'measurement.reflux_time',
]);

/**
 * Deterministic, index-derived values. NO randomness: a certification proof that
 * varies run to run cannot be compared against itself, and `Math.random()` in a
 * generator that feeds a stored artifact makes every re-run a different document.
 *
 * The spread is deliberate rather than decorative: diameters straddle the
 * clinically ordinary 3–8 mm band, and reflux alternates either side of the
 * 0.5 s competence cutoff so a run exercises BOTH the competent and the
 * incompetent branch instead of proving one of them twice.
 */
function diameterFor(index: number): string {
  return (3.2 + ((index * 7) % 45) / 10).toFixed(1);
}
function refluxFor(index: number): { seconds: string; competent: boolean } {
  const competent = index % 2 === 0;
  return {
    seconds: competent ? (0.2 + (index % 3) / 10).toFixed(1) : (1.1 + (index % 5) / 2).toFixed(1),
    competent,
  };
}

/**
 * Build a synthetic dictation that speaks to THIS template's own measurement
 * rows. Falls back to the generic encounter when a template has no measurement
 * fields at all — a SOAP-shaped template has nothing to enumerate, and the
 * generic text is right for it.
 */
export function deriveVerificationEncounter(
  fields: readonly EncounterSourceField[],
): string {
  const labels: string[] = [];
  const seen = new Set<string>();
  for (const f of fields) {
    if (!f.clinicalConcept || !MEASUREMENT_CONCEPTS.has(f.clinicalConcept)) continue;
    const label = (f.originalLabel ?? '').trim();
    if (!label || PLACEHOLDER.test(label)) continue;
    // The reflux column's own label is a UNIT HEADER ("REFLUX TIME (ms)"), not a
    // vessel. It addresses no row and must not become a dictated segment.
    if (/^reflux\s+time/i.test(label)) continue;
    const key = label.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    labels.push(label);
  }

  if (labels.length === 0) return VERIFICATION_ENCOUNTER;

  const lines: string[] = [
    // ⚠️ LOAD-BEARING: the evidence gate requires an explicit synthetic marker
    // and throws SYNTHETIC_EVIDENCE_REJECTED, before any model call, without it.
    'Synthetic certification test encounter — fictional example data, no real patient.',
    'Bilateral lower extremity venous reflux study, standing, with distal augmentation.',
    'Indication: bilateral leg heaviness, aching, and visible varicosities.',
  ];

  // Both legs, because the form carries each row twice and a one-legged
  // dictation leaves half the table unaddressed — and because the laterality
  // arms downstream only mean something when a side is actually said.
  for (const side of ['Right', 'Left'] as const) {
    labels.forEach((label, i) => {
      const idx = side === 'Right' ? i : i + labels.length;
      const d = diameterFor(idx);
      const r = refluxFor(idx);
      lines.push(
        `${side} ${label}: diameter ${d} millimeters, reflux time ${r.seconds} seconds` +
          `${r.competent ? '; competent, within normal limits.' : '; incompetent.'}`,
      );
    });
  }

  lines.push(
    'Deep venous system patent bilaterally, compressible, phasic, no deep vein thrombosis.',
  );
  return lines.join(' ');
}
