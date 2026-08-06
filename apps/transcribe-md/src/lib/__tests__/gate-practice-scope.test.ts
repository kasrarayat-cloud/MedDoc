// ============================================================================
// T5 — the guard that keeps the practice-scoped accessor the ONLY way in.
// ----------------------------------------------------------------------------
// ⚠️ THIS IS A RATCHET, NOT A WALL, AND THAT IS DELIBERATE.
// There are 81 request-context clinical reads that predate the accessor. A guard
// that demanded zero on day one would be red for the whole migration, and a
// permanently-red gate is a gate everyone learns to ignore — which is worse than
// no gate, because it looks like coverage.
//
// So it pins the CURRENT number and forbids it from growing. New code cannot add
// an unscoped clinical read; adoption lowers the ceiling commit by commit. The
// number only ever goes down, and the day it reaches zero this becomes a wall
// with no further work.
//
// ⚠️ WHY THE GUARD LANDS BEFORE THE ADOPTION. If 81 call sites were migrated
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
const MAX_UNSCOPED_REQUEST_READS = 81;

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

/**
 * ⚠️ MATCHES THAT LIVE IN COMMENTS, DECLARED BY FILE AND COUNT.
 *
 * A commented-out read is not a read, and the scanner has to know that — but a
 * scanner that silently reclassifies things is worse than one that miscounts,
 * because the dangerous direction is invisible: if `stripComments` ever mistakes
 * real CODE for a comment, a genuine unscoped read disappears from the count and
 * the gate reports green about a leak.
 *
 * So every comment-resident match is declared here and checked with `toEqual`.
 * A new one fails until someone writes it down; a misclassification of real code
 * fails the same way. Measured 2026-08-06.
 */
const COMMENT_MATCHES: Record<string, number> = {
  // The accessor's own usage example, which shows the shape it replaces.
  'src/lib/practice-scope.ts': 1,
};

/**
 * Blanks comments, preserving length and newlines so offsets and line numbers
 * still map to the original source.
 *
 * ⚠️ WHY THIS EXISTS AT ALL. The first version of this guard matched raw source,
 * so the usage example inside `practice-scope.ts`'s own doc comment counted as an
 * unscoped read. That is one unit of free headroom — a real unscoped read could
 * be added and stay under the ceiling — and, worse, it put a floor of 1 under a
 * ratchet whose whole purpose is to reach 0 and become a wall.
 *
 * String states are tracked so a `//` inside a URL literal is not read as the
 * start of a comment.
 */
function stripComments(src: string): string {
  const out = src.split('');
  type Mode = 'code' | 'line' | 'block' | 'sq' | 'dq' | 'tpl';
  let mode: Mode = 'code';
  let i = 0;
  while (i < src.length) {
    const c = src[i];
    const d = src[i + 1];
    if (mode === 'code') {
      if (c === '/' && d === '/') {
        mode = 'line';
        out[i] = ' ';
        out[i + 1] = ' ';
        i += 2;
        continue;
      }
      if (c === '/' && d === '*') {
        mode = 'block';
        out[i] = ' ';
        out[i + 1] = ' ';
        i += 2;
        continue;
      }
      if (c === "'") mode = 'sq';
      else if (c === '"') mode = 'dq';
      else if (c === '`') mode = 'tpl';
      i += 1;
      continue;
    }
    if (mode === 'line') {
      if (c === '\n') mode = 'code';
      else out[i] = ' ';
      i += 1;
      continue;
    }
    if (mode === 'block') {
      if (c === '*' && d === '/') {
        mode = 'code';
        out[i] = ' ';
        out[i + 1] = ' ';
        i += 2;
        continue;
      }
      if (c !== '\n') out[i] = ' ';
      i += 1;
      continue;
    }
    // Inside a string literal.
    if (c === '\\') {
      i += 2;
      continue;
    }
    if ((mode === 'sq' && c === "'") || (mode === 'dq' && c === '"') || (mode === 'tpl' && c === '`'))
      mode = 'code';
    i += 1;
  }
  return out.join('');
}

function clinicalReads(): { request: string[]; system: string[]; commented: string[] } {
  const re = new RegExp(`prisma\\.(${CLINICAL_MODELS.join('|')})\\.${READ_METHODS}\\(`, 'g');
  const request: string[] = [];
  const system: string[] = [];
  const commented: string[] = [];
  for (const file of walk('src')) {
    const src = readFileSync(file, 'utf8');
    const code = stripComments(src);
    for (const m of src.matchAll(re)) {
      const line = src.slice(0, m.index).split('\n').length;
      const at = `${file}:${line}`;
      // The match survives in the blanked copy only if it was real code.
      if (code.slice(m.index, m.index! + m[0].length) !== m[0]) commented.push(at);
      else (isSystem(file) ? system : request).push(at);
    }
  }
  return { request, system, commented };
}

function byFile(hits: string[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const h of hits) {
    const file = h.slice(0, h.lastIndexOf(':'));
    out[file] = (out[file] ?? 0) + 1;
  }
  return out;
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
    expect(
      byFile(system),
      'the system-context read map changed — update SYSTEM_ALLOWLIST deliberately',
    ).toEqual(SYSTEM_ALLOWLIST);
  });

  it('matches living in COMMENTS are declared, not silently dropped', () => {
    // The reclassification this guards is the invisible-failure direction: if
    // stripComments ever mistakes real code for a comment, a genuine unscoped
    // read vanishes from the ratchet and the gate goes green over a leak.
    const { commented } = clinicalReads();
    expect(
      byFile(commented),
      'a clinical read was classified as living in a comment without being declared',
    ).toEqual(COMMENT_MATCHES);
  });

  it('POSITIVE CONTROL — the scanner SEES a new unscoped read', () => {
    // Proves the ratchet can actually fire. Without this, a regex that matches
    // nothing keeps the count at 0 forever and the gate passes through any
    // amount of new unscoped access.
    const re = new RegExp(`prisma\\.(${CLINICAL_MODELS.join('|')})\\.${READ_METHODS}\\(`, 'g');
    const code = `const v = await prisma.transcribeVisit.findMany({ where: {} });`;
    expect(
      [...stripComments(code).matchAll(re)].length,
      'the scanner does not match a plainly unscoped clinical read',
    ).toBe(1);
  });

  it('NEGATIVE CONTROL — a COMMENTED read is not counted, but a URL string is not a comment', () => {
    const re = new RegExp(`prisma\\.(${CLINICAL_MODELS.join('|')})\\.${READ_METHODS}\\(`, 'g');

    const commented = `// const v = await prisma.transcribeVisit.findMany({ where: {} });\n`;
    expect(
      [...stripComments(commented).matchAll(re)].length,
      'a commented-out read still counts — the ratchet can never reach zero',
    ).toBe(0);

    const block = `/**\n * const v = await prisma.transcribeVisit.findMany({});\n */\n`;
    expect([...stripComments(block).matchAll(re)].length, 'a doc-comment read still counts').toBe(0);

    // ⚠️ And the stripper must not be over-eager: `//` inside a string is not a
    // comment, and an over-eager stripper hides real reads — the direction that
    // fails silently.
    const url = `const u = 'https://x/y'; await prisma.transcribeVisit.findMany({});`;
    expect(
      [...stripComments(url).matchAll(re)].length,
      'a read after a URL literal was swallowed — the stripper treats // in a string as a comment',
    ).toBe(1);
  });
});
