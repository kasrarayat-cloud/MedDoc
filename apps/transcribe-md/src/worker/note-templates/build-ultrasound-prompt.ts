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

/** Render one section's body. The ultrasound sections carry styleInstructions
 *  and never inject default text (all omit_unless_supported), so this is just
 *  the directive line(s). */
function renderSectionBody(styleInstructions: string | null, formatHint: string): string[] {
  if (styleInstructions) return [styleInstructions];
  switch (formatHint) {
    case 'numbered':
      return ['Write this section as a numbered list.'];
    case 'bullets':
      return ['Write this section as a bulleted list.'];
    default:
      return ['Write this section as prose.'];
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
    template.styleProfile.preamble,
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
      ...renderSectionBody(s.styleInstructions, s.formatHint),
      '',
    ]),
    // Anti-hallucination + measurement/laterality rules (from the ultrasound
    // styleProfile — reuses the SOAP safety rules verbatim + imaging discipline).
    'Critical rules:',
    ...template.styleProfile.globalRules,
    // Instruction-as-data boundary (unchanged mechanism).
    delimiterSystemSuffix('transcript'),
  ];

  return lines.filter((l): l is string => typeof l === 'string').join('\n');
}
