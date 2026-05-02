// ============================================================================
// E&M Coding — corpus test harness (Phase 5.2 §6)
// ----------------------------------------------------------------------------
// Loads every .md fixture from /opt/meddoc-pro/tests/fixtures/soap-em-corpus/
// (excluding _README.md), parses the YAML frontmatter, runs computeEmScore
// in deterministic-fallback mode (mdmCachedJudgement=null, no LLM call),
// and asserts the engine matches each fixture's `expected` block.
//
// Pass threshold per rubric §6: ≥28/30 fixtures pass to ship. The
// it.each() loop reports per-fixture failures so calibration is
// targeted (engine vs. fixture).
// ============================================================================

import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { computeEmScore } from '../score';
import type {
  ElementLevel,
  EmCode,
  MdmTier,
  VisitType,
} from '../types';

interface FixtureExpected {
  code: EmCode;
  mdmTier: MdmTier;
  hpiElements: number;
  rosSystems: number;
  pfshCategories: number;
  examSystems: number;
  problems: ElementLevel;
  data: ElementLevel;
  risk: ElementLevel;
}

interface Fixture {
  id: string;
  category: string;
  visitType: VisitType;
  expected: FixtureExpected;
  bumpableTo?: EmCode | null;
  notes?: string;
  soap: string;
  filePath: string;
}

// Resolve the corpus directory relative to the running test file so the
// harness picks up THIS worktree's fixtures (not the production tree's).
// __dirname for the test file resolves to .../apps/transcribe-md/src/lib/em-coding/__tests__,
// then we walk up to the worktree root.
const CORPUS_DIR = path.resolve(
  __dirname,
  '../../../../../../tests/fixtures/soap-em-corpus',
);

/** Tiny YAML frontmatter parser — handles the constrained shape used by
 *  this corpus only. Supports nested keys (expected: { ... }) two levels
 *  deep, with values typed as number / string / null. Multi-line strings
 *  via `key: |` block scalars (used for `notes:`). */
function parseFrontmatter(raw: string): { meta: Record<string, unknown>; body: string } {
  const m = raw.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!m) return { meta: {}, body: raw };
  const yaml = m[1];
  const body = m[2];

  const meta: Record<string, unknown> = {};
  const lines = yaml.split('\n');

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const indent = line.match(/^(\s*)/)?.[1].length ?? 0;

    if (indent === 0 && line.trim()) {
      const colonIdx = line.indexOf(':');
      if (colonIdx === -1) {
        i++;
        continue;
      }
      const key = line.slice(0, colonIdx).trim();
      const rest = line.slice(colonIdx + 1).trim();

      if (rest === '|') {
        // Block scalar: collect indented lines.
        const blockLines: string[] = [];
        i++;
        while (i < lines.length && (lines[i].startsWith('  ') || lines[i] === '')) {
          blockLines.push(lines[i].slice(2));
          i++;
        }
        meta[key] = blockLines.join('\n');
        continue;
      }
      if (rest === '') {
        // Nested object follows.
        const nested: Record<string, unknown> = {};
        i++;
        while (i < lines.length) {
          const subline = lines[i];
          const subIndent = subline.match(/^(\s*)/)?.[1].length ?? 0;
          if (subIndent < 2 || !subline.trim()) {
            if (!subline.trim()) { i++; continue; }
            break;
          }
          const subColon = subline.indexOf(':');
          if (subColon === -1) { i++; continue; }
          const subKey = subline.slice(0, subColon).trim();
          const subVal = subline.slice(subColon + 1).trim();
          nested[subKey] = parseScalar(subVal);
          i++;
        }
        meta[key] = nested;
        continue;
      }
      meta[key] = parseScalar(rest);
      i++;
      continue;
    }
    i++;
  }
  return { meta, body };
}

function parseScalar(s: string): unknown {
  if (s === 'null' || s === '~' || s === '') return null;
  if (s === 'true') return true;
  if (s === 'false') return false;
  if (/^-?\d+$/.test(s)) return parseInt(s, 10);
  if (/^-?\d+\.\d+$/.test(s)) return parseFloat(s);
  // Strip surrounding quotes if present.
  if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) {
    return s.slice(1, -1);
  }
  return s;
}

function loadFixtures(dir: string): Fixture[] {
  const files = fs.readdirSync(dir).filter(
    (f) => f.endsWith('.md') && !f.startsWith('_'),
  );
  const fixtures: Fixture[] = [];
  for (const f of files) {
    const filePath = path.join(dir, f);
    const raw = fs.readFileSync(filePath, 'utf8');
    const { meta, body } = parseFrontmatter(raw);

    const expected = meta.expected as Record<string, unknown> | undefined;
    if (!expected) {
      throw new Error(`Fixture ${f} is missing 'expected' frontmatter block`);
    }

    fixtures.push({
      id: String(meta.id ?? f.replace(/\.md$/, '')),
      category: String(meta.category ?? 'unknown'),
      visitType: (meta.visitType as VisitType) ?? 'established',
      expected: {
        code: String(expected.code) as EmCode,
        mdmTier: String(expected.mdmTier) as MdmTier,
        hpiElements: Number(expected.hpiElements),
        rosSystems: Number(expected.rosSystems),
        pfshCategories: Number(expected.pfshCategories),
        examSystems: Number(expected.examSystems),
        problems: String(expected.problems) as ElementLevel,
        data: String(expected.data) as ElementLevel,
        risk: String(expected.risk) as ElementLevel,
      },
      bumpableTo: meta.bumpableTo == null ? null : String(meta.bumpableTo) as EmCode,
      notes: typeof meta.notes === 'string' ? meta.notes : undefined,
      soap: body,
      filePath,
    });
  }
  return fixtures;
}

const fixtures = loadFixtures(CORPUS_DIR);

describe('em-coding corpus', () => {
  it('loads at least 30 fixtures', () => {
    expect(fixtures.length).toBeGreaterThanOrEqual(30);
  });

  let passCount = 0;
  let failCount = 0;
  const perFixtureResults: Array<{ id: string; pass: boolean; reasons: string[] }> = [];

  it.each(fixtures.map((f) => [f.id, f]))(
    'fixture %s',
    async (_id, fxArg) => {
      const fx = fxArg as Fixture;
      const score = await computeEmScore(fx.soap, {
        visitType: fx.visitType,
        mdmCachedJudgement: null, // force deterministic fallback (no LLM in tests)
      });

      const reasons: string[] = [];

      // Counts (±1 wiggle per rubric §6).
      const inWiggle = (actual: number, expected: number, name: string) => {
        if (actual < expected - 1 || actual > expected + 1) {
          reasons.push(`${name}: actual ${actual}, expected ${expected} (±1 wiggle)`);
        }
      };
      inWiggle(score.satisfied.hpiElements, fx.expected.hpiElements, 'hpiElements');
      inWiggle(score.satisfied.rosSystems, fx.expected.rosSystems, 'rosSystems');
      inWiggle(score.satisfied.pfshCategories, fx.expected.pfshCategories, 'pfshCategories');
      inWiggle(score.satisfied.examSystems, fx.expected.examSystems, 'examSystems');

      if (score.satisfied.problems !== fx.expected.problems) {
        reasons.push(`problems: ${score.satisfied.problems}, expected ${fx.expected.problems}`);
      }
      if (score.satisfied.data !== fx.expected.data) {
        reasons.push(`data: ${score.satisfied.data}, expected ${fx.expected.data}`);
      }
      if (score.satisfied.risk !== fx.expected.risk) {
        reasons.push(`risk: ${score.satisfied.risk}, expected ${fx.expected.risk}`);
      }
      if (score.code !== fx.expected.code) {
        reasons.push(`code: ${score.code}, expected ${fx.expected.code}`);
      }
      if (score.mdmTier !== fx.expected.mdmTier) {
        reasons.push(`mdmTier: ${score.mdmTier}, expected ${fx.expected.mdmTier}`);
      }

      const pass = reasons.length === 0;
      if (pass) passCount++; else failCount++;
      perFixtureResults.push({ id: fx.id, pass, reasons });

      // Per-fixture assertions still run — failures show in the summary.
      // We don't bail the whole suite; the aggregate threshold test below
      // is what gates ship.
      if (!pass) {
        // Use a soft expectation that records the diff but doesn't bail.
        // (Vitest will still count the test as failing.)
        expect.soft(reasons, `${fx.id}: ${reasons.join(' | ')}`).toEqual([]);
      }
    },
  );

  it('aggregate ≥28/30 fixtures pass', () => {
    const total = passCount + failCount;
    // eslint-disable-next-line no-console
    console.log(`[corpus] ${passCount}/${total} fixtures passed`);
    if (failCount > 0) {
      // eslint-disable-next-line no-console
      console.log('[corpus] failures:');
      for (const r of perFixtureResults.filter((x) => !x.pass)) {
        // eslint-disable-next-line no-console
        console.log(`  - ${r.id}: ${r.reasons.join(' | ')}`);
      }
    }
    expect(passCount).toBeGreaterThanOrEqual(28);
  });
});
