// ============================================================================
// Note-format customization — Phase 2a: parse a doctor's note → template
// ----------------------------------------------------------------------------
// STATELESS + PHI-SAFE. Takes a doctor's note TEXT, returns a structured
// template DRAFT (format/style only) or a rejection. Persists NOTHING: the
// note text is processed in-memory and discarded; the AI-call logger records
// only a prompt HASH + metadata (never raw content); this module writes no DB
// row, no log line, no file containing the note.
//
// Pipeline:
//   1. Parse LLM (useToolUse + Zod ParsedTemplateLlmSchema) — extract FORMAT.
//   2. Build the draft; FORCE defaultTextMode = scaffold_confirm for any
//      parsed default (never always_include).
//   3. PHI-scan LLM (useToolUse + Zod PhiScanSchema) over the built fields.
//   4. Fail-safe PHI gate (regex + LLM scan): scrub defaults / REJECT on doubt.
//
// SAFETY BOUNDARY: the parse produces FORMAT only. It never emits the
// immutable anti-hallucination preamble/guardrails (those are sourced at
// generation time from the canonical system default, per Phase 1) — the
// output schema has no such fields. A resulting template can only append
// sections; it cannot weaken safety.
// ============================================================================

import {
  modelClient,
  wrapAsData,
  delimiterSystemSuffix,
} from '@meddoc/ai';
import {
  ParsedTemplateLlmSchema,
  PhiScanSchema,
  type ParsedTemplateDraft,
  type ParseNoteResult,
  type NoteTemplateSection,
} from './note-template-schema';
import { applyPhiGate, enumerateTextFields } from './phi-gate';

const MODEL = 'claude-opus-4-7';

export interface ParseContext {
  /** Tenant for AI-call cost attribution (never persisted with the note). */
  practiceId: string;
  /** Calling doctor for per-user cost rollups; null tolerated. */
  userId: string | null;
}

const PARSE_SYSTEM = [
  "You are extracting the FORMAT of a clinician's note template — NOT its",
  'content. You are given ONE clinician\'s note. Produce a reusable note-',
  'format template: its section structure, ordering, formatting, phrasing',
  'style, and any clearly-generic reusable ("normal"/boilerplate) text.',
  '',
  'EXTRACT (format/style only):',
  '- Section headings in order. Set `key` to the canonical slug when it maps',
  '  to a standard section (subjective, objective, ros, pe, assessment, plan,',
  '  patient_education); otherwise a slug of the heading. Preserve the',
  "  clinician's own wording in `label`.",
  '- `formatHint` per section: prose | bullets | numbered.',
  '- `styleInstructions`: brief GENERIC guidance on how the section is written',
  '  (structure/tone). Describe the FORMAT; never copy patient content.',
  '- `defaultText`: ONLY clearly-generic, reusable templated language that',
  '  recurs across patients (e.g. a normal-exam boilerplate with NO patient',
  '  specifics). If a passage mixes generic + patient-specific, OMIT it.',
  '- `styleProfile`: overall tense / tone / abbreviation style.',
  '',
  'NEVER include patient-specific content of ANY kind: names, dates, ages,',
  'MRNs, contact info, specific findings, measurements, values, sites, or any',
  'detail unique to a patient. That is PHI and must not appear anywhere in the',
  'template — not in labels, instructions, defaults, the name, or styleProfile.',
  '',
  'If UNSURE whether a phrase is reusable boilerplate vs. a patient specific,',
  'OMIT it and add a short note to `flags` describing the FORMAT of what you',
  'omitted (e.g. "a normal cardiac exam line — confirm before adding"). NEVER',
  'quote patient content in `flags` either.',
  '',
  'Submit via the submit_note_template tool.',
  delimiterSystemSuffix('transcript'),
].join('\n');

const PHI_SCAN_SYSTEM = [
  'You are a STRICT PHI auditor. You are given the TEXT FIELDS of a note-',
  'format template. It should contain ONLY formatting/structure/style — never',
  'patient data. Identify any field containing Protected Health Information or',
  'any patient-specific content: names, dates, ages, MRNs/IDs, contact info,',
  'specific findings, measurements, values, sites, or anything unique to a',
  'patient.',
  '',
  'Return `phiFields`: the exact field paths (as given, e.g. "name",',
  '"sections[2].defaultText", "sections[0].label") that contain ANY such',
  'content. Be CONSERVATIVE — when in doubt, INCLUDE the field. If you are',
  'unsure about the overall safety of ANY field, set `anyUncertain` = true.',
  '',
  'Generic templated language ("all systems reviewed and negative", "normal',
  'exam") is NOT PHI. A FORMAT instruction ("write as a numbered list") is NOT',
  'PHI. Only patient-specific content counts.',
  '',
  'Submit via the submit_phi_scan tool.',
  delimiterSystemSuffix('transcript'),
].join('\n');

/**
 * Parse a doctor's note into a template draft. Stateless + PHI-gated.
 * Throws ModelOutputMalformedError (from @meddoc/ai) if the parse LLM output
 * fails schema validation after retries — the caller maps that to a generic
 * "couldn't parse" without surfacing raw content.
 */
export async function parseNoteToTemplate(
  noteText: string,
  ctx: ParseContext
): Promise<ParseNoteResult> {
  // ── 1. Parse LLM — extract format/style. Wrap the note as data for
  //    prompt-injection safety. The worker pipeline (L4/L5) logs a
  //    PIPELINE_REJECTED_INJECTION_DELIMITER audit row (keyed by visitId) and
  //    continues; this is a STATELESS, visit-less action with a strict no-
  //    persistence guarantee, so instead of logging we REJECT outright — we
  //    refuse to parse a note crafted to escape the data boundary. ──
  const wrapped = wrapAsData(noteText, 'transcript');
  if (wrapped.injectionAttemptDetected) {
    return {
      rejected: true,
      template: null,
      reason:
        'This note contains text resembling a system delimiter and can\'t be safely parsed. Remove any angle-bracket delimiter tokens and try again.',
    };
  }
  const llm = await modelClient.complete({
    practiceId: ctx.practiceId,
    visitId: null,
    userId: ctx.userId,
    purpose: 'tm_template_parse',
    provider: 'anthropic',
    model: MODEL,
    system: PARSE_SYSTEM,
    user: ['Clinician note to extract the FORMAT from:', wrapped.wrapped].join('\n'),
    schema: ParsedTemplateLlmSchema,
    maxTokens: 4096,
    temperature: 0,
    useToolUse: {
      name: 'submit_note_template',
      description:
        "Submit the reusable FORMAT of the clinician's note — sections, order, formatting, style, and only clearly-generic default text. No patient-specific content.",
    },
  });

  // ── 2. Build the draft. FORCE defaultTextMode: a parsed default is always
  //    scaffold_confirm (doctor must confirm), never always_include. ──
  const sections: NoteTemplateSection[] = [...llm.sections]
    .sort((a, b) => a.order - b.order)
    .map((s, i) => ({
      key: s.key,
      label: s.label,
      order: i + 1,
      formatHint: s.formatHint,
      styleInstructions: s.styleInstructions,
      defaultText: s.defaultText,
      defaultTextMode: s.defaultText ? 'scaffold_confirm' : 'omit_unless_supported',
    }));

  const draft: ParsedTemplateDraft = {
    name: llm.name,
    encounterType: llm.encounterType,
    sections,
    styleProfile: llm.styleProfile,
  };

  // ── 3. PHI-scan LLM over the built fields (the gate's content-aware layer). ──
  const fields = enumerateTextFields(draft);
  const fieldsForScan = Object.fromEntries(fields.map((f) => [f.path, f.value]));
  const scan = await modelClient.complete({
    practiceId: ctx.practiceId,
    visitId: null,
    userId: ctx.userId,
    purpose: 'tm_template_phi_scan',
    provider: 'anthropic',
    model: MODEL,
    system: PHI_SCAN_SYSTEM,
    user: [
      'Template fields to audit (path → value):',
      wrapAsData(JSON.stringify(fieldsForScan, null, 2), 'transcript').wrapped,
    ].join('\n'),
    schema: PhiScanSchema,
    maxTokens: 1024,
    temperature: 0,
    useToolUse: {
      name: 'submit_phi_scan',
      description:
        'Submit the list of template field paths that contain PHI / patient-specific content, plus an uncertainty flag.',
    },
  });

  // ── 4. Fail-safe gate (regex + LLM scan): scrub defaults / reject on doubt. ──
  return applyPhiGate(draft, llm.flags, scan.phiFields, scan.anyUncertain);
}
