// @vitest-environment node
// ============================================================================
// Every mocked-vendor test prevents the REAL metering write. The list is a scan.
// ----------------------------------------------------------------------------
// ⚠️ WHAT THIS KILLS, AND WHY A HAND-KEPT LIST WOULD NOT.
//
// Since B0 the mock substitutes only the VENDOR CALL, so under MOCK_AI_CALLS
// everything below it runs for real — including `logApiUsage`, which defers
// `apiUsageEvent.create` via `setImmediate` (api-usage.ts:172) and, on failure,
// emits `console.warn` (:204) from a callback NOTHING AWAITS.
//
// The `unit` CI job leaves DATABASE_URL unset ON PURPOSE, so the db-guard tests
// can assert the fail-closed path. That makes the write unable to succeed, so
// the warn always fires — and when it lands after its test file has finished,
// vitest's worker RPC is already closing and the pending `onUserConsoleLog`
// rejects:
//
//     EnvironmentTeardownError: Closing rpc while "onUserConsoleLog" was pending
//
// That is an unhandled error, so the run EXITS 1 WITH EVERY TEST GREEN — the
// worst shape a CI failure can take, because the summary says 3288 passed and
// the cause is nowhere near the tests.
//
// Observed on run 31351013424 attempt 1 (head 6247aa33): five such warns after
// two different test files, two of which lost the race and produced the two
// unhandled rejections. The tree was byte-identical to a green run, which is
// what proves it is a race and not a code defect.
//
// ⚠️ THE FIX BELONGS HERE RATHER THAN IN A COMMENT ON EACH FILE. Two files were
// exposed when this was written, and the pair goes stale the moment a third
// `*.mock.test.ts` is added — AGENTS.md: "a per-caller list is kept complete by
// hand, and hand-kept lists are wrong eventually". So this SCANS the same
// universe vitest runs, and a new exposed file fails the gate instead of
// reddening CI at random weeks later.
//
// ⚠️ AND HERE IS EXACTLY WHAT THIS GATE DOES **NOT** COVER. Say it plainly,
// because the first version of this file implied completeness it did not have.
// Arm 1's universe is "test files that set MOCK_AI_CALLS". That is a PROXY, not
// the predicate. The predicate is "can reach logApiUsage", and a file can do
// that without ever naming the flag: `email-no-phi.test.ts` reaches the meter
// through `../email` and emitted TEN real metering writes per CI run while this
// gate reported 0 EXPOSED — truthfully, over a universe that did not contain
// them. That is the "right quantity, wrong universe" defect this repo has
// written down, occurring inside the gate written to prevent its sibling.
//
// Import-reachability was tried as a replacement universe and REJECTED: it
// reports 45 exposed files where the measured number is 1, because importing
// `@meddoc/ai` pulls in `whisper-batch.ts` whether or not the test ever calls
// it. A gate with 44 false positives is not kept.
//
// So arm 5 attacks the ACTUAL bug instead, exactly and with no false positives:
// **a `vi.mock()` whose specifier resolves to no module at all.** That is what
// `email-no-phi.test.ts` had — `vi.mock('../api-usage')` where no such file
// exists, because the real module is `@meddoc/ai`. Vitest does not warn about
// it. Across 268 test files and 197 file-resolvable specifiers there was
// exactly ONE, and it was the one causing the flake.
//
// ⚠️ IT ALSO ASSERTS AN INVARIANT THE WORKFLOW ALREADY CLAIMED.
// `.github/workflows/test.yml` states the suite "mocks @meddoc/db + @meddoc/ai
// and runs fully on a bare runner". Nothing asserted that, and two files
// violated it. A stated invariant with no check is a wish.
// ============================================================================

import { readdirSync, readFileSync, existsSync } from 'node:fs';
import { join, relative, sep, dirname, resolve } from 'node:path';

import { describe, it, expect } from 'vitest';

/** Executable source only — prose must never satisfy a code assertion. */
const strip = (s: string) =>
  s
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .filter((l) => !l.trim().startsWith('//'))
    .join('\n');

/** Walk up until we find the workspace root; never assume cwd. */
function repoRoot(): string {
  let d = process.cwd();
  for (let i = 0; i < 8; i++) {
    if (existsSync(join(d, 'apps', 'transcribe-md')) && existsSync(join(d, 'packages'))) return d;
    d = join(d, '..');
  }
  throw new Error('could not locate the workspace root from ' + process.cwd());
}

const ROOT = repoRoot();
const SKIP = ['node_modules', '.next', 'dist'];
const isTest = (f: string) => /\.(test|spec)\.[cm]?[jt]sx?$/.test(f);

function walk(dir: string, out: string[] = []): string[] {
  if (!existsSync(dir)) return out;
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    if (SKIP.includes(e.name)) continue;
    const p = join(dir, e.name);
    if (e.isDirectory()) walk(p, out);
    // vitest.config.ts excludes **/tests/e2e/** — mirror it exactly.
    else if (isTest(e.name) && !p.includes(join('tests', 'e2e'))) out.push(p);
  }
  return out;
}

/** The same universe vitest.config.ts includes: the app, plus packages/-*-/src. */
function suiteFiles(): string[] {
  const files = walk(join(ROOT, 'apps', 'transcribe-md'));
  for (const pkg of readdirSync(join(ROOT, 'packages'), { withFileTypes: true })) {
    if (pkg.isDirectory()) files.push(...walk(join(ROOT, 'packages', pkg.name, 'src')));
  }
  return files.map((f) => relative(ROOT, f).split(sep).join('/')).sort();
}

// Needles are EXACT executable tokens, never bare words. `vi.mock` alone would
// match the prose "which vi.mocks modelClient" that sits in one of these very
// files — the substring trap, fourth sighting, and it fired on this fix's own
// build script before this line existed.
const N_FLAG = 'MOCK_AI_CALLS';
const N_DB = "vi.mock('@meddoc/db'";
const N_AI = "vi.mock('@meddoc/ai'";
const RE_USAGE = /vi\.mock\('(\.\.\/)*api-usage'/;

/**
 * Files that reach `MOCK_AI_CALLS` but genuinely cannot reach the metering
 * write. Each carries the reason it is safe — an exemption without one is
 * indistinguishable from an oversight. Verified individually, not assumed.
 */
const EXEMPT: Record<string, string> = {
  'apps/transcribe-md/src/lib/em-coding/__tests__/gate-mock-ai-honored.test.ts':
    'a static source-grep gate: it readFileSync-s sources and asserts on their text, and never invokes the pipeline.',
  // ⚠️ REMOVED BY B4, AND THE REMOVAL IS THE POINT.
  //
  //   'apps/transcribe-md/tests/worker/embed-mock.test.ts':
  //     'embed.ts:72 returns mockEmbed() under mock, ABOVE the logApiUsage
  //      calls at :123/:162 — the meter is never reached.'
  //
  // That sentence was TRUE when written and became FALSE the moment B4 moved
  // embed.ts's mock boundary below the meter. The file now stubs `@meddoc/db`
  // and classifies as `mocks-db` on its own merits.
  //
  // ⚠️ NOTHING HERE COULD HAVE CAUGHT THAT. The stale-exemption arm below
  // verifies an exempted file still EXISTS and still names the flag — both of
  // which stayed true. It cannot check whether the REASON is still true,
  // because the reason is prose. An exemption's justification is exactly the
  // kind of claim that decays silently, so it is re-read by hand whenever the
  // code it describes is touched — the same discipline the watched-set rule
  // asks for, applied to an exclusion list instead of a model list.
  // NOT exempted, deliberately: packages/ai/src/__tests__/mock-chat-edit.test.ts
  // names MOCK_AI_CALLS only in a COMMENT, so stripped source puts it out of
  // scope entirely and an exemption for it would be permanently stale. That is
  // the substring trap running the other way, and the stale-exemption arm below
  // is what caught it before this gate ever shipped.
  'packages/ai/src/__tests__/gate-mock-suite-stubs-the-db.test.ts':
    'this gate itself: a static scanner over the suite, executing no pipeline.',
};

type Bucket = 'exempt' | 'mocks-db' | 'mocks-ai' | 'mocks-api-usage' | 'EXPOSED';

/** EXEMPT is checked FIRST so the buckets stay disjoint and the total holds. */
function classify(rel: string, code: string): Bucket {
  if (rel in EXEMPT) return 'exempt';
  if (code.includes(N_DB)) return 'mocks-db';
  if (code.includes(N_AI)) return 'mocks-ai';
  if (RE_USAGE.test(code)) return 'mocks-api-usage';
  return 'EXPOSED';
}

describe('every mocked-vendor test prevents the real metering write', () => {
  const inScope = suiteFiles()
    .map((rel) => ({ rel, code: strip(readFileSync(join(ROOT, rel), 'utf8')) }))
    .filter((f) => f.code.includes(N_FLAG));

  it('NON-VACUITY — the scan found the suite, and found a known member of it', () => {
    // A traversal that silently covers nothing returns zero for every needle you
    // try, and a clean sweep and a broken sweep are the same output.
    expect(suiteFiles().length, 'the walk found no test files at all').toBeGreaterThan(100);
    expect(inScope.length, 'no file sets MOCK_AI_CALLS — the needle or the walk is broken')
      .toBeGreaterThan(0);
    expect(
      inScope.map((f) => f.rel),
      'the known B0 boundary gate is missing — the scan is not covering packages/',
    ).toContain('packages/ai/src/__tests__/gate-b0-mock-boundary.test.ts');
  });

  it('THE BUCKETS RECONCILE — every in-scope file lands in exactly one', () => {
    const b = inScope.map((f) => classify(f.rel, f.code));
    const count = (k: Bucket) => b.filter((x) => x === k).length;
    const total =
      count('exempt') + count('mocks-db') + count('mocks-ai') + count('mocks-api-usage') + count('EXPOSED');
    // Anything that does not fit a named bucket IS the finding.
    expect(total, `bucket total ${total} != ${inScope.length} in-scope files`).toBe(inScope.length);
  });

  it('NO FILE IS EXPOSED — the metering write cannot outlive any test file', () => {
    const exposed = inScope.filter((f) => classify(f.rel, f.code) === 'EXPOSED').map((f) => f.rel);
    expect(
      exposed,
      'these set MOCK_AI_CALLS and stub nothing, so logApiUsage will attempt a real\n' +
        'write and console.warn from a setImmediate callback after the file finishes.\n' +
        "Add vi.mock('@meddoc/db', …) as in gate-b0-mock-boundary.test.ts:39-55, or add\n" +
        'an EXEMPT entry stating why the meter is unreachable:\n  ' +
        exposed.join('\n  '),
    ).toEqual([]);
  });

  it('NO STALE EXEMPTION — every exempted file still exists and is still in scope', () => {
    // An exemption that outlives its file is a hole nobody can see.
    for (const rel of Object.keys(EXEMPT)) {
      expect(existsSync(join(ROOT, rel)), `EXEMPT names a file that no longer exists: ${rel}`).toBe(true);
      expect(
        inScope.map((f) => f.rel),
        `EXEMPT names ${rel}, which no longer sets ${N_FLAG} — drop the exemption`,
      ).toContain(rel);
    }
  });

  it('POSITIVE CONTROL — the classifier fires on a file that stubs nothing', () => {
    // Mutating toward FAILURE: an exposed shape must be detected.
    const exposedShape = `
      process.env.${N_FLAG} = 'true';
      const r = await parseNoteToTemplate(NOTE, ctx);
    `;
    expect(classify('some/new.mock.test.ts', exposedShape)).toBe('EXPOSED');

    // Mutating toward SUCCESS: the fix must actually move it out of EXPOSED,
    // otherwise the gate is a decoration that can never go green by being fixed.
    expect(classify('some/new.mock.test.ts', `${N_DB}, () => ({}));${exposedShape}`)).toBe('mocks-db');

    // And prose must NOT satisfy it — the substring trap this repo has met four times.
    const proseOnly = `
      // Unlike parse-note-to-template.test.ts (which vi.mocks modelClient), this
      // file uses the REAL modelClient and flips ${N_FLAG}=true.
      process.env.${N_FLAG} = 'true';
    `;
    expect(classify('some/prose.mock.test.ts', strip(proseOnly))).toBe('EXPOSED');
  });
  // ── ARM 5 ── EVERY MOCK ACTUALLY MOCKS SOMETHING ─────────────────────────
  it('NO DEAD vi.mock — every file-resolvable specifier resolves to a module', () => {
    // A vi.mock naming a module that does not exist is a silent no-op: vitest
    // raises nothing, the test passes, and the code it meant to neutralise runs
    // for real. Only specifiers that SHOULD resolve to a file are checked —
    // relative paths and the @meddoc/* workspace aliases. A bare package name
    // ('resend', 'next/navigation') legitimately resolves in node_modules and
    // is out of scope here.
    const dead: string[] = [];
    let checked = 0;
    for (const rel of suiteFiles()) {
      const code = strip(readFileSync(join(ROOT, rel), 'utf8'));
      for (const m of code.matchAll(/vi\.mock\(\s*['"]([^'"]+)['"]/g)) {
        const spec = m[1];
        let base: string | null = null;
        if (spec.startsWith('.')) base = resolve(dirname(join(ROOT, rel)), spec);
        else if (spec.startsWith('@meddoc/')) {
          const [, pkg, ...rest] = spec.split('/');
          base = join(ROOT, 'packages', pkg, 'src', ...rest);
        } else if (spec.startsWith('@/')) {
          // vitest.config.ts aliases '@' -> apps/transcribe-md/src. Omitting it
          // dropped ~90 of the 197 file-resolvable specifiers from this arm —
          // a universe narrower than the one it claimed to cover, which is the
          // very defect the header above is about. Caught by reconciling the
          // count against an independent scan, not by reading the code.
          base = join(ROOT, 'apps', 'transcribe-md', 'src', spec.slice(2));
        }
        if (base === null) continue; // a real npm package — not our business
        checked++;
        const found = [base, `${base}.ts`, `${base}.tsx`, join(base, 'index.ts')].some(existsSync);
        if (!found) dead.push(`${rel}  ->  vi.mock('${spec}')`);
      }
    }
    // Non-vacuity: if the matcher found no specifiers at all, its zero is empty.
    expect(checked, 'no file-resolvable vi.mock specifiers found — the matcher is broken')
      .toBeGreaterThan(150);
    expect(
      dead,
      'these vi.mock() calls name a module that does not exist, so they mock NOTHING\n' +
        'and the real implementation runs. Point them at the module the code under\n' +
        'test actually imports:\n  ' + dead.join('\n  '),
    ).toEqual([]);
  });

  it('POSITIVE CONTROL — the dead-mock matcher fires on a known-bad specifier', () => {
    // Mutate toward failure: the exact shape email-no-phi.test.ts carried.
    const base = join(ROOT, 'apps/transcribe-md/src/lib/__tests__', '../api-usage');
    const found = [base, `${base}.ts`, `${base}.tsx`, join(base, 'index.ts')].some(existsSync);
    expect(found, "'../api-usage' must NOT resolve — if it ever does, this control is dead").toBe(false);
    // Mutate toward success: the specifier that replaced it does resolve.
    const good = join(ROOT, 'packages', 'ai', 'src', 'api-usage');
    expect([good, `${good}.ts`].some(existsSync)).toBe(true);
  });
});
