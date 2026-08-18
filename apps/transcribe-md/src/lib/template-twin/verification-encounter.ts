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
