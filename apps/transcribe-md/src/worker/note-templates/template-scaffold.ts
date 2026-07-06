// ============================================================================
// Template scaffold model for the anchored verifier (04b).
// ----------------------------------------------------------------------------
// A custom structured template's `defaultText` carries the doctor's PRE-APPROVED
// report scaffold: fixed boilerplate lines and carrier sentences with inline
// `{{one of: A | B | C}}` choice slots (see docx-content-controls.ts). 04b
// otherwise verifies that scaffold against the transcript as if it were free-
// text clinical assertion — a category error that over-demotes a correctly
// filled report. This module distills the template into what 04b needs to fix
// that precisely, WITHOUT touching any frozen judge/override surface:
//
//   - fixedLines: normalized fixed-scaffold lines (no slots) → exempt as
//     scaffold (the doctor's own format, not a generated claim);
//   - carriers:   a filled carrier line still runs every frozen override on
//     its full text; if it survives to entailment, 04b feeds the judge the
//     `reducedClaim` (laterality + the chosen picks) instead of the boilerplate
//     it can't entail. The picks are STILL judged — a wrong pick still demotes.
//
// Pre-registered: docs/eval-runs/verifier-scaffold-exemption-20260706T202636Z.md
// ============================================================================

import type { NoteTemplateSection } from './system-default-template';

/** Match-normalization: lowercase, punctuation→space, whitespace collapsed.
 *  Deliberately the SAME shape as 04b's `norm`, so a template line and the
 *  model's reproduction of it align despite spacing/punctuation drift. */
export function normForMatch(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

const MARKER_RE = /\{\{one of:\s*([^}]*)\}\}/g;
const LATERALITY_RE = /\b(right|left|bilateral)\b/g;

interface Segment {
  kind: 'fixed' | 'slot';
  /** fixed: the literal text; slot: normalized option list. */
  fixed?: string;
  options?: string[];
}

export interface Carrier {
  segments: Segment[];
  /** Matches a normalized output line, one capture group per slot. */
  matcher: RegExp;
  slotCount: number;
}

export interface TemplateScaffold {
  fixedLines: Set<string>;
  carriers: Carrier[];
}

/** Split one carrier defaultText line into fixed/slot segments. */
function parseCarrier(line: string): Segment[] {
  const segments: Segment[] = [];
  let last = 0;
  for (const m of line.matchAll(MARKER_RE)) {
    const before = line.slice(last, m.index);
    if (before) segments.push({ kind: 'fixed', fixed: before });
    const options = m[1]
      .split('|')
      .map((o) => normForMatch(o))
      .filter(Boolean);
    segments.push({ kind: 'slot', options });
    last = m.index! + m[0].length;
  }
  const tail = line.slice(last);
  if (tail) segments.push({ kind: 'fixed', fixed: tail });
  return segments;
}

/** Compile a carrier's segments into a whole-line matcher over normForMatch
 *  text: fixed text as escaped literals with flexible whitespace, each slot as
 *  an alternation of its own options (longest-first so a prefix option can't
 *  shadow a longer one). Only options the template enumerates can match — a
 *  fabricated value never matches, so it can never take the carrier path. */
function compileMatcher(segments: Segment[]): RegExp {
  const parts = segments.map((seg) => {
    if (seg.kind === 'fixed') {
      const n = normForMatch(seg.fixed!);
      if (!n) return '';
      return escapeRe(n).replace(/ /g, '\\s+');
    }
    const opts = [...(seg.options ?? [])]
      .filter(Boolean)
      .sort((a, b) => b.length - a.length)
      .map((o) => escapeRe(o).replace(/ /g, '\\s+'));
    if (opts.length === 0) return '(\\S.*?)';
    return `(${opts.join('|')})`;
  });
  // Tolerate optional whitespace between adjacent segments.
  return new RegExp('^\\s*' + parts.filter(Boolean).join('\\s*') + '\\s*$', 'i');
}

/** Build the scaffold model from a resolved template's sections. */
export function buildTemplateScaffold(
  sections: readonly NoteTemplateSection[]
): TemplateScaffold {
  const fixedLines = new Set<string>();
  const carriers: Carrier[] = [];
  for (const s of sections) {
    const dt = s.defaultText;
    if (!dt) continue;
    for (const rawLine of dt.split('\n')) {
      const line = rawLine.trim();
      if (!line) continue;
      if (line.includes('{{one of:')) {
        const segments = parseCarrier(line);
        const slotCount = segments.filter((seg) => seg.kind === 'slot').length;
        if (slotCount === 0) continue;
        carriers.push({ segments, matcher: compileMatcher(segments), slotCount });
      } else {
        const n = normForMatch(line);
        if (n) fixedLines.add(n);
      }
    }
  }
  return { fixedLines, carriers };
}

/** True when a normalized line is exactly a fixed-scaffold line. */
export function isFixedScaffoldLine(
  scaffold: TemplateScaffold,
  normalizedLine: string
): boolean {
  return scaffold.fixedLines.has(normalizedLine);
}

/**
 * If a line matches a carrier, return the REDUCED CLAIM for the judge —
 * laterality tokens from the fixed parts (in order) plus the chosen picks,
 * dropping the connective boilerplate the transcript can't entail. Null when
 * the line matches no carrier (→ 04b keeps the normal full-line path).
 */
export function carrierReducedClaim(
  scaffold: TemplateScaffold,
  normalizedLine: string
): string | null {
  for (const carrier of scaffold.carriers) {
    const m = normalizedLine.match(carrier.matcher);
    if (!m) continue;
    const parts: string[] = [];
    let group = 1;
    for (const seg of carrier.segments) {
      if (seg.kind === 'fixed') {
        const lat = normForMatch(seg.fixed!).match(LATERALITY_RE);
        if (lat) parts.push(...lat);
      } else {
        const pick = m[group++];
        if (pick && pick.trim()) parts.push(pick.trim());
      }
    }
    const reduced = parts.join(' ').trim();
    if (reduced) return reduced;
  }
  return null;
}
