// ============================================================================
// GATE — NO IMAGING ROW REACHES L4 WITHOUT ITS OWN BUILDER
// ADMIN-3 PR-1, ruling #197.
// ----------------------------------------------------------------------------
// The imaging rule is catalog data now (`reportKind: 'imaging'`). Before it
// was, every consumer downstream of "is imaging" was ultrasound-shaped, so a
// second imaging row (x-ray, CT) would have silently inherited:
//   - L4's ULTRASOUND_REPORT_TEMPLATE and buildUltrasoundSystemPrompt, and
//   - the worker's venous-duplex `reconcileMeasurementTables` rebuild.
// This file pins that every imaging row names a builder, that the builder is
// implemented, that both consumers look it up BY THAT NAME, and that a row
// with no builder FAILS CLOSED instead of falling back to ultrasound.
//
// `tsc` refuses a builderless imaging row too (discriminated union +
// mapped-type registry), but vitest strips types without checking them, so
// every claim here is also asserted at runtime.
// ============================================================================

import { readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';

import {
  IMAGING_REPORT_BUILDERS,
  SPECIALTIES,
} from '@meddoc/shared/specialties';
import {
  IMAGING_REPORT_BUILDER_REGISTRY,
  imagingReportBuilderFor,
  resolveImagingReportBuilder,
} from '../imaging-report-builders';
import { ULTRASOUND_REPORT_TEMPLATE } from '../ultrasound-report-template';
import { buildUltrasoundSystemPrompt } from '../build-ultrasound-prompt';
import { reconcileMeasurementTables } from '../reconcile-measurement-tables';
import type { ResolvedNoteTemplate } from '../build-soap-prompt';
import {
  FLAG_STATES,
  FULL_UNIVERSE,
  frozen,
  restoreUltrasoundFlag,
  setUltrasoundFlag,
  show,
} from '../../../../../../packages/shared/src/__test-support__/report-kind-oracle';

const APP = path.resolve(__dirname, '../../../..');
const read = (rel: string) => readFileSync(path.join(APP, rel), 'utf8');
/** The house comment stripper (review-read-only-paper.test.ts): a file's
 *  comments are the one place the token you grep for is guaranteed to appear. */
const stripComments = (src: string) =>
  src.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/^\s*\/\/.*$/gm, ' ');

type Row = { id: string; reportKind?: unknown; reportBuilder?: unknown };
const ROWS = SPECIALTIES as unknown as readonly Row[];

afterEach(restoreUltrasoundFlag);

describe('THE CATALOG: every row declares a kind, every imaging row names a builder', () => {
  it('every row carries reportKind "office" or "imaging"', () => {
    const bad = ROWS.filter((r) => r.reportKind !== 'office' && r.reportKind !== 'imaging');
    expect(bad.map((r) => r.id)).toEqual([]);
  });

  it('POSITIVE CONTROL — there is at least one imaging row, so the next arm is not vacuous', () => {
    expect(ROWS.filter((r) => r.reportKind === 'imaging').length).toBeGreaterThan(0);
  });

  it('⚠️ EVERY IMAGING ROW NAMES A BUILDER THAT IS DECLARED AND IMPLEMENTED', () => {
    const declared = new Set<string>(IMAGING_REPORT_BUILDERS);
    const offenders = ROWS.filter((r) => r.reportKind === 'imaging')
      .filter(
        (r) =>
          typeof r.reportBuilder !== 'string' ||
          !declared.has(r.reportBuilder) ||
          !Object.prototype.hasOwnProperty.call(IMAGING_REPORT_BUILDER_REGISTRY, r.reportBuilder)
      )
      .map((r) => `${r.id} -> ${show(r.reportBuilder)}`);
    expect(
      offenders,
      'an imaging row with no registered builder would reach L4 with no template or ' +
        'prompt of its own — add its builder to imaging-report-builders.ts'
    ).toEqual([]);
  });

  it('no office row carries a reportBuilder (a builder on an office row is a mislabelled kind)', () => {
    const bad = ROWS.filter((r) => r.reportKind === 'office' && 'reportBuilder' in r);
    expect(bad.map((r) => r.id)).toEqual([]);
  });

  it('the registry implements EXACTLY the declared names — no orphan, no gap', () => {
    expect(Object.keys(IMAGING_REPORT_BUILDER_REGISTRY).sort()).toEqual(
      [...IMAGING_REPORT_BUILDERS].sort()
    );
    for (const b of Object.values(IMAGING_REPORT_BUILDER_REGISTRY)) {
      expect(typeof b.buildSystemPrompt).toBe('function');
      expect(typeof b.reconcileFinalNote).toBe('function');
      expect(Array.isArray(b.defaultTemplate.sections)).toBe(true);
    }
  });
});

describe('FAIL CLOSED — a row the catalog does not contain yet', () => {
  const CASES: Array<[string, Row]> = [
    ['imaging row with no reportBuilder', { id: 'xray', reportKind: 'imaging' }],
    ['imaging row naming an unimplemented builder', { id: 'xray', reportKind: 'imaging', reportBuilder: 'xray' }],
    ['imaging row naming a prototype key', { id: 'xray', reportKind: 'imaging', reportBuilder: 'toString' }],
    ['imaging row naming __proto__', { id: 'xray', reportKind: 'imaging', reportBuilder: '__proto__' }],
    ['imaging row naming constructor', { id: 'xray', reportKind: 'imaging', reportBuilder: 'constructor' }],
    ['imaging row with a null builder', { id: 'xray', reportKind: 'imaging', reportBuilder: null }],
    ['imaging row with a non-string builder', { id: 'xray', reportKind: 'imaging', reportBuilder: 1 }],
    ['office row naming the ultrasound builder', { id: 'xray', reportKind: 'office', reportBuilder: 'ultrasound' }],
  ];
  it.each(CASES)('%s THROWS, and never hands back the ultrasound builder', (_label, row) => {
    expect(() => resolveImagingReportBuilder(row as never)).toThrow(/"xray".*no registered imaging report builder/);
  });

  it('CONTROL — the real ultrasound row resolves, to the registry entry itself', () => {
    const us = ROWS.find((r) => r.id === 'ultrasound')!;
    expect(resolveImagingReportBuilder(us as never)).toBe(IMAGING_REPORT_BUILDER_REGISTRY.ultrasound);
  });
});

describe('BYTE-IDENTITY — the ultrasound entry is the bindings the call sites used to make', () => {
  const US = IMAGING_REPORT_BUILDER_REGISTRY.ultrasound;
  const OPTS = [
    { specialty: 'ultrasound', audioQualityAlert: null, interpreterAlert: null, specialtyGuidanceText: null },
    { specialty: 'ultrasound', audioQualityAlert: 'AUDIO QUALITY ALERT: x', interpreterAlert: 'INTERPRETED VISIT: y', specialtyGuidanceText: null },
  ];

  it('the default template is the SAME object L4 used to bind', () => {
    expect(US.defaultTemplate).toBe(ULTRASOUND_REPORT_TEMPLATE);
  });

  it('the prompt builder returns exactly what buildUltrasoundSystemPrompt returns', () => {
    for (const opts of OPTS) {
      const t = ULTRASOUND_REPORT_TEMPLATE as ResolvedNoteTemplate;
      expect(US.buildSystemPrompt(t, opts)).toBe(buildUltrasoundSystemPrompt(t, opts));
    }
  });

  it('the final-note pass returns exactly what reconcileMeasurementTables returns', () => {
    const NOTES = [
      '',
      'Impression: normal study.',
      [
        '## Findings',
        'Right Leg:',
        '| Segment | Diameter (mm) | Reflux (seconds) |',
        '| --- | --- | --- |',
        '| GSV at the SFJ | 6.2 | 1.4 |',
        'The right small saphenous vein at the proximal calf measures 2.8 mm.',
      ].join('\n'),
    ];
    for (const n of NOTES) expect(US.reconcileFinalNote(n)).toBe(reconcileMeasurementTables(n));
    // The fixture must actually exercise the rebuild, or the arm is vacuous.
    expect(reconcileMeasurementTables(NOTES[2]!)).not.toBe(NOTES[2]);
  });
});

describe.each(FLAG_STATES.map((v) => [show(v), v] as const))(
  'imagingReportBuilderFor, NEXT_PUBLIC_ULTRASOUND_SPECIALTY = %s',
  (_label, value) => {
    it('non-null EXACTLY where the frozen raw predicate was true (flag-agnostic, like worker.ts)', () => {
      setUltrasoundFlag(value);
      const diffs = FULL_UNIVERSE.filter(
        (u) => (imagingReportBuilderFor(u) !== null) !== frozen.isImaging(u)
      ).map(show);
      expect(diffs).toEqual([]);
      expect(imagingReportBuilderFor('ultrasound')).toBe(IMAGING_REPORT_BUILDER_REGISTRY.ultrasound);
    });
  }
);

describe('KEYED BY NAME — both consumers look the builder up, neither binds ultrasound directly', () => {
  const ULTRASOUND_SYMBOLS = [
    'ULTRASOUND_REPORT_TEMPLATE',
    'buildUltrasoundSystemPrompt',
    'reconcileMeasurementTables',
  ];

  it('L4 takes its imaging template AND prompt builder from the row\'s builder', () => {
    const code = stripComments(read('src/worker/layers/04-generate-soap.ts'));
    expect(code).toContain('imagingReportBuilderFor(input.specialty)');
    expect(code).toContain('imagingBuilder.defaultTemplate');
    expect(code).toContain('imagingBuilder.buildSystemPrompt(template, systemOpts)');
    for (const sym of ULTRASOUND_SYMBOLS) {
      expect(code, `L4 binds ${sym} directly — the route is no longer keyed by name`).not.toMatch(
        new RegExp(`\\b${sym}\\b`)
      );
    }
  });

  it('the worker\'s post-L6 table rebuild is the row\'s builder, not the venous pass', () => {
    const code = stripComments(read('src/worker.ts'));
    expect(code).toContain('imagingReportBuilderFor(visit.specialty)');
    expect(code).toContain('.reconcileFinalNote(polished.soapFinal)');
    expect(code).not.toMatch(/\breconcileMeasurementTables\b/);
  });

  it('CENSUS — outside their own modules, only the registry names the ultrasound builders', () => {
    // Derived from the filesystem, not a hand-kept list: a NEW consumer that
    // binds an ultrasound builder directly reds here by name.
    const files: string[] = [];
    const walk = (dir: string) => {
      for (const e of readdirSync(dir)) {
        const p = path.join(dir, e);
        if (statSync(p).isDirectory()) {
          if (e === '__tests__' || e === 'node_modules') continue;
          walk(p);
        } else if (/\.(ts|tsx)$/.test(e) && !/\.(test|spec)\.tsx?$/.test(e)) {
          files.push(p);
        }
      }
    };
    walk(path.join(APP, 'src'));
    expect(files.length, 'the walk found no source — check the path').toBeGreaterThan(100);

    const referencing = files
      .filter((f) => {
        const code = stripComments(readFileSync(f, 'utf8'));
        return ULTRASOUND_SYMBOLS.some((sym) => new RegExp(`\\b${sym}\\b`).test(code));
      })
      .map((f) => path.relative(APP, f))
      .sort();
    expect(referencing).toEqual(
      [
        // The three defining modules (build-ultrasound-prompt also reads the
        // canonical template for its immutable safety layer).
        'src/worker/note-templates/build-ultrasound-prompt.ts',
        'src/worker/note-templates/reconcile-measurement-tables.ts',
        'src/worker/note-templates/ultrasound-report-template.ts',
        // The one place a name becomes a binding.
        'src/worker/note-templates/imaging-report-builders.ts',
      ].sort()
    );
  });
});
