// ============================================================================
// SOAP prompt builder — Phase 1. Builds L4's system + user prompt from a
// resolved NoteTemplate instead of a hard-coded string.
// ----------------------------------------------------------------------------
// BYTE-IDENTITY CONTRACT: for the system-default template, buildSoapSystemPrompt
// reproduces the exact prompt L4 emitted before Phase 1 (locked by the golden
// test at worker/layers/__tests__/l4-golden-prompt.test.ts). The line layout
// here mirrors the original L4 array element-for-element.
//
// SAFETY BOUNDARY: the anti-hallucination preamble + global guardrails are
// IMMUTABLE — sourced from the canonical system-default styleProfile, NEVER
// from the (possibly custom) resolved template. A custom template contributes
// SECTIONS only; it appends structure, it can never override or weaken the
// safety layer. The preamble stays first; the guardrails stay in their fixed
// position after the sections.
// ============================================================================

import { delimiterSystemSuffix } from '@meddoc/ai';
import {
  SYSTEM_DEFAULT_NOTE_TEMPLATE,
  type NoteTemplateSection,
  type NoteTemplateStyleProfile,
  type SectionFormatHint,
} from './system-default-template';

/** The minimal template shape the builder consumes — produced from either the
 *  system-default constant or a Prisma NoteTemplate row (via {@link
 *  normalizeTemplate}). */
export interface ResolvedNoteTemplate {
  id: string;
  version: number;
  isSystemDefault: boolean;
  sections: NoteTemplateSection[];
  styleProfile: NoteTemplateStyleProfile;
}

/** The IMMUTABLE safety layer (preamble + global guardrails). Always sourced
 *  from the canonical system default so a custom template cannot weaken it. */
const SAFETY = SYSTEM_DEFAULT_NOTE_TEMPLATE.styleProfile;

/** Marker appended after a `scaffold_confirm` default — signals the clinician
 *  (and L5's normals-scrutiny) that the text was inserted as a scaffold and
 *  must be verified against the transcript or removed. */
export const SCAFFOLD_CONFIRM_MARKER =
  '[SCAFFOLD — confirm this against the transcript or remove it; it was inserted as a template default, not derived from the encounter.]';

/** Normalize a Prisma NoteTemplate row (JSONB columns are untyped) into the
 *  builder's shape. */
export function normalizeTemplate(row: {
  id: string;
  version: number;
  isSystemDefault: boolean;
  sections: unknown;
  styleProfile: unknown;
}): ResolvedNoteTemplate {
  return {
    id: row.id,
    version: row.version,
    isSystemDefault: row.isSystemDefault,
    sections: (row.sections as NoteTemplateSection[]) ?? [],
    styleProfile: (row.styleProfile as NoteTemplateStyleProfile) ?? SAFETY,
  };
}

function formatHintDirective(hint: SectionFormatHint): string {
  switch (hint) {
    case 'numbered':
      return 'Write this section as a numbered list.';
    case 'bullets':
      return 'Write this section as a bulleted list.';
    case 'prose':
    default:
      return 'Write this section as prose.';
  }
}

/** Render the body lines for one section: the explicit styleInstructions (or a
 *  formatHint fallback), then any inserted default per defaultTextMode.
 *  `omit_unless_supported` injects NOTHING — the section is included only if
 *  the transcript supports it, which the styleInstructions already govern.
 *  This is why the system default (all sections omit_unless_supported) yields
 *  exactly the original L4 bytes. */
// ── Structured-fill directives (feat/structured-templates, 2026-07-02) ─────
// Tables + option-sets are CONSTRAINED-CHOICE tasks and must be MORE
// conservative than free text: option fields may only take one of the
// template's own enumerated options (or stay unchecked); table cells take
// dictated values only, with the canonical "[not documented]" token for
// silent cells (verifier-exempt scaffolding — asserts no clinical fact).
// Every sentence RESTATES an existing immutable guardrail; nothing here
// relaxes one. Emitted ONLY for sections carrying `structure` — the system
// default has none, so the golden-prompt bytes are untouched.
function renderStructureDirective(
  structure: NonNullable<NoteTemplateSection['structure']>
): string {
  if (structure.kind === 'options') {
    const lines = structure.options.map((o) => `- [ ] ${o}`);
    return [
      'This section is a CHECKLIST. Reproduce ALL of these option lines —',
      'every line, in this order, byte-for-byte — changing ONLY "[ ]" to',
      '"[x]" where checked:',
      ...lines,
      structure.multi
        ? 'Multiple options may be checked ("check all that apply").'
        : 'At most ONE option may be checked (single-select).',
      'Mark "- [x]" ONLY when the transcript AFFIRMS that option as present.',
      'A DENIED or negative finding does NOT check that option — "denies',
      'fever" means the Fever line stays "- [ ]"; when the transcript denies',
      'every finding in a group and the group has a "None"-style option,',
      'check that "None" option instead. A checked option is a clinical',
      'claim and needs an evidence anchor appended to its line; unchecked',
      'lines need no anchor and assert nothing. NEVER check an option',
      'because it is typical, plausible, or usually true. Never add, remove,',
      'reorder, merge, reword, or annotate option lines — not even to fix a',
      'spelling.',
    ].join('\n');
  }
  const header = `| ${structure.columns.join(' | ')} |`;
  const separator = `| ${structure.columns.map(() => '---').join(' | ')} |`;
  if (structure.rowLabels && structure.rowLabels.length > 0) {
    const rows = structure.rowLabels.map(
      (r) =>
        `| ${r} |${structure.columns
          .slice(1)
          .map(() => ' [not documented] |')
          .join('')}`
    );
    return [
      'This section is a TABLE with fixed rows. Reproduce this markdown',
      'table skeleton exactly — same header row, same row labels, same',
      'order:',
      header,
      separator,
      ...rows,
      'Replace a "[not documented]" cell ONLY with a value the transcript',
      'states, copied as dictated — do not append units or qualifiers the',
      'transcript does not state. Leave it "[not documented]" otherwise.',
      'Never invent, estimate, or carry forward a value. Do not add,',
      'remove, rename, or reorder rows or columns. Append the evidence',
      'anchor(s) for a filled row after its final "|".',
    ].join('\n');
  }
  return [
    'This section is a TABLE. Reproduce this markdown table skeleton',
    'exactly — same header row, same column order; do not add, remove,',
    'rename, or reorder columns:',
    header,
    separator,
    'Add ONE row per item the transcript supports, and append the evidence',
    'anchor(s) for each row after its final "|". Copy cell values as',
    'dictated — do not append units or qualifiers the transcript does not',
    'state. In a supported row, put "[not documented]" in any cell whose',
    'value the transcript does not state — never invent a value to',
    'complete a row. Do NOT add a row for an item the transcript never',
    'mentions.',
  ].join('\n');
}

function renderSectionBody(s: NoteTemplateSection): string[] {
  const out: string[] = [];
  out.push(s.styleInstructions ?? formatHintDirective(s.formatHint));
  if (s.structure) {
    out.push(renderStructureDirective(s.structure));
  }
  if (s.defaultText) {
    if (s.defaultTextMode === 'always_include') {
      out.push(s.defaultText);
    } else if (s.defaultTextMode === 'scaffold_confirm') {
      out.push(`${s.defaultText}\n${SCAFFOLD_CONFIRM_MARKER}`);
    }
    // omit_unless_supported → never inject the default.
  }
  return out;
}

export interface BuildSystemPromptOpts {
  /** Visit specialty — used only for the specialty-guidance line label. */
  specialty: string;
  /** L4's dynamic audio-quality hedge block, or null. */
  audioQualityAlert: string | null;
  /** L4's interpreter-mode block, or null. */
  interpreterAlert: string | null;
  /** specialtyGuidance(specialty) text, or null/empty when none. */
  specialtyGuidanceText: string | null;
}

/**
 * Build the L4 SYSTEM prompt from a resolved template. Element order mirrors
 * the pre-Phase-1 L4 array exactly; for the system default this is byte-
 * identical to the original (golden-locked).
 */
export function buildSoapSystemPrompt(
  template: ResolvedNoteTemplate,
  opts: BuildSystemPromptOpts
): string {
  const sections = [...template.sections].sort((a, b) => a.order - b.order);
  const guidance = opts.specialtyGuidanceText || null;

  const lines: (string | null | undefined)[] = [
    // 1. Immutable safety preamble — always first.
    SAFETY.preamble,
    '',
    // Dynamic hedge slices (same conditionals as the original L4).
    opts.audioQualityAlert,
    opts.audioQualityAlert ? '' : null,
    opts.interpreterAlert,
    opts.interpreterAlert ? '' : null,
    // 3. Template sections.
    'Structure the note with these markdown headings exactly:',
    '',
    ...sections.flatMap((s) => [`## ${s.label}`, ...renderSectionBody(s), '']),
    // 5. Immutable safety guardrails — fixed position after the sections.
    'Critical rules:',
    ...SAFETY.globalRules,
    // Specialty guidance (unchanged mechanism — from specialtyGuidance()).
    guidance ? '' : undefined,
    guidance ? `Specialty guidance (${opts.specialty}):\n${guidance}` : undefined,
    // Instruction-as-data boundary (unchanged).
    delimiterSystemSuffix('transcript'),
  ];

  return lines.filter((l): l is string => typeof l === 'string').join('\n');
}

export interface BuildUserPromptOpts {
  specialty: string;
  /** JSON.stringify(entities, null, 2) — computed by the caller. */
  entitiesJson: string;
  /** wrapAsData(transcript).wrapped — computed by the caller. */
  wrappedTranscript: string;
}

/**
 * Build the L4 USER prompt. UNCHANGED from the original L4 — the transcript /
 * entities injection mechanism is not template-driven.
 */
export function buildSoapUserPrompt(opts: BuildUserPromptOpts): string {
  return [
    `Specialty: ${opts.specialty}`,
    '',
    'Extracted entities (structured, with evidence):',
    opts.entitiesJson,
    '',
    'Role-labeled transcript:',
    opts.wrappedTranscript,
  ].join('\n');
}

/** Sections whose template default would be INSERTED into the draft (i.e. not
 *  omit_unless_supported with a default). L5's normals-scrutiny checks these
 *  against the transcript. Empty for the system default. */
export function insertedDefaultSections(
  template: ResolvedNoteTemplate
): NoteTemplateSection[] {
  return template.sections.filter(
    (s) =>
      s.defaultText != null &&
      (s.defaultTextMode === 'always_include' ||
        s.defaultTextMode === 'scaffold_confirm')
  );
}

/** The template's required section labels — used by the generalized
 *  structure validator. */
export function requiredSectionLabels(template: ResolvedNoteTemplate): string[] {
  return [...template.sections]
    .sort((a, b) => a.order - b.order)
    .map((s) => s.label);
}
