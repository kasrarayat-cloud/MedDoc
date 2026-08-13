// ============================================================================
// NOTE COMPOSITION — the model's markdown, with the doctor's sections spliced
// back in from their own bytes (ruling #106(a), SPEC §4.3a).
// ----------------------------------------------------------------------------
// `section-assembly.ts` stitches ONE section. This module places the results in
// the document, and it is deliberately a SPLICE rather than a rebuild:
//
//   - generative sections are carried through BYTE-FOR-BYTE, exactly as the
//     model emitted them, including any section the template never named;
//   - `always_include` sections are REPLACED by the assembled bytes, or
//     INSERTED at their template position when the model omitted them.
//
// ⚠️ A REBUILD WAS THE OBVIOUS DESIGN AND IT IS THE WRONG ONE. Composing the
// note purely from an ordered section list would silently DELETE anything the
// model wrote outside the template's own headings — and L7's later steps
// (PATIENT SUMMARY, PROCEDURES / E&M) append exactly such sections. A splice
// cannot lose content it does not recognise; a rebuild loses it by default, and
// nothing would have failed.
//
// ⚠️ ZERO STATIC SECTIONS ⇒ THE INPUT IS RETURNED UNTOUCHED, BY CONSTRUCTION.
// That is the pipeline-level half of #106(e)'s byte-identity invariant: plain
// SOAP does not pass through a splice at all, so it cannot be changed by one.
// ============================================================================

import {
  assembleSection,
  segmentSection,
  type AssembleOptions,
  type AssemblyLine,
  type StaticRegion,
} from './section-assembly';
import { headingMatcher } from '../layers/soap-structure-validator';
import type { NoteTemplateSection } from './system-default-template';

/**
 * Sections whose text is the doctor's own and is composed by code, never by the
 * model: `always_include`, WITH text, and NOT structured.
 *
 * ⚠️ THE STRUCTURED EXCLUSION IS LOAD-BEARING AND IS NOT A TIDY-UP. A `table`
 * section's cells hold values the TRANSCRIPT dictated — a diameter, a reflux
 * time — and its `defaultText` is the empty skeleton. Composing such a section
 * from its `defaultText` would emit the skeleton and DELETE every measurement
 * the visit produced, silently, while satisfying every static-fidelity check in
 * this programme (the doctor's bytes would be perfectly preserved; the patient's
 * numbers would be gone). A table is a FILL SURFACE, not a static region.
 *
 * ⚠️ AND IT IS ASSERTED AGAIN IN THE RECLASSIFICATION MIGRATION, on purpose.
 * This predicate protects the RENDER path; the migration protects the DATA. A
 * structured section that somehow acquired `always_include` would be ignored
 * here — correctly — and would then look like a mode nobody honours, which is
 * the kind of quiet disagreement that costs a session to re-derive.
 */
export function staticSections(
  sections: readonly NoteTemplateSection[]
): NoteTemplateSection[] {
  return [...sections]
    .sort((a, b) => a.order - b.order)
    .filter(
      (s) =>
        s.defaultTextMode === 'always_include' &&
        (s.defaultText ?? '').length > 0 &&
        !s.structure
    );
}

/** Sections the MODEL is asked to write — everything else. Exported because the
 *  re-scoped structure validator measures the model's raw output against
 *  exactly this set, and a second derivation of it would drift. */
export function generatedSections(
  sections: readonly NoteTemplateSection[]
): NoteTemplateSection[] {
  const staticKeys = new Set(staticSections(sections).map((s) => s.key));
  return [...sections]
    .sort((a, b) => a.order - b.order)
    .filter((s) => !staticKeys.has(s.key));
}

/** The segmented form of every static section, computed once and shared by the
 *  prompt builder and the composer so the slot ids they speak about are the
 *  same ids. */
export function segmentStaticSections(
  sections: readonly NoteTemplateSection[]
): { section: NoteTemplateSection; lines: AssemblyLine[] }[] {
  return staticSections(sections).map((section) => ({
    section,
    lines: segmentSection(section.defaultText ?? ''),
  }));
}

export interface Block {
  /** The heading text without the leading `## `, or null for a preamble block
   *  that precedes the first heading. */
  heading: string | null;
  /** The block's full text INCLUDING its heading line. */
  text: string;
}

/** Split markdown into `##`-headed blocks. A leading block with no heading (the
 *  model's preamble, if any) is preserved as `heading: null` — this module
 *  never decides that content is worthless. */
export function splitBlocks(markdown: string): Block[] {
  // An empty draft has no blocks at all — not one empty preamble block. The
  // difference shows up as a stray leading newline in the composed note, which
  // is the kind of drift a byte-identity gate is supposed to catch and a reader
  // never would.
  if (markdown.length === 0) return [];
  const lines = markdown.split('\n');
  const out: Block[] = [];
  let current: Block | null = null;
  for (const line of lines) {
    const m = /^##\s+(\S.*)$/.exec(line);
    if (m) {
      if (current) out.push(current);
      current = { heading: m[1]!.trim(), text: line };
    } else if (current) {
      current.text += `\n${line}`;
    } else {
      current = { heading: null, text: line };
    }
  }
  if (current) out.push(current);
  return out;
}

export interface ComposeResult {
  text: string;
  /** What code assembled, byte-exact — the input to the L6b static-divergence
   *  arm. Empty when no static section applied. */
  regions: StaticRegion[];
  /** Static sections that OVERWROTE a block the model emitted. */
  replaced: number;
  /** Static sections the model omitted; inserted at their template position. */
  inserted: number;
  /** Extra model blocks carrying a static section's heading, dropped because an
   *  assembled block of that heading replaced the first one. */
  duplicatesDropped: number;
  unfilled: number;
  rejected: number;
  droppedLines: number;
}

export interface ComposeOptions {
  /** Per-section-key assembly options. Absent ⇒ defaults, which KEEP every
   *  line (#106(f)). Plumbed now so the pure-carrier opt-in is a data change
   *  rather than a code change when a template can express it. */
  perSection?: Record<string, AssembleOptions>;
}

/**
 * Splice the doctor's assembled sections into the model's note.
 *
 * ⚠️ THE MODEL'S BLOCK IS DISCARDED FOR A STATIC SECTION, DELIBERATELY AND
 * SILENTLY. The prompt tells it so in as many words. Keeping the model's
 * version anywhere would recreate the defect: two versions of the doctor's
 * paragraph in one document, one of them paraphrased.
 */
export function composeNote(
  modelText: string,
  sections: readonly NoteTemplateSection[],
  fills: Readonly<Record<string, Record<string, string>>>,
  opts: ComposeOptions = {}
): ComposeResult {
  const statics = segmentStaticSections(sections);
  if (statics.length === 0) {
    return {
      text: modelText,
      regions: [],
      replaced: 0,
      inserted: 0,
      duplicatesDropped: 0,
      unfilled: 0,
      rejected: 0,
      droppedLines: 0,
    };
  }

  const blocks = splitBlocks(modelText);
  const regions: StaticRegion[] = [];
  let replaced = 0;
  let inserted = 0;
  let unfilled = 0;
  let rejected = 0;
  let droppedLines = 0;
  let duplicatesDropped = 0;

  // Ordered template labels, so an omitted static section lands where the
  // template says it belongs rather than at the end of the document.
  const ordered = [...sections].sort((a, b) => a.order - b.order);

  for (const { section, lines } of statics) {
    const result = assembleSection(
      lines,
      fills[section.key] ?? {},
      opts.perSection?.[section.key] ?? {}
    );
    unfilled += result.unfilled;
    rejected += result.rejected;
    droppedLines += result.droppedLines;
    const body = result.text;
    const blockText = `## ${section.label}\n${body}`;
    // ⚠️ TRIMMED, AND IT MUST MATCH `staticRegionsFromNote` EXACTLY. This is the
    // byte sequence the L6b arm asserts still exists after the polisher; if the
    // two normalise differently, the guard compares a string nothing ever wrote
    // and fires on every visit. Pinned by a round-trip test.
    regions.push({ sectionKey: section.key, label: section.label, text: body.trim() });

    // ⚠️ THE LENIENT MATCHER IS THE RIGHT ONE HERE, AND THE REASON IS NOT
    // "reuse". It also matches a heading that merely STARTS with the label
    // ("## TECHNIQUE AND METHOD"), which for a REPLACEMENT is the safe
    // direction: that block would otherwise survive beside the assembled one,
    // leaving two versions of the doctor's paragraph in the document with one
    // of them paraphrased — the original defect, inside its own fix. Exact
    // matching would be safer only if the model's version were worth keeping,
    // and for a section it was told not to write, it is not.
    const re = headingMatcher(section.label);
    const at = blocks.findIndex((b) => b.heading !== null && re.test(`## ${b.heading}`));
    if (at !== -1) {
      blocks[at] = { heading: section.label, text: blockText };
      replaced += 1;
      // ⚠️ A SECOND BLOCK UNDER THE SAME HEADING IS DROPPED, AND ONLY HERE.
      // A model that emits the doctor's section twice would otherwise leave one
      // assembled copy and one PARAPHRASED copy in the same document — the
      // original defect, surviving inside its own fix. This is the single place
      // this module removes model content, and it removes it only where an
      // assembled version of that exact heading has taken its place.
      for (let i = blocks.length - 1; i > at; i--) {
        const b = blocks[i]!;
        if (b.heading !== null && re.test(`## ${b.heading}`)) {
          blocks.splice(i, 1);
          duplicatesDropped += 1;
        }
      }
      continue;
    }

    // Not emitted by the model. Place it after the nearest PRECEDING template
    // section that IS present, else before the nearest FOLLOWING one, else at
    // the end. Deterministic in every case, and never at index 0 ahead of a
    // preamble block that belongs to whatever came first.
    const myIdx = ordered.findIndex((s) => s.key === section.key);
    let insertAt = blocks.length;
    for (let i = myIdx - 1; i >= 0; i--) {
      const prev = ordered[i]!;
      const prevRe = headingMatcher(prev.label);
      const found = blocks.findIndex((b) => b.heading !== null && prevRe.test(`## ${b.heading}`));
      if (found !== -1) {
        insertAt = found + 1;
        break;
      }
    }
    if (insertAt === blocks.length) {
      for (let i = myIdx + 1; i < ordered.length; i++) {
        const next = ordered[i]!;
        const nextRe = headingMatcher(next.label);
        const found = blocks.findIndex((b) => b.heading !== null && nextRe.test(`## ${b.heading}`));
        if (found !== -1) {
          insertAt = found;
          break;
        }
      }
    }
    blocks.splice(insertAt, 0, { heading: section.label, text: blockText });
    inserted += 1;
  }

  return {
    text: blocks.map((b) => b.text).join('\n'),
    regions,
    replaced,
    inserted,
    duplicatesDropped,
    unfilled,
    rejected,
    droppedLines,
  };
}

/**
 * Read back the static regions from a composed note.
 *
 * ⚠️ WHY THIS EXISTS INSTEAD OF THREADING `composed.regions` THROUGH THE
 * PIPELINE: L4 is SKIPPABLE. `worker.ts` resumes a retried visit from
 * `resumeState.soapDraft` without ever calling `runLayer4GenerateSoap`, so a
 * value returned by L4 is simply absent on exactly the runs a guard is most
 * needed. The draft, by contrast, is always there — it is where code WROTE
 * those bytes — so deriving from it is the form that cannot go missing.
 *
 * ⚠️ AND THE TWO DERIVATIONS ARE PINNED TO EACH OTHER BY A TEST, not by hope:
 * `staticRegionsFromNote(composeNote(...).text, sections)` must equal
 * `composeNote(...).regions`. That assertion is what makes this a second READING
 * of one fact rather than a second SOURCE of it.
 *
 * A section the note does not carry is skipped rather than reported empty:
 * "this heading is missing" is the structure validator's question, and a region
 * with no bytes could only ever assert that nothing is contained in anything.
 */
export function staticRegionsFromNote(
  note: string,
  sections: readonly NoteTemplateSection[]
): StaticRegion[] {
  const statics = staticSections(sections);
  if (statics.length === 0) return [];
  const blocks = splitBlocks(note);
  const out: StaticRegion[] = [];
  for (const section of statics) {
    const re = headingMatcher(section.label);
    const block = blocks.find((b) => b.heading !== null && re.test(`## ${b.heading}`));
    if (block === undefined) continue;
    const nl = block.text.indexOf('\n');
    const body = nl === -1 ? '' : block.text.slice(nl + 1);
    const trimmed = body.trim();
    if (trimmed.length === 0) continue;
    out.push({ sectionKey: section.key, label: section.label, text: trimmed });
  }
  return out;
}
