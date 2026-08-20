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

/**
 * ⚠️ BOUND TO THE GATE, NOT COPIED FROM IT. An earlier draft declared its own
 * `LIFECYCLE_MIN_FILLED_FIELDS = 10` beside the real, then-private
 * `MIN_CERTIFIED_FILLED_FIELDS` in `certification-lifecycle.ts`. Two constants
 * for one threshold drift the day either moves, and the copy is the one nobody
 * re-reads. Found by the adversarial pass.
 */
export { MIN_CERTIFIED_FILLED_FIELDS } from './certification-thresholds';

export interface EncounterSourceField {
  originalLabel: string | null;
  clinicalConcept: string | null;
}

/** Placeholder rows carry no anatomy — the customer form literally contains
 *  `Saphenous Tributary Vein <<insert location>>` three times per leg. Dictating
 *  a measurement for a location nobody named would be inventing a finding. */
const PLACEHOLDER = /<<.*?>>|&lt;&lt;.*?&gt;&gt;/;

/**
 * ⚠️ THE WHOLE MEASUREMENT FAMILY, READ FROM THE REGISTRY'S OWN VOCABULARY.
 * An earlier draft hand-kept `{diameter, reflux_time}` — 2 of the registry's 5 —
 * so a form whose rows carry `measurement.velocity` or `.length` produced NO
 * dictation and silently fell back to the generic encounter. A hand-kept subset
 * of somebody else's list is wrong eventually.
 */
const MEASUREMENT_PREFIX = 'measurement.';

/**
 * ⚠️ THE NARRATIVE IS VENOUS, SO IT IS ONLY EMITTED FOR A VENOUS FORM.
 * The generator dictates reflux times, competence verdicts and a
 * "no deep vein thrombosis" negative. On a NON-venous form carrying measurement
 * rows — a thyroid or obstetric study — that is FABRICATED CLINICAL CONTENT in
 * a document the certification stores. Found by the adversarial pass's
 * clinical lens, and it is the only finding of the set that could have put
 * invented findings into an artifact.
 *
 * The evidence for "venous" is the form's OWN labels, not a guess about the
 * doctor: a venous duplex names its saphenous/femoral/popliteal segments.
 */
const VENOUS_TOKEN =
  /\b(gsv|ssv|aagsv|pagsv|saphenous|femoral|popliteal|perforator|tibial|reflux|varicos)\b/i;

/**
 * Deterministic values. NO randomness: a proof that varies run to run cannot be
 * compared against itself, and this text feeds a stored artifact.
 *
 * ⚠️ AND EVERY VALUE IS GLOBALLY UNIQUE ACROSS THE WHOLE ENCOUNTER, WHICH IS
 * THE ENTIRE POINT AND WAS THE BUG.
 *
 * The first version derived values from `index % 3` / `index % 5`. With the
 * owner's ten-vessel form the left leg's index is `i + 10`, and `10 % 5 === 0`,
 * so EVERY incompetent vessel got the IDENTICAL reflux value on both legs — 8
 * distinct values across 20 cells, measured. `bridge-evidence.ts:183` then
 * refuses a cell whose candidate facts disagree on side
 * (`sides.size > 1 -> ambiguous_laterality`), and that check runs BEFORE the
 * row's own laterality can break the tie. Measured downstream: 14 of 20 reflux
 * cells refused, one filled citing a DIFFERENT vein.
 *
 * The gate could not see it — 20 diameters alone clear the >= 10 threshold — so
 * certification would have SUCCEEDED on a proof that never once exercised an
 * incompetent-vein cell.
 */
function measurementValues(count: number): { diameter: string; reflux: string; competent: boolean }[] {
  const out: { diameter: string; reflux: string; competent: boolean }[] = [];
  for (let k = 0; k < count; k += 1) {
    const competent = k % 2 === 0;
    out.push({
      // 3.10 .. upward in 0.13 steps: distinct, and inside the ordinary 3-8mm band
      diameter: (3.1 + k * 0.13).toFixed(2),
      // competent stays under the 0.5s cutoff, incompetent over it; both strictly
      // increasing, so no two cells anywhere in the encounter share a number.
      reflux: competent ? (0.11 + k * 0.003).toFixed(3) : (0.62 + k * 0.017).toFixed(3),
      competent,
    });
  }
  return out;
}

/** Hard ceiling. The evidence gate refuses anything over 12,000 chars BEFORE any
 *  model call, and that refusal reads as SYNTHETIC_EVIDENCE_REJECTED — a
 *  security-shaped error for what is really "your form is large". A big form
 *  must degrade to a shorter dictation, never to a misleading refusal. */
const MAX_ENCOUNTER_CHARS = 9_000;

/**
 * Build a synthetic dictation that speaks to THIS template's own measurement
 * rows. Falls back to the generic encounter when a template has no measurement
 * fields, when its rows are all placeholders, or when the form is not venous —
 * the narrative this generator writes is venous, and it must not be told about
 * a study it does not describe.
 */
export function deriveVerificationEncounter(
  fields: readonly EncounterSourceField[],
): string {
  const labels: string[] = [];
  const seen = new Set<string>();
  for (const f of fields) {
    if (!f.clinicalConcept || !f.clinicalConcept.startsWith(MEASUREMENT_PREFIX)) continue;
    const label = (f.originalLabel ?? '').trim();
    if (!label || PLACEHOLDER.test(label)) continue;
    // A column's UNIT HEADER ("REFLUX TIME (ms)") labels a column, addresses no
    // row, and would become a dictated segment that aligns with nothing.
    if (/^reflux\s+time/i.test(label)) continue;
    const key = label.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    labels.push(label);
  }

  if (labels.length === 0) return VERIFICATION_ENCOUNTER;

  // ⚠️ EVIDENCE, NOT ASSUMPTION: the form's own labels must look venous before a
  // venous narrative is written about it.
  if (!labels.some((l) => VENOUS_TOKEN.test(l))) return VERIFICATION_ENCOUNTER;

  const build = (take: number): string => {
    const used = labels.slice(0, take);
    const vals = measurementValues(used.length * 2);
    const lines: string[] = [
      // ⚠️ LOAD-BEARING: the evidence gate requires an explicit synthetic marker
      // and throws SYNTHETIC_EVIDENCE_REJECTED, before any model call, without it.
      'Synthetic certification test encounter — fictional example data, no real patient.',
      'Bilateral lower extremity venous reflux study, standing, with distal augmentation.',
      'Indication: bilateral leg heaviness, aching, and visible varicosities.',
    ];
    (['Right', 'Left'] as const).forEach((side, s) => {
      used.forEach((label, i) => {
        const v = vals[s * used.length + i];
        lines.push(
          `${side} ${label}: diameter ${v.diameter} millimeters, reflux time ${v.reflux} seconds` +
            `${v.competent ? '; competent, within normal limits.' : '; incompetent.'}`,
        );
      });
    });
    lines.push(
      'Deep venous system patent bilaterally, compressible, phasic, no deep vein thrombosis.',
    );
    return lines.join(' ');
  };

  // Shrink rather than overflow. A form large enough to exceed the gate's scan
  // window degrades to fewer segments — still far above the fill threshold —
  // instead of being refused with a security-shaped error.
  let take = labels.length;
  let text = build(take);
  while (text.length > MAX_ENCOUNTER_CHARS && take > 1) {
    take -= 1;
    text = build(take);
  }
  return text;
}
