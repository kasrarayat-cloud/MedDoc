// ============================================================================
// Deterministic marker reconciliation.
// ----------------------------------------------------------------------------
// docx-content-controls.ts extracts ALL of a template's dropdowns as
// `{{one of: …}}` markers reliably. The tm_template_parse LLM then structures
// that text into sections — but run-to-run it can DROP or normalize the
// header-region markers (SIDE OF EXAM / referring physician / machine /
// location / indications / diagnosis, which sit ABOVE the first clinical
// heading), so a doctor's template would render inconsistently.
//
// This reconciler makes the extraction AUTHORITATIVE: after the LLM step, any
// marker that was extracted but is missing from the parsed sections is
// re-attached deterministically — header-region markers into an "Exam Metadata"
// section (merged into an existing pre-heading section when the LLM made one,
// else prepended), body markers appended to the nearest section by source
// position. When the LLM preserved everything (or the source has no markers at
// all — every SOAP / scaffold-free template), this is a NO-OP → byte-identical.
//
// Pure; no I/O. Reconciles by option-signature (a marker's own option list is
// its identity), so wording drift in the surrounding prose never matters.
// ============================================================================

import type { NoteTemplateSection } from '../../worker/note-templates/system-default-template';

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
 * restored deterministically by reconcileTemplateMarkers AFTER the gate (marker
 * lines only). Body / mixed / no-header sections are untouched. No-op when the
 * note has no header region → byte-identical for every SOAP / scaffold-free
 * template.
 */
export function dropHeaderMarkerSections<T extends { label: string; defaultText?: string | null }>(
  sourceText: string,
  sections: T[]
): T[] {
  const sourceLines = sourceText.split('\n');
  const headingPos = firstHeadingPos(sourceLines, sections);
  if (headingPos >= sourceLines.length) return sections; // no clinical heading found → no-op
  const { seqs, norms } = headerLineIndex(sourceLines, headingPos);
  if (seqs.size === 0 && norms.size === 0) return sections;
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

/**
 * Re-attach every extracted `{{one of}}` marker that the LLM structuring step
 * dropped. Returns the same array reference when nothing is missing (no-op).
 */
export function reconcileTemplateMarkers(
  sourceText: string,
  sections: NoteTemplateSection[]
): NoteTemplateSection[] {
  const sourceLines = sourceText.split('\n');
  const sourceMarkerLines: SourceMarkerLine[] = [];
  sourceLines.forEach((text, idx) => {
    const seq = lineSeq(text);
    if (seq) sourceMarkerLines.push({ idx, text: text.trim(), seq });
  });
  if (sourceMarkerLines.length === 0) return sections; // no markers → no-op (SOAP)

  // Which marker LINE-sequences survived into the parsed sections?
  const survived = new Set<string>();
  for (const s of sections)
    for (const line of (s.defaultText ?? '').split('\n')) {
      const seq = lineSeq(line);
      if (seq) survived.add(seq);
    }

  const missing = sourceMarkerLines.filter((l) => !survived.has(l.seq));
  if (missing.length === 0) return sections; // LLM preserved everything → byte-identical

  // Anchor each section to its label's line in the source (first heading match).
  const anchors = sections
    .map((s) => {
      const nl = norm(s.label);
      const pos = nl ? sourceLines.findIndex((sl) => norm(sl) === nl || (nl.length > 4 && norm(sl).startsWith(nl))) : -1;
      return { s, pos };
    })
    .filter((a) => a.pos >= 0)
    .sort((a, b) => a.pos - b.pos);
  const firstHeadingPos = anchors.length > 0 ? anchors[0].pos : sourceLines.length;

  const headerMissing = missing.filter((l) => l.idx < firstHeadingPos);
  const bodyMissing = missing.filter((l) => l.idx >= firstHeadingPos);

  const out = sections.map((s) => ({ ...s }));

  // ── Body markers: append to the nearest section whose heading precedes them. ──
  for (const l of bodyMissing) {
    const target =
      [...anchors].reverse().find((a) => a.pos <= l.idx)?.s ?? anchors[anchors.length - 1]?.s;
    const targetOut = out.find((o) => o.key === target?.key && o.label === target?.label);
    if (targetOut) {
      targetOut.defaultText = ((targetOut.defaultText ?? '') + '\n' + l.text).trim();
      targetOut.defaultTextMode = 'scaffold_confirm';
    }
  }

  // ── Header markers: an "Exam Metadata" block above the first clinical heading. ──
  if (headerMissing.length > 0) {
    // Include ONLY the missing MARKER lines (the dropdowns), in source order —
    // never interstitial fixed lines. A fixed header line can hold a raw
    // provider name ("INTERPRETING PHYSICIAN: Dr X") that the PHI gate flags,
    // dropping the whole section; a marker line's provider/clinic options are
    // dropdown FORMAT (excluded from the PHI scan by enumerateTextFields).
    const blockText = headerMissing.map((l) => l.text).join('\n');

    // Merge into an existing pre-heading section if the LLM made one; else prepend.
    const existingHeader = out.find((o) => {
      const a = anchors.find((x) => x.s.key === o.key && x.s.label === o.label);
      const beforeBody = !a || a.pos < firstHeadingPos;
      return beforeBody && /\{\{one of:/.test(o.defaultText ?? '');
    });
    if (existingHeader) {
      // append only the genuinely-missing marker lines (avoid duplicating survivors)
      const add = headerMissing.map((l) => l.text).filter((t) => !(existingHeader.defaultText ?? '').includes(t));
      if (add.length) {
        existingHeader.defaultText = ((existingHeader.defaultText ?? '') + '\n' + add.join('\n')).trim();
        existingHeader.defaultTextMode = 'scaffold_confirm';
      }
    } else {
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

  return out.map((s, i) => ({ ...s, order: i + 1 }));
}
