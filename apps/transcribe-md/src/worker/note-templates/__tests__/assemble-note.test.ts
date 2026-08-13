// ============================================================================
// GATE — composition splices the doctor's sections in and changes NOTHING else
// (ruling #106(a)/(e), SPEC §4.3a).
// ----------------------------------------------------------------------------
// ⚠️ THE FIXTURE IS SANITIZED, PER SPEC §4.3a(e) — the same STRUCTURAL features
// as the real customer form (a fixed protocol paragraph carrying one dropdown,
// a label:value field block, per-leg carrier lines) and NO real clinic,
// physician or technologist names. `500 milliseconds` is the permitted verbatim
// tripwire: it is the exact text the live defect normalised to "0.5 seconds".
// ============================================================================
import { describe, expect, it } from 'vitest';

import {
  composeNote,
  generatedSections,
  segmentStaticSections,
  splitBlocks,
  staticRegionsFromNote,
  staticSections,
} from '../assemble-note';
import type { NoteTemplateSection } from '../system-default-template';

const TECHNIQUE_TEXT =
  'A duplex Doppler color flow ultrasound study was performed in the upright ' +
  'position, documenting the condition of the {{one of: deep and superficial | ' +
  'superficial}} venous systems of the extremity. This study documents reflux ' +
  'as lasting more than 500 milliseconds in either the saphenous veins or the ' +
  'perforator veins.';

function section(over: Partial<NoteTemplateSection> & { key: string; label: string; order: number }): NoteTemplateSection {
  return {
    formatHint: 'prose',
    styleInstructions: null,
    defaultText: null,
    defaultTextMode: 'omit_unless_supported',
    ...over,
  } as NoteTemplateSection;
}

const TECHNIQUE = section({
  key: 'technique',
  label: 'TECHNIQUE',
  order: 2,
  defaultText: TECHNIQUE_TEXT,
  defaultTextMode: 'always_include',
});

const FINDINGS = section({
  key: 'findings',
  label: 'FINDINGS',
  order: 3,
  defaultText: 'Right Leg:\n{{one of: normal | abnormal}}',
  defaultTextMode: 'scaffold_confirm',
});

const EXAM = section({ key: 'exam_metadata', label: 'EXAM', order: 1 });

const SECTIONS = [EXAM, TECHNIQUE, FINDINGS];

const MODEL_NOTE = [
  '## EXAM',
  'Bilateral lower extremity.',
  '',
  '## TECHNIQUE',
  'A duplex study was done, documenting reflux over 0.5 seconds.',
  '',
  '## FINDINGS',
  'Right Leg: normal',
].join('\n');

describe('staticSections — which sections code owns', () => {
  it('is EMPTY for a template with no always_include section', () => {
    expect(staticSections([EXAM, FINDINGS])).toEqual([]);
  });

  it('picks up an always_include section carrying text', () => {
    expect(staticSections(SECTIONS).map((s) => s.key)).toEqual(['technique']);
  });

  it('EXCLUDES an always_include section with no text — there is nothing to assemble', () => {
    const empty = section({ key: 'x', label: 'X', order: 9, defaultTextMode: 'always_include' });
    expect(staticSections([empty])).toEqual([]);
  });

  // ⚠️ THE ONE THAT PROTECTS THE PATIENT'S NUMBERS. A table's cells hold
  // dictated measurements and its defaultText is the empty skeleton, so
  // composing it would preserve the doctor's bytes perfectly and delete every
  // value the visit produced.
  it('EXCLUDES a STRUCTURED always_include section — a table is a fill surface', () => {
    const table = section({
      key: 'grid',
      label: 'GRID',
      order: 4,
      defaultText: '| A | B |',
      defaultTextMode: 'always_include',
      structure: { kind: 'table', columns: ['DIAMETER (mm)'] },
    });
    expect(staticSections([table])).toEqual([]);
    // …and it is therefore still the model's to write.
    expect(generatedSections([table]).map((s) => s.key)).toEqual(['grid']);
  });

  it('partitions: generated ∪ static = every section, with no overlap', () => {
    const g = generatedSections(SECTIONS).map((s) => s.key);
    const s = staticSections(SECTIONS).map((x) => x.key);
    expect(g.length + s.length).toBe(SECTIONS.length);
    expect(new Set([...g, ...s]).size).toBe(SECTIONS.length);
  });
});

describe('splitBlocks', () => {
  it('keeps a preamble that precedes the first heading', () => {
    const blocks = splitBlocks('stray prose\n## A\nbody');
    expect(blocks.map((b) => b.heading)).toEqual([null, 'A']);
  });

  it('round-trips byte-for-byte', () => {
    expect(splitBlocks(MODEL_NOTE).map((b) => b.text).join('\n')).toBe(MODEL_NOTE);
  });

  it('returns NO blocks for empty input — not one empty block', () => {
    expect(splitBlocks('')).toEqual([]);
  });
});

describe('⚠️ #106(e) — ZERO STATICS means the note is returned UNTOUCHED', () => {
  it('is byte-identical for a template with no always_include section', () => {
    const out = composeNote(MODEL_NOTE, [EXAM, FINDINGS], { findings: { s0: 'normal' } });
    expect(out.text).toBe(MODEL_NOTE);
    expect(out.regions).toEqual([]);
    expect(out.replaced + out.inserted + out.duplicatesDropped).toBe(0);
  });

  it('is byte-identical even when fills are supplied for keys that exist', () => {
    // A fill for a section the composer does not own must not reach the note.
    const out = composeNote(MODEL_NOTE, [EXAM, FINDINGS], { technique: { s0: 'superficial' } });
    expect(out.text).toBe(MODEL_NOTE);
  });
});

describe('composeNote — the doctor bytes replace the model\'s paraphrase', () => {
  it('⚠️ THE TRIPWIRE: 500 milliseconds survives, 0.5 seconds is gone', () => {
    const out = composeNote(MODEL_NOTE, SECTIONS, {
      technique: { s0: 'deep and superficial' },
    });
    expect(out.text).toContain('500 milliseconds');
    expect(out.text).not.toContain('0.5 seconds');
    expect(out.replaced).toBe(1);
    expect(out.inserted).toBe(0);
  });

  it('keeps the fixed paragraph even when the slot is UNFILLED', () => {
    const out = composeNote(MODEL_NOTE, SECTIONS, {});
    expect(out.text).toContain('500 milliseconds');
    expect(out.text).toContain('—');
    expect(out.unfilled).toBe(1);
  });

  it('REFUSES an out-of-menu value and marks the hole', () => {
    const out = composeNote(MODEL_NOTE, SECTIONS, {
      technique: { s0: 'whatever the model preferred' },
    });
    expect(out.rejected).toBe(1);
    expect(out.text).not.toContain('whatever the model preferred');
    expect(out.text).toContain('500 milliseconds');
  });

  it('leaves every GENERATED section byte-for-byte as the model wrote it', () => {
    const out = composeNote(MODEL_NOTE, SECTIONS, { technique: { s0: 'superficial' } });
    expect(out.text).toContain('## EXAM\nBilateral lower extremity.');
    expect(out.text).toContain('## FINDINGS\nRight Leg: normal');
  });

  it('INSERTS a static section the model omitted, at its template position', () => {
    const without = ['## EXAM', 'Bilateral.', '', '## FINDINGS', 'Right Leg: normal'].join('\n');
    const out = composeNote(without, SECTIONS, {});
    expect(out.inserted).toBe(1);
    expect(out.replaced).toBe(0);
    const blocks = splitBlocks(out.text).map((b) => b.heading);
    expect(blocks).toEqual(['EXAM', 'TECHNIQUE', 'FINDINGS']);
  });

  it('inserts BEFORE the following section when no preceding one is present', () => {
    const out = composeNote('## FINDINGS\nRight Leg: normal', SECTIONS, {});
    expect(splitBlocks(out.text).map((b) => b.heading)).toEqual(['TECHNIQUE', 'FINDINGS']);
  });

  it('appends when the model emitted nothing recognisable', () => {
    const out = composeNote('## OTHER\nsomething', SECTIONS, {});
    expect(splitBlocks(out.text).map((b) => b.heading)).toEqual(['OTHER', 'TECHNIQUE']);
  });

  // ⚠️ Keeping a paraphrased duplicate beside the assembled one would be the
  // original defect surviving inside its own fix.
  it('DROPS a second block carrying a static section\'s heading', () => {
    const twice = [MODEL_NOTE, '', '## TECHNIQUE', 'reflux over 0.5 seconds again.'].join('\n');
    const out = composeNote(twice, SECTIONS, {});
    expect(out.duplicatesDropped).toBe(1);
    expect(out.text).not.toContain('0.5 seconds');
    expect(splitBlocks(out.text).filter((b) => b.heading === 'TECHNIQUE')).toHaveLength(1);
  });

  it('does NOT drop a duplicate of a GENERATED heading — that is the model\'s content', () => {
    const twice = [MODEL_NOTE, '', '## FINDINGS', 'Left Leg: normal'].join('\n');
    const out = composeNote(twice, SECTIONS, {});
    expect(out.duplicatesDropped).toBe(0);
    expect(out.text).toContain('Left Leg: normal');
  });

  it('preserves a preamble block rather than deciding it is worthless', () => {
    const out = composeNote(`stray\n${MODEL_NOTE}`, SECTIONS, {});
    expect(out.text.startsWith('stray\n')).toBe(true);
  });
});

describe('staticRegionsFromNote — the SECOND READING of one fact, not a second source', () => {
  it('⚠️ ROUND-TRIP: what it reads back equals what composeNote assembled', () => {
    const cases: Record<string, Record<string, string>>[] = [
      {},
      { technique: { s0: 'superficial' } },
      { technique: { s0: 'deep and superficial' } },
      { technique: { s0: 'not on the menu' } },
    ];
    for (const fills of cases) {
      const out = composeNote(MODEL_NOTE, SECTIONS, fills);
      expect(staticRegionsFromNote(out.text, SECTIONS)).toEqual(out.regions);
    }
  });

  it('is EMPTY for a template with no statics', () => {
    expect(staticRegionsFromNote(MODEL_NOTE, [EXAM, FINDINGS])).toEqual([]);
  });

  it('skips a static section the note does not carry', () => {
    expect(staticRegionsFromNote('## EXAM\nBilateral.', SECTIONS)).toEqual([]);
  });
});

describe('segmentStaticSections — the ids the prompt names are the ids the composer fills', () => {
  it('numbers slots per section, starting at s0', () => {
    const segs = segmentStaticSections(SECTIONS);
    expect(segs).toHaveLength(1);
    expect(segs[0]!.section.key).toBe('technique');
    const ids = segs[0]!.lines
      .flatMap((l) => l.segments)
      .filter((s) => s.kind === 'slot')
      .map((s) => (s as { id: string }).id);
    expect(ids).toEqual(['s0']);
  });
});
