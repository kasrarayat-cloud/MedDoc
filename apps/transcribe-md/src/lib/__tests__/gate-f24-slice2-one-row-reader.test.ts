import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { flattenTables } from '../ehr-formatters';
import { parseMarkdownRow, MARKDOWN_RULE_ROW_RE } from '../markdown-row';

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
