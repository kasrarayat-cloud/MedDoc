// ============================================================================
// Fixed SYNTHETIC encounter for the note-format live sample-note preview.
// ----------------------------------------------------------------------------
// The preview (Settings → My Note Format → review screen) generates a sample
// SOAP note IN THE DOCTOR'S PARSED FORMAT so they see real output before
// activating. It must NEVER touch a real patient/visit/PHI, so the ONLY input
// is this hardcoded, fully-synthetic encounter — a generic T2DM/HTN follow-up
// (no real person; mirrors the PC1 audit scenario used in the prior end-to-end
// proof). Both the transcript AND a pre-extracted `entities` fixture are baked
// here so the preview runs ONE model call (L4-equivalent) and skips L3 (which
// is visit-row-coupled). Bump SYNTHETIC_TRANSCRIPT_VERSION whenever this
// content changes — it is part of the preview cache key.
//
// The generated sample inherits the IMMUTABLE safety preamble + confirm-not-
// fabricate guardrails from buildSoapSystemPrompt (sourced from the system
// default, never from the custom template), so the preview cannot fabricate
// beyond what this synthetic transcript supports.
// ============================================================================

import type { z } from 'zod';

import { ExtractedEntities } from '../layers/03-extract-entities';

/** Cache-key component — bump on ANY change to the transcript/entities below. */
export const SYNTHETIC_TRANSCRIPT_VERSION = 'v1-t2dm-htn-2026-06';

/** The specialty slug the preview generates against (drives specialty guidance
 *  the same way `visit.specialty` does in the real pipeline). */
export const SAMPLE_PREVIEW_SPECIALTY = 'primary-care';

/** Fixed synthetic transcript (text-mode). Generic T2DM/HTN follow-up — no real
 *  patient, no PHI. Verbatim-equivalent to the PC1 audit scenario. */
export const SAMPLE_PREVIEW_TRANSCRIPT = `
Patient is a 58-year-old female with a 12-year history of type 2 diabetes mellitus presenting for routine follow-up. Last A1c three months ago was 7.4, today's value is 8.2 with fasting glucose 168. Patient has been compliant with metformin 1000 milligrams twice daily and is also on lisinopril 20 milligrams daily for hypertension and atorvastatin 20 milligrams daily for hyperlipidemia. Recent lipid panel shows LDL 112 which is above goal for this ASCVD-equivalent patient. Patient reports neuropathic tingling in both feet over the last two months without ulceration. Blood pressure today 138 over 82.
Assessment: type 2 diabetes mellitus with hyperglycemia and likely diabetic peripheral neuropathy, hyperlipidemia not at goal, essential hypertension. Plan: continue metformin, add empagliflozin 10 milligrams daily for both glycemic control and cardiovascular benefit, increase atorvastatin to 40 milligrams daily targeting LDL under 70 in this high-risk patient, continue lisinopril, start gabapentin 100 milligrams three times daily for the neuropathic symptoms, order microalbumin, foot exam annually, and three-month follow-up with repeat A1c.
This is an established patient visit with moderate-complexity medical decision-making and approximately 25 minutes face-to-face.
`.trim();

/** Pre-extracted entities for the synthetic transcript (the L3 output, baked so
 *  the preview skips the visit-coupled L3 layer). Validated against
 *  ExtractedEntities by tests/.../sample-preview-transcript.test.ts. */
export const SAMPLE_PREVIEW_ENTITIES: z.infer<typeof ExtractedEntities> =
  ExtractedEntities.parse({
    chief_complaint: {
      statement: 'Routine follow-up for type 2 diabetes mellitus.',
      evidence_quote:
        'presenting for routine follow-up',
    },
    hpi: {
      duration: '12-year history of type 2 diabetes mellitus',
      context: 'Established patient, compliant with current regimen.',
      associated_symptoms:
        'Neuropathic tingling in both feet over the last two months without ulceration.',
      evidence_quote:
        "Last A1c three months ago was 7.4, today's value is 8.2 with fasting glucose 168.",
    },
    past_medical_history: [
      { condition: 'Type 2 diabetes mellitus', evidence_quote: '12-year history of type 2 diabetes mellitus' },
      { condition: 'Essential hypertension', evidence_quote: 'on lisinopril 20 milligrams daily for hypertension' },
      { condition: 'Hyperlipidemia', evidence_quote: 'atorvastatin 20 milligrams daily for hyperlipidemia' },
    ],
    medications: [
      { name: 'Metformin', dose: '1000 mg', frequency: 'twice daily', evidence_quote: 'compliant with metformin 1000 milligrams twice daily' },
      { name: 'Lisinopril', dose: '20 mg', frequency: 'daily', evidence_quote: 'lisinopril 20 milligrams daily for hypertension' },
      { name: 'Atorvastatin', dose: '20 mg', frequency: 'daily', evidence_quote: 'atorvastatin 20 milligrams daily for hyperlipidemia' },
    ],
    // Q1 audit §02.9 — this entry used to read "Bilateral foot tingling, no
    // ulceration": ONE row conflating an affirmed finding with a denied one,
    // which is precisely the collapse structured polarity exists to prevent.
    // Split, because they are two different claims about the patient.
    ros: [
      { system: 'Neurological', finding: 'Foot tingling', polarity: 'affirmed', laterality: 'bilateral', evidence_quote: 'neuropathic tingling in both feet over the last two months without ulceration' },
      { system: 'Neurological', finding: 'Ulceration', polarity: 'denied', laterality: 'bilateral', evidence_quote: 'neuropathic tingling in both feet over the last two months without ulceration' },
    ],
    exam_findings: [
      { system: 'Vitals', finding: 'Blood pressure 138/82', evidence_quote: 'Blood pressure today 138 over 82' },
    ],
    tests_mentioned: [
      { test: 'Hemoglobin A1c', result_if_given: '8.2 (up from 7.4)', evidence_quote: "today's value is 8.2" },
      { test: 'Fasting glucose', result_if_given: '168', evidence_quote: 'fasting glucose 168' },
      { test: 'Lipid panel (LDL)', result_if_given: 'LDL 112', evidence_quote: 'Recent lipid panel shows LDL 112' },
    ],
    assessment_discussed: [
      { finding: 'Type 2 diabetes mellitus with hyperglycemia', evidence_quote: 'type 2 diabetes mellitus with hyperglycemia' },
      { finding: 'Likely diabetic peripheral neuropathy', evidence_quote: 'likely diabetic peripheral neuropathy' },
      { finding: 'Hyperlipidemia not at goal', evidence_quote: 'hyperlipidemia not at goal' },
      { finding: 'Essential hypertension', evidence_quote: 'essential hypertension' },
    ],
    plan_discussed: [
      { item: 'Continue metformin', evidence_quote: 'continue metformin' },
      { item: 'Add empagliflozin 10 mg daily', evidence_quote: 'add empagliflozin 10 milligrams daily for both glycemic control and cardiovascular benefit' },
      { item: 'Increase atorvastatin to 40 mg daily (LDL goal <70)', evidence_quote: 'increase atorvastatin to 40 milligrams daily targeting LDL under 70' },
      { item: 'Start gabapentin 100 mg three times daily', evidence_quote: 'start gabapentin 100 milligrams three times daily for the neuropathic symptoms' },
      { item: 'Order microalbumin; annual foot exam; 3-month follow-up with repeat A1c', evidence_quote: 'order microalbumin, foot exam annually, and three-month follow-up with repeat A1c' },
    ],
  });
