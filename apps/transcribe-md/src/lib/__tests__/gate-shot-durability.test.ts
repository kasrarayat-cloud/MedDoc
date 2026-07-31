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

import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

const SPEC_PATH = 'tests/e2e/scenarios/rounds-a11y.spec.ts';
const SPEC = readFileSync(SPEC_PATH, 'utf8');
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
  const code = executableOnly(SPEC);

  it('the comment-stripper works — negative control', () => {
    // If this ever stops removing prose, every assertion below silently starts
    // reading comments again and the guard reverts to the thing it replaced.
    expect(SPEC).toContain('test-results/rounds-shots/'); // it IS discussed…
    expect(code).not.toContain('test-results/rounds-shots/'); // …only in prose.
  });

  it('screenshots are NOT written under any playwright outputDir', () => {
    expect(code).toContain('rounds-shots');
    // The executable path must not sit under `test-results/`, which the runner
    // deletes at the start of every subsequent invocation.
    expect(code).not.toMatch(/test-results\s*\/\s*rounds-shots/);
    expect(code).not.toMatch(/path:\s*[`'"]test-results/);
  });

  it('no project overrides outputDir to point back at the shot directory', () => {
    // The other way to reintroduce defect 1: leave the path alone and move the
    // outputDir onto it.
    const config = executableOnly(readFileSync('playwright.config.ts', 'utf8'));
    expect(config).not.toMatch(/outputDir\s*:\s*[`'"][^`'"]*rounds-shots/);
  });

  it('CI uploads the shots on a GREEN run, not only on failure', () => {
    const step = WORKFLOW.split(/\n(?=      - name: )/).find((s) =>
      /path:\s*apps\/transcribe-md\/rounds-shots/.test(s),
    );
    expect(step, 'no upload step whose path is the rounds-shots directory').toBeDefined();
    expect(step).toMatch(/if:\s*always\(\)/);
    expect(step).not.toMatch(/if:\s*failure\(\)/);
    // An empty upload is the same as no upload, and it would read as success.
    expect(step).toMatch(/if-no-files-found:\s*error/);
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
