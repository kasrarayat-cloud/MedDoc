// ============================================================================
// Ultrasound IMAGING-REPORT prompt builder (flag-gated, additive).
// ----------------------------------------------------------------------------
// Parallel to build-soap-prompt.ts. Deliberately a SEPARATE builder so the
// SOAP prompt path stays byte-identical (the L4 golden test is untouched).
//
// It reuses the SAME machinery shape (preamble → section headings with
// directives → Critical rules → instruction-as-data delimiter) but draws the
// preamble + globalRules from the ULTRASOUND template's own styleProfile —
// which itself REUSES the SOAP anti-hallucination rules verbatim and adds
// measurement/laterality discipline (see ultrasound-report-template.ts). The
// audio-quality + interpreter hedge slices are identical to L4's.
// ============================================================================

import { delimiterSystemSuffix } from '@meddoc/ai';
import type { ResolvedNoteTemplate, BuildSystemPromptOpts } from './build-soap-prompt';
import {
  renderSectionBody,
  staticLinesByKey,
  CHOICE_SLOT_DIRECTIVE,
  hasGenerativeChoiceSlots,
} from './build-soap-prompt';
import { SLOT_VALUES_DIRECTIVE } from './slot-fill-protocol';
import { staticSections } from './assemble-note';
import type { NoteTemplateSection } from './system-default-template';
import { ULTRASOUND_REPORT_TEMPLATE } from './ultrasound-report-template';

/** The immutable imaging-report safety layer (preamble + anti-hallucination /
 *  measurement / laterality rules). ALWAYS sourced from the canonical
 *  ultrasound template — never from the passed template — so a doctor's custom
 *  imaging template contributes only its SECTIONS and can no more weaken the
 *  imaging safety rules than a custom SOAP template can weaken the SOAP ones.
 *  (A custom template's styleProfile carries tense/tone, not globalRules.) */
const IMAGING_SAFETY = ULTRASOUND_REPORT_TEMPLATE.styleProfile;

// ⚠️ THIS FILE NO LONGER HAS ITS OWN `renderSectionBody`, AND THE DELETION IS
// THE FIX FOR A CLINICAL DEFECT. It carried a near-identical copy of the SOAP
// builder's, so RC-1's static-aware treatment — added to that one — never
// reached this route. Every production visit bound to a reclassified template
// is an IMAGING visit, so the model would have been handed the doctor's bytes
// as scaffold while `composeNote` composed as though it had not been, replacing
// dictated values (side of exam, indication) with an em dash on a signed
// report, silently. Both structure gates pass on that output.
//
// ⚠️ AND THE COPY CARRIED THE ROOT CAUSE OF #106 ITSELF.
//
//     normalizeRefluxTimeUnit("… reflux as lasting more than 500 milliseconds …")
//       → "… reflux as lasting more than 0.5 seconds …"
//
// It was applied to `defaultText` before the prompt was built, so the PROMPT
// said `0.5 seconds` and the model reproduced it faithfully. **The paraphrase
// the ruling attributes to the model was written by this code**, deterministic
// on every imaging visit. Ruling #106's diagnosis is corrected on that point.
//
// The unit concern behind it was real — a bare seconds value under a
// milliseconds header is a mismatch — but the remedy edited the doctor's
// sentence, which SPEC §4.3a(a) forbids in as many words ("never normalised,
// never 'improved'. `500 milliseconds` stays `500 milliseconds`"). The column
// headers are still reconciled inside `renderStructureDirective`, where the
// unit actually lives, and the convention is now STATED to the model instead of
// applied to the doctor's prose.
const REFLUX_UNIT_NOTE = [
  'REFLUX TIME UNITS. Where a table column asks for a reflux or reverse-flow',
  'time, write the value in SECONDS as dictated (e.g. "3.4") — whatever unit the',
  'protocol prose above uses to state the threshold. Never convert a dictated',
  'value, and never rewrite the protocol prose to match the column.',
].join('\n');


/**
 * Build the ultrasound report SYSTEM prompt from the resolved ultrasound
 * template. Unlike buildSoapSystemPrompt (which sources the immutable safety
 * layer from the SOAP system-default), this uses the ULTRASOUND template's own
 * styleProfile — an imaging-report preamble + the shared anti-hallucination
 * rules + measurement/laterality discipline.
 */
export function buildUltrasoundSystemPrompt(
  template: ResolvedNoteTemplate,
  opts: BuildSystemPromptOpts
): string {
  const sections = [...template.sections].sort((a, b) => a.order - b.order);

  const staticLines = staticLinesByKey(sections);
  const generativeSlots = hasGenerativeChoiceSlots(sections);
  // A reflux/reverse-flow TIME column anywhere in the template. The unit note
  // is about a table cell, so it is emitted only when a table asks for one.
  const hasRefluxTimeColumn = sections.some((s) =>
    (s.structure?.kind === 'table' ? s.structure.columns : []).some((c) =>
      /\b(reflux|reverse[-\s]?flow)\b/i.test(c)
    )
  );

  const lines: (string | null | undefined)[] = [
    // Imaging-report preamble (NOT the SOAP "writing a SOAP note" preamble).
    IMAGING_SAFETY.preamble,
    '',
    // Same dynamic hedge slices as L4 (audio quality / interpreter).
    opts.audioQualityAlert,
    opts.audioQualityAlert ? '' : null,
    opts.interpreterAlert,
    opts.interpreterAlert ? '' : null,
    // Report section structure.
    'Structure the report with these markdown headings exactly:',
    '',
    ...sections.flatMap((s) => [
      `## ${s.label}`,
      // `emptyStyleInstructionsFallBack` preserves this route's prior
      // behaviour: an EMPTY-STRING styleInstructions falls back to the format
      // hint, which the built-in ultrasound template relies on.
      ...renderSectionBody(s, staticLines, { emptyStyleInstructionsFallBack: true }),
      '',
    ]),
    // Anti-hallucination + measurement/laterality rules (from the ultrasound
    // styleProfile — reuses the SOAP safety rules verbatim + imaging discipline).
    'Critical rules:',
    ...IMAGING_SAFETY.globalRules,
    // Choice-slot directive — only for a custom template that actually has
    // `{{one of}}` menus; the built-in ultrasound template has none, so its
    // prompt is byte-identical to before.
    generativeSlots ? '' : null,
    generativeSlots ? CHOICE_SLOT_DIRECTIVE : null,
    // ⚠️ THE SAME CONTRACT THE SOAP ROUTE EMITS, ON THE ROUTE THAT ACTUALLY
    // CARRIES IT IN PRODUCTION. Both entries are null when the template has no
    // assembled statics, so the built-in ultrasound template's prompt — and
    // every custom imaging template until the reclassification — is unchanged.
    staticLines.size > 0 ? '' : null,
    staticLines.size > 0 ? SLOT_VALUES_DIRECTIVE : null,
    // Stated, not applied: see REFLUX_UNIT_NOTE. Only when a table asks for one.
    hasRefluxTimeColumn ? '' : null,
    hasRefluxTimeColumn ? REFLUX_UNIT_NOTE : null,
    // Instruction-as-data boundary (unchanged mechanism).
    delimiterSystemSuffix('transcript'),
  ];

  return lines.filter((l): l is string => typeof l === 'string').join('\n');
}
