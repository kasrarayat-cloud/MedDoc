/**
 * RULING #186(2) — `retire-branch.sh` must refuse to delete a branch that is
 * the BASE of an open pull request.
 *
 * ⚠️ WHY THE EXISTING GATE DOES NOT COVER IT. The script already refuses a
 * branch that is not an ancestor of `origin/main`. That is a different
 * question: a stacked branch can be FULLY MERGED into main while another PR is
 * still open against it. Deleting the base then makes GitHub close that PR and
 * the diff it carried goes with it. This repo has produced exactly that shape —
 * PR #951, `feat/t8b-billable-descendants` -> `feat/t8-icd10-fy2026-full`.
 *
 * ⚠️ THE ARM GIVES THE SCRIPT ITS OWN REPO. `retire-branch.sh` resolves its
 * root from BASH_SOURCE and cd's there, so it can only ever act on the repo it
 * lives in — pointing it at a temp tree by changing cwd does nothing. The
 * script is therefore COPIED into a scratch repo that has its own `origin`,
 * and `gh` is stubbed on PATH so the dependant-PR answer is controlled rather
 * than guessed.
 */
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync, copyFileSync, chmodSync, symlinkSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const REAL = resolve(__dirname, '../../../../../scripts/retire-branch.sh');

let root: string, work: string, binDir: string, nogh: string;

const git = (cwd: string, ...a: string[]) =>
  execFileSync('git', a, { cwd, encoding: 'utf8' });

/** Write a fake `gh` whose `pr list` prints exactly `out`, or fails if `fail`. */
function stubGh(out: string, fail = false) {
  const p = join(binDir, 'gh');
  writeFileSync(p, fail
    ? '#!/usr/bin/env bash\necho "stub: API is down" >&2\nexit 1\n'
    : `#!/usr/bin/env bash\ncat <<'EOF'\n${out}\nEOF\n`);
  chmodSync(p, 0o755);
}
function removeGh() {
  writeFileSync(join(binDir, 'gh'), '#!/usr/bin/env bash\nexit 127\n');
  // command -v still finds it, so instead shadow PATH without it below.
}

function run(branch: string, withGh = true) {
  // ⚠️ `/usr/bin:/bin` is NOT a gh-free PATH — the real gh lives there, and the
  // first version of this arm found it, took the query-FAILED branch, and
  // passed on the exit code while testing a different arm entirely. A
  // gh-free PATH has to be CONSTRUCTED.
  const PATH = withGh ? `${binDir}:${process.env.PATH}` : nogh;
  try {
    const out = execFileSync('bash', [join(work, 'scripts/retire-branch.sh'), branch],
      { cwd: work, encoding: 'utf8', env: { ...process.env, PATH } });
    return { code: 0, out };
  } catch (e: any) {
    return { code: e.status as number, out: `${e.stdout ?? ''}${e.stderr ?? ''}` };
  }
}

beforeAll(() => {
  root = mkdtempSync(join(tmpdir(), 'retire-'));
  binDir = join(root, 'bin'); mkdirSync(binDir);

  // a PATH holding exactly what the script needs and NOT gh
  nogh = join(root, 'nogh'); mkdirSync(nogh);
  // The exact set retire-branch.sh invokes. `dirname` was missing from the
  // first version of this list and the script died before reaching the gh
  // check — an arm that failed for a reason unrelated to what it tests.
  for (const tool of ['git', 'sed', 'wc', 'cat', 'bash', 'grep', 'tr', 'env',
                      'dirname', 'basename', 'printf', 'ls', 'uname']) {
    try {
      const real = execFileSync('bash', ['-lc', `command -v ${tool}`], { encoding: 'utf8' }).trim();
      if (real) symlinkSync(real, join(nogh, tool));
    } catch { /* tool absent; the script degrades the same way a user would */ }
  }
  expect(existsSync(join(nogh, 'gh')), 'the gh-free PATH must not contain gh').toBe(false);

  // a bare "origin"
  const origin = join(root, 'origin.git');
  execFileSync('git', ['init', '--bare', '-q', '-b', 'main', origin]);

  work = join(root, 'work');
  execFileSync('git', ['init', '-q', '-b', 'main', work]);
  git(work, 'config', 'user.email', 'arm@test');
  git(work, 'config', 'user.name', 'arm');
  git(work, 'config', 'commit.gpgsign', 'false');
  git(work, 'remote', 'add', 'origin', origin);

  mkdirSync(join(work, 'scripts'), { recursive: true });
  copyFileSync(REAL, join(work, 'scripts/retire-branch.sh'));

  writeFileSync(join(work, 'a.txt'), 'base');
  git(work, 'add', '-A');
  git(work, 'commit', '-q', '-m', 'base', '--no-verify');
  git(work, 'push', '-q', 'origin', 'main');

  // a branch fully merged into main (fast-forward), pushed to origin
  git(work, 'checkout', '-q', '-b', 'feat/stacked-base');
  writeFileSync(join(work, 'b.txt'), 'more');
  git(work, 'add', '-A');
  git(work, 'commit', '-q', '-m', 'stacked', '--no-verify');
  git(work, 'push', '-q', 'origin', 'feat/stacked-base');
  git(work, 'checkout', '-q', 'main');
  git(work, 'merge', '-q', '--ff-only', 'feat/stacked-base');
  git(work, 'push', '-q', 'origin', 'main');
  git(work, 'fetch', '-q', 'origin');
});

afterAll(() => rmSync(root, { recursive: true, force: true }));

describe('#186(2) — retire-branch refuses the base of an open PR', () => {
  it('POSITIVE CONTROL: the topology is what the test claims', () => {
    // Without this the refusals below could be the ancestor gate firing, and
    // the new arm would be laundered by a guard it is not.
    const ahead = git(work, 'rev-list', '--count', 'origin/main..origin/feat/stacked-base').trim();
    expect(ahead, 'branch must be fully merged, or the OLD gate refuses first').toBe('0');
    expect(git(work, 'ls-remote', '--heads', 'origin', 'feat/stacked-base')).toContain('feat/stacked-base');
  });

  it('REFUSES (1) and NAMES the dependant PR', () => {
    stubGh('PR #951 (feat/t8b-billable-descendants)');
    const r = run('feat/stacked-base');
    expect(r.code).toBe(1);
    expect(r.out).toContain('is the BASE of open pull request');
    expect(r.out).toContain('PR #951');
    // ⚠️ THE FAILURE MUST NAME **THIS** ARM, not another guard that happened
    // to catch it — otherwise the arm is unproved and the red is laundered.
    expect(r.out).toContain('#186(2)');
    expect(r.out).not.toContain('NOT an ancestor');
    // and it must NOT have deleted anything
    expect(git(work, 'ls-remote', '--heads', 'origin', 'feat/stacked-base')).toContain('feat/stacked-base');
  });

  it('REFUSES (2) when the PR query FAILS — cannot-tell is not permission', () => {
    stubGh('', true);
    const r = run('feat/stacked-base');
    expect(r.code).toBe(2);
    expect(r.out).toContain('cannot tell');
    expect(git(work, 'ls-remote', '--heads', 'origin', 'feat/stacked-base')).toContain('feat/stacked-base');
  });

  it('REFUSES (2) when gh is absent entirely', () => {
    const r = run('feat/stacked-base', false);
    expect(r.code).toBe(2);
    expect(r.out).toContain("no 'gh'");
  });

  it('PROCEEDS when no PR depends on it — the arm is not vacuous', () => {
    // ⚠️ If this did not pass, every refusal above would be consistent with a
    // guard that simply always refuses.
    stubGh('');
    const r = run('feat/stacked-base');
    expect(r.out).not.toContain('BASE of open pull request');
    expect(git(work, 'ls-remote', '--heads', 'origin', 'feat/stacked-base').trim()).toBe('');
  });
});
