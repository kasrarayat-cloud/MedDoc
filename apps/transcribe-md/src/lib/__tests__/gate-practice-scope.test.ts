// ============================================================================
// T5 — the guard that keeps the practice-scoped accessor the ONLY way in.
// ----------------------------------------------------------------------------
// ⚠️ THIS IS A RATCHET, NOT A WALL, AND THAT IS DELIBERATE.
// There are 82 request-context clinical reads that predate the accessor. A guard
// that demanded zero on day one would be red for the whole migration, and a
// permanently-red gate is a gate everyone learns to ignore — which is worse than
// no gate, because it looks like coverage.
//
// So it pins the CURRENT number and forbids it from growing. New code cannot add
// an unscoped clinical read; adoption lowers the ceiling commit by commit. The
// number only ever goes down, and the day it reaches zero this becomes a wall
// with no further work.
//
// ⚠️ WHY THE GUARD LANDS BEFORE THE ADOPTION. If 82 call sites were migrated
// first and the guard added last, the guard's first run would be a bug report
// against work already declared done — and every site missed would be found one
// CI cycle at a time. That is the exact failure T3 and T4 paid five cycles for.
// Landing the guard first makes every unmigrated site fail LOUDLY from the first
// commit.
//
// ⚠️ TWO CLASSES OF READ, DISTINGUISHED EXPLICITLY.
//   REQUEST — a signed-in user asking. Must be practice-scoped. Counted here.
//   SYSTEM  — the worker on a queued job, a retention sweep. No acting user, so
//             no practice to scope BY; forcing one would mean INVENTING a
//             tenant, which is worse than an honest unscoped read.
// System paths are listed by name below. The list is short, and anything not on
// it counts as a request read — the safe default, because a forgotten request
// read is a cross-tenant leak while a mislabelled system read is only noise.
// ============================================================================

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { describe, it, expect } from 'vitest';

/** Prisma models holding clinical data. */
const CLINICAL_MODELS = ['transcribeVisit', 'transcribeMdPatient', 'noteTemplate'] as const;

const READ_METHODS =
  '(findMany|findFirst|findUnique|findUniqueOrThrow|count|aggregate|groupBy)';

/**
 * Paths that run WITHOUT an acting user. Listed by name, deliberately:
 * a prefix like `src/lib/` would quietly absorb request code as the tree grows.
 */
const SYSTEM_PATHS = ['src/worker/', 'src/lib/template-twin/', 'src/worker.ts'] as const;

/**
 * ⚠️ THE SYSTEM-CONTEXT ALLOWLIST, CHECKED IN BY FILE AND COUNT.
 *
 * A path prefix alone would let the system side grow silently: drop a new file
 * under `src/worker/`, do an unscoped clinical read, and the guard would wave it
 * through as "system". That is drift with a permission slip.
 *
 * So growth HERE is a declared decision too. Adding a system read means adding
 * its line below, which puts it in a diff where someone can ask whether it is
 * genuinely user-less. Measured 2026-08-06.
 */
const SYSTEM_ALLOWLIST: Record<string, number> = {
  'src/lib/template-twin/create-draft.ts': 1,
  'src/lib/template-twin/fill-engine.ts': 1,
  'src/lib/template-twin/native-export.ts': 1,
  'src/lib/template-twin/synthetic-test.ts': 1,
  'src/lib/template-twin/workspace-read.ts': 1,
  'src/worker.ts': 5,
  'src/worker/cleanup/minio-orphans.ts': 1,
  'src/worker/cleanup/retention-sweep.ts': 1,
  'src/worker/cleanup/stale-visits.ts': 2,
  'src/worker/cleanup/stuck-visit-watchdog.ts': 1,
  'src/worker/note-templates/resolve-active-template.ts': 1,
  'src/worker/resume-state.ts': 1,
  'src/worker/template-twin-note-generator.ts': 1,
};

/**
 * ⚠️ THE RATCHET. Lower this as sites migrate; never raise it.
 *
 * Raising it is always the wrong fix: if this test fails because the number went
 * UP, a new clinical read was added without practice scoping, and the fix is to
 * scope it — not to move the line. Measured 2026-08-06.
 */
const MAX_UNSCOPED_REQUEST_READS = 82;

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    if (statSync(p).isDirectory()) {
      if (entry === '__tests__' || entry === 'node_modules') continue;
      out.push(...walk(p));
    } else if (p.endsWith('.ts') || p.endsWith('.tsx')) {
      out.push(p);
    }
  }
  return out;
}

const isSystem = (p: string) => SYSTEM_PATHS.some((s) => p.startsWith(s));

function clinicalReads(): { request: string[]; system: string[] } {
  const re = new RegExp(`prisma\\.(${CLINICAL_MODELS.join('|')})\\.${READ_METHODS}\\(`, 'g');
  const request: string[] = [];
  const system: string[] = [];
  for (const file of walk('src')) {
    const src = readFileSync(file, 'utf8');
    for (const m of src.matchAll(re)) {
      const line = src.slice(0, m.index).split('\n').length;
      (isSystem(file) ? system : request).push(`${file}:${line}`);
    }
  }
  return { request, system };
}

describe('T5 — clinical reads go through the practice-scoped accessor', () => {
  it('NON-VACUITY — the scanner finds reads at all', () => {
    // Without this, a broken regex or a moved source root makes every assertion
    // below trivially true and the gate reports green about nothing. This has
    // happened to a sweep in this repo twice: once returning 0 sites from shell
    // escaping, once flagging 3 false positives from a too-narrow window.
    const { request, system } = clinicalReads();
    expect(request.length + system.length, 'the scanner found NO clinical reads').toBeGreaterThan(
      50,
    );
    expect(system.length, 'no system-context reads found — the worker paths moved').toBeGreaterThan(
      0,
    );
  });

  it('⚠️ THE RATCHET — unscoped request-context reads never increase', () => {
    const { request } = clinicalReads();
    expect(
      request.length,
      `Unscoped request-context clinical reads went UP (${request.length} > ` +
        `${MAX_UNSCOPED_REQUEST_READS}). A new clinical read was added without ` +
        `practice scoping. Scope it through src/lib/practice-scope.ts — do NOT ` +
        `raise this number.`,
    ).toBeLessThanOrEqual(MAX_UNSCOPED_REQUEST_READS);
  });

  it('the accessor exists and returns a PREDICATE, not a wrapped query', () => {
    const src = readFileSync('src/lib/practice-scope.ts', 'utf8');
    for (const fn of ['visitScope', 'patientScope', 'templateScope', 'visitByIdScope']) {
      expect(src, `practice-scope.ts lost ${fn}`).toContain(`export function ${fn}`);
    }
    // ⚠️ It must scope visits on the COLUMN, not through the author's practice.
    // `{ user: { practiceId } }` answers a different question — whose practice
    // the AUTHOR belongs to — and gives the wrong answer for a locum's note.
    expect(src).toMatch(/export function visitScope[\s\S]{0,200}return \{ practiceId \}/);
    expect(src, 'visitScope routes through the author — that is the wrong tenant').not.toMatch(
      /export function visitScope[\s\S]{0,200}user: \{ practiceId \}/,
    );
  });

  it('the SYSTEM-context allowlist matches reality, file by file', () => {
    // ⚠️ BOTH DIRECTIONS. An UNLISTED system read is undeclared growth wearing a
    // path prefix; a listed file whose count DROPPED means a read moved and the
    // allowlist is now stale, which is how an allowlist becomes a rubber stamp.
    const { system } = clinicalReads();
    const actual: Record<string, number> = {};
    for (const s of system) {
      const file = s.slice(0, s.lastIndexOf(':'));
      actual[file] = (actual[file] ?? 0) + 1;
    }
    expect(actual, 'the system-context read map changed — update SYSTEM_ALLOWLIST deliberately').toEqual(
      SYSTEM_ALLOWLIST,
    );
  });

  it('POSITIVE CONTROL — the scanner would SEE a new unscoped read', () => {
    // Proves the ratchet can actually fire. Without this, a regex that matches
    // nothing keeps the count at 0 forever and the gate passes through any
    // amount of new unscoped access.
    const fixture = `const v = await prisma.transcribeVisit.findMany({ where: {} });`;
    const re = new RegExp(`prisma\\.(${CLINICAL_MODELS.join('|')})\\.${READ_METHODS}\\(`, 'g');
    expect(
      [...fixture.matchAll(re)].length,
      'the scanner does not match a plainly unscoped clinical read',
    ).toBe(1);
  });
});
