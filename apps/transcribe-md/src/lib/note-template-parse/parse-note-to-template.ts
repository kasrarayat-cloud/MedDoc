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
  clampDraftToLimits,
  type ParsedTemplateDraft,
  type ParseNoteResult,
  type NoteTemplateSection,
  type SectionStructure,
} from './note-template-schema';
import {
  applyPhiGate,
  enumerateTextFields,
  dropAdministrativeChrome,
  detectPhiKeywords,
} from './phi-gate';
import {
  reconcileBodyMarkers,
  reconcileHeaderMarkers,
  dropHeaderMarkerSections,
  firstClinicalHeadingIndex,
} from './reconcile-markers';

// TRANSCRIBE_MD_CLINICAL_MODEL — eval override (feat/fable5-eval); unset → default unchanged.
const MODEL = process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-opus-4-8';

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
  "  clinician's own wording in `label` — including any numbering that is",
  '  part of the heading itself (e.g. "1. Subjective Data", "2.1 Vital',
  '  Signs"), verbatim. Numbered headings are part of the format.',
  '- `formatHint` per section: prose | bullets | numbered.',
  '- `structure` per section, ONLY when the note clearly shows one:',
  '  * a TABLE (values organized in columns): {"kind":"table","columns":',
  '    [...], "rowLabels":[...]} — columns verbatim; rowLabels ONLY when the',
  '    template fixes the rows (e.g. a vitals grid BP/HR/RR); omit rowLabels',
  '    when rows vary per patient (e.g. a medication list). Note: a Word',
  '    table may reach you flattened to alternating label/value lines —',
  '    reconstruct the grid when the pattern is clear.',
  '  * an OPTION SET (checkbox glyphs like ☐, "circle one", "check all',
  '    that apply", Normal/Abnormal picks, severity or 0-10 scales):',
  '    {"kind":"options","options":[...],"multi":true|false} — options',
  "    VERBATIM from the note (keep the clinician's own wording and",
  '    spelling; a 0-10 scale becomes options "0".."10"); multi=true ONLY',
  '    for "check all that apply"-style sets.',
  '  Sections without a clear table/option structure OMIT `structure`.',
  '- CHOICE MARKERS: the note may contain inline dropdown choices written',
  '  `{{one of: A | B | C}}` — a fixed set the clinician picks ONE from. These',
  '  come from Word dropdown fields. PRESERVE every marker EXACTLY and verbatim',
  '  — all options, in order, wrapped in `{{one of: ... }}` — inside that',
  "  section's `defaultText`, keeping the surrounding fixed sentence so the",
  '  marker stays in its carrier sentence (e.g. "The {{one of: ...vein...}}',
  '  from the {{one of: ...segment...}} ..."). NEVER drop or reword options,',
  '  collapse a marker to one value, or move its options into `structure`.',
  '  A marker is generic FORMAT (a menu of choices), never patient content.',
  '- `styleInstructions`: brief GENERIC guidance on how the section is written',
  '  (structure/tone). Describe the FORMAT; never copy patient content.',
  '- `defaultText`: ONLY clearly-generic, reusable templated language that',
  '  recurs across patients (e.g. a normal-exam boilerplate with NO patient',
  '  specifics). If a passage mixes generic + patient-specific, OMIT it.',
  '- `styleProfile`: overall tense / tone / abbreviation style.',
  '',
  'Keep generated text CONCISE: `name` is a short label (a few words); each',
  '`styleProfile` value (tense / tone / abbreviations) is a brief phrase, not a',
  "sentence; `label`s are the clinician's own headings. Over-long values are",
  'truncated, so be succinct.',
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
  'EXCLUDE administrative chrome — extract ONLY the clinical note body. Do NOT',
  'create sections for the practice letterhead / clinic metadata, the patient',
  'demographics or header block (name, MRN, DOB, age, insurance, date of',
  'visit, provider line, etc.), or the signature / attestation footer. Those',
  'are system-rendered identifiers, not note format. If present, note their',
  'omission in `flags` ("skipped the patient header — added automatically").',
  '',
  'Do NOT write instructions to generate ICD/CPT codes or include specific code',
  'values — medical coding is produced by a separate validated step, not this',
  'note. If the clinician uses inline ICD/CPT codes as a convention, note that',
  'in `flags` ("you include ICD codes inline — our coding step produces those")',
  'rather than putting code generation into styleInstructions.',
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
// ── Structure sanitizer (feat/structured-templates, 2026-07-02) ────────────
// Deterministic cleanup of LLM-emitted structure BEFORE the draft leaves the
// parse: trims entries, drops empties, DEDUPES options case-insensitively
// (first-seen casing wins — a doctor's duplicated "☐ Moderate ☐ Moderate"
// collapses to one), and drops degenerate structures (an empty option set or
// a single-option "set" falls back to prose). The doctor's own wording —
// including typos — is preserved verbatim: constrained fill may only pick
// from THEIR list, so their list is reproduced as-is.
function sanitizeStructure(
  structure: SectionStructure | null
): SectionStructure | null {
  if (!structure) return null;
  if (structure.kind === 'options') {
    const seen = new Set<string>();
    const options: string[] = [];
    for (const raw of structure.options) {
      const o = raw.trim().slice(0, 120);
      if (!o) continue;
      const k = o.toLowerCase();
      if (seen.has(k)) continue;
      seen.add(k);
      options.push(o);
    }
    if (options.length < 2) return null; // degenerate → prose
    return { kind: 'options', options: options.slice(0, 24), multi: structure.multi };
  }
  const columns = structure.columns
    .map((c: string) => c.trim().slice(0, 60))
    .filter(Boolean)
    .slice(0, 8);
  if (columns.length < 2) return null;
  const rowLabels = structure.rowLabels
    ?.map((r: string) => r.trim().slice(0, 80))
    .filter(Boolean)
    .slice(0, 30);
  return {
    kind: 'table',
    columns,
    ...(rowLabels && rowLabels.length > 0 ? { rowLabels } : {}),
  };
}

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
      structure: sanitizeStructure(s.structure ?? null),
    }));

  // ── 2b. Drop administrative chrome (letterhead / demographics / signature)
  //    DETERMINISTICALLY — regardless of LLM run-to-run variance — BEFORE the
  //    PHI gate. These blocks are system-rendered identifiers or pure PHI, not
  //    clinical note FORMAT, and are where MRN/DOB-style content appears. The
  //    gate then runs on the surviving clinical sections and stays the
  //    fail-safe backstop on everything that survives. ──
  const { kept, droppedLabels } = dropAdministrativeChrome(sections);
  const clinicalSections = kept.map((s, i) => ({ ...s, order: i + 1 }));
  const flags = [...llm.flags];
  if (droppedLabels.length > 0) {
    flags.push(
      'Skipped the patient header and signature block — those are added automatically, not part of your note format.'
    );
  }
  if (clinicalSections.length === 0) {
    return {
      rejected: true,
      template: null,
      reason:
        "Couldn't find a clinical note body to template — the note looked like header/signature only. Paste the clinical sections (history, exam, assessment, plan) and try again.",
    };
  }

  // Stable header/body boundary = source line index of the first clinical
  // heading, computed ONCE from the FULL clinical-section set. Both reconcile
  // passes use it so the split is identical even after sections are dropped/
  // scrubbed between them — a body-region line can never be reclassified as
  // header and restored post-gate (which would bypass the LLM PHI scan).
  const headerBoundaryIdx = firstClinicalHeadingIndex(noteText, clinicalSections);

  // Reconcile dropped BODY-region markers BEFORE the PHI scan (fix/template-
  // parse-determinism). A body carrier sentence the LLM dropped can, in a pasted
  // FILLED example, carry a patient name / free-text specific that only the LLM
  // PHI-scan (not regex) catches — so re-attaching body markers here means the
  // full gate (regex ∪ LLM, steps 3-4) covers them. Header-region markers are
  // restored AFTER the gate (step 5): scanning the provider-label metadata block
  // makes the LLM scan reject non-deterministically. No body markers → no-op.
  const bodyReconciled = reconcileBodyMarkers(noteText, clinicalSections, headerBoundaryIdx);

  // Drop header-marker sections (provider / clinic / study-metadata dropdowns)
  // BEFORE the PHI scan: their provider-identifier LABELS make the scan LLM
  // variably reject the whole parse. reconcileHeaderMarkers restores every one
  // deterministically AFTER the gate (step 5). No header markers → no-op.
  const sectionsForScan = dropHeaderMarkerSections(noteText, bodyReconciled);

  // Clamp generated string fields to their persisted caps so a verbose value
  // (e.g. a long styleProfile.tense) can never break review/save or leak a raw
  // Zod "Too big". Done BEFORE the PHI gate below, so the gate scans the final
  // (clamped) values; truncation only removes content (PHI-neutral).
  const draft: ParsedTemplateDraft = clampDraftToLimits({
    name: llm.name,
    encounterType: llm.encounterType,
    sections: sectionsForScan,
    styleProfile: llm.styleProfile,
  });

  // ── 3. PHI-scan LLM over the built fields (the gate's content-aware layer).
  //    Bare PHI field-name keywords (no value) are demoted to a SOFT signal:
  //    the affected paths are handed to the LLM scan for extra scrutiny rather
  //    than auto-rejected (a label word alone carries no patient data). ──
  const fields = enumerateTextFields(draft);
  const fieldsForScan = Object.fromEntries(fields.map((f) => [f.path, f.value]));
  const keywordFields = fields
    .filter((f) => detectPhiKeywords(f.value))
    .map((f) => f.path);
  const scanUser = [
    'Template fields to audit (path → value):',
    wrapAsData(JSON.stringify(fieldsForScan, null, 2), 'transcript').wrapped,
  ];
  if (keywordFields.length > 0) {
    scanUser.push(
      `Extra scrutiny: these fields mention identifier LABELS — confirm they carry no patient VALUES (a label word alone is fine): ${keywordFields.join(', ')}.`
    );
  }
  const scan = await modelClient.complete({
    practiceId: ctx.practiceId,
    visitId: null,
    userId: ctx.userId,
    purpose: 'tm_template_phi_scan',
    provider: 'anthropic',
    model: MODEL,
    system: PHI_SCAN_SYSTEM,
    user: scanUser.join('\n'),
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
  const gated = applyPhiGate(draft, flags, scan.phiFields, scan.anyUncertain);
  if (gated.rejected || !gated.template) return gated;

  // ── 5. Deterministic HEADER-marker reconciliation (fix/template-parse-
  //    determinism), AFTER the gate. The docx extraction is authoritative for
  //    the FULL set of {{one of}} dropdowns; the LLM structuring step can drop
  //    the header-region ones (side of exam / physician / machine / location /
  //    indications / diagnosis) run-to-run. Restore them into an Exam Metadata
  //    section (marker LINES only, so no raw provider-name fixed text). Running
  //    header reconciliation AFTER the gate is deterministic: the provider/clinic
  //    names are dropdown OPTIONS (excluded from the PHI scan) and each restored
  //    line's fixed carrier is regex-PHI-scanned — while a pre-scan restore of
  //    this metadata block would make the LLM scan reject non-deterministically.
  //    Body markers were already reconciled + fully scanned pre-gate (step 2).
  //    No-op when the LLM preserved the header markers, or the note has none
  //    (SOAP / scaffold-free templates) → byte-identical. ──
  const reconciled = reconcileHeaderMarkers(noteText, gated.template.sections, headerBoundaryIdx);
  return { ...gated, template: { ...gated.template, sections: reconciled } };
}
