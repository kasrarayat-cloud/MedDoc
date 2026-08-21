// ============================================================================
// ONE reader for a markdown pipe-table row. FIVE callers.
// ----------------------------------------------------------------------------
// This repository carried FIVE independent pipe-row matchers, four strict and
// one tolerant, and they disagreed about the shape L4 actually emits:
//
//   note-table-edit.ts   /^\s*\|.*\|\s*$/        strict
//   claim-prose.ts       /^\s*\|(.+)\|\s*$/      strict
//   ehr-formatters.ts    /^\s*\|.*\|\s*$/        strict
//   docx-generator.ts    /^\s*\|.*\|\s*$/        strict
//   bridge-fill.ts       /^\s*\|(.+)\|\s*.*$/    TOLERANT — greedy to the LAST pipe
//
// A row may carry a trailing annotation AFTER its closing pipe. Three forms
// have been observed from L4 and enumerating them was a losing game:
//
//   | GSV at the SFJ | 6.2 | 3.4 | [S1: "..."]
//   | GSV at the SFJ | 6.2 | 3.4 | "Right great saphenous ..."
//   | GSV at the SFJ | 7   | 2.4 | Great saphenous vein ...
//
// The cells are fixed by the pipes BEFORE the annotation, so the trailing text
// cannot change how the row parses — only whether it parses at all. Under the
// strict matchers it did not: the fill read the row and every other surface
// skipped it, so the same note was two different documents depending on who
// read it. In the EHR paste the row leaked as RAW MARKDOWN between two
// flattened neighbours.
//
// ⚠️ THE SUFFIX IS RETURNED, NEVER DISCARDED HERE. Callers differ: the fill
// wants cells only; the editor needs to know a suffix exists; the export must
// not drop it, because `ehr-formatters.ts` states the rule for exactly this
// case — "this is a clinical export, nothing may drop silently". Deciding the
// suffix's fate inside this function would make that decision for all five.
//
// ⚠️ AND IT IS NOT AN EVIDENCE-ANCHOR READER. Anchors are `⟦A:…⟧` and are
// stripped during GENERATION at 04b-anchor-verify.ts:1236, before a note is
// stored. Measured on production 2026-08-21: 0 of 50 notes carry either anchor
// form, against a control of 24 notes carrying pipe tables. Nothing here is a
// second opinion on anchor visibility, because no anchor reaches an exporter.
// ============================================================================

/** A table's alignment rule — `| --- | :--- |`. Never content. */
export const MARKDOWN_RULE_ROW_RE = /^\s*\|[\s:|-]+\|\s*$/;

/** Any line that opens with a pipe and closes one somewhere after. */
const ROW_RE = /^\s*\|(.+)\|\s*(.*)$/;

export interface MarkdownRow {
  /** The trimmed cell strings, fixed by the pipes. */
  cells: string[];
  /** Everything after the LAST pipe. Empty string when there is none. */
  suffix: string;
}

/**
 * Split one `| a | b | c |` line into its cells, tolerating a trailing
 * annotation. Returns null for a separator row or a line that is not a row.
 */
export function parseMarkdownRow(line: string): MarkdownRow | null {
  // ⚠️ A SEPARATOR ROW IS PARSED, NOT REFUSED — and that is a caller judgement
  // this function deliberately does NOT make.
  //
  // The first version returned null for `| --- | --- |`, which reads as
  // obviously right and broke `bridge-fill.parseMarkdownTables` completely: it
  // SPLITS the separator on purpose (`:7-8`) and validates every cell against
  // `SEP_ROW_RE` to confirm the line really is a rule before accepting the
  // table. With null it found ZERO tables and 28 fill tests went red.
  //
  // Callers that want separators excluded say so with `MARKDOWN_RULE_ROW_RE`,
  // which is exported for exactly that. Same principle as claim-prose's
  // `>= 2`: the primitive PARSES, each caller DECIDES.
  const m = ROW_RE.exec(line);
  if (!m) return null;
  return {
    cells: m[1].split('|').map((c) => c.trim()),
    suffix: (m[2] ?? '').trim(),
  };
}
