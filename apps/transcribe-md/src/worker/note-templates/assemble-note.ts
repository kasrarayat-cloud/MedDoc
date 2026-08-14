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
  headingIs,
  segmentSection,
  splitBlocks,
  type AssembleOptions,
  type AssemblyLine,
  type StaticRegion,
} from './section-assembly';

// ⚠️ RE-EXPORTED, NOT RE-IMPLEMENTED. `splitBlocks` and `headingIs` moved DOWN
// into `section-assembly.ts` so `findStaticDivergence` could become positional
// without importing this module (which imports it — a cycle). One definition,
// two consumers.
export { headingIs, splitBlocks, type Block } from './section-assembly';
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

    // ⚠️ EXACT HEADING EQUALITY, AND THIS REVERSES AN EARLIER DECISION IN THIS
    // FILE. It used the LENIENT `headingMatcher` — the validator's presence
    // check — on the argument that a near-miss block would otherwise survive
    // beside the assembled one carrying a paraphrase. That argument was wrong,
    // and an adversarial pass produced the counterexample:
    //
    //     ## TECHNIQUE NOTES FOR THIS STUDY
    //     Augmentation was limited by patient pain; the study was terminated early.
    //
    // `##\s*TECHNIQUE(?!\w)` matches that heading — a following space is not
    // `\w` — so a DIFFERENT section, carrying a dictated limitation, was
    // overwritten by the doctor's boilerplate and counted as a duplicate.
    // Deleting the visit's own clinical content is strictly worse than leaving
    // a visible duplicate a clinician can see and resolve.
    //
    // The validator keeps the lenient matcher: it asks "is a section like this
    // present?", which is a different question from "is this block THIS
    // section?". Two questions, two matchers — stated here so the divergence is
    // deliberate rather than discovered.
    const at = blocks.findIndex((b) => headingIs(b.heading, section.label));
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
        if (headingIs(b.heading, section.label)) {
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
      const found = blocks.findIndex((b) => headingIs(b.heading, prev.label));
      if (found !== -1) {
        insertAt = found + 1;
        break;
      }
    }
    if (insertAt === blocks.length) {
      for (let i = myIdx + 1; i < ordered.length; i++) {
        const next = ordered[i]!;
        const found = blocks.findIndex((b) => headingIs(b.heading, next.label));
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
    const block = blocks.find((b) => headingIs(b.heading, section.label));
    if (block === undefined) continue;
    const nl = block.text.indexOf('\n');
    const body = nl === -1 ? '' : block.text.slice(nl + 1);
    const trimmed = body.trim();
    if (trimmed.length === 0) continue;
    // ⚠️ ONLY A BLOCK THAT CODE ACTUALLY ASSEMBLED IS GUARDED, AND THIS TEST IS
    // WHAT MAKES THE GUARD HONEST ON A RESUMED RUN. `worker.ts` resumes a
    // retried visit from `resumeState.soapDraft`, which on a visit drafted
    // before this shipped is the OLD scaffold output — the model's own prose.
    // Without this check the arm would take that paraphrase as the sacred
    // bytes, reject a polish that endangered nothing, and tell the clinician
    // "the note keeps your template's exact wording" about a note that says
    // `0.5 seconds`. A false assurance is worse than the generic message it
    // replaced.
    //
    // An assembled block contains every literal span of its template text by
    // construction; a pre-assembly draft does not. Short spans are ignored —
    // a two-character fragment between slots proves nothing.
    const literals = segmentSection(section.defaultText ?? '')
      .flatMap((l) => l.segments)
      .filter((seg) => seg.kind === 'literal')
      .map((seg) => (seg as { text: string }).text.trim())
      .filter((t) => t.length >= 8);
    if (literals.length > 0 && !literals.every((t) => trimmed.includes(t))) continue;
    out.push({ sectionKey: section.key, label: section.label, text: trimmed });
  }
  return out;
}
