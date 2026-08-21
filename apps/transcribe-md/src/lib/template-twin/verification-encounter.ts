/**
 * THE REFERENCE VENOUS ENCOUNTER.
 *
 * ⚠️ SINCE F5-i THIS IS NOT A FALLBACK, AND IT MUST NEVER BE MADE ONE AGAIN.
 * `deriveVerificationEncounter` used to return this text for any form it could
 * not address, which certified operative notes, SOAP templates and thyroid
 * studies against a bilateral leg-vein study. That is now a NAMED REFUSAL —
 * see the F5-i block below. **Zero production call sites read this constant**;
 * its remaining readers are the gates that assert the shape a derived
 * encounter must have, and it is exported for them.
 *
 * If you are here because a template will not certify: the answer is a
 * generator that speaks to THAT form, never a re-pointed fallback to this one.
 *
 * ⚠️ IT LIVES HERE, NOT IN THE ACTION, BECAUSE A `'use server'` FILE MAY EXPORT
 * ASYNC FUNCTIONS ONLY. Exporting this const from `template-twin-certify.ts`
 * made Next refuse to evaluate the module, and every page importing it would
 * have failed to render. `use-server-exports.test.ts` caught it — a guard that
 * exists precisely because this trap has been paid for before.
 *
 * ⚠️ AND THE DERIVATION IS STILL ONE FUNCTION, SHARED. The manual certify
 * action and the auto-certify worker job both attest against what
 * `deriveVerificationEncounter` returns for their own template — and both
 * refuse on the same reasons. Two derivations would mean the automatic path
 * proved something the manual path never did, and neither reader could say
 * what their template actually passed.
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
/**
 * ⚠️ AND THE FIRST VERSION OF THIS GUARD ADMITTED AN ARTERIAL STUDY, WHICH IS
 * THE SAME FABRICATION IT WAS WRITTEN TO PREVENT. Found by F5-i's adversarial
 * pass, reproduced against this function before it was changed.
 *
 * The old single list included `femoral`, `popliteal` and `tibial`. Those three
 * name a VEIN **and an ARTERY at the same level** — the artery/vein
 * discriminator is the one word the list never read. So a lower-extremity
 * ARTERIAL duplex, an ordinary vascular-lab form, satisfied the venous check
 * and was dictated as:
 *
 *     Right Superficial Femoral Artery: diameter 3.23 millimeters,
 *     reflux time 0.637 seconds; incompetent.
 *
 * ⚠️ ARTERIES HAVE NO VALVES. There is no arterial "reflux time", "incompetent"
 * is not a verdict that exists for an artery, the study measures velocity in
 * cm/s rather than a diameter in millimetres, and the closing line asserts a
 * DEEP VENOUS negative about a form with no venous rows.
 *
 * The old comment stated the intent exactly right — "a venous duplex names its
 * saphenous/femoral/popliteal segments" — and that sentence IS the bug: an
 * arterial duplex names them too.
 */

/** No artery is dictated by this generator, full stop. A form naming one is
 *  not a study it can speak to, whatever else the form also contains — the
 *  MIXED case (real venous rows beside an arterial row) is the dangerous one,
 *  because the venous evidence is genuine and the arteries still get reflux
 *  times. */
const ARTERIAL_TOKEN = /\barter(y|ies|ial)\b/i;

/** Unambiguously venous — no artery carries any of these names. */
const VENOUS_UNAMBIGUOUS = /\b(gsv|ssv|aagsv|pagsv|saphenous|perforator|reflux|varicos)\b/i;

/** Shared with the arterial tree at the same level. Evidence of a VENOUS study
 *  only when the form says so somewhere else. */
const VENOUS_AMBIGUOUS = /\b(femoral|popliteal|tibial)\b/i;
const EXPLICIT_VEIN = /\b(vein|veins|venous)\b/i;

/**
 * Does the form's OWN vocabulary establish a lower-extremity venous study?
 *
 * ⚠️ SCOPED TO THE MEASUREMENT LABELS — the rows that actually get DICTATED,
 * which is where fabrication can occur. A wider scan over every field on the
 * form would refuse a legitimate venous study carrying an unrelated field like
 * "Arterial history: none", and that over-refusal costs a capability for no
 * safety gain. Stated so the boundary is checkable rather than assumed.
 */
function venousEvidence(labels: readonly string[]): boolean {
  if (labels.some((l) => ARTERIAL_TOKEN.test(l))) return false;
  if (labels.some((l) => VENOUS_UNAMBIGUOUS.test(l))) return true;
  return (
    labels.some((l) => VENOUS_AMBIGUOUS.test(l)) && labels.some((l) => EXPLICIT_VEIN.test(l))
  );
}

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

/* ──────────────────────────────────────────────────────────────────────────
 * F5-i — SHAPE-DERIVED, OR REFUSE. NEVER A FALLBACK.
 * ──────────────────────────────────────────────────────────────────────────
 *
 * ⚠️ THIS FUNCTION USED TO RETURN `VERIFICATION_ENCOUNTER` — a bilateral lower
 * extremity VENOUS REFLUX dictation — for any form it could not address. So a
 * Colonoscopy Operative Note, a SOAP office template and a thyroid study were
 * each certified against a leg-vein study that never mentions one field they
 * contain.
 *
 * > A certificate must mean THE form was exercised, not that A form was.
 *
 * The fallback was the weaker claim wearing the stronger one's clothes. It is
 * removed: a template this generator cannot speak to now returns a NAMED
 * refusal, and both callers land it in needs-review saying so.
 *
 * ⚠️ THE RETURN SHAPE CHANGED, NOT JUST ITS NULLABILITY, AND THAT IS
 * DELIBERATE. A `string | null` would have let a caller stringify the refusal
 * into an encounter. A discriminated union cannot be passed to `encounterText`
 * at all, so `tsc` names every site — and the `reason` is what needs-review
 * has to display, so it must survive the return.
 *
 * ⚠️ THIS IS A TIGHTENING AND IT COSTS A CAPABILITY, KNOWINGLY. A non-venous
 * template that would previously have "certified" now cannot certify at all.
 * That is the correct direction: production holds 10 note templates and
 * exactly ONE compiled twin — the venous one — so no template loses a
 * certificate it actually holds, and the ones that would have gained one would
 * have gained a false one. Widening coverage (a per-shape generator for
 * operative notes / SOAP / imaging) is F5-i's second half and is ADDITIVE on
 * top of this; it must never be delivered by restoring the fallback.
 */

/** Why this template could not have a self-test generated FOR IT. Displayed to
 *  the doctor via needs-review, so each value names a real, distinguishable
 *  situation rather than one catch-all. */
export type EncounterNotDerivable =
  | 'no_measurement_rows'
  | 'only_placeholder_rows'
  | 'unsupported_study_type';

export type DerivedEncounter =
  | { readonly ok: true; readonly text: string }
  | { readonly ok: false; readonly reason: EncounterNotDerivable };

/**
 * Build a synthetic dictation that speaks to THIS template's own measurement
 * rows, or REFUSE with a named reason. It never invents a narrative about a
 * study the form does not describe.
 */
export function deriveVerificationEncounter(
  fields: readonly EncounterSourceField[],
): DerivedEncounter {
  const labels: string[] = [];
  const seen = new Set<string>();
  /** Counted separately from `labels` so "no measurement rows at all" stays
   *  distinguishable from "measurement rows that name no anatomy". Collapsing
   *  them would put a table-less SOAP form and an all-placeholder venous form
   *  under one reason, and they need different answers from the doctor. */
  let measurementRows = 0;
  for (const f of fields) {
    if (!f.clinicalConcept || !f.clinicalConcept.startsWith(MEASUREMENT_PREFIX)) continue;
    measurementRows += 1;
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

  // A form with no measurement rows AT ALL — a SOAP office template, and the
  // common shape of an operative note.
  //
  // ⚠️ "OPERATIVE NOTE" IS NOT A SYNONYM FOR THIS BUCKET, AND AN EARLIER
  // VERSION OF THIS COMMENT SAID IT WAS. The adversarial pass produced the
  // counterexample: a colonoscopy operative note carrying `Polyp size (mm)` →
  // `measurement.length` and `Scope insertion depth (cm)` → `measurement.depth`
  // has measurementRows = 2 and lands in `unsupported_study_type` instead.
  // That is the CORRECT bucket for it — the rows exist and this generator
  // cannot speak to them — but the buckets are defined by the FIELD SET, never
  // by what the document is called. A reader who maps them to document kinds
  // will be wrong about exactly the forms F5-i's second half must handle.
  if (measurementRows === 0) return { ok: false, reason: 'no_measurement_rows' };

  // Measurement rows exist but none of them name anatomy, so any dictation
  // would address a location nobody wrote down.
  if (labels.length === 0) return { ok: false, reason: 'only_placeholder_rows' };

  // ⚠️ EVIDENCE, NOT ASSUMPTION: the form's own labels must look venous before a
  // venous narrative is written about it. A thyroid or obstetric study reaches
  // here, and dictating reflux times and a "no deep vein thrombosis" negative
  // about it would be FABRICATED CLINICAL CONTENT in a stored artifact.
  if (!venousEvidence(labels)) {
    return { ok: false, reason: 'unsupported_study_type' };
  }

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
  return { ok: true, text };
}
