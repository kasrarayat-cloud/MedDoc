/**
 * RULING #186(3) — in-flight runs on a base block a merge ONLY when that base
 * is a declared deploy candidate.
 *
 * ⚠️ THIS NARROWS A SAFETY GUARD ON THE DOOR WITH THE WORSE RECORD. The merge
 * side has already produced a 3-of-4 citation on a DEPLOYED commit, and killed
 * a run at 33m39s that another session was deliberately waiting for. So the
 * property under test is not "it lets merges through" — it is that it can only
 * ever be more permissive when it POSITIVELY establishes NOT, and that every
 * doubt keeps today's behaviour.
 *
 * The arms drive the REAL merge-pr.sh in a scratch repo whose libraries and
 * `gh` are controlled, so CANDIDATE / NOT / UNKNOWN are exercised end-to-end
 * rather than asserted about source text.
 */
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync, copyFileSync, chmodSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const ROOT = resolve(__dirname, '../../../../..');
let root: string, work: string, bin: string;

const git = (...a: string[]) => execFileSync('git', a, { cwd: work, encoding: 'utf8' });

/** merge-pr.sh with the in-flight count forced, and `gh` reporting base=main. */
function run(busy: number, opts: { withLib?: boolean } = {}) {
  const withLib = opts.withLib !== false;
  // a controlled inflight.sh: no network, the count is the input
  writeFileSync(join(work, 'scripts/lib/inflight.sh'), `
inflight_declaration_ok(){ return 0; }
inflight_require_gh(){ return 0; }
inflight_positive_control(){ return 0; }
inflight_count(){ INFLIGHT_BY_COMMIT=${busy}; INFLIGHT_BY_BRANCH=${busy}; return 0; }
inflight_total(){ echo ${busy}; }
`);
  if (!withLib) rmSync(join(work, 'scripts/lib/deploy-candidate.sh'), { force: true });
  // ⚠️ BOTH STREAMS, ALWAYS. The narrowing announces itself on STDERR, and
  // execFileSync discards stderr on success — so the first version of this arm
  // could only ever see the refusal path and was blind to the path it exists to
  // prove. A harness that cannot observe the success case is not a harness.
  const r = spawnSync('bash', [join(work, 'scripts/merge-pr.sh'), '999'],
    { cwd: work, encoding: 'utf8', env: { ...process.env, PATH: `${bin}:${process.env.PATH}` } });
  return { code: r.status ?? -1, out: `${r.stdout ?? ''}${r.stderr ?? ''}` };
}

beforeAll(() => {
  root = mkdtempSync(join(tmpdir(), 'candidate-'));
  bin = join(root, 'bin'); mkdirSync(bin);
  // `gh` answers only what merge-pr.sh asks of it here: the PR's base, and the
  // post-merge re-read. It never merges anything.
  // ⚠️ THE STUB MUST DISTINGUISH THE TWO `state` QUERIES. merge-pr.sh asks
  // `--json state` BEFORE it does anything (must be OPEN or it exits early) and
  // `--json state,mergeCommit` AFTER merging (must be MERGED). A stub that
  // answers MERGED to both makes the script exit before the code under test —
  // which is how the first version of this arm passed nothing and failed four.
  writeFileSync(join(bin, 'gh'), `#!/usr/bin/env bash
case "$*" in
  *baseRefName*)  echo main ;;
  *mergeCommit*)  echo "MERGED abc123" ;;
  *state*)        echo OPEN ;;
  *merge*)        exit 0 ;;
  *)              echo "" ;;
esac
`);
  chmodSync(join(bin, 'gh'), 0o755);

  work = join(root, 'work');
  execFileSync('git', ['init', '-q', '-b', 'main', work]);
  git('config', 'user.email', 'arm@test');
  git('config', 'user.name', 'arm');
  git('config', 'commit.gpgsign', 'false');
  git('remote', 'add', 'origin', work); // origin/main resolves locally

  mkdirSync(join(work, 'scripts/lib'), { recursive: true });
  mkdirSync(join(work, 'docs/foundation/deploys'), { recursive: true });
  copyFileSync(join(ROOT, 'scripts/merge-pr.sh'), join(work, 'scripts/merge-pr.sh'));
  copyFileSync(join(ROOT, 'scripts/lib/deploy-candidate.sh'), join(work, 'scripts/lib/deploy-candidate.sh'));
  // ⚠️ THE DEPLOYS DIRECTORY MUST BE NON-EMPTY, AND THAT IS NOT TEST SCENERY.
  // An empty listing is indistinguishable from a broken `git ls-tree`, so
  // deploy_candidate_state returns UNKNOWN for it BY DESIGN — and git does not
  // track empty directories. The first version of this arm created the folder,
  // committed nothing into it, and measured UNKNOWN while expecting NOT. The
  // real repo always carries a README plus dozens of judged declarations; this
  // mirrors that, and it also exercises the keep-list skip.
  writeFileSync(join(work, 'docs/foundation/deploys/README.md'), '# deploy records\n');
  writeFileSync(join(work, 'a.txt'), 'base');
  git('add', '-A'); git('commit', '-q', '-m', 'base', '--no-verify');
  git('update-ref', 'refs/remotes/origin/main', 'HEAD');
});

afterAll(() => rmSync(root, { recursive: true, force: true }));

/** Put an UNJUDGED declaration naming HEAD into the tree, and commit it. */
function declareCandidate() {
  const sha = git('rev-parse', 'HEAD').trim().slice(0, 8);
  writeFileSync(join(work, `docs/foundation/deploys/20260905-${sha}.md`), '# decl\n');
  // ⚠️ `git add docs/`, NEVER `git add -A`. The first version used -A, which
  // swept in the stub `scripts/lib/inflight.sh` that an earlier arm had
  // written — and `scripts/` is RUNTIME under the drift regex, so the
  // declaration correctly stopped governing and the state read NOT. The
  // library was right and the FIXTURE manufactured the drift. Recorded because
  // it is the same defect the library exists to detect, arriving through the
  // test harness.
  git('add', 'docs'); git('commit', '-q', '-m', 'declare', '--no-verify');
  git('update-ref', 'refs/remotes/origin/main', 'HEAD');
}

describe('#186(3) — candidacy gates the in-flight refusal', () => {
  it('POSITIVE CONTROL: with runs in flight and NO declaration, it PROCEEDS', () => {
    // The whole narrowing. If this failed, nothing below would mean anything.
    const r = run(3);
    expect(r.out).toContain('NOT protecting');
    expect(r.out).toContain('#186(3)');
    expect(r.out).not.toContain('REFUSED');
  });

  it('with runs in flight and NO runs at all, it never mentions the narrowing', () => {
    const r = run(0);
    expect(r.out).not.toContain('NOT protecting');
  });

  it('DIAGNOSTIC: the library itself reports CANDIDATE for this tree', () => {
    // Separates the SIGNAL from the WIRING. If this is CANDIDATE and the
    // wrapper still merges, the defect is in merge-pr.sh, not the library.
    declareCandidate();
    const sha = execFileSync('git', ['rev-parse', 'refs/remotes/origin/main'], { cwd: work, encoding: 'utf8' }).trim();
    const st = execFileSync('bash', ['-c',
      `. "${join(work, 'scripts/lib/deploy-candidate.sh')}"; deploy_candidate_state main ${sha}`],
      { cwd: work, encoding: 'utf8' }).trim();
    expect(st, `origin/main=${sha}`).toBe('CANDIDATE');
  });

  it('REFUSES once an UNJUDGED declaration governs the base — the guard survives', () => {
    const r = run(3);
    expect(r.code).toBe(1);
    expect(r.out).toContain('REFUSED');
    expect(r.out).toContain('deploy-candidate state: CANDIDATE');
  });

  it('REFUSES again once the declaration is JUDGED... no — it PROCEEDS, and that is the point', () => {
    const sha = git('rev-parse', 'HEAD~1').trim().slice(0, 8);
    writeFileSync(join(work, `docs/foundation/deploys/20260905-${sha}-JUDGED.md`), '# judged\n');
    git('add', 'docs'); git('commit', '-q', '-m', 'judged', '--no-verify');
    git('update-ref', 'refs/remotes/origin/main', 'HEAD');
    const r = run(3);
    // a judged declaration is a closed-out deploy; its runs are nobody's pending citation
    expect(r.out).toContain('NOT protecting');
  });

  it('FAIL-CLOSED: an absent library is UNKNOWN, and UNKNOWN refuses', () => {
    // ⚠️ The direction that matters. A missing signal must never read as
    // permission — otherwise deleting a file silently disarms the guard.
    const r = run(3, { withLib: false });
    expect(r.code).toBe(1);
    expect(r.out).toContain('REFUSED');
    expect(r.out).toContain('deploy-candidate state: UNKNOWN');
  });
});
