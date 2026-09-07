/**
 * GATE — THE LENS SANDBOX IS ARMED, AND THE ARMING IS DRIVEN, NOT DESCRIBED.
 *
 * ⚠️ THIS IS PRECAUTIONARY, AND THE FILING BESIDE IT SAYS SO HONESTLY.
 * It was built on 2026-09-06 after writes appeared in a worktree during a
 * five-lens pass that had been told, in its prompt, not to write. I attributed
 * them to the lens agents. **I was wrong — twice.** The author turned out to be
 * a PEER SESSION building the same item in the same worktree, and it said so
 * directly. See `docs/foundation/board/A-WRITE-I-COULD-NOT-ATTRIBUTE.md`.
 *
 * The guard is kept anyway, on its own merits: a refutation lens has no reason
 * to write, subagents inherit the session's permission mode, and "the prompt
 * said not to" is not a mechanism. But this file must NOT be read as evidence
 * that pass agents write out — no such evidence exists.
 *
 * ⚠️ THIS GATE DRIVES `scripts/arm-lens-sandbox.sh` RATHER THAN RE-IMPLEMENTING
 * IT, for the same reason `gate-agents-md-size` drives its script: a second copy
 * of the check drifts from the first the day either is fixed, and the copy that
 * drifts is always the one nobody runs by hand.
 *
 * WHAT WOULD MAKE THIS FILE FAIL:
 *   · a guard is dropped from `make-lens-sandbox.sh`   -> ARM 1 / ARM 2
 *   · the sandbox's config leaks into the SHARED repo  -> ARM 5
 *   · `gh` becomes reachable from a lens environment   -> ARM 3 / ARM 4
 *   · the arming script stops naming WHICH guard fired -> ARM 2's own text
 */
import { describe, expect, it } from 'vitest';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const ROOT = resolve(__dirname, '../../../../..');
const ARM = resolve(ROOT, 'scripts/arm-lens-sandbox.sh');
const MAKE = resolve(ROOT, 'scripts/make-lens-sandbox.sh');

/**
 * ⚠️ ONE BUDGET, USED TWICE, BECAUSE TWO OF THEM DISAGREED BY 24× AND THE
 * SMALLER ONE WAS INVISIBLE.
 *
 * This arm handed `execFileSync` a `timeout: 120_000` and then ran under
 * vitest's DEFAULT test timeout of 5_000. The inner number could never be
 * reached: whatever the subprocess was doing, vitest killed the test first. So
 * the 120s described an intention nothing enforced — the *"a script that prints
 * a number it does not act on"* family, with the number that actually governs
 * not written down anywhere.
 *
 * ⚠️ AND IT FAILED IN CI ON EXACTLY THAT. `Error: Test timed out in 5000ms`,
 * on a run whose only changes were elsewhere. Measured on this box: the script
 * completes in **2.13s**, exit 0, all six arms green — a 2.3× margin for a test
 * that shells out to `git worktree add` while 450 other test files run beside
 * it. That is not a passing test, it is a coin flip; canon 121 — an intermittent
 * guard is worse than none, because a red is read as a flake and a flake is
 * read as a red.
 *
 * ⚠️ THE SECOND COST IS THE DIAGNOSTIC, AND IT IS THE WORSE ONE. A vitest
 * timeout reports `Test timed out in 5000ms` and NOTHING ELSE — the script's own
 * output, which every assertion below is written to quote, is discarded. So a
 * genuine hang and a busy runner produce byte-identical evidence. Aligning the
 * budgets means a real failure comes back as the script's own words.
 */
const ARM_BUDGET_MS = 120_000;

describe('the lens sandbox is armed', () => {
  it('POSITIVE CONTROL — the scripts exist and are executable', () => {
    expect(existsSync(ARM), 'scripts/arm-lens-sandbox.sh is missing').toBe(true);
    expect(existsSync(MAKE), 'scripts/make-lens-sandbox.sh is missing').toBe(true);
  });

  it('⚠️ every planted write is REFUSED — the script is RUN, not read', () => {
    let out = '';
    let code = 0;
    try {
      out = execFileSync('bash', [ARM], { encoding: 'utf8', stdio: 'pipe', timeout: ARM_BUDGET_MS });
    } catch (e) {
      const err = e as { status?: number; stdout?: string; stderr?: string };
      code = err.status ?? -1;
      out = `${err.stdout ?? ''}${err.stderr ?? ''}`;
    }
    // The verdict, and the arms behind it, so a failure names itself in CI.
    expect(out, `arming output:\n${out}`).toContain('LENS SANDBOX ARMED');
    expect(code, `arm-lens-sandbox.sh exited ${code}:\n${out}`).toBe(0);
    for (const arm of ['ARM 0', 'ARM 1', 'ARM 2', 'ARM 3', 'ARM 4', 'ARM 5']) {
      expect(out, `${arm} did not report`).toContain(arm);
    }
    // ⚠️ ON THE **VERDICT LINES**, NOT THE WHOLE OUTPUT. A passing ARM 1 quotes
    // the hook's own refusal, which itself begins "🔴 REFUSED — this is a LENS
    // SANDBOX" — so a bare `not.toContain('🔴')` reds on success. Measured: it
    // did, on the first run of this gate. The check is whether any ARM line
    // reports red, which is the thing actually being claimed.
    const redArms = out
      .split('\n')
      .filter((line) => line.trimStart().startsWith('🔴'));
    expect(redArms, `red arms:\n${redArms.join('\n')}`).toEqual([]);
    // ⚠️ THE TEST BUDGET IS THE SUBPROCESS BUDGET. Passed explicitly rather
    // than left to vitest's default, so the two numbers cannot disagree again.
  }, ARM_BUDGET_MS);

  it('⚠️ ARM 2 names WHICH guard refused the push — found by mutation', () => {
    // With both guards removed, the push still failed — on "could not read
    // Username", i.e. the absence of credentials, which is ARM 3's job. Two
    // refusals that read identically in a report and mean different things. If
    // that discrimination is ever removed, the arm goes back to proving nothing.
    const src = readFileSync(ARM, 'utf-8');
    expect(src).toContain("does not appear to be a git repository");
    expect(src).toContain('NOT by the sandbox');
  });

  it('⚠️ NO SCRIPT HARDCODES THE REPO ROOT — the #1009 class, one hour later', () => {
    // A literal `/opt/meddoc-pro` is correct on the VPS and does not exist on
    // the CI runner or inside any worktree. #1009's boundary arm reached for
    // `/opt/meddoc-pro/README.md` and, on CI, measured a file that had never
    // been there — passing the refusal check and failing the survival check for
    // a reason that had nothing to do with the guard. These scripts derive the
    // root from their own location instead. Occurrences inside COMMENTS are
    // allowed, because the comment explaining the trap has to name it.
    for (const f of ['make', 'arm', 'reap']) {
      const src = readFileSync(resolve(ROOT, `scripts/${f}-lens-sandbox.sh`), 'utf-8');
      const code = src
        .split('\n')
        .filter((line) => !line.trimStart().startsWith('#'))
        .join('\n');
      expect(code, `${f}-lens-sandbox.sh hardcodes the repo root`).not.toContain('/opt/meddoc-pro');
      expect(code, `${f}-lens-sandbox.sh does not derive its root`).toContain(
        'rev-parse --show-toplevel',
      );
    }
  });

  it('.gitignore covers the sandboxes, or a pass dirties the tree that built it', () => {
    expect(readFileSync(resolve(ROOT, '.gitignore'), 'utf-8')).toContain('.lens-*/');
  });

  it('the four guards are all still declared in the builder', () => {
    const src = readFileSync(MAKE, 'utf-8');
    expect(src).toContain('remote.origin.pushurl /dev/null');
    expect(src).toContain('--detach');
    expect(src).toContain('core.hooksPath');
    expect(src).toContain('unset GH_TOKEN');
    // ⚠️ AND `--worktree` IS LOAD-BEARING: without it this line lands in the
    // SHARED config and disables pushes for every worktree at once.
    expect(src).toContain('config --worktree remote.origin.pushurl');
  });
});
