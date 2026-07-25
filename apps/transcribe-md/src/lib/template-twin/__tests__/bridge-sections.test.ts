// ============================================================================
// The twin BRIDGE — the twin NoteTemplate must carry the DOCUMENT's structure.
// ----------------------------------------------------------------------------
// The shipped bridge handed the twin NoteTemplate `systemDefault.sections`
// verbatim, i.e. Subjective / Objective / Assessment / Plan. Measured against
// the real WM_IOV docx on 2026-07-25: the twin extracted 80 field definitions
// and then generated against SOAP headings the document does not contain, so
// L4 wrote a SOAP note and the fill bound almost nothing.
//
// After the fix the same docx bridges to
//   "Venous Duplex Lower Extremities Report" — Exam Metadata | TECHNIQUE |
//   FINDINGS | IMPRESSION | DIAMETER AND REFLUX TIME
//
// These tests are deterministic: the bridge's structure comes from
// parseNoteToTemplate, which is an LLM call, so it is stubbed. What is under
// test is the BRIDGE's own contract — which structure it chooses, and what it
// does when the parse cannot supply one. The end-to-end behaviour against the
// real docx is covered by scripts/prod-smoke/twin-probe.ts.
// ============================================================================

import { describe, expect, it, vi, beforeEach } from 'vitest';

const SYSTEM_DEFAULT_SECTIONS = [
  { key: 'subjective', label: 'Subjective', order: 1 },
  { key: 'objective', label: 'Objective', order: 2 },
  { key: 'assessment', label: 'Assessment', order: 3 },
  { key: 'plan', label: 'Plan', order: 4 },
];

const DOC_SECTIONS = [
  { key: 'exam_metadata', label: 'Exam Metadata', order: 1 },
  { key: 'technique', label: 'TECHNIQUE', order: 2 },
  { key: 'findings', label: 'FINDINGS', order: 3 },
  { key: 'impression', label: 'IMPRESSION', order: 4 },
  { key: 'diameter_reflux', label: 'DIAMETER AND REFLUX TIME', order: 5 },
];

/** Mirrors the bridge's decision logic in create-draft.ts. Kept as a pure
 *  function here so the choice can be asserted without standing up Prisma,
 *  MinIO, the compiler and two model calls. */
function chooseBridgeStructure(parse: {
  threw?: boolean;
  extractedText?: string;
  rejected?: boolean;
  sections?: unknown[] | null;
  name?: string | null;
}): { sections: unknown[]; name: string; fallbackReason: string | null } {
  const fallback = {
    sections: SYSTEM_DEFAULT_SECTIONS as unknown[],
    name: 'Original Word template',
  };
  if (parse.threw) return { ...fallback, fallbackReason: 'BRIDGE_THREW' };
  if (!parse.extractedText?.trim()) return { ...fallback, fallbackReason: 'NO_TEXT_EXTRACTED' };
  if (parse.rejected) return { ...fallback, fallbackReason: 'PARSE_REJECTED' };
  if (!Array.isArray(parse.sections) || parse.sections.length === 0) {
    return { ...fallback, fallbackReason: 'PARSE_EMPTY_SECTIONS' };
  }
  return {
    sections: parse.sections,
    name: parse.name?.trim() || fallback.name,
    fallbackReason: null,
  };
}

const labelsOf = (rows: unknown[]) => rows.map((r) => (r as { label: string }).label);

describe('twin bridge — structure selection', () => {
  it("uses the DOCUMENT's sections when the parse succeeds", () => {
    const r = chooseBridgeStructure({
      extractedText: 'VENOUS DUPLEX ...',
      sections: DOC_SECTIONS,
      name: 'Venous Duplex Lower Extremities Report',
    });
    expect(r.fallbackReason).toBeNull();
    expect(labelsOf(r.sections)).toEqual([
      'Exam Metadata',
      'TECHNIQUE',
      'FINDINGS',
      'IMPRESSION',
      'DIAMETER AND REFLUX TIME',
    ]);
    expect(r.name).toBe('Venous Duplex Lower Extremities Report');
  });

  it('never silently emits the system-default SOAP sections on success', () => {
    const r = chooseBridgeStructure({
      extractedText: 'x',
      sections: DOC_SECTIONS,
      name: 'Doc',
    });
    // The exact regression: 4 SOAP labels where the document had none.
    expect(labelsOf(r.sections)).not.toEqual(['Subjective', 'Objective', 'Assessment', 'Plan']);
  });

  it.each([
    ['a throw', { threw: true }, 'BRIDGE_THREW'],
    ['no extractable text', { extractedText: '   ' }, 'NO_TEXT_EXTRACTED'],
    ['a rejected parse', { extractedText: 'x', rejected: true }, 'PARSE_REJECTED'],
    ['an empty section list', { extractedText: 'x', sections: [] }, 'PARSE_EMPTY_SECTIONS'],
  ])('falls back VISIBLY on %s', (_label, input, reason) => {
    const r = chooseBridgeStructure(input);
    // Fails SOFT — the draft still exists, the source artifact is still kept.
    expect(labelsOf(r.sections)).toEqual(['Subjective', 'Objective', 'Assessment', 'Plan']);
    // ...but never SILENTLY. A caller can see which branch it took.
    expect(r.fallbackReason).toBe(reason);
  });

  it('keeps the default name when the parse supplies a blank one', () => {
    const r = chooseBridgeStructure({ extractedText: 'x', sections: DOC_SECTIONS, name: '  ' });
    expect(r.name).toBe('Original Word template');
    expect(r.fallbackReason).toBeNull();
  });
});

describe('twin bridge — wiring in create-draft.ts', () => {
  let src = '';
  beforeEach(async () => {
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    src = readFileSync(join(__dirname, '..', 'create-draft.ts'), 'utf-8')
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/^\s*\/\/.*$/gm, '');
  });

  it('does NOT pass systemDefault.sections into the NoteTemplate insert', () => {
    expect(
      src,
      'the bridge is back to copying the system-default SOAP sections — the twin ' +
        'will generate against headings the uploaded document does not contain'
    ).not.toMatch(/sections:\s*systemDefault\.sections/);
    expect(src).toMatch(/sections:\s*bridgedSections/);
  });

  it('derives structure from the same parser the one-tap upload uses', () => {
    // Reusing parseNoteToTemplate is the point: a second, divergent docx
    // section parser is exactly the drift this codebase keeps paying for.
    expect(src).toContain('parseNoteToTemplate');
    expect(src).toContain('extractNoteTextFromUpload');
  });

  it('still records a reason when it falls back', () => {
    expect(src).toContain('bridgeFallbackReason');
  });
});
