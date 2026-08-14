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
import { segmentStaticSections, staticSections } from './assemble-note';
import type { AssemblyLine } from './section-assembly';
import {
  renderStaticSectionRequest,
  SLOT_VALUES_DIRECTIVE,
} from './slot-fill-protocol';

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

/** Directive for inline dropdown menus rendered as `{{one of: A | B | C}}`
 *  choice slots (from Word content-control dropdowns; see
 *  docx-content-controls.ts). Constrained-fill invariant: pick ONLY a listed
 *  option, blank when unsupported, never invent — and fill a multi-slot
 *  carrier sentence as one coherent set.
 *
 *  ⚠️ ITS REPRODUCE-THE-SCAFFOLD CONTRACT IS RETIRED FOR `always_include`
 *  SECTIONS (ruling #106(a)). This directive hands the model the doctor's fixed
 *  prose and asks it to hold the line structure and hand it back — and a model
 *  asked to reproduce prose normalises it, which is how `500 milliseconds`
 *  became `0.5 seconds` in a real customer's note. A static section now takes
 *  `SLOT_VALUES_DIRECTIVE` instead: the model returns VALUES and never receives
 *  the doctor's bytes as writable.
 *
 *  ⚠️ IT IS NOT DELETED, AND THAT IS DELIBERATE. Slots also live in sections the
 *  model genuinely writes (`scaffold_confirm`, `omit_unless_supported`), and
 *  every template in production is still classified that way. Emitted ONLY when
 *  a NON-static section carries a marker — so a template with no statics
 *  produces a byte-identical prompt, which is #106(e)'s invariant and is now
 *  asserted rather than hoped for. */
export const CHOICE_SLOT_DIRECTIVE = [
  'CHOICE SLOTS. Some scaffold text contains inline menus written',
  '`{{one of: A | B | C}}`. For each menu, replace the ENTIRE `{{...}}` marker',
  'with EXACTLY ONE of its listed options, copied verbatim — the one the',
  'transcript supports. Pick ONLY from that menu\'s own listed options; never',
  'output a value that is not listed and never invent or reword an option.',
  'If the transcript supports none of a menu\'s options, do NOT guess: drop',
  'that marker (leave it blank); if the whole carrier sentence is then',
  'undictated, omit the sentence entirely.',
  'When one sentence has several menus (e.g. "The {{one of: ...vein...}} from',
  'the {{one of: ...segment...}} to the {{one of: ...segment...}} ..."), fill',
  'them as ONE coherent set: the segments must belong to the vein you chose',
  'and read proximal-to-distal. Never place an option from one menu into a',
  'different menu.',
  'SIDE / SUBJECT GROUNDING (laterality is sacred). A carrier names a specific',
  'side and structure (e.g. "Left great saphenous vein is {{...}}"). Choose an',
  'option ONLY when the transcript states it FOR THAT SAME side and structure.',
  'A finding about the RIGHT leg must NEVER fill a LEFT carrier\'s menu (and',
  'vice-versa); the mere appearance of an option\'s words elsewhere in the',
  'transcript (e.g. "reflux positive" said of the OTHER leg) is NOT support',
  'for THIS carrier. Never default to the first-listed option.',
  'NORMAL FINDING → OMIT, and never contradict a sibling line. When the',
  'transcript describes this carrier\'s side/structure as NORMAL / competent /',
  'no reflux and NO listed option encodes that (a menu of only abnormal',
  'options, e.g. "{{one of: reflux positive | is absent}}"), do NOT pick an',
  'abnormal option to fill the sentence — OMIT the entire carrier line. In',
  'particular, never emit a per-side abnormal carrier that contradicts an',
  'adjacent fixed line stating the opposite (e.g. keep "No saphenous reflux',
  'in <side> lower extremity." and drop that side\'s carrier).',
  'MUTUALLY-EXCLUSIVE SIBLING LINES (both directions). When a per-side carrier',
  'and a nearby FIXED scaffold line make OPPOSITE assertions about the SAME',
  'side and structure (e.g. the carrier "<Side> <vein> is {{one of: reflux',
  'positive. | is absent.}}" vs the fixed line "No saphenous reflux in <side>',
  'lower extremity."), they are ALTERNATIVES — emit EXACTLY ONE per side, the',
  'one the transcript supports, and DROP the other so the section never states',
  'a finding AND its negation for the same side. If the transcript dictates',
  'saphenous reflux on this side, keep the "... is reflux positive." carrier',
  '(with the correct vein and side) AND DROP the fixed "No saphenous reflux in',
  '<side> lower extremity." line. If the side is normal / competent (no',
  'saphenous reflux), DROP the reflux carrier and KEEP that fixed line. Resolve',
  'each side independently by ITS OWN dictated status (the two legs commonly',
  'differ — one refluxing, one normal).',
  'Preserve the scaffold\'s LINE STRUCTURE: reproduce each labeled field and',
  'each sentence on its OWN line, exactly as laid out — never merge separate',
  'fields or sentences onto one line.',
].join('\n');

/** True when any section carries an inline `{{one of: ...}}` choice slot. */
export function templateHasChoiceSlots(sections: readonly NoteTemplateSection[]): boolean {
  const re = /\{\{one of:/;
  return sections.some(
    (s) => re.test(s.defaultText ?? '') || re.test(s.styleInstructions ?? '')
  );
}

/** True when a slot lives in a section the MODEL still writes — i.e. anywhere
 *  outside the assembled static set. This, not the whole-template predicate, is
 *  what gates `CHOICE_SLOT_DIRECTIVE` now: a slot inside an `always_include`
 *  section is spoken about by the slot-values protocol instead, and telling the
 *  model to "replace the ENTIRE marker" in text it never receives would be an
 *  instruction about nothing. */
export function hasGenerativeChoiceSlots(
  sections: readonly NoteTemplateSection[]
): boolean {
  const staticKeys = new Set(staticSections(sections).map((s) => s.key));
  return templateHasChoiceSlots(sections.filter((s) => !staticKeys.has(s.key)));
}

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

/**
 * Reconcile venous-reflux TIME units to SECONDS (the code-wide convention —
 * see ultrasound-report-template.ts's measurement discipline — and how reflux
 * is dictated: "3.4 seconds"). A doctor's Word template may label the reflux
 * column and its threshold in milliseconds ("REFLUX TIME (ms)", "reflux
 * lasting more than 500 milliseconds"); a bare seconds value ("3.4") under an
 * "(ms)" header is a unit mismatch. We render the header/threshold in seconds
 * (never CONVERT the dictated value to ms — 3400 is a token the transcript
 * never states and would trip 04b's measurement guard). NARROW: touches only a
 * reflux / reverse-flow context, never other columns/units (e.g. "(mm)").
 * No reflux/ms token → returns the string unchanged.
 */
export function normalizeRefluxTimeUnit(text: string): string {
  if (!text) return text;
  // (1) Column header: "REFLUX TIME (ms)" / "reverse flow (msec)" -> "(seconds)".
  let out = text.replace(
    /\b(reflux|reverse[-\s]?flow)((?:\s+time)?[^()\n]*?)\(\s*(?:ms|msec|millisec(?:ond)?s?)\s*\)/gi,
    (_m, label, mid) => `${label}${mid}(seconds)`
  );
  // (2) Threshold prose: "reflux ... more than 500 milliseconds" -> "... 0.5 seconds".
  out = out.replace(
    /(\breflux\b[^.\n]*?\bmore than\s+)(\d+(?:\.\d+)?)\s*(?:ms|msec|milliseconds?)\b/gi,
    (_m, pre, num) => `${pre}${Number(num) / 1000} seconds`
  );
  return out;
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
export function renderStructureDirective(
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
  // ⚠️ THE DOCTOR'S COLUMN HEADERS, VERBATIM. This used to run them through
  // `normalizeRefluxTimeUnit`, rewriting `REFLUX TIME (ms)` to
  // `REFLUX TIME (seconds)` — the doctor's own header, edited to match a
  // convention we prefer.
  //
  // That is the same defect as ruling #107, one layer over: a header is
  // doctor-AUTHORED template text, and SPEC §4.3a(a) says such text is "never
  // paraphrased, never normalised, never 'improved'". The unit concern is real
  // — a bare seconds value under a milliseconds header IS a mismatch — but the
  // remedy belongs in what we ASK FOR, not in what the doctor wrote. See
  // `CELL_DISCIPLINE` below, which now states the convention explicitly.
  //
  // ⚠️ THE FUNCTION IS NOT DELETED. Its application to DICTATED or MODEL values
  // is a separate question, recorded as one and untouched tonight.
  const cols = [...structure.columns];
  const header = `| ${cols.join(' | ')} |`;
  const separator = `| ${cols.map(() => '---').join(' | ')} |`;
  // Cell-value discipline shared by both table shapes: a numeric column cell
  // holds the BARE value in the header's unit (no repeated/added unit word),
  // and a STATED-normal segment gets a clean "—" marker — never a prose phrase.
  const CELL_DISCIPLINE = [
    'A cell holds ONLY the BARE value: when a column header ends in a unit',
    // The example names the unit the DOCTOR's header uses, not one we prefer —
    // an instruction that silently models a rewritten header teaches the
    // rewrite. (It also stopped a test asserting the header is verbatim from
    // tripping on this very line: prose is where the token you are grepping for
    // is guaranteed to appear.)
    '(e.g. "DIAMETER (mm)", "REFLUX TIME (ms)"), write just the number',
    'the transcript dictated (e.g. "6.2") — never repeat the unit word and',
    'never write a unit the header does not name. Never put a phrase or a',
    'sentence in a cell.',
    'When the transcript EXPLICITLY reports a segment as normal/absent (e.g.',
    '"no reflux", "competent"), put "—" in that numeric cell — reserve',
    '"[not documented]" for a segment that was NOT assessed.',
    // Stated, not applied — see the header note above. This replaces an edit to
    // the doctor's own column header with an instruction about the value.
    'REFLUX / REVERSE-FLOW TIME IS WRITTEN IN SECONDS AS DICTATED (e.g. "3.4"),',
    'whatever unit the column header or the protocol prose uses to state the',
    'threshold. Never convert a dictated value, and never restate a header or',
    'a protocol sentence to match the cell.',
  ];
  if (structure.rowLabels && structure.rowLabels.length > 0) {
    // HOW MANY VALUE CELLS DOES A ROW HAVE?
    //
    // `.slice(1)` assumed the header's first column is the row-label column.
    // WM_IOV's is not: its header is [DIAMETER (mm) | REFLUX TIME (seconds)]
    // and the vein name lives in an unheaded first cell. So a row got ONE
    // placeholder for TWO data columns, and the generator did exactly what the
    // skeleton showed — one value per row — then said so in the note itself:
    //   "Diameter values ... could not be placed, as the table skeleton
    //    provides only a single value column per row."
    // Every diameter in the document was lost that way, and certification
    // blocked on a fill path that had never been given room to work.
    //
    // A header column that names a unit or a metric is a DATA column; a plain
    // word like "VEIN" is the label column. When the header is all data, the
    // label cell is extra and the row carries one placeholder per column.
    const isDataColumn = (h: string) =>
      /\([^)]*\)\s*$/.test(h) || /diameter|reflux|velocity|length|depth|time|size/i.test(h);
    const valueColumnCount =
      structure.columns.length > 0 && isDataColumn(structure.columns[0]!)
        ? structure.columns.length
        : structure.columns.length - 1;
    const rows = structure.rowLabels.map(
      (r) =>
        `| ${r} |${Array.from({ length: Math.max(valueColumnCount, 1) })
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
      'states, copied as dictated.',
      'Each row has one cell per column above, in that order — fill every',
      'column the transcript supports. Never drop a column, and never write a',
      'quotation or a sentence in place of a value.',
      ...CELL_DISCIPLINE,
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
    'anchor(s) for each row after its final "|".',
    ...CELL_DISCIPLINE,
    'Never invent a value to complete a row. Do NOT add a row for an item',
    'the transcript never mentions.',
  ].join('\n');
}

/**
 * Render one section's body — THE ONE IMPLEMENTATION, shared by both builders.
 *
 * ⚠️ IT IS EXPORTED BECAUSE A SECOND COPY ALMOST SHIPPED A CLINICAL DEFECT.
 * `build-ultrasound-prompt.ts` carried its own near-identical copy, and RC-1's
 * static-aware treatment was added to THIS one only. Every production visit
 * bound to the templates the reclassification migration touches takes the
 * IMAGING route — so the model would have been handed the doctor's bytes as
 * scaffold while `composeNote` composed as though it had not been, replacing
 * the model's dictated values (side of exam, indication) with an em dash on a
 * signed imaging report. Silently: both structure gates pass.
 *
 * That is AGENTS.md's "shared components — diff the callers BEFORE you replace
 * them" in its second recorded shape: the treatment was put on ONE caller and
 * verified there, correctly and incompletely. The cure the canon prescribes is
 * the one applied here — put the behaviour where it cannot be forgotten, on the
 * thing both callers already share.
 *
 * `styleInstructionsFallback` is the only remaining difference between the two
 * routes: the imaging builder uses `||` so an EMPTY-STRING styleInstructions
 * falls back to the format hint, which the built-in ultrasound template relies
 * on. A parameter, not a fork.
 */
export function renderSectionBody(
  s: NoteTemplateSection,
  staticLines: ReadonlyMap<string, AssemblyLine[]>,
  opts: { emptyStyleInstructionsFallBack?: boolean } = {}
): string[] {
  // ⚠️ A STATIC SECTION'S BODY IS A REQUEST, NOT A SCAFFOLD (ruling #106(a)).
  // The doctor's bytes are not in this prompt at all — not as text to
  // reproduce, not as an example, not behind a "do not change" instruction.
  // The model is told the section exists, told which holes it may fill and from
  // which menus, and nothing else. It also gets no styleInstructions and no
  // structure directive, because both describe how to WRITE a section this
  // model does not write.
  const lines = staticLines.get(s.key);
  if (lines !== undefined) {
    return renderStaticSectionRequest(s, lines);
  }
  const out: string[] = [];
  out.push(
    (opts.emptyStyleInstructionsFallBack
      ? s.styleInstructions || null
      : s.styleInstructions) ?? formatHintDirective(s.formatHint)
  );
  if (s.structure) {
    out.push(renderStructureDirective(s.structure));
  }
  if (s.defaultText) {
    if (s.defaultTextMode === 'always_include') {
      // Reachable only for an `always_include` section that `staticSections`
      // excludes — today that means a STRUCTURED one, whose cells carry
      // dictated values and which is therefore a fill surface, not a static
      // region. It keeps the pre-#106 behaviour on purpose; see
      // `staticSections` for why composing it from `defaultText` would delete
      // the transcript's own numbers.
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

/** The segmented static sections, keyed for the renderer. ONE derivation, so
 *  the slot ids a prompt names are the ids `composeNote` fills — whichever
 *  builder wrote the prompt. */
export function staticLinesByKey(
  sections: readonly NoteTemplateSection[]
): Map<string, AssemblyLine[]> {
  return new Map(segmentStaticSections(sections).map((x) => [x.section.key, x.lines]));
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
  // Segmented ONCE, here, and shared with the composer through
  // `segmentStaticSections`. The slot ids this prompt names and the slot ids
  // `composeNote` fills are produced by the same function over the same text —
  // two derivations would agree until the day one of them was fixed.
  const staticLines = staticLinesByKey(sections);
  const generativeSlots = hasGenerativeChoiceSlots(sections);

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
    ...sections.flatMap((s) => [`## ${s.label}`, ...renderSectionBody(s, staticLines), '']),
    // 5. Immutable safety guardrails — fixed position after the sections.
    'Critical rules:',
    ...SAFETY.globalRules,
    // Choice-slot directive — only when a section the MODEL WRITES carries a
    // `{{one of}}` menu, so a slot-free template's prompt stays byte-identical
    // (golden) and a template whose slots are all inside assembled statics is
    // not handed a contract about text it never sees.
    generativeSlots ? '' : undefined,
    generativeSlots ? CHOICE_SLOT_DIRECTIVE : undefined,
    // Slot-values protocol — only when the template HAS assembled statics.
    // ⚠️ THIS IS THE ZERO-STATIC BYTE-IDENTITY GUARANTEE, AND IT IS STRUCTURAL:
    // both entries are `undefined` when `staticLines` is empty, so a template
    // with no `always_include` sections cannot receive a byte of this feature.
    // #106(e), asserted by the golden gate at pipeline level.
    staticLines.size > 0 ? '' : undefined,
    staticLines.size > 0 ? SLOT_VALUES_DIRECTIVE : undefined,
    // Specialty guidance (unchanged mechanism — from specialtyGuidance()).
    guidance ? '' : undefined,
    guidance ? `Specialty guidance (${opts.specialty}):\n${guidance}` : undefined,
    // Instruction-as-data boundary (unchanged).
    delimiterSystemSuffix('transcript'),
  ];

  return lines.filter((l): l is string => typeof l === 'string').join('\n');
}

/**
 * Q1 audit §02.9 — polarity is stated as DATA now, and the note must render it.
 * Nothing else in this prompt re-derives it, so a model that read the finding
 * text and ignored the field would silently reintroduce exactly the "denies
 * chest pain" → "chest pain" flip the field was added to stop.
 *
 * EXPORTED so the L4 golden-prompt guard can assert this block, and ONLY this
 * block, as the delta against the pre-Phase-1 bytes. The golden file keeps its
 * original contents; nothing here can drift from what that test measures.
 */
export const ROS_POLARITY_RULE = [
  '',
  'A review-of-systems entry carries an explicit "polarity". It is',
  'authoritative — "denied" means the patient does NOT have that finding and',
  'the note must say so, and "affirmed" means they DO. Never flip one, and',
  'never let a denied finding in the same sentence turn an affirmed one',
  "negative. Where a \"laterality\" is given it is that finding's own side —",
  'do not widen it to bilateral.',
].join('\n');

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
    // Appended to the entities line rather than added as its own array element,
    // so the rule is one exactly-removable substring. That is what lets the L4
    // golden guard keep its original bytes and assert this block as the delta.
    opts.entitiesJson + ROS_POLARITY_RULE,
    '',
    'Role-labeled transcript:',
    opts.wrappedTranscript,
  ].join('\n');
}

/**
 * Sections whose template default would be INSERTED into the draft (i.e. not
 * omit_unless_supported with a default). L5's normals-scrutiny checks these
 * against the transcript. Empty for the system default.
 *
 * ⚠️ ASSEMBLED STATICS ARE EXCLUDED, AND THE OMISSION IS THE POINT (#106(a)).
 * L5's scrutiny asks "is this inserted finding supported by the transcript?" —
 * the right question for a scaffold the model was handed and may have kept
 * wrongly, and the WRONG question for a paragraph the doctor's own form
 * mandates. There is no transcript span for a scan-protocol sentence and there
 * never will be, so scrutinising it produces a CRITICAL "Unsupported template
 * default" on every visit, which sets needsReview, sends L6 to "fix" the
 * doctor's prose, and is then rejected by the L6b gate. The whole cascade fires
 * because a section was asked a question that never applied to it — the same
 * argument `SectionProvenance` already makes for `template`-provenance sections
 * against the anchored verifier.
 *
 * ⚠️ NO EXISTING TEMPLATE CHANGES. Every production row is `scaffold_confirm`
 * or `omit_unless_supported` today, so `staticSections` is empty for all of
 * them and this filter removes nothing until the reclassification lands.
 */
export function insertedDefaultSections(
  template: ResolvedNoteTemplate
): NoteTemplateSection[] {
  const assembled = new Set(staticSections(template.sections).map((s) => s.key));
  return template.sections.filter(
    (s) =>
      s.defaultText != null &&
      !assembled.has(s.key) &&
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
