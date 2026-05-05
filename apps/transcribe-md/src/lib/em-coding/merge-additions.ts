// ============================================================================
// merge-additions.ts — append BumpModal additions into a SOAP draft
// ----------------------------------------------------------------------------
// The BumpModal collects per-gap edits keyed by criterionId. The server
// route maps each criterionId to a SOAP section + sub-heading via
// criterion-to-section.ts and merges the doctor's text into the right
// scaffold. This file owns the merge primitive — separated from the
// route so it's unit-testable.
//
// Merge semantics:
//   - The doctor's text is APPENDED, not replaced — the existing SOAP
//     scaffolding stays intact.
//   - Additions targeting a sub-heading (`**HPI:**`) land directly
//     beneath that line. If the sub-heading is missing, the addition
//     is appended at the end of the section with the sub-heading line
//     prepended so it's still labeled.
//   - Additions targeting the section root (Plan items, exam systems
//     for Objective root) are appended at the bottom of the section.
//   - The function never modifies sections it isn't asked about.
//   - Empty/whitespace-only additions are ignored (no-op).
// ============================================================================

import { sectionTargetFor, type SoapSectionKey } from './criterion-to-section';

const SECTION_HEADING: Record<SoapSectionKey, string> = {
  S: '## Subjective',
  O: '## Objective',
  A: '## Assessment',
  P: '## Plan',
};

const SECTION_ORDER: SoapSectionKey[] = ['S', 'O', 'A', 'P'];

export interface AdditionInput {
  criterionId: string;
  text: string;
}

export interface MergeResult {
  /** SOAP markdown after the merge. */
  newSoap: string;
  /** Subset of `additions` that actually landed (non-empty + recognised
   *  criterion id). The audit row uses this for its count + labels. */
  applied: AdditionInput[];
  /** Subset that was skipped (empty text or unrecognised id). Surfaced
   *  in the route response so the doctor can see what didn't take. */
  skipped: Array<AdditionInput & { reason: string }>;
}

/** Split a SOAP markdown blob into a map keyed by S/O/A/P. Anything
 *  before the first canonical heading is preserved as a "preamble"
 *  block so we never silently drop content. */
function splitSections(soap: string): {
  preamble: string;
  sections: Record<SoapSectionKey, string>;
} {
  const sections: Record<SoapSectionKey, string> = { S: '', O: '', A: '', P: '' };
  if (!soap || !soap.trim()) {
    return { preamble: '', sections };
  }
  const lines = soap.split('\n');
  const preambleLines: string[] = [];
  let current: SoapSectionKey | null = null;
  // Buffers per section, line-by-line, so we can re-join with the
  // original whitespace fidelity.
  const bufs: Record<SoapSectionKey, string[]> = { S: [], O: [], A: [], P: [] };
  for (const raw of lines) {
    const m = /^\s{0,3}#{1,3}\s+(.+?)\s*$/.exec(raw);
    if (m) {
      const heading = m[1].toLowerCase().replace(/[^a-z]/g, '');
      const found = SECTION_ORDER.find((k) => {
        const label = SECTION_HEADING[k]
          .replace(/^##\s+/, '')
          .toLowerCase();
        return heading === label || heading === k.toLowerCase();
      });
      if (found) {
        current = found;
        continue;
      }
    }
    if (current === null) {
      preambleLines.push(raw);
    } else {
      bufs[current].push(raw);
    }
  }
  for (const k of SECTION_ORDER) {
    sections[k] = bufs[k].join('\n').replace(/\s+$/, '');
  }
  return { preamble: preambleLines.join('\n').replace(/\s+$/, ''), sections };
}

/** Insert text directly beneath a sub-heading line within a section
 *  body. If the sub-heading isn't present, append the sub-heading +
 *  text at the bottom of the section (so the addition stays labeled). */
function insertUnderSubHeading(
  sectionBody: string,
  subHeading: string,
  text: string,
): string {
  const lines = sectionBody.split('\n');
  const idx = lines.findIndex((l) => l.trim() === subHeading);
  if (idx < 0) {
    // Sub-heading missing — append the labeled addition at the bottom
    // so the doctor's text is still attributed.
    const trailing = sectionBody.replace(/\s+$/, '');
    const sep = trailing ? '\n\n' : '';
    return `${trailing}${sep}${subHeading}\n${text}`;
  }
  // Insert immediately after the sub-heading, before the next blank
  // line OR the next sub-heading (whichever comes first).
  const out = [...lines];
  const insertText = text.replace(/\s+$/, '');
  out.splice(idx + 1, 0, insertText);
  return out.join('\n');
}

/** Append text at the end of a section body (used for sections without
 *  a sub-heading mapping — Objective.exam-systems, Plan items). */
function appendToSection(sectionBody: string, text: string): string {
  const trailing = sectionBody.replace(/\s+$/, '');
  const sep = trailing ? '\n\n' : '';
  return `${trailing}${sep}${text.replace(/\s+$/, '')}`;
}

/** Reassemble preamble + 4 sections back into a SOAP markdown blob.
 *  Preserves the section order S → O → A → P. */
function rejoin(preamble: string, sections: Record<SoapSectionKey, string>): string {
  const parts: string[] = [];
  if (preamble.trim()) parts.push(preamble);
  for (const k of SECTION_ORDER) {
    const heading = SECTION_HEADING[k];
    const body = sections[k].replace(/\s+$/, '');
    if (body) {
      parts.push(`${heading}\n${body}`);
    } else {
      // Empty section — keep the heading so the parser still finds
      // the scaffold. Pre-merge empty sections were authored as
      // `## Subjective\n[not documented]` style by the model; we
      // preserve whatever the empty body is. If truly empty we still
      // emit the heading.
      parts.push(heading);
    }
  }
  return parts.join('\n\n');
}

/** Pure merge primitive — testable without a DB. */
export function mergeAdditions(
  soap: string,
  additions: ReadonlyArray<AdditionInput>,
): MergeResult {
  const { preamble, sections } = splitSections(soap);
  const applied: AdditionInput[] = [];
  const skipped: Array<AdditionInput & { reason: string }> = [];

  for (const add of additions) {
    const trimmed = (add.text ?? '').trim();
    if (!trimmed) {
      skipped.push({ ...add, reason: 'empty text' });
      continue;
    }
    const target = sectionTargetFor(add.criterionId);
    if (!target) {
      // Unknown criterion id — least-destructive fallback: append to
      // Plan with a plain bullet, and surface the unknown id so the
      // doctor sees that the route didn't drop the text.
      sections.P = appendToSection(
        sections.P,
        `- (unrecognised criterion ${add.criterionId}) ${trimmed}`,
      );
      applied.push({ ...add, text: trimmed });
      continue;
    }
    if (target.subHeading) {
      sections[target.section] = insertUnderSubHeading(
        sections[target.section],
        target.subHeading,
        trimmed,
      );
    } else {
      sections[target.section] = appendToSection(sections[target.section], trimmed);
    }
    applied.push({ ...add, text: trimmed });
  }

  return {
    newSoap: rejoin(preamble, sections),
    applied,
    skipped,
  };
}
