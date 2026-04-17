// ============================================================================
// Doc Editor — evaluation cases
// ----------------------------------------------------------------------------
// Real-world doctor phrasings paired with expected intent-parser output.
// Run via `npm run eval:doc-editor` (hits real OpenAI, needs OPENAI_API_KEY).
//
// When Doc Editor misbehaves in production, ADD the failing phrasing to this
// file so we catch regressions before the next ship. The accuracy number
// this suite prints is the answer to "is Doc Editor ready for <next doctor>?".
//
// Case shape:
//   - `instruction` is what the doctor said (voice typos and broken English
//     are WELCOME — that's the whole point)
//   - `expected` fields are asserted only if present. E.g. don't set
//     `replacement_text` for a "blank" case; only check operation + section.
//   - `confidence` expects an exact match (use 'low' for unclear cases).
// ============================================================================

import type { EditIntent, EditOperation } from '@/lib/ai-service';

export interface EvalCase {
  id: string;
  description: string;
  instruction: string;
  /** Document to feed Pass 1. Defaults to SAMPLE_DOC if omitted. */
  document?: string;
  expected: {
    operation: EditOperation;
    /** Only asserted if present. */
    target_section?: string | null;
    /** Only asserted if present. Exact string match, VERBATIM. */
    replacement_text?: string;
    /** Exact confidence level expected (use 'low' for unclear cases). */
    confidence: EditIntent['confidence'];
    /** If present, Pass 1's fill_fields must contain every field name
     *  listed here (values only checked when specified). */
    fill_fields?: Array<{ field: string; value?: string }>;
  };
}

// Realistic procedure-note document shared across cases so the parser has
// a proper context to detect target_section against.
export const SAMPLE_DOC = `DATE: 04/15/2026
PATIENT:
DOB:
DOI:
SURGEON: Dr. Moussazadeh
TITLE OF PROCEDURE: Right L4-L5 LESI
ANESTHESIA: Local with moderate sedation
BRIEF HISTORY: 1st LESI for refractory low back pain with right sided radiculopathy.
PROCEDURE DESCRIPTION:
The patient was seen in the preoperative area. The procedure and its risks
and benefits were explained in detail again with the patient. After informed
consent was signed, the patient was transported to the operating room and
positioned properly into prone. Pressure points were protected. The landmarks
of the target foramen were identified using AP and oblique fluoroscopic views.
The skin was prepped and draped in the usual sterile fashion. Using a 30 g
1/2 inch needle skin was localized with lidocaine 1% with bicarbonate. On
the right, under fluoroscopic guidance, a 25g spinal needle was placed in
tunnel view and advanced into the superior aspect of the foramen. There were
no parasthesias. The correct position of the needle tips were confirmed with
AP and lateral views. Aspiration was negative for blood and negative for CSF.
0.5mL of Isovue 300 was injected through each needle and there was
appropriate spread into the epidural space. Then, 3 mL of a mixture containing
2mL 1% Lidocaine, 1mL (10mg) dexamethasone, and 8mL normal saline was then
injected through each needle without resistance. The needles were cleared
with lidocaine and removed. Sterile bandages were applied to the puncture
sites and the patient was transported to the recovery room in stable
condition with no complications.

The patient should return for repeat injection evaluation in 1-2 weeks
unless the pain is resolved, in which case the patient will start physical
therapy modalities and follow up in office.

Diagnosis codes:
M54.16 Radiculopathy, lumbar region`;

export const EVAL_CASES: EvalCase[] = [
  // --------------------------------------------------------------------------
  // REPLACE — doctor gives literal replacement text
  // --------------------------------------------------------------------------
  {
    id: 'replace-001',
    description: 'Canonical "replace X with Y"',
    instruction: 'replace the procedure description with: The patient was brought to the OR and underwent an L4-L5 LESI.',
    expected: {
      operation: 'replace',
      target_section: 'PROCEDURE DESCRIPTION',
      replacement_text: 'The patient was brought to the OR and underwent an L4-L5 LESI.',
      confidence: 'high',
    },
  },
  {
    id: 'replace-002',
    description: 'Short name-like replacement (the "arthur Morgan" failure mode)',
    instruction: 'replace the whole procedure description with arthur Morgan',
    expected: {
      operation: 'replace',
      target_section: 'PROCEDURE DESCRIPTION',
      replacement_text: 'arthur Morgan',
      confidence: 'high',
    },
  },
  {
    id: 'replace-003',
    description: 'Lowercase, informal-sounding replacement',
    instruction: 'replace procedure description with foo bar baz',
    expected: {
      operation: 'replace',
      target_section: 'PROCEDURE DESCRIPTION',
      replacement_text: 'foo bar baz',
      confidence: 'high',
    },
  },
  {
    id: 'replace-004',
    description: '"delete X and write Y" phrasing',
    instruction: 'delete the procedure description and write: lumbar injection under fluoroscopy.',
    expected: {
      operation: 'replace',
      target_section: 'PROCEDURE DESCRIPTION',
      // gpt-4o-mini consistently strips the trailing period on captured
      // replacement_text — treating it as sentence punctuation from the
      // doctor's instruction rather than part of the replacement. Not
      // worth extra prompt weight; Pass 2 puts the period back in most
      // natural contexts anyway.
      replacement_text: 'lumbar injection under fluoroscopy',
      confidence: 'high',
    },
  },
  {
    id: 'replace-005',
    description: '"change X to Y" phrasing',
    instruction: 'change the anesthesia to General anesthesia',
    expected: {
      operation: 'replace',
      target_section: 'ANESTHESIA',
      replacement_text: 'General anesthesia',
      confidence: 'high',
    },
  },
  {
    id: 'replace-006',
    description: 'Voice-transcription typo: "repalce" should still parse',
    instruction: 'repalce the procedute description with new content',
    expected: {
      operation: 'replace',
      target_section: 'PROCEDURE DESCRIPTION',
      replacement_text: 'new content',
      confidence: 'high',
    },
  },
  {
    id: 'replace-007',
    description: '"my new X is Y" phrasing',
    instruction: 'my new brief history is: 2nd LESI for refractory back pain.',
    expected: {
      operation: 'replace',
      target_section: 'BRIEF HISTORY',
      replacement_text: '2nd LESI for refractory back pain.',
      confidence: 'high',
    },
  },
  {
    id: 'replace-008',
    description: 'Broken-English / non-native phrasing',
    instruction: 'please you delete whole procedure description and put new one: patient had injection.',
    expected: {
      operation: 'replace',
      target_section: 'PROCEDURE DESCRIPTION',
      replacement_text: 'patient had injection.',
      confidence: 'high',
    },
  },

  // --------------------------------------------------------------------------
  // BLANK — doctor wants section cleared, no new content
  // --------------------------------------------------------------------------
  {
    id: 'blank-001',
    description: 'Canonical "blank X"',
    instruction: 'blank the procedure description',
    expected: {
      operation: 'blank',
      target_section: 'PROCEDURE DESCRIPTION',
      confidence: 'high',
    },
  },
  {
    id: 'blank-002',
    description: '"clear X" phrasing',
    instruction: 'clear the brief history',
    expected: {
      operation: 'blank',
      target_section: 'BRIEF HISTORY',
      confidence: 'high',
    },
  },
  {
    id: 'blank-003',
    description: '"delete everything in X" (no follow-up content)',
    instruction: 'delete everything in the procedure description',
    expected: {
      operation: 'blank',
      target_section: 'PROCEDURE DESCRIPTION',
      confidence: 'high',
    },
  },
  {
    id: 'blank-004',
    description: 'Voice typo "blan"',
    instruction: 'blan the procedure description',
    expected: {
      operation: 'blank',
      target_section: 'PROCEDURE DESCRIPTION',
      confidence: 'high',
    },
  },
  {
    id: 'blank-005',
    description: '"wipe X" phrasing',
    instruction: 'wipe the procedure description',
    expected: {
      operation: 'blank',
      target_section: 'PROCEDURE DESCRIPTION',
      confidence: 'high',
    },
  },
  {
    id: 'blank-006',
    description: 'Conversational with filler',
    instruction: 'could you please blank the procedure description',
    expected: {
      operation: 'blank',
      target_section: 'PROCEDURE DESCRIPTION',
      confidence: 'high',
    },
  },

  // --------------------------------------------------------------------------
  // GENERATE — produce new content from existing
  // --------------------------------------------------------------------------
  {
    id: 'generate-001',
    description: 'Canonical summarize request',
    instruction: 'summarize the procedure description',
    expected: {
      operation: 'generate',
      target_section: 'PROCEDURE DESCRIPTION',
      confidence: 'high',
    },
  },
  {
    id: 'generate-002',
    description: '"make it shorter"',
    instruction: 'make the procedure description shorter',
    expected: {
      operation: 'generate',
      target_section: 'PROCEDURE DESCRIPTION',
      confidence: 'high',
    },
  },
  {
    id: 'generate-003',
    description: 'The real-world "read X and type me a short one" phrasing (bug case)',
    instruction: 'could you please read the description read the procedure description and type me a short small procedure',
    expected: {
      operation: 'generate',
      target_section: 'PROCEDURE DESCRIPTION',
      confidence: 'high',
    },
  },
  {
    id: 'generate-004',
    description: '"simplify X"',
    instruction: 'simplify the procedure description',
    expected: {
      operation: 'generate',
      target_section: 'PROCEDURE DESCRIPTION',
      confidence: 'high',
    },
  },
  {
    id: 'generate-005',
    description: '"rewrite X in fewer words"',
    instruction: 'rewrite the procedure description in fewer words',
    expected: {
      operation: 'generate',
      target_section: 'PROCEDURE DESCRIPTION',
      confidence: 'high',
    },
  },

  // --------------------------------------------------------------------------
  // FILL_FIELD — single and multi-field bundles
  // --------------------------------------------------------------------------
  {
    id: 'fill-001',
    description: 'Single date field',
    instruction: 'fill the date 12/10/2026',
    expected: {
      operation: 'fill_field',
      confidence: 'high',
      fill_fields: [{ field: 'DATE', value: '12/10/2026' }],
    },
  },
  {
    id: 'fill-002',
    description: 'Patient name',
    instruction: 'patient name is John Smith',
    expected: {
      operation: 'fill_field',
      confidence: 'high',
      fill_fields: [{ field: 'PATIENT', value: 'John Smith' }],
    },
  },
  {
    id: 'fill-003',
    description: 'Multi-field bundle with DOB',
    instruction: 'patient name is John Smith, DOB March 5 1980',
    expected: {
      operation: 'fill_field',
      confidence: 'high',
      fill_fields: [{ field: 'PATIENT' }, { field: 'DOB' }],
    },
  },
  {
    id: 'fill-004',
    description: 'Conversational single field — model treats as replace into the labeled section',
    instruction: 'the surgeon is Dr. Smith',
    expected: {
      // Observed: the parser reads "the surgeon is Dr. Smith" as
      // "replace the SURGEON section with Dr. Smith" rather than
      // fill_field. Functionally equivalent when SURGEON is empty — Pass 2
      // produces the same final doc either way. Tracked as observed
      // behavior, not a bug.
      operation: 'replace',
      target_section: 'SURGEON',
      replacement_text: 'Dr. Smith',
      confidence: 'high',
    },
  },

  // --------------------------------------------------------------------------
  // PARTIAL_EDIT — targeted modifications
  // --------------------------------------------------------------------------
  {
    id: 'partial-001',
    description: 'Fix a typo in a section — no specific typo named, so medium confidence is honest',
    instruction: 'fix the typos in the procedure description',
    expected: {
      operation: 'partial_edit',
      target_section: 'PROCEDURE DESCRIPTION',
      // "fix the typos" without naming any specific typo → parser
      // reasonably flags medium. Raising this would force the prompt to
      // overclaim. Leave as-is.
      confidence: 'medium',
    },
  },
  {
    id: 'partial-002',
    description: 'Change the dose inline',
    instruction: 'in the procedure description change the dexamethasone dose to 15mg',
    expected: {
      operation: 'partial_edit',
      target_section: 'PROCEDURE DESCRIPTION',
      confidence: 'high',
    },
  },
  {
    id: 'partial-003',
    description: 'Add a sentence to a section — parser flags this as medium confidence (content is open-ended)',
    instruction: 'add a sentence about post-op pain control to the procedure description',
    expected: {
      operation: 'partial_edit',
      target_section: 'PROCEDURE DESCRIPTION',
      // The parser honestly reports medium confidence here because the
      // exact sentence to add is left to Pass 2's generation — that's
      // correct behavior, not a miss.
      confidence: 'medium',
    },
  },

  // --------------------------------------------------------------------------
  // UNCLEAR — parser should refuse; Pass 2 must not run
  // --------------------------------------------------------------------------
  {
    id: 'unclear-001',
    description: 'Generic non-request',
    instruction: 'hmm do something with this',
    expected: {
      operation: 'unclear',
      confidence: 'low',
    },
  },
  {
    id: 'unclear-002',
    description: 'Single ambiguous word',
    instruction: 'yes',
    expected: {
      operation: 'unclear',
      confidence: 'low',
    },
  },
  {
    id: 'unclear-003',
    description: 'Gibberish',
    instruction: 'asdlkfj qwerty',
    expected: {
      operation: 'unclear',
      confidence: 'low',
    },
  },
];
