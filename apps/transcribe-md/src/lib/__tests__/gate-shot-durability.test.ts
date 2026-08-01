// ============================================================================
// Gate B's screenshots have to still exist when something can look at them.
// ----------------------------------------------------------------------------
// The screenshots clause was discharged, for one commit, by files that could
// not survive the run that produced them. Two independent defects, either of
// which was sufficient:
//
//  1. THEY WERE WRITTEN INTO `test-results/`. Playwright's runner pushes
//     `createRemoveOutputDirsTask` into global setup and `fs.rm(outputDir,
//     {recursive:true, force:true})` before the first test. With no `outputDir`
//     override every project shares `test-results`, and FOUR further
//     `playwright test` invocations run after the a11y pack (review-doc,
//     doc-preview, visit-doc, phi-reject+rx-safety). The first one deleted
//     them. They survived only if the job died inside the a11y step itself —
//     i.e. only when the gate was already red.
//
//  2. THE ONLY UPLOAD OF THAT DIRECTORY WAS `if: failure()`. So on a GREEN
//     run — the only kind relay rule 2a lets the ledger cite — nothing left
//     the runner at all. The always-uploaded HTML report cannot stand in:
//     `page.screenshot({path})` writes a file and registers no `testInfo`
//     attachment, so the captures never enter `playwright-report/`.
//
// Neither is visible in a passing run. Both produce exactly the same output as
// a correct one: a green tick and an artefact list nobody reads. That is this
// project's recurring defect — an answer about a set whose boundary was never
// established — so the cure is a check that fails when the answer stops
// meaning anything.
//
// ⚠️ EVERY ASSERTION BELOW READS EXECUTABLE LINES ONLY. The spec's own comment
// explains the old path and NAMES it, so a naive grep matches the explanation
// and passes on a file that reintroduced the bug. That is A2 defect 2, and it
// has now caught three separate guards in this repo.
// ============================================================================

import { readdirSync, readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

// ⚠️ THE SOURCE SET IS DERIVED, NOT NAMED. This gate used to read exactly one
// path — `tests/e2e/scenarios/rounds-a11y.spec.ts` — because that was the only
// pack taking screenshots. C1-d moved the sink into `helpers/rounds-axe.ts` so
// a second pack could share it, and the hard-coded path reddened immediately.
// That was the gate working; pinning it back to two named paths would not have
// been. A third pack that writes shots must be covered the day it lands, not
// the day someone remembers to add it here, so the list comes from a traversal
// and the non-vacuity assertion below fails if the traversal ever returns a set
// that has lost a member.
const SCENARIO_DIR = 'tests/e2e/scenarios';
const SOURCE_PATHS = [
  'tests/e2e/helpers/rounds-axe.ts',
  ...readdirSync(SCENARIO_DIR)
    .filter((f) => /^rounds-.*\.spec\.ts$/.test(f))
    .sort()
    .map((f) => `${SCENARIO_DIR}/${f}`),
];
const SOURCES = SOURCE_PATHS.map((p) => ({ path: p, src: readFileSync(p, 'utf8') }));
const ALL_SRC = SOURCES.map((s) => s.src).join('\n');
const WORKFLOW = readFileSync('../../.github/workflows/e2e.yml', 'utf8');

/** Drop `//` line comments and `/* *\/` blocks. Deliberately crude: it only has
 *  to remove the prose that talks ABOUT the path. */
function executableOnly(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .filter((l) => !l.trim().startsWith('//') && !l.trim().startsWith('*'))
    .join('\n');
}

describe('Gate B screenshots — durable, and actually uploaded', () => {
  const code = SOURCES.map((s) => executableOnly(s.src)).join('\n');

  it('the traversal found the shot sink and every Rounds pack — non-vacuity', () => {
    // Without this, a traversal that silently returns [] makes every assertion
    // below pass by covering nothing — the defect this repo keeps re-finding.
    expect(SOURCE_PATHS).toContain('tests/e2e/helpers/rounds-axe.ts');
    expect(SOURCE_PATHS).toContain('tests/e2e/scenarios/rounds-a11y.spec.ts');
    expect(SOURCE_PATHS).toContain('tests/e2e/scenarios/rounds-c1.spec.ts');
    // Five Gate A/B packs + rounds-c1 + the helper.
    expect(SOURCE_PATHS.length).toBeGreaterThanOrEqual(7);
  });

  it('the comment-stripper works — negative control', () => {
    // If this ever stops removing prose, every assertion below silently starts
    // reading comments again and the guard reverts to the thing it replaced.
    expect(ALL_SRC).toContain('test-results/rounds-shots/'); // it IS discussed…
    expect(code).not.toContain('test-results/rounds-shots/'); // …only in prose.
  });

  it('screenshots are NOT written under any playwright outputDir', () => {
    expect(code).toContain('rounds-shots');
    // The executable path must not sit under `test-results/`, which the runner
    // deletes at the start of every subsequent invocation.
    expect(code).not.toMatch(/test-results\s*\/\s*rounds-shots/);
    expect(code).not.toMatch(/path:\s*[`'"]test-results/);
  });

  it('every pack that screenshots writes through the shared sink', () => {
    // Two packs writing to the same directory by two different literals is how
    // one of them ends up under an outputDir again. `page.screenshot({path})`
    // may appear in exactly one place: the helper's `shoot`.
    // ⚠️ THE OFFENDER SCAN AND ITS CONTROL MUST USE THE SAME REGEX. The first
    // draft scanned with `[^}]*` and controlled with `[\s\S]*?` — and `[^}]*`
    // cannot cross a `}`, so a pack writing
    // `page.screenshot({ clip: {...}, path: 'test-results/…' })` — precisely
    // the outputDir leak the sibling test forbids — was invisible to the scan
    // while the looser control still matched the helper. Two different
    // questions, one reported as the answer to the other.
    const SHOT_PATH = /\.screenshot\(\s*\{[\s\S]*?path:/;
    const offenders = SOURCES.filter(
      (s) =>
        s.path !== 'tests/e2e/helpers/rounds-axe.ts' &&
        SHOT_PATH.test(executableOnly(s.src)),
    ).map((s) => s.path);
    expect(offenders, 'these write a screenshot path directly instead of via shoot()').toEqual([]);
    // …and the sink really does exist, or the emptiness above means nothing.
    const helper = SOURCES.find((s) => s.path === 'tests/e2e/helpers/rounds-axe.ts')!;
    expect(SHOT_PATH.test(executableOnly(helper.src))).toBe(true);
    // The matcher can see the multi-property form too — the shape that was
    // slipping through.
    expect(SHOT_PATH.test("page.screenshot({ clip: { x: 0 }, path: 'x.png' })")).toBe(true);
  });

  it('no project overrides outputDir to point back at the shot directory', () => {
    // The other way to reintroduce defect 1: leave the path alone and move the
    // outputDir onto it.
    const config = executableOnly(readFileSync('playwright.config.ts', 'utf8'));
    expect(config).not.toMatch(/outputDir\s*:\s*[`'"][^`'"]*rounds-shots/);
  });

  it('CI uploads the shots on a GREEN run, not only on failure', () => {
    // ⚠️ `filter`, not `find`. The original took the FIRST matching step, so a
    // second rounds-shots upload added later would never have been checked —
    // and the one that IS checked might not be the one that runs.
    const steps = WORKFLOW.split(/\n(?=      - name: )/).filter((s) =>
      /path:\s*apps\/transcribe-md\/rounds-shots/.test(s),
    );
    expect(steps.length, 'expected exactly one rounds-shots upload step').toBe(1);
    for (const step of steps) {
      expect(step).toMatch(/if:\s*always\(\)/);
      expect(step).not.toMatch(/if:\s*failure\(\)/);
      // An empty upload is the same as no upload, and it would read as success.
      expect(step).toMatch(/if-no-files-found:\s*error/);
    }
  });

  it('every Rounds pack runs BEFORE the upload step — nothing no unit can see', () => {
    // The ordering constraint the helper's header names, made executable. One
    // upload serves every pack, and it runs immediately after the last of them.
    // A pack added AFTER it writes shots nothing collects, and
    // `if-no-files-found: error` cannot catch that: the directory is non-empty
    // from the earlier packs, so the upload succeeds and the new pack's
    // evidence is silently absent. That is a green tick over missing evidence,
    // which is the exact defect this file exists for.
    const uploadAt = WORKFLOW.indexOf('path: apps/transcribe-md/rounds-shots');
    expect(uploadAt, 'rounds-shots upload step not found').toBeGreaterThan(-1);

    const packRuns = [...WORKFLOW.matchAll(/--project=(rounds-[\w-]+)/g)];
    // Non-vacuity: if this regex ever stops matching, "all packs precede the
    // upload" is trivially true of an empty set.
    expect(packRuns.length, 'no --project=rounds-* runs found in the workflow').toBeGreaterThanOrEqual(6);

    const late = packRuns.filter((m) => m.index! > uploadAt).map((m) => m[1]);
    expect(late, 'these Rounds packs run after the screenshot upload').toEqual([]);
  });

  it('the workflow matcher is capable of finding a failure()-gated upload — positive control', () => {
    // Proves the split-and-find form above can see step attributes at all. The
    // traces upload IS `if: failure()`; if this stops finding it, the negative
    // result in the previous test means nothing.
    const traces = WORKFLOW.split(/\n(?=      - name: )/).find((s) =>
      /path:\s*apps\/transcribe-md\/test-results/.test(s),
    );
    expect(traces, 'positive control: the traces upload step was not found').toBeDefined();
    expect(traces).toMatch(/if:\s*failure\(\)/);
  });

  it('the shot directory is gitignored — a rendered note is never committed', () => {
    const ignore = readFileSync('../../.gitignore', 'utf8');
    const lines = ignore
      .split('\n')
      .map((l) => l.trim())
      .filter((l) => l.length > 0 && !l.startsWith('#'));
    expect(lines).toContain('rounds-shots/');
  });
});
