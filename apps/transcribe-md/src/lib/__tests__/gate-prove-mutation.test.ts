// ============================================================================
// THE MUTATION PROOF IS MECHANIZED, BECAUSE THE HABIT KEPT NOT REACHING
// BEHAVIOUR.
// ----------------------------------------------------------------------------
// A mutation proof breaks the code on purpose, watches an arm go red, and
// restores. The restore is `git checkout -- <file>` — which restores to the
// COMMIT, not to the state before the mutation. Uncommitted work in that file
// is destroyed, silently, exit 0.
//
// It cost real work THREE times in one session, and each time the lesson was
// written down. **Writing a lesson down is not obeying it** — which is this
// repository's own recorded reason for turning a rule into mechanism.
//
// ⚠️ THE ARMS RUN AGAINST A THROWAWAY GIT REPO, NEVER THIS CHECKOUT. A gate
// that asserted against the working tree would measure whatever the session
// happened to leave lying around, and would pass or fail for reasons that have
// nothing to do with the script — the same defect that made an earlier
// container-revision gate meaningless when CI's ref made two commits identical.
// ============================================================================
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, readFileSync, rmSync, mkdirSync, copyFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

import { afterAll, describe, expect, it } from 'vitest';

const REPO = resolve(__dirname, '../../../../..');
const SCRIPT = resolve(REPO, 'scripts/prove-mutation.sh');

/**
 * ⚠️ ONE BUDGET, NAMED, USED FOR BOTH THE SHELL-OUT AND THE `it`. An inner
 * timeout larger than vitest's default 5s makes every arm die on
 * "Test timed out in 5000ms" with the subprocess's own message unreachable.
 *
 * (The ruling that makes this a sweep-wide requirement is recorded on an
 * unmerged branch, so it is stated here rather than cited by number — see the
 * commit message. Citing it would be citing a claim, not a fact.)
 */
const ARM_BUDGET_MS = 30_000;

const tmps: string[] = [];
afterAll(() => {
  for (const d of tmps) {
    try {
      rmSync(d, { recursive: true, force: true });
    } catch {
      /* a leaked temp dir is not worth failing a gate over */
    }
  }
});

/**
 * A throwaway repo with one committed file, and the real script copied in.
 *
 * ⚠️ THE CONTRACT BELOW IS LOAD-BEARING — #265(c). Its `execFileSync` sits in a
 * HELPER, so reading any single arm never reveals its budget, and the sweep
 * gate cannot resolve an enclosing `it`. The contract declares the budget every
 * calling arm carries; without it the gate correctly reports "no budget".
 */
// shell-budget-governed-by: ARM_BUDGET_MS
function sandbox(): { dir: string; subject: string } {
  const dir = mkdtempSync(join(tmpdir(), 'provemut-'));
  tmps.push(dir);
  const git = (...a: string[]) =>
    execFileSync('git', a, { cwd: dir, encoding: 'utf8', timeout: ARM_BUDGET_MS });
  git('init', '-q');
  git('config', 'user.email', 'gate@example.invalid');
  git('config', 'user.name', 'gate');
  writeFileSync(join(dir, 'subject.txt'), 'ORIGINAL\n');
  mkdirSync(join(dir, 'scripts'), { recursive: true });
  copyFileSync(SCRIPT, join(dir, 'scripts/prove-mutation.sh'));
  git('add', '-A');
  git('commit', '-qm', 'baseline');
  return { dir, subject: 'subject.txt' };
}

// shell-budget-governed-by: ARM_BUDGET_MS
function run(dir: string, args: string[]): { rc: number; out: string } {
  const r = spawnSync('bash', ['scripts/prove-mutation.sh', ...args], {
    cwd: dir,
    encoding: 'utf8',
    timeout: ARM_BUDGET_MS,
  });
  return { rc: r.status ?? 1, out: `${r.stdout ?? ''}${r.stderr ?? ''}` };
}

const MUTATE_OK = `printf 'MUTATED\\n' > subject.txt`;

describe('prove-mutation.sh — it refuses on a DIRTY tree, which is the whole point', () => {
  it('REFUSES, and does NOT touch the file — the uncommitted work survives', () => {
    const { dir } = sandbox();
    // Uncommitted work in a DIFFERENT file than the one being mutated: the
    // restore would take the whole tree's HEAD, so the guard is tree-wide.
    writeFileSync(join(dir, 'subject.txt'), 'HALF-FINISHED FIX\n');

    const r = run(dir, ['--file', 'subject.txt', '--marker', 'MUTATED', '--mutate', MUTATE_OK, '--expect-fail', 'false']);

    expect(r.rc, r.out).toBe(1);
    expect(r.out).toContain('uncommitted tracked changes');
    // ⚠️ THE ASSERTION THAT MATTERS. A refusal that still ran the mutation
    // would have destroyed exactly what it claims to protect.
    expect(
      readFileSync(join(dir, 'subject.txt'), 'utf8'),
      'the uncommitted work was destroyed by the very guard meant to save it',
    ).toBe('HALF-FINISHED FIX\n');
  }, ARM_BUDGET_MS);

  it('names the dirty paths — a refusal you cannot act on gets worked around', () => {
    const { dir } = sandbox();
    writeFileSync(join(dir, 'subject.txt'), 'dirty\n');
    const r = run(dir, ['--file', 'subject.txt', '--marker', 'M', '--mutate', MUTATE_OK, '--expect-fail', 'false']);
    expect(r.out).toContain('subject.txt');
  }, ARM_BUDGET_MS);

  it('an UNTRACKED file does not count as dirty — otherwise nothing could ever run', () => {
    // ⚠️ Scratch files, reports and probes are untracked by design here. A
    // guard that refused on those would be refused on every real invocation,
    // and a guard that always refuses gets bypassed.
    const { dir } = sandbox();
    writeFileSync(join(dir, 'scratch.log'), 'noise\n');
    const r = run(dir, ['--file', 'subject.txt', '--marker', 'MUTATED', '--mutate', MUTATE_OK, '--expect-fail', 'false']);
    expect(r.rc, r.out).toBe(0);
  }, ARM_BUDGET_MS);
});

describe('prove-mutation.sh — an unapplied mutation is REFUSED, never reported green', () => {
  it('REFUSES when the marker is absent — the no-op that reads as a pass', () => {
    const { dir } = sandbox();
    // The mutation "succeeds" (exit 0) and changes nothing that matters — the
    // exact shape of a `.replace()` whose anchor did not match.
    const r = run(dir, [
      '--file', 'subject.txt',
      '--marker', 'MUTATED',
      '--mutate', 'true',
      '--expect-fail', 'false',
    ]);
    expect(r.rc, r.out).toBe(1);
    expect(r.out).toContain('did not apply');
  }, ARM_BUDGET_MS);

  it('REFUSES when the mutation command itself fails', () => {
    const { dir } = sandbox();
    const r = run(dir, ['--file', 'subject.txt', '--marker', 'MUTATED', '--mutate', 'exit 3', '--expect-fail', 'false']);
    expect(r.rc, r.out).toBe(1);
    expect(r.out).toContain('mutation command itself failed');
  }, ARM_BUDGET_MS);
});

describe('prove-mutation.sh — a VACUOUS arm is the finding, not a pass', () => {
  it('exit 2 when the proof PASSES under mutation', () => {
    const { dir } = sandbox();
    const r = run(dir, ['--file', 'subject.txt', '--marker', 'MUTATED', '--mutate', MUTATE_OK, '--expect-fail', 'true']);
    expect(r.rc, r.out).toBe(2);
    expect(r.out).toContain('VACUOUS');
  }, ARM_BUDGET_MS);

  it('exit 0 when the arm fails under mutation — and the file is RESTORED', () => {
    const { dir } = sandbox();
    const r = run(dir, ['--file', 'subject.txt', '--marker', 'MUTATED', '--mutate', MUTATE_OK, '--expect-fail', 'false']);
    expect(r.rc, r.out).toBe(0);
    expect(r.out).toContain('the proof holds');
    // ⚠️ RESTORED EVEN ON THE HAPPY PATH. A proof that leaves the mutation
    // behind is how a deliberate break reaches a commit.
    expect(readFileSync(join(dir, 'subject.txt'), 'utf8')).toBe('ORIGINAL\n');
  }, ARM_BUDGET_MS);

  it('and it RESTORES after a refusal mid-flight, not only after a clean run', () => {
    const { dir } = sandbox();
    // The proof command does not exist, so the run dies after mutating.
    run(dir, ['--file', 'subject.txt', '--marker', 'MUTATED', '--mutate', MUTATE_OK, '--expect-fail', 'no-such-command-here']);
    expect(readFileSync(join(dir, 'subject.txt'), 'utf8')).toBe('ORIGINAL\n');
  }, ARM_BUDGET_MS);
});

describe('prove-mutation.sh — fail-closed on cannot-tell, and on a missing argument', () => {
  it('REFUSES outside a git work tree', () => {
    const dir = mkdtempSync(join(tmpdir(), 'provemut-nogit-'));
    tmps.push(dir);
    mkdirSync(join(dir, 'scripts'), { recursive: true });
    copyFileSync(SCRIPT, join(dir, 'scripts/prove-mutation.sh'));
    writeFileSync(join(dir, 'subject.txt'), 'x\n');
    const r = run(dir, ['--file', 'subject.txt', '--marker', 'M', '--mutate', 'true', '--expect-fail', 'false']);
    expect(r.rc, r.out).toBe(1);
    expect(r.out).toContain('not inside a git work tree');
  }, ARM_BUDGET_MS);

  it.each([
    [['--marker', 'M', '--mutate', 'true', '--expect-fail', 'false'], '--file is required'],
    [['--file', 'subject.txt', '--mutate', 'true', '--expect-fail', 'false'], '--marker is required'],
    [['--file', 'subject.txt', '--marker', 'M', '--expect-fail', 'false'], '--mutate is required'],
    [['--file', 'subject.txt', '--marker', 'M', '--mutate', 'true'], '--expect-fail'],
  ])('REFUSES a missing required argument (%#)', (args, needle) => {
    const { dir } = sandbox();
    const r = run(dir, args as string[]);
    expect(r.rc, r.out).toBe(1);
    expect(r.out).toContain(needle);
  }, ARM_BUDGET_MS);
});
