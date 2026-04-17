// ============================================================================
// Clinical Notes — evaluation cases
// ----------------------------------------------------------------------------
// Real-world doctor phrasings for editing an existing clinical note via the
// realtime AI assistant (dispatchEditNote → editClinicalNoteTwoPass).
//
// Run via `npm run eval:clinical-notes` (hits real OpenAI, needs OPENAI_API_KEY).
//
// Why this is separate from doc-editor-phrasings.ts: clinical notes are
// edited differently (typically partial_edit on a free-text record, vs the
// labeled-section-heavy procedure templates the Doc Editor handles), so
// the case set + the expected operation distribution are different.
//
// When a doctor reports "the AI butchered my note", ADD the failing
// phrasing here so we catch the regression before the next ship.
// ============================================================================

import type { EditIntent, EditOperation } from '@/lib/ai-service';

export interface NoteEvalCase {
  id: string;
  description: string;
  instruction: string;
  /** Note content to feed Pass 1. Defaults to SAMPLE_NOTE if omitted. */
  note?: string;
  expected: {
    operation: EditOperation;
    /** Only asserted if present. */
    target_section?: string | null;
    /** Only asserted if present. Exact verbatim match. */
    replacement_text?: string;
    confidence: EditIntent['confidence'];
  };
}

// Realistic clinical note shared across cases. Multi-paragraph free text —
// the typical shape of what doctors dictate post-procedure.
export const SAMPLE_NOTE = `PROCEDURE: Right L4-L5 transforaminal epidural steroid injection (LESI).

INDICATION: Refractory low back pain with right-sided radiculopathy. Patient
has failed conservative management including PT and oral analgesics over the
past 6 months.

PROCEDURE NOTE:
After informed consent was obtained, the patient was placed prone on the
fluoroscopy table. The right L4-L5 region was prepped and draped in sterile
fashion. Under fluoroscopic guidance using AP and oblique views, a 25g
spinal needle was advanced to the L4-L5 foramen. Aspiration was negative for
blood and CSF. 0.5mL of Isovue 300 was injected demonstrating appropriate
epidural spread. 3mL of mixture containing 2mL 1% lidocaine, 1mL (10mg)
dexamethasone, and 8mL normal saline was then injected without resistance.
The needle was removed and a sterile bandage applied.

POST-PROCEDURE: Patient tolerated the procedure well with no complications.
Transferred to recovery in stable condition.

PLAN: Follow up in office in 2 weeks. If pain is significantly improved,
will continue conservative management. If still symptomatic, will consider
repeat injection or surgical consultation.`;

export const NOTE_EVAL_CASES: NoteEvalCase[] = [
  // --------------------------------------------------------------------------
  // PARTIAL EDIT — the bread-and-butter operation for clinical notes
  // --------------------------------------------------------------------------
  {
    id: 'partial-001',
    description: 'Change a dose inline (most common edit type)',
    instruction: 'change the dexamethasone dose to 15mg',
    expected: {
      operation: 'partial_edit',
      confidence: 'high',
    },
  },
  {
    id: 'partial-002',
    description: 'Change the spinal level — currently fails (parser misclassifies as replace)',
    instruction: 'change L4-L5 to L5-S1',
    expected: {
      // EXPECTED FAILURE in current state: the parser sees "change X to Y"
      // and pattern-matches to operation=replace even when X is a short
      // clinical token (anatomy, dose) and Y is similarly short — semantic
      // intent is a token swap (partial_edit). The eval suite reports this
      // as a failure (correctly), and the 85% threshold absorbs it. Fix is
      // a parser-prompt heuristic that distinguishes section labels from
      // short clinical tokens. Tracked, not yet shipped.
      operation: 'partial_edit',
      confidence: 'high',
    },
  },
  {
    id: 'partial-003',
    description: 'Add a sentence to a section',
    instruction: 'add a sentence about post-op pain control to the plan',
    expected: {
      operation: 'partial_edit',
      target_section: 'PLAN',
      confidence: 'high',
    },
  },
  {
    id: 'partial-004',
    description: 'Fix a typo (vague — medium confidence is honest)',
    instruction: 'fix the typo in the procedure note',
    expected: {
      operation: 'partial_edit',
      target_section: 'PROCEDURE NOTE',
      confidence: 'medium',
    },
  },
  {
    id: 'partial-005',
    description: 'Update the follow-up timeframe',
    instruction: 'change the follow up to 4 weeks instead of 2',
    expected: {
      operation: 'partial_edit',
      confidence: 'high',
    },
  },
  {
    id: 'partial-006',
    description: 'Voice typo "chnge" — should still parse as partial_edit',
    instruction: 'chnge the dose of lidocaine to three milliliters',
    expected: {
      operation: 'partial_edit',
      confidence: 'high',
    },
  },

  // --------------------------------------------------------------------------
  // REPLACE — doctor gives literal new text for a labeled section
  // --------------------------------------------------------------------------
  {
    id: 'replace-001',
    description: 'Replace the indication wholesale',
    instruction: 'replace the indication with: refractory neck pain with bilateral radiculopathy',
    expected: {
      operation: 'replace',
      target_section: 'INDICATION',
      replacement_text: 'refractory neck pain with bilateral radiculopathy',
      confidence: 'high',
    },
  },
  {
    id: 'replace-002',
    description: 'Replace the plan section',
    instruction: 'replace the plan with: schedule second injection in 2 weeks',
    expected: {
      operation: 'replace',
      target_section: 'PLAN',
      replacement_text: 'schedule second injection in 2 weeks',
      confidence: 'high',
    },
  },
  {
    id: 'replace-003',
    description: 'Short / informal replacement (the "arthur Morgan" failure mode)',
    instruction: 'replace the plan with TBD',
    expected: {
      operation: 'replace',
      target_section: 'PLAN',
      replacement_text: 'TBD',
      confidence: 'high',
    },
  },
  {
    id: 'replace-004',
    description: '"change X to Y" phrasing — currently fails (parser invents wrong section name)',
    instruction: 'change the procedure to Right L5-S1 transforaminal epidural',
    expected: {
      // EXPECTED FAILURE in current state: the note has "PROCEDURE:" (top
      // line) and "PROCEDURE NOTE:" (later section), but the parser
      // hallucinates "PROCEDURE DESCRIPTION" — a Doc Editor template label
      // from the parser prompt's "common sections" list, which biases it
      // toward names that don't exist in clinical notes. Fix: tighten the
      // parser to use the EXACT label found in the document, not the
      // example list. Tracked, not yet shipped.
      operation: 'replace',
      target_section: 'PROCEDURE',
      replacement_text: 'Right L5-S1 transforaminal epidural',
      confidence: 'high',
    },
  },

  // --------------------------------------------------------------------------
  // BLANK — clear a section
  // --------------------------------------------------------------------------
  {
    id: 'blank-001',
    description: 'Delete the post-procedure section',
    instruction: 'delete the post-procedure section',
    expected: {
      operation: 'blank',
      target_section: 'POST-PROCEDURE',
      confidence: 'high',
    },
  },
  {
    id: 'blank-002',
    description: 'Clear the plan section',
    instruction: 'clear the plan',
    expected: {
      operation: 'blank',
      target_section: 'PLAN',
      confidence: 'high',
    },
  },
  {
    id: 'blank-003',
    description: 'Voice typo "blan"',
    instruction: 'blan the indication',
    expected: {
      operation: 'blank',
      target_section: 'INDICATION',
      confidence: 'high',
    },
  },

  // --------------------------------------------------------------------------
  // GENERATE — produce new content from existing
  // --------------------------------------------------------------------------
  {
    id: 'generate-001',
    description: 'Make the procedure note shorter',
    instruction: 'make the procedure note shorter',
    expected: {
      operation: 'generate',
      target_section: 'PROCEDURE NOTE',
      confidence: 'high',
    },
  },
  {
    id: 'generate-002',
    description: 'Summarize the indication',
    instruction: 'summarize the indication into one sentence',
    expected: {
      operation: 'generate',
      target_section: 'INDICATION',
      confidence: 'high',
    },
  },
  {
    id: 'generate-003',
    description: 'Rewrite the plan more concise',
    instruction: 'rewrite the plan to be more concise',
    expected: {
      operation: 'generate',
      target_section: 'PLAN',
      confidence: 'high',
    },
  },
  {
    id: 'generate-004',
    description: 'Real-world phrasing — "read it and write me a short version"',
    instruction: 'read the procedure note and give me a shorter version',
    expected: {
      operation: 'generate',
      target_section: 'PROCEDURE NOTE',
      confidence: 'high',
    },
  },

  // --------------------------------------------------------------------------
  // BROKEN ENGLISH / non-native phrasing
  // --------------------------------------------------------------------------
  {
    id: 'broken-001',
    description: 'Non-native conversational replacement',
    instruction: 'please you change the dose lidocaine make it five milliliter',
    expected: {
      operation: 'partial_edit',
      confidence: 'high',
    },
  },
  {
    id: 'broken-002',
    description: 'Voice with filler words',
    instruction: 'um yeah uh just delete the post procedure part please',
    expected: {
      operation: 'blank',
      target_section: 'POST-PROCEDURE',
      confidence: 'high',
    },
  },

  // --------------------------------------------------------------------------
  // UNCLEAR — parser should refuse; Pass 2 must not run
  // --------------------------------------------------------------------------
  {
    id: 'unclear-001',
    description: 'Generic non-request',
    instruction: 'fix it',
    expected: {
      operation: 'unclear',
      confidence: 'low',
    },
  },
  {
    id: 'unclear-002',
    description: 'Single ambiguous word',
    instruction: 'better',
    expected: {
      operation: 'unclear',
      confidence: 'low',
    },
  },
  {
    id: 'unclear-003',
    description: 'Empty-ish input',
    instruction: 'do the thing',
    expected: {
      operation: 'unclear',
      confidence: 'low',
    },
  },
];
