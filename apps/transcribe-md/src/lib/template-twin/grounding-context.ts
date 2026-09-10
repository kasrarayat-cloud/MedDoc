// ============================================================================
// #314 v2 — THE TEXT A FILL IS GROUNDED AGAINST, DECIDED ONCE. Pure.
// ----------------------------------------------------------------------------
// `projectEncounterFacts` locates every fact's quote in `contextText`, and #314
// refuses a total time whose quote is not there. So `contextText` must be the
// text L3 READ — and five callers were deciding it independently:
//
//   worker (the first fill)      text_notes -> rawTextInput (what L3 read)
//   sign-freeze · native-export  ─┐
//   preview-visit-document       ├ every mode -> `visit.transcriptText ?? ''`
//   set-template-control         ─┘
//
// ⚠️ `transcriptText` IS NULL FOR EVERY text_notes VISIT — 55 of 58 visits in
// production, measured 2026-09-10 (the other three are voice_dictation). So on
// the four re-fill doors a typed visit was projected against '' : the preview,
// the sign-time re-fill, the export and a control edit would all BLANK a total
// the worker had filled, and every other fact lost its offsets. Same visit,
// same entities, two documents.
//
// ONE RULE, FIVE READERS. Every caller asks this function; none derives it.
//
//   text_notes       -> rawTextInput, trimmed   (= L3's `input.rawText.trim()`)
//   voice_dictation  -> transcriptText, trimmed (= L3's `dictationText.trim()`;
//                       L1b persists the same string it returns)
//   conversation     -> TODAY'S BEHAVIOUR, KEPT, AND A NAMED RESIDUAL:
//                       the worker passes the role-labelled transcript L3 read;
//                       the doors have only `transcriptText`, which is NOT that
//                       text (no role labels, different joins). A quote spanning
//                       two utterances can ground at the worker and not at a
//                       door. Production has ZERO audio_upload visits today
//                       (measured 2026-09-10), so this is filed, not fixed.
//
//   PROOF: __tests__/gate-314-grounding-context-doors.test.ts
// ============================================================================

export interface GroundingContextVisit {
  inputMode: string | null | undefined;
  rawTextInput: string | null | undefined;
  transcriptText: string | null | undefined;
}

export function groundingContextFor(
  visit: GroundingContextVisit,
  options?: {
    /** The WORKER ONLY: the role-labelled transcript L3 read for a
     *  conversation. No door has it, which is the conversation residual. */
    conversationTranscript?: string;
  },
): string {
  if (visit.inputMode === 'text_notes') return (visit.rawTextInput ?? '').trim();
  if (visit.inputMode === 'voice_dictation') return (visit.transcriptText ?? '').trim();
  return options?.conversationTranscript ?? visit.transcriptText ?? '';
}
