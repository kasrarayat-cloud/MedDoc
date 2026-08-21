import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { flattenTables } from '../ehr-formatters';
import { claimProse } from '../claim-prose';
import { editTableCell } from '../note-table-edit';
import { parseMarkdownRow, MARKDOWN_RULE_ROW_RE } from '../markdown-row';
import JSZip from 'jszip';
import { generateVisitDocx } from '../docx-generator';

/**
 * F24 SLICE 2 — ONE ROW READER, FIVE CALLERS.
 *
 * The repository carried FIVE independent pipe-row matchers, four strict and
 * one tolerant, and they disagreed about a shape L4 emits: a row carrying a
 * trailing annotation after its last pipe. The fill path read such a row
 * correctly; every other surface skipped it. One note, two documents.
 *
 * Byte-identity across all 49 production notes was proven separately for both
 * export surfaces (EHR paste and `document.xml`), each with a control on a
 * production-exercised path. Those are corpus proofs and cannot live here.
 */
const LIB = join(__dirname, '..');

describe('the annotated row no longer leaks raw markdown', () => {
  const table = [
    '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
    '| --- | --- | --- |',
    '| GSV at the SFJ | 6.2 | 3.4 | "Great saphenous vein 6.2 mm, reflux 3.4 seconds."',
    '| SSV at the SPJ | 4.1 | 1.2 |',
  ].join('\n');

  it('renders the annotated row as a ROW, not as a line of pipes', () => {
    const out = flattenTables(table);
    // non-vacuity: the fixture really does carry an un-terminated row
    expect(table.split('\n')[2].trimEnd().endsWith('|')).toBe(false);
    // the defect: a raw pipe line surviving into the doctor's EHR paste
    const leaked = out.split('\n').filter((l) => l.trim().startsWith('|'));
    expect(leaked).toEqual([]);
    expect(out).toContain('GSV at the SFJ');
    expect(out).toContain('DIAMETER (mm): 6.2');
  });

  it('the annotation SURVIVES — a clinical export drops nothing silently', () => {
    // ehr-formatters states this rule for orphan cells; the suffix is the same
    // class of content. The primitive returns it so each caller can decide.
    expect(flattenTables(table)).toContain('reflux 3.4 seconds');
  });

  it('an unheaded column contributes its value in BOTH join paths', () => {
    // Row path and header-only path. I fixed one and called the class closed;
    // `flattenTables` has THREE `join(' · ')` sites and the header-only one
    // still emitted a leading separator.
    expect(flattenTables(table).startsWith(':')).toBe(false);
    const headerOnly = ['|  | DIAMETER (mm) | REFLUX TIME (ms) |', '| --- | --- | --- |'].join('\n');
    expect(flattenTables(headerOnly)).toBe('DIAMETER (mm) · REFLUX TIME (ms)');
    // direction control: a NAMED column keeps its name in that same path
    const named = ['| VEIN | DIAMETER (mm) |', '| --- | --- |'].join('\n');
    expect(flattenTables(named)).toBe('VEIN · DIAMETER (mm)');
  });
});

describe('the primitive PARSES; each caller JUDGES', () => {
  it('parses a separator row rather than refusing it', () => {
    // ⚠️ Returning null here reads as obviously right and broke bridge-fill
    // completely: it SPLITS the separator on purpose and validates every cell
    // against its own SEP_ROW_RE before accepting a table. With null it found
    // ZERO tables and 28 fill tests went red — invisible to both render
    // digests, caught only by the fill-verdict census.
    expect(parseMarkdownRow('| --- | --- |')?.cells).toEqual(['---', '---']);
    expect(MARKDOWN_RULE_ROW_RE.test('| --- | --- |')).toBe(true);
  });

  it('returns the suffix instead of deciding its fate', () => {
    const r = parseMarkdownRow('| a | 6.2 | "quote here"');
    expect(r?.cells).toEqual(['a', '6.2']);
    expect(r?.suffix).toBe('"quote here"');
    expect(parseMarkdownRow('| a | b |')?.suffix).toBe('');
  });

  it('is not a row at all when there is no closing pipe', () => {
    expect(parseMarkdownRow('just prose')).toBeNull();
    expect(parseMarkdownRow('| unterminated')).toBeNull();
  });
});

describe('⚠️ the FROZEN-MANIFEST SERVE never routes through the row reader', () => {
  // §2.5's native-path assertion, as a test rather than a sentence.
  //
  // THE DISTINCTION IS CREATE vs SERVE. `bridge-fill` BUILDS a manifest and is
  // a legitimate caller. `native-export` SERVES a frozen one — stored bytes,
  // resolved by pointer — and must not acquire an opinion about markdown at
  // all, or a rendering change could alter what a signed record hands back.
  const SERVE = [
    'template-twin/native-export.ts',
    'template-twin/fill-engine.ts',
    'template-twin/sign-freeze.ts',
    'template-twin/note-identity.ts',
    'visit-docx-source.ts',
  ];

  it('no serve-path module imports markdown-row', () => {
    for (const f of SERVE) {
      const src = readFileSync(join(LIB, f), 'utf8');
      expect(src.includes('markdown-row')).toBe(false);
    }
  });

  it('and the caller set is EXACTLY five — a sixth is a decision, not a drift', () => {
    const walk = (dir: string): string[] =>
      readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
        e.name === '__tests__'
          ? []
          : e.isDirectory()
            ? walk(join(dir, e.name))
            : e.name.endsWith('.ts')
              ? [join(dir, e.name)]
              : [],
      );
    const importers = walk(LIB)
      .filter((p) => !p.endsWith('markdown-row.ts'))
      .filter((p) => /from '(@\/lib\/|\.\/|\.\.\/)markdown-row'/.test(readFileSync(p, 'utf8')))
      .map((p) => p.replace(LIB + '/', ''))
      .sort();
    // positive control: the walk actually found files
    expect(walk(LIB).length).toBeGreaterThan(20);
    expect(importers).toEqual([
      'claim-prose.ts',
      'docx-generator.ts',
      'ehr-formatters.ts',
      'note-table-edit.ts',
      'template-twin/bridge-fill.ts',
    ]);
  });
});

describe('⚠️ BOTH export surfaces, not one — the watched-set gap the pass found', () => {
  // The original arm asserted "the annotation SURVIVES" against `flattenTables`
  // ONLY. The DOCX surface sat outside its watched set, and that is exactly
  // where the content was being deleted: an evidence annotation vanished from
  // word/document.xml while the EHR paste kept it, and `| Side of exam | Right`
  // — closing pipe omitted by L4 — lost `Right`, THE SIDE OF EXAM, from a
  // signed imaging report. A gate that watches one of two emitters reports zero
  // for the one it cannot see.
  const docxText = async (soapText: string) => {
    const buf = await generateVisitDocx({
      visitId: 'v', patientName: 'X', specialty: 'ultrasound', chiefComplaint: null,
      status: 'SIGNED', createdAt: new Date(0), signedAt: new Date(0),
      clinicianName: 'C', clinicianEmail: 'c@e', soapText,
      icdCodes: [], em: null, procedures: [], modifiers: [],
      prescriptions: [], rxWarnings: [], referrals: [], patientSummary: null,
      headerFields: [], formOnly: false,
    } as never);
    const zip = await JSZip.loadAsync(buf as never);
    return (await zip.file('word/document.xml')?.async('string')) ?? '';
  };

  it('an evidence annotation reaches the SIGNED document, not only the paste', async () => {
    const note = [
      '## EXAM', '',
      '|  | DIAMETER (mm) | REFLUX (ms) |',
      '| --- | --- | --- |',
      '| GSV at the SFJ | 6.2 | 3400 | "reflux 3.4 seconds"',
      '',
    ].join('\n');
    const xml = await docxText(note);
    // non-vacuity: the document really was produced and holds the row
    expect(xml).toContain('GSV at the SFJ');
    expect(xml).toContain('reflux 3.4 seconds');
    expect(flattenTables(note)).toContain('reflux 3.4 seconds');
  });

  it('⚠️ a row whose closing pipe L4 omitted keeps its LAST VALUE', async () => {
    // The greedy read cannot tell an annotation from a truncated final cell —
    // both are "text after the last pipe". Dropping it deleted a measurement.
    const note = [
      '## EXAM', '',
      '| FIELD | VALUE |',
      '| --- | --- |',
      '| Side of exam | Right',
      '| Study indication | Venous reflux |',
      '',
    ].join('\n');
    const xml = await docxText(note);
    expect(xml).toContain('Side of exam');
    expect(xml).toContain('Right');
    expect(xml).toContain('Venous reflux');
  });

  it('the FILL still never sees the annotation as a cell', () => {
    // The other half of the contract. `visit-fill-defects.test.ts` pins it, and
    // it is why the trailing text is carried at the RENDERER rather than
    // promoted to a cell in the shared primitive: the fill writes cells into
    // the doctor's own form, so prose there would become a measurement.
    const r = parseMarkdownRow('| GSV at the SFJ | 6.2 | 3.4 | "reflux 3.4 seconds"');
    expect(r?.cells).toEqual(['GSV at the SFJ', '6.2', '3.4']);
    expect(r?.cells).not.toContain('"reflux 3.4 seconds"');
    expect(r?.suffix).toBe('"reflux 3.4 seconds"');
  });
});

describe('the two remaining callers, re-tested against HEAD', () => {
  it('an EDIT drops the annotation, deliberately — and that is content loss by choice', () => {
    // ⚠️ RECORDED AS A DECISION, NOT LEFT IMPLICIT. An edit rewrites the row
    // from its cells, so the evidence quote no longer supports the value
    // standing in the cell. Keeping it would put two records on one line —
    // "a WRONG field is content that says the opposite of the record being
    // signed". Dropping it IS content loss; it is the lesser of the two, and
    // it is pinned here so nobody restores the quote thinking they are fixing
    // a bug.
    const r = editTableCell({
      note: ['## F', '', '|  | D (mm) |', '| --- | --- |', '| GSV | 6.2 | "evidence for 6.2"', ''].join('\n'),
      sectionLabel: 'F', rowLabel: 'GSV', columnLabel: 'D (mm)', value: '9.9',
    });
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.body).toContain('| GSV | 9.9 |');
      expect(r.body).not.toContain('evidence for 6.2');
    }
  });

  it('claim-prose converts an ANNOTATED row it used to hand back as markup', () => {
    // Its strict matcher rejected the annotated row, so a demoted claim was
    // shown to the doctor as `| GSV at the SFJ | 6.2 | 3400 | "quote"` — a
    // fragment of markup they were asked to make a clinical decision about,
    // which is the exact thing that file exists to prevent.
    const note = (row: string) =>
      ['## FINDINGS', '', 'Right Leg:', '|  | DIAMETER (mm) | REFLUX (ms) |', '| --- | --- | --- |', row, ''].join('\n');
    const annotated = '| GSV at the SFJ | 6.2 | 3400 | "quote"';
    const out = claimProse(annotated, note(annotated));
    expect(out.trim().startsWith('|')).toBe(false);
    expect(out).toContain('GSV at the SFJ');
    expect(out).toContain('Right Leg');
    // control: the well-formed row still converts, unchanged in behaviour
    const plain = '| GSV at the SFJ | 6.2 | 3400 |';
    expect(claimProse(plain, note(plain)).trim().startsWith('|')).toBe(false);
  });
});
