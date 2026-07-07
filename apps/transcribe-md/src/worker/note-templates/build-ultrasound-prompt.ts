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
  renderStructureDirective,
  SCAFFOLD_CONFIRM_MARKER,
  CHOICE_SLOT_DIRECTIVE,
  templateHasChoiceSlots,
} from './build-soap-prompt';
import type { NoteTemplateSection } from './system-default-template';
import { ULTRASOUND_REPORT_TEMPLATE } from './ultrasound-report-template';

/** The immutable imaging-report safety layer (preamble + anti-hallucination /
 *  measurement / laterality rules). ALWAYS sourced from the canonical
 *  ultrasound template — never from the passed template — so a doctor's custom
 *  imaging template contributes only its SECTIONS and can no more weaken the
 *  imaging safety rules than a custom SOAP template can weaken the SOAP ones.
 *  (A custom template's styleProfile carries tense/tone, not globalRules.) */
const IMAGING_SAFETY = ULTRASOUND_REPORT_TEMPLATE.styleProfile;

/** Render one section's body. The BUILT-IN ultrasound template carries only
 *  styleInstructions and no default text — for it this is byte-identical to
 *  before. A CUSTOM imaging template (a doctor's own report) may also carry
 *  table/option `structure` and marker-bearing scaffold `defaultText`; emit
 *  those the same way the SOAP builder does so the custom report is filled
 *  from its own fields. */
function renderSectionBody(s: NoteTemplateSection): string[] {
  const out: string[] = [];
  // `||` (not `??`) preserves the built-in template's prior behavior: an
  // empty-string styleInstructions falls back to the format-hint directive.
  out.push(s.styleInstructions || formatHintDirective(s.formatHint));
  if (s.structure) out.push(renderStructureDirective(s.structure));
  if (s.defaultText) {
    if (s.defaultTextMode === 'always_include') out.push(s.defaultText);
    else if (s.defaultTextMode === 'scaffold_confirm')
      out.push(`${s.defaultText}\n${SCAFFOLD_CONFIRM_MARKER}`);
  }
  return out;
}

function formatHintDirective(formatHint: string): string {
  switch (formatHint) {
    case 'numbered':
      return 'Write this section as a numbered list.';
    case 'bullets':
      return 'Write this section as a bulleted list.';
    default:
      return 'Write this section as prose.';
  }
}

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
    ...sections.flatMap((s) => [`## ${s.label}`, ...renderSectionBody(s), '']),
    // Anti-hallucination + measurement/laterality rules (from the ultrasound
    // styleProfile — reuses the SOAP safety rules verbatim + imaging discipline).
    'Critical rules:',
    ...IMAGING_SAFETY.globalRules,
    // Choice-slot directive — only for a custom template that actually has
    // `{{one of}}` menus; the built-in ultrasound template has none, so its
    // prompt is byte-identical to before.
    templateHasChoiceSlots(sections) ? '' : null,
    templateHasChoiceSlots(sections) ? CHOICE_SLOT_DIRECTIVE : null,
    // Instruction-as-data boundary (unchanged mechanism).
    delimiterSystemSuffix('transcript'),
  ];

  return lines.filter((l): l is string => typeof l === 'string').join('\n');
}
