// ============================================================================
// Deterministic marker reconciliation.
// ----------------------------------------------------------------------------
// docx-content-controls.ts extracts ALL of a template's dropdowns as
// `{{one of: …}}` markers reliably. The tm_template_parse LLM then structures
// that text into sections — but run-to-run it can DROP or normalize markers, so
// a doctor's template would render inconsistently. This reconciler makes the
// extraction AUTHORITATIVE: any marker that was extracted but is missing from
// the parsed sections is re-attached deterministically.
//
// It runs in TWO passes at two points in the parse pipeline, split by region so
// that re-attached content is always PHI-covered without reintroducing scan
// variance (see parse-note-to-template.ts steps 2 & 5):
//
//   • reconcileBodyMarkers()   — BEFORE the PHI scan. Body carrier sentences
//     ("The {{vein}} is refluxing") can, in a pasted FILLED example, carry a
//     patient name / free-text specific that only the LLM PHI-scan can catch;
//     re-attaching them pre-scan means the full gate (regex ∪ LLM) covers them.
//   • reconcileHeaderMarkers() — AFTER the gate. Header-region dropdowns (side
//     of exam / physician / machine / location / diagnosis) sit above the first
//     clinical heading; scanning that provider-label metadata block makes the
//     LLM scan reject non-deterministically, and the provider/clinic names live
//     inside the dropdown OPTIONS (excluded from the scan by design), so these
//     are restored post-gate. A deterministic regex backstop (lineCarriesPhi)
//     still drops any header line whose FIXED carrier text carries structured
//     PHI.
//
// Both passes drop any candidate line whose option-stripped carrier text trips
// the SAME deterministic detectors the gate uses (detectStructuredPhi). When the
// LLM preserved everything, or the source has no markers (every SOAP /
// scaffold-free template), each pass is a NO-OP → byte-identical.
//
// Pure; no I/O. Reconciles by option-signature (a marker line's ORDERED option
// lists are its identity), so wording drift in the surrounding prose never
// matters; identical-signature lines are matched by prose first, then position,
// so a genuinely dropped duplicate is restored without duplicating a survivor.
// ============================================================================

import type { NoteTemplateSection } from './note-template-schema';
import { TEMPLATE_FIELD_LIMITS } from './note-template-schema';
import { detectStructuredPhi } from './phi-gate';

// Persisted cap on a section's defaultText. A re-attached marker line must never
// push a section over this, because clampDraftToLimits would then hard-slice the
// string — potentially mid-`{{one of:` — leaving a dangling, unbalanced marker.
// We skip the append instead (fail-safe marker loss, never corruption).
const DEFAULT_TEXT_CAP = TEMPLATE_FIELD_LIMITS.defaultText;

const MARKER_G = /\{\{one of:\s*([^}]*)\}\}/g;

/** A LINE's identity = the ORDERED sequence of its marker option-lists, joined.
 *  Using the whole line's sequence (not per-marker) distinguishes two lines that
 *  reuse the same dropdown — e.g. Findings "The {{vein}} is refluxing" ([vein])
 *  vs Impression "Right {{vein}} is {{status}}" ([vein,status]) — so a dropped
 *  line is never mistaken as surviving because a DIFFERENT line reused its
 *  dropdown. Empty (no markers) → ''. */
function lineSeq(line: string): string {
  const sigs = [...line.matchAll(MARKER_G)].map((m) =>
    m[1].split('|').map((o) => o.trim().toLowerCase()).filter(Boolean).join('|')
  );
  return sigs.join(' >> ');
}

function norm(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

/** Replace every `{{one of: … }}` option list with an inert placeholder so the
 *  PHI scan sees ONLY the fixed carrier text (option content is enumerated
 *  format, excluded from PHI detection — same as enumerateTextFields). */
function stripMarkerOptions(line: string): string {
  return line.replace(MARKER_G, '{{options}}');
}

/** True when a candidate line's FIXED (non-option) text carries structured PHI
 *  — the same deterministic detectors the output gate applies. Such a line is
 *  never re-attached (deterministic backstop; the body pass adds LLM coverage
 *  on top via its pre-scan placement). */
function lineCarriesPhi(line: string): boolean {
  return detectStructuredPhi(stripMarkerOptions(line)).length > 0;
}

/** Line index of the first clinical BODY heading in the source (the earliest
 *  section label that appears as a source line). Content above it is the
 *  header/metadata region. */
function firstHeadingPos(sourceLines: string[], sections: { label: string }[]): number {
  const positions = sections
    .map((s) => {
      const nl = norm(s.label);
      return nl ? sourceLines.findIndex((sl) => norm(sl) === nl || (nl.length > 4 && norm(sl).startsWith(nl))) : -1;
    })
    .filter((p) => p >= 0);
  return positions.length > 0 ? Math.min(...positions) : sourceLines.length;
}

/** Source line index of the first clinical BODY heading, computed from a STABLE
 *  section-label set (the full clinical section list at parse time). The caller
 *  computes this ONCE and passes it to BOTH reconcile passes so the header/body
 *  classification boundary is identical in each — a body-region line can then
 *  never be reclassified as header (and restored post-gate, bypassing the LLM
 *  PHI scan) just because the surviving-section set shrank between passes. */
export function firstClinicalHeadingIndex(sourceText: string, sections: { label: string }[]): number {
  return firstHeadingPos(sourceText.split('\n'), sections);
}

/** The header-region source lines above the first clinical heading, indexed by
 *  BOTH their marker sig-sequence (dropdowns) and their normalized text (fixed
 *  lines like "INTERPRETING PHYSICIAN: <name>"). */
function headerLineIndex(sourceLines: string[], headingPos: number): { seqs: Set<string>; norms: Set<string> } {
  const seqs = new Set<string>();
  const norms = new Set<string>();
  for (let i = 0; i < headingPos; i++) {
    const line = sourceLines[i];
    const q = lineSeq(line);
    if (q) seqs.add(q);
    const n = norm(line);
    if (n) norms.add(n);
  }
  return { seqs, norms };
}

/**
 * Remove sections whose content is ENTIRELY header-region (provider / clinic /
 * study-metadata dropdowns AND fixed provider-name lines like "INTERPRETING
 * PHYSICIAN: <name>") before the PHI scan: those provider-identifier LABELS and
 * hardcoded names make the scan LLM variably flag/reject the whole parse, even
 * though the values are the doctor's own inert format. The header dropdowns are
 * restored deterministically by reconcileHeaderMarkers AFTER the gate (marker
 * lines only, each PHI-re-scanned).
 *
 * GATED on the header region actually containing DROPDOWN markers (seqs > 0):
 * only a structured template with header-region dropdowns has anything to
 * reconcile back, so only then is it safe to drop header sections pre-scan.
 * A note with no header dropdowns (every SOAP / scaffold-free template, even one
 * with a fixed preamble line) is a strict NO-OP → byte-identical — the
 * reconciler would NOT restore a dropped fixed-text section (it has no marker),
 * so we must never drop one here. Body / mixed sections are always untouched.
 */
export function dropHeaderMarkerSections<T extends { label: string; defaultText?: string | null }>(
  sourceText: string,
  sections: T[]
): T[] {
  const sourceLines = sourceText.split('\n');
  const headingPos = firstHeadingPos(sourceLines, sections);
  if (headingPos >= sourceLines.length) return sections; // no clinical heading found → no-op
  const { seqs, norms } = headerLineIndex(sourceLines, headingPos);
  if (seqs.size === 0) return sections; // no header dropdowns to reconcile back → no-op (SOAP-safe)
  return sections.filter((s) => {
    const lines = (s.defaultText ?? '').split('\n').filter((l) => l.trim());
    if (lines.length === 0) return true; // empty → keep
    // drop iff EVERY line is a header line (by dropdown sig OR by fixed text)
    const allHeader = lines.every((l) => {
      const q = lineSeq(l);
      return q ? seqs.has(q) : norms.has(norm(l));
    });
    return !allHeader;
  });
}

interface SourceMarkerLine {
  idx: number;
  text: string;
  seq: string;
}

interface MissingComputation {
  safeMissing: SourceMarkerLine[];
  anchors: Array<{ s: NoteTemplateSection; pos: number }>;
  firstBodyPos: number;
}

/** Which extracted marker lines are missing from `sections`, PHI-filtered, plus
 *  the section anchors + first body-heading position used to place them. */
function computeSafeMissing(
  sourceLines: string[],
  sourceMarkerLines: SourceMarkerLine[],
  sections: NoteTemplateSection[]
): MissingComputation {
  // Group source marker lines by their line-sequence, in source order.
  const sourceBySeq = new Map<string, SourceMarkerLine[]>();
  for (const l of sourceMarkerLines) {
    const arr = sourceBySeq.get(l.seq);
    if (arr) arr.push(l);
    else sourceBySeq.set(l.seq, [l]);
  }

  // The normalized prose of every SURVIVING marker line, grouped by sequence.
  const survivedBySeq = new Map<string, string[]>();
  for (const s of sections)
    for (const line of (s.defaultText ?? '').split('\n')) {
      const seq = lineSeq(line);
      if (seq) {
        const arr = survivedBySeq.get(seq);
        if (arr) arr.push(norm(line));
        else survivedBySeq.set(seq, [norm(line)]);
      }
    }

  const missing: SourceMarkerLine[] = [];
  for (const [seq, srcLines] of sourceBySeq) {
    const survivors = [...(survivedBySeq.get(seq) ?? [])];
    const need = srcLines.length - survivors.length;
    if (need <= 0) continue; // all occurrences of this dropdown survived
    // Match each source occurrence to a survivor by PROSE (consume greedily) so
    // we can tell WHICH lines were dropped even when several share an option
    // sequence. Then restore `need` lines, preferring prose that matched no
    // survivor (definitely dropped), then by source order — so a later-kept /
    // earlier-dropped duplicate restores the right line and never duplicates a
    // survivor. Prose drift (LLM reworded the kept line) falls back to position.
    const scored = srcLines.map((l) => {
      const i = survivors.indexOf(norm(l.text));
      if (i >= 0) survivors.splice(i, 1);
      return { l, matched: i >= 0 };
    });
    const ranked = [...scored.filter((x) => !x.matched), ...scored.filter((x) => x.matched)].map((x) => x.l);
    missing.push(...ranked.slice(0, need));
  }

  const safeMissing = missing.filter((l) => !lineCarriesPhi(l.text)).sort((a, b) => a.idx - b.idx);

  const anchors = sections
    .map((s) => {
      const nl = norm(s.label);
      const pos = nl ? sourceLines.findIndex((sl) => norm(sl) === nl || (nl.length > 4 && norm(sl).startsWith(nl))) : -1;
      return { s, pos };
    })
    .filter((a) => a.pos >= 0)
    .sort((a, b) => a.pos - b.pos);
  const firstBodyPos = anchors.length > 0 ? anchors[0].pos : sourceLines.length;

  return { safeMissing, anchors, firstBodyPos };
}

type Region = 'body' | 'header' | 'all';

/** Append a marker line to a section's defaultText — deduped and CAP-aware: skip
 *  when the section already has the line, or when appending would exceed the
 *  persisted defaultText cap (clamp would otherwise hard-slice mid-`{{one of:`,
 *  leaving a broken marker). Skipping is fail-safe (marker loss, not corruption). */
function appendMarkerLine(section: NoteTemplateSection, text: string): void {
  const cur = section.defaultText ?? '';
  if (cur.includes(text)) return;
  const next = (cur + '\n' + text).trim();
  if (next.length > DEFAULT_TEXT_CAP) return;
  section.defaultText = next;
  section.defaultTextMode = 'scaffold_confirm';
}

/** Re-attach the extracted markers the LLM dropped in the requested region.
 *  `headerBoundaryIdx` is the source line index of the first clinical heading,
 *  computed ONCE from the full clinical-section set so the header/body split is
 *  identical across the two production passes (see reconcileBodyMarkers /
 *  reconcileHeaderMarkers). Omitted → derived from the passed sections (the
 *  test/utility 'all' path). Returns the SAME array reference when nothing in
 *  the requested region is missing. */
function reconcileRegion(
  sourceText: string,
  sections: NoteTemplateSection[],
  region: Region,
  headerBoundaryIdx?: number
): NoteTemplateSection[] {
  const sourceLines = sourceText.split('\n');
  const sourceMarkerLines: SourceMarkerLine[] = [];
  sourceLines.forEach((text, idx) => {
    const seq = lineSeq(text);
    if (seq) sourceMarkerLines.push({ idx, text: text.trim(), seq });
  });
  if (sourceMarkerLines.length === 0) return sections; // no markers → no-op (SOAP)

  const { safeMissing, anchors, firstBodyPos } = computeSafeMissing(sourceLines, sourceMarkerLines, sections);
  if (safeMissing.length === 0) return sections;

  // Stable source-intrinsic boundary when the caller supplies it; else fall back
  // to the surviving-anchor position. Using the caller's boundary guarantees a
  // body-region line is never reclassified as header (and restored post-gate,
  // bypassing the LLM PHI scan) when the surviving-section set shrinks.
  const boundary = headerBoundaryIdx ?? firstBodyPos;

  const bodyMissing = region !== 'header' ? safeMissing.filter((l) => l.idx >= boundary) : [];
  const headerMissing = region !== 'body' ? safeMissing.filter((l) => l.idx < boundary) : [];
  if (bodyMissing.length === 0 && headerMissing.length === 0) return sections; // nothing in this region → no-op

  const out = sections.map((s) => ({ ...s }));

  // ── Body markers: append to the nearest section whose heading precedes them. ──
  for (const l of bodyMissing) {
    const target =
      [...anchors].reverse().find((a) => a.pos <= l.idx)?.s ?? anchors[anchors.length - 1]?.s;
    const targetOut = out.find((o) => o.key === target?.key && o.label === target?.label);
    if (targetOut) appendMarkerLine(targetOut, l.text);
  }

  // ── Header markers: an "Exam Metadata" block above the first clinical heading. ──
  if (headerMissing.length > 0) {
    // Merge into an existing pre-heading section if the LLM made one; else prepend.
    // Include ONLY the missing MARKER lines (the dropdowns), in source order —
    // never interstitial fixed lines. A fixed header line can hold a raw provider
    // name ("INTERPRETING PHYSICIAN: Dr X") that the PHI gate flags, dropping the
    // whole section; a marker line's provider/clinic options are dropdown FORMAT
    // (excluded from the PHI scan) and its carrier is PHI-scanned.
    const existingHeader = out.find((o) => {
      const a = anchors.find((x) => x.s.key === o.key && x.s.label === o.label);
      const beforeBody = !a || a.pos < boundary;
      return beforeBody && /\{\{one of:/.test(o.defaultText ?? '');
    });
    if (existingHeader) {
      for (const l of headerMissing) appendMarkerLine(existingHeader, l.text); // deduped + cap-aware
    } else {
      // Build the block cap-aware: keep whole marker lines until the cap.
      let blockText = '';
      for (const l of headerMissing) {
        const next = blockText ? blockText + '\n' + l.text : l.text;
        if (next.length > DEFAULT_TEXT_CAP) break;
        blockText = next;
      }
      if (blockText) {
        out.unshift({
          key: 'exam_metadata',
          label: 'Exam Metadata',
          order: 0,
          formatHint: 'prose',
          styleInstructions: null,
          defaultText: blockText,
          defaultTextMode: 'scaffold_confirm',
          structure: null,
        });
      }
    }
  }

  return out.map((s, i) => ({ ...s, order: i + 1 }));
}

/** Restore dropped BODY-region markers (idx ≥ first clinical heading). Called
 *  BEFORE the PHI scan so the full gate (regex ∪ LLM) covers re-attached
 *  clinical carrier text. Pass the stable `headerBoundaryIdx` from
 *  firstClinicalHeadingIndex(sourceText, <full clinical sections>). No-op (same
 *  ref) when no body marker is missing. */
export function reconcileBodyMarkers(
  sourceText: string,
  sections: NoteTemplateSection[],
  headerBoundaryIdx?: number
): NoteTemplateSection[] {
  return reconcileRegion(sourceText, sections, 'body', headerBoundaryIdx);
}

/** Restore dropped HEADER-region markers (idx < first clinical heading) into an
 *  "Exam Metadata" block. Called AFTER the gate — scanning the provider-label
 *  metadata block makes the LLM scan reject non-deterministically, and its names
 *  live in stripped dropdown options; a regex backstop still drops any header
 *  line whose fixed carrier carries structured PHI. Pass the SAME stable
 *  `headerBoundaryIdx` used for the body pass. No-op (same ref) when no header
 *  marker is missing. */
export function reconcileHeaderMarkers(
  sourceText: string,
  sections: NoteTemplateSection[],
  headerBoundaryIdx?: number
): NoteTemplateSection[] {
  return reconcileRegion(sourceText, sections, 'header', headerBoundaryIdx);
}

/** Reconcile BOTH regions in one call (test/utility). The production pipeline
 *  uses the split body/header passes above so re-attached body content is
 *  LLM-scanned; this convenience keeps the deterministic regex backstop only. */
export function reconcileTemplateMarkers(sourceText: string, sections: NoteTemplateSection[]): NoteTemplateSection[] {
  return reconcileRegion(sourceText, sections, 'all');
}
