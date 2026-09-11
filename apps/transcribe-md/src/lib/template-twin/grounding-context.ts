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
//   conversation     -> TODAY'S BEHAVIOUR, KEPT for every other fact:
//                       the worker passes the role-labelled transcript L3 read;
//                       the doors have only `transcriptText`, which is NOT that
//                       text (no role labels, different joins).
//                       ⚠️ #314 v3: A CONVERSATION TOTAL IS REFUSED EVERYWHERE.
//                       Round two measured the v2 divergence running the other
//                       way: the label "[Doctor #0, 3:05]:" put a clock time in
//                       every utterance's first sentence, so the worker refused
//                       a total that every door grounded (the preview showed 45,
//                       the signature froze a blank). `encounter-facts` now
//                       emits no total for mode 'conversation' at all, so the
//                       worker and the four doors agree. The proper fix —
//                       persist L3's labelled context so the doors can read it —
//                       is FILED. Production has ZERO audio_upload visits
//                       (measured 2026-09-11).
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
