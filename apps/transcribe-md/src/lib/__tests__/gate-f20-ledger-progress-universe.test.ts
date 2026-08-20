// ============================================================================
// F20 — THE NO-PROGRESS KILL SWITCH MEASURES THE LEDGER WHERE THE WORK LANDS.
// ----------------------------------------------------------------------------
// ⚠️ THE DEFECT ENDED A PRODUCTIVE NIGHT, AND IT WAS STRUCTURAL RATHER THAN
// CARELESS. `foundation-loop.sh`'s KILL SWITCH 4 hashed the SHARED TREE's
// working copy of `docs/foundation/RELAY.md`. A session never writes that file:
// it works in its own `git worktree` and lands its ledger row through a merged
// PR onto `origin/main`. The shared tree learns about it only through the
// launch-time `--ff-only` sync, which runs BEFORE the session — so the switch
// was reading a file the judged session could not affect.
//
// MEASURED, run `20260818-232127-b1`:
//
//     session   launch (sample)   shared-tree commit   ledger hash
//     run03     06:52:02Z         febfdcfd             c631a099
//     run04     09:11:51Z         febfdcfd             c631a099   <- identical
//
// At both sample moments `origin/main` genuinely WAS `febfdcfd`, so the sync was
// not broken — it correctly did nothing. Session 04 then merged #740 (10:00:35Z)
// and #741/#742 (~12:07Z), every one carrying a RELAY row, and the run halted on
// NO-PROGRESS at 12:44:53Z — 14 commits behind the file it was reading.
//
// ⚠️ SO THE SWITCH COLLAPSED TWO DISTINGUISHABLE STATES INTO ONE OBSERVATION:
// "no item finished" and "no sync ran" produced byte-identical output, and only
// one of them is a finding. That is this house's named family, and the fix must
// not re-commit it — which is why CANNOT-TELL is a third state here, with its
// own exit code and its own halt name.
//
// ── WHAT THIS GATE DRIVES ───────────────────────────────────────────────────
// The REAL `scripts/lib/ledger-progress.sh`, sourced by a real bash, against
// THROWAWAY git repositories under $TMPDIR with a real `origin`. Nothing here
// re-implements the logic — a second copy drifts from the first the day either
// is fixed.
//
// ⚠️ IT PROVES BOTH DIRECTIONS, AND THE HAPPY PATH IS ASSERTED FIRST. A
// resolver that answered CANNOT-TELL to everything would satisfy every refusal
// arm in this file. `retire-branch.sh` passed 9 of 9 refusal tests and then
// printed a false green on the one path that mattered; the accept arms are this
// gate's positive control and they come first for that reason.
//
// ⚠️ AND THE LOAD-BEARING ARM IS `the STALE WORKING TREE`. It reproduces the
// 2026-08-19 shape exactly — origin moves, the local tree does not — and asserts
// BOTH that the new measure sees it AND that the old one did not. Asserting only
// the first would pass just as happily against a hash of the working copy on a
// fixture where the two happen to agree.
//
// ⚠️ IT REAPS ITS OWN TMPDIR. The FOUNDATION loop runs unattended and `shred`
// and `rm` are DENIED to it by design, so a gate that mints a directory per run
// mints scratch the only actor present cannot delete.
//
// ⚠️ HONEST LIMIT, NAMED RATHER THAN IMPLIED: this proves the MEASURE, not the
// runner's loop arithmetic. It does not launch sessions, and it cannot — a test
// that spawns 24 headless agents is not a test. The wiring is guarded instead by
// the `WIRED INTO THE RUNNER` arms below, which assert the call sites and the
// streak semantics that a silent revert would have to remove.
// ============================================================================

import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterAll, beforeAll, describe, expect, it } from 'vitest';

const REPO_ROOT = `${__dirname}/../../../../..`;
const LIB = join(REPO_ROOT, 'scripts/lib/ledger-progress.sh');
const RUNNER = join(REPO_ROOT, 'scripts/foundation-loop.sh');
const LEDGER = 'docs/foundation/RELAY.md';

let TMP: string;
let seq = 0;

beforeAll(() => {
  TMP = mkdtempSync(join(tmpdir(), 'f20-ledger-'));
});

afterAll(() => {
  rmSync(TMP, { recursive: true, force: true });
});

function git(cwd: string, ...args: string[]): string {
  return execFileSync('git', args, { cwd, encoding: 'utf8' }).trim();
}

function write(dir: string, rel: string, body: string): void {
  mkdirSync(join(dir, rel, '..'), { recursive: true });
  writeFileSync(join(dir, rel), body);
}

function identify(dir: string): void {
  git(dir, 'config', 'user.email', 'f20-gate@example.invalid');
  git(dir, 'config', 'user.name', 'F20 gate');
  git(dir, 'config', 'commit.gpgsign', 'false');
}

/** Result of calling the REAL shell function. */
interface Probe {
  rc: number;
  out: string;
}

/** Sources `ledger-progress.sh` in a real bash and calls it, exactly as the
 *  runner does. The RC is captured WITHOUT `|| true` — see the runner's own
 *  note: `|| true` would make `$?` the status of `true` and silently disarm the
 *  cannot-tell arm. */
function probe(cwd: string, ledgerArg: string = LEDGER): Probe {
  const script = `
set -uo pipefail
. ${JSON.stringify(LIB)}
out="$(ledger_progress_hash ${JSON.stringify(ledgerArg)})"
rc=$?
printf '%s\\n' "$rc"
printf '%s\\n' "$out"
`;
  let raw: string;
  try {
    raw = execFileSync('bash', ['-c', script], { cwd, encoding: 'utf8' });
  } catch (e) {
    const err = e as { stdout?: string; stderr?: string };
    throw new Error(
      `bash aborted — the library did not merely return non-zero, it DIED. ` +
        `That is the set -u class F14-a paid for.\nstdout: ${err.stdout}\nstderr: ${err.stderr}`,
    );
  }
  const lines = raw.split('\n');
  return { rc: Number(lines[0]), out: (lines[1] ?? '').trim() };
}

/** A throwaway `origin` plus a clone, with the ledger committed and pushed. */
function newPair(ledgerBody: string): { origin: string; work: string } {
  const origin = join(TMP, `o${seq}.git`);
  const work = join(TMP, `w${seq}`);
  seq += 1;

  mkdirSync(origin, { recursive: true });
  git(origin, 'init', '-q', '--bare', '-b', 'main');

  execFileSync('git', ['clone', '-q', origin, work], { encoding: 'utf8' });
  identify(work);
  write(work, LEDGER, ledgerBody);
  git(work, 'add', '-A');
  git(work, 'commit', '-q', '-m', 'ledger');
  git(work, 'push', '-q', 'origin', 'main');

  return { origin, work };
}

/** A SECOND actor pushing to the same origin — the merged PR, in miniature. */
function landOnOrigin(origin: string, ledgerBody: string): void {
  const other = join(TMP, `x${seq++}`);
  execFileSync('git', ['clone', '-q', origin, other], { encoding: 'utf8' });
  identify(other);
  write(other, LEDGER, ledgerBody);
  git(other, 'add', '-A');
  git(other, 'commit', '-q', '-m', 'ledger row lands');
  git(other, 'push', '-q', 'origin', 'main');
}

const HEX64 = /^[0-9a-f]{64}$/;

// ───────────────────────────────────────────────────────────────────────────
// THE ACCEPT ARMS COME FIRST — they are the positive control for everything
// below. A library that could never measure anything would pass every refusal.
// ───────────────────────────────────────────────────────────────────────────
describe('F20 — it MEASURES (the positive control)', () => {
  it('returns 0 and a real sha256 for a ledger that is on origin/main', () => {
    const { work } = newPair('# ledger\nrow one\n');
    const p = probe(work);
    expect(p.rc).toBe(0);
    expect(p.out).toMatch(HEX64);
  });

  it('is BYTE-FAITHFUL — it hashes the blob, not a shell-mangled copy of it', () => {
    // A trailing newline is exactly what `$(git show …)` eats. If the library
    // ever regressed to capturing into a variable, this would diverge — and it
    // would still be deterministic, which is why nobody would notice.
    const body = '# ledger\nrow one\n';
    const { work } = newPair(body);
    const viaLib = probe(work).out;

    const viaGit = execFileSync(
      'bash',
      ['-c', `git show origin/main:${LEDGER} | sha256sum | cut -d' ' -f1`],
      { cwd: work, encoding: 'utf8' },
    ).trim();

    expect(viaLib).toBe(viaGit);
  });

  it('is STABLE across calls when nothing lands — the no-progress signal is not noise', () => {
    const { work } = newPair('# ledger\nrow one\n');
    expect(probe(work).out).toBe(probe(work).out);
  });
});

// ───────────────────────────────────────────────────────────────────────────
// THE LOAD-BEARING ARM — the 2026-08-19 shape, reproduced.
// ───────────────────────────────────────────────────────────────────────────
describe('F20 — a STALE WORKING TREE does not hide a landed ledger row', () => {
  it('SEES a row that landed on origin while the local tree never moved', () => {
    const { origin, work } = newPair('# ledger\nrow one\n');

    const before = probe(work);
    expect(before.rc).toBe(0);

    const headBefore = git(work, 'rev-parse', 'HEAD');
    landOnOrigin(origin, '# ledger\nrow one\nrow two — F12-g CLOSED\n');

    const after = probe(work);
    expect(after.rc).toBe(0);

    // The working tree is untouched: this is precisely session 04's situation.
    expect(git(work, 'rev-parse', 'HEAD')).toBe(headBefore);
    expect(git(work, 'status', '--porcelain')).toBe('');

    // THE ASSERTION THE WHOLE ITEM EXISTS FOR.
    expect(after.out).not.toBe(before.out);
  });

  it('and the OLD measure was blind to exactly that — stated as a measurement, not a worry', () => {
    const { origin, work } = newPair('# ledger\nrow one\n');

    const oldBefore = execFileSync('bash', ['-c', `sha256sum ${LEDGER} | cut -d' ' -f1`], {
      cwd: work,
      encoding: 'utf8',
    }).trim();

    landOnOrigin(origin, '# ledger\nrow one\nrow two — F12-g CLOSED\n');

    const oldAfter = execFileSync('bash', ['-c', `sha256sum ${LEDGER} | cut -d' ' -f1`], {
      cwd: work,
      encoding: 'utf8',
    }).trim();

    // The retired implementation cannot tell the two states apart. This arm is
    // what makes the arm above meaningful: without it, a fixture where the
    // working copy happens to track origin would pass both.
    expect(oldAfter).toBe(oldBefore);
  });
});

// ───────────────────────────────────────────────────────────────────────────
// THE SWITCH STILL FIRES ON GENUINE STASIS — this is NOT a loosening.
// ───────────────────────────────────────────────────────────────────────────
describe('F20 — a genuinely spinning session is STILL caught', () => {
  it('reports an UNCHANGED hash when nothing lands on origin at all', () => {
    const { origin, work } = newPair('# ledger\nrow one\n');
    const before = probe(work).out;

    // A session that commits plenty and lands no ledger row: work happens on a
    // branch that never reaches main. This is the exact failure the switch was
    // written for and it must survive the repair.
    const other = join(TMP, `spin${seq++}`);
    execFileSync('git', ['clone', '-q', origin, other], { encoding: 'utf8' });
    identify(other);
    git(other, 'checkout', '-q', '-b', 'feat/busy');
    write(other, 'apps/some-file.ts', 'export const x = 1;\n');
    git(other, 'add', '-A');
    git(other, 'commit', '-q', '-m', 'lots of work, no ledger row');
    git(other, 'push', '-q', 'origin', 'feat/busy');

    expect(probe(work).out).toBe(before);
  });

  it('a commit that lands on main WITHOUT touching the ledger is also no progress', () => {
    const { origin, work } = newPair('# ledger\nrow one\n');
    const before = probe(work).out;

    const other = join(TMP, `nolr${seq++}`);
    execFileSync('git', ['clone', '-q', origin, other], { encoding: 'utf8' });
    identify(other);
    write(other, 'apps/other-file.ts', 'export const y = 2;\n');
    git(other, 'add', '-A');
    git(other, 'commit', '-q', '-m', 'merged, but no ledger row');
    git(other, 'push', '-q', 'origin', 'main');

    // main MOVED and the ledger did not. The contract is "an item is not
    // finished until its ledger row lands", so this must read as no progress —
    // a git-log check would have called it progress.
    expect(probe(work).out).toBe(before);
  });
});

// ───────────────────────────────────────────────────────────────────────────
// CANNOT-TELL IS A THIRD STATE, NEVER A ZERO.
// ───────────────────────────────────────────────────────────────────────────
describe('F20 — CANNOT TELL is exit 2 and never masquerades as unchanged', () => {
  it('refuses when there is no origin remote at all', () => {
    const dir = join(TMP, `noremote${seq++}`);
    mkdirSync(dir, { recursive: true });
    git(dir, 'init', '-q', '-b', 'main');
    identify(dir);
    write(dir, LEDGER, '# ledger\n');
    git(dir, 'add', '-A');
    git(dir, 'commit', '-q', '-m', 'ledger');

    const p = probe(dir);
    expect(p.rc).toBe(2);
    expect(p.out).toMatch(/^CANNOT-TELL:/);
  });

  it('refuses when origin exists but carries no main', () => {
    const origin = join(TMP, `bare${seq}.git`);
    const work = join(TMP, `nomain${seq++}`);
    mkdirSync(origin, { recursive: true });
    git(origin, 'init', '-q', '--bare', '-b', 'main');
    execFileSync('git', ['clone', '-q', origin, work], { encoding: 'utf8' });
    identify(work);
    write(work, LEDGER, '# ledger\n');
    git(work, 'add', '-A');
    git(work, 'commit', '-q', '-m', 'ledger'); // committed LOCALLY, never pushed

    const p = probe(work);
    expect(p.rc).toBe(2);
    expect(p.out).toBe('CANNOT-TELL:no-origin-main');
  });

  it('refuses when the ledger is absent from main, and says WHICH failure it was', () => {
    const { work } = newPair('# ledger\n');
    // The ledger exists on main here; ask for a path that does not.
    const p = probe(work, 'docs/foundation/NOT-THE-LEDGER.md');
    expect(p.rc).toBe(2);
    expect(p.out).toBe('CANNOT-TELL:ledger-absent-on-main');
  });

  it('refuses an empty ledger path rather than hashing something arbitrary', () => {
    const { work } = newPair('# ledger\n');
    const p = probe(work, '');
    expect(p.rc).toBe(2);
    expect(p.out).toBe('CANNOT-TELL:no-ledger-path');
  });

  it('NEVER returns a hash-shaped string on any cannot-tell path', () => {
    // The caller branches on the RC, but a token that LOOKED like a hash would
    // make a future string-comparing caller read "changed" forever — permanent
    // progress, the exact inverse of the bug being fixed.
    const dir = join(TMP, `shape${seq++}`);
    mkdirSync(dir, { recursive: true });
    git(dir, 'init', '-q', '-b', 'main');
    identify(dir);
    write(dir, LEDGER, '# ledger\n');
    git(dir, 'add', '-A');
    git(dir, 'commit', '-q', '-m', 'ledger');

    expect(probe(dir).out).not.toMatch(HEX64);
  });
});

// ───────────────────────────────────────────────────────────────────────────
// WIRED INTO THE RUNNER — a library nothing calls is a library that does
// nothing, and a silent revert of the wiring is invisible to every arm above.
// ───────────────────────────────────────────────────────────────────────────
describe('F20 — the runner actually uses it', () => {
  const runner = () => readFileSync(RUNNER, 'utf8');

  // ⚠️ EVERY OTHER ARM IN THIS BLOCK READS THE RUNNER AS TEXT, so a syntax
  // error in it would leave all of them green while the loop could not start at
  // all — the worst available outcome, since a runner that does not parse takes
  // the whole night rather than one item. `bash -n` is a weak instrument (it
  // cannot see the `unbound variable` class that cost F14-a a run) and it is
  // strictly better than the nothing that was here first.
  it('PARSES — both the runner and the library it sources', () => {
    expect(() =>
      execFileSync('bash', ['-n', RUNNER], { encoding: 'utf8' }),
    ).not.toThrow();
    expect(() => execFileSync('bash', ['-n', LIB], { encoding: 'utf8' })).not.toThrow();
  });

  it('sources the library', () => {
    expect(runner()).toContain('. scripts/lib/ledger-progress.sh');
  });

  it('takes BOTH samples through it — opening and closing', () => {
    const src = runner();
    expect(src).toContain('ledger_before="$(ledger_progress_hash "$LEDGER")"');
    expect(src).toContain('ledger_after="$(ledger_progress_hash "$LEDGER")"');
  });

  it('no longer hashes the working copy of the ledger', () => {
    // The retired form. Its return is the whole regression.
    expect(runner()).not.toContain('sha256sum "$LEDGER"');
  });

  it('captures the return code WITHOUT `|| true` on either sample', () => {
    // `|| true` makes `$?` the status of `true` — always 0 — which disarms the
    // cannot-tell arm while looking like defensive shell. The first draft of
    // this fix had exactly that line.
    const src = runner();
    expect(src).not.toContain('ledger_progress_hash "$LEDGER")" || true');
    expect(src).toContain('ledger_before_rc=$?');
    expect(src).toContain('ledger_after_rc=$?');
  });

  it('routes a cannot-tell to its OWN halt name, not to NO-PROGRESS', () => {
    const src = runner();
    expect(src).toContain('LEDGER-UNREADABLE');
    // and the no-progress banner is only reachable from the measured branch
    expect(src).toContain('unchanged on origin/main across two consecutive sessions');
  });

  it('keeps the streak counters OUTSIDE the batch loop, so a relight cannot disarm them', () => {
    const src = runner();
    const declLine = src.indexOf('noprogress_streak=0');
    const batchLoop = src.indexOf('while : ; do');
    expect(declLine).toBeGreaterThan(-1);
    expect(batchLoop).toBeGreaterThan(-1);
    expect(declLine).toBeLessThan(batchLoop);
  });

  it('resets the cannot-tell streak on BOTH measured paths — "consecutive" means consecutive', () => {
    // A reset that lived only on the progress path would let three cannot-tells
    // scattered across a night, each separated by a clean session, add up to a
    // halt that never happened consecutively.
    const src = runner();
    const resets = src.split('cannottell_streak=0').length - 1;
    // one declaration + one on the no-progress path + one on the progress path
    expect(resets).toBe(3);
  });
});

// ───────────────────────────────────────────────────────────────────────────
// THE PIPE SWALLOWS `git show`'s EXIT CODE — filed as an owed residual in
// INBOX 2026-08-20T01:45:00Z, closed here.
//
// `git cat-file -e` proves the blob exists, which is what makes this
// near-unreachable. Near-unreachable is not unreachable (a corrupt object, a gc
// racing the read, a truncated pack), and the failure is the nastiest shape
// there is: `git show` writes NOTHING, the pipe runs anyway, `sha256sum` hashes
// EMPTY STDIN, and the result is `e3b0c442…855` — 64 hex characters, so the
// `-z` guard cannot see it, and IDENTICAL ON EVERY BROKEN READ. Two consecutive
// blind sessions therefore compare EQUAL and the no-progress switch fires: this
// function would become the cause of the exact false halt it was written to
// cure.
//
// ⚠️ MAKING IT REACHABLE IS THE WHOLE DIFFICULTY, so the failure is injected
// rather than simulated: a `git` shim on PATH that is byte-for-byte the real
// git for every subcommand EXCEPT the one named. `cat-file -e` still succeeds,
// so control genuinely reaches the pipe — this exercises the real gap, not a
// re-implementation of it.
// ───────────────────────────────────────────────────────────────────────────

/** sha256 of zero bytes. Named, because an unexplained constant in a test is
 *  indistinguishable from a typo. */
const SHA256_OF_EMPTY = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';

/** A `git` that is the real git except for `sub`, which exits 1 printing
 *  nothing — precisely how a failed `git show` behaves. */
function shimBreaking(sub: string): string {
  const dir = join(TMP, `shim${seq++}`);
  mkdirSync(dir, { recursive: true });
  const real = execFileSync('bash', ['-c', 'command -v git'], { encoding: 'utf8' }).trim();
  writeFileSync(
    join(dir, 'git'),
    `#!/usr/bin/env bash\n` +
      `if [ "\${1:-}" = ${JSON.stringify(sub)} ]; then exit 1; fi\n` +
      `exec ${JSON.stringify(real)} "$@"\n`,
    { mode: 0o755 },
  );
  return dir;
}

/** `probe`, with a shim directory prepended to PATH. */
function probeWithPath(cwd: string, shimDir: string): Probe {
  const script = `
set -uo pipefail
export PATH=${JSON.stringify(shimDir)}:"$PATH"
. ${JSON.stringify(LIB)}
out="$(ledger_progress_hash ${JSON.stringify(LEDGER)})"
rc=$?
printf '%s\\n' "$rc"
printf '%s\\n' "$out"
`;
  const raw = execFileSync('bash', ['-c', script], { cwd, encoding: 'utf8' });
  const lines = raw.split('\n');
  return { rc: Number(lines[0]), out: (lines[1] ?? '').trim() };
}

describe('F20 — a FAILED READ is cannot-tell, never a stable plausible hash', () => {
  // ⚠️ THE HARNESS IS CONTROLLED FIRST. A shim that broke *everything* would
  // make every refusal arm below pass while proving nothing about `show`.
  it('the shim is a real git for everything it does not break (harness control)', () => {
    const { work } = newPair('# ledger\ncontrolled\n');
    const clean = probeWithPath(work, shimBreaking('this-is-not-a-git-subcommand'));
    expect(clean.rc).toBe(0);
    expect(clean.out).toMatch(HEX64);
  });

  it('returns CANNOT-TELL and exit 2 when `git show` fails, instead of hashing empty stdin', () => {
    const { work } = newPair('# ledger\nrow one\n');
    const p = probeWithPath(work, shimBreaking('show'));

    expect(p.rc).toBe(2);
    expect(p.out).toBe('CANNOT-TELL:show-failed');
  });

  it('⚠️ and specifically does NOT return the empty-stdin digest — the shape of the bug', () => {
    // This is the arm that would have gone RED before the fix. The old code
    // reached `[ -z "$blob_hash" ]` holding e3b0c442…855, which is not empty,
    // so it returned that value with exit 0 — a valid-looking hash meaning
    // "I could not read anything".
    const { work } = newPair('# ledger\nrow one\n');
    const p = probeWithPath(work, shimBreaking('show'));

    expect(p.out).not.toBe(SHA256_OF_EMPTY);
    expect(p.rc).not.toBe(0);
  });

  it('⚠️ TWO blind reads do not compare EQUAL — the false halt is what this prevents', () => {
    // The defect was never "a wrong hash". It was "the SAME wrong hash twice",
    // because the no-progress switch fires on equality. Asserting inequality of
    // the returned values would be the wrong test: both are the same
    // CANNOT-TELL string. What must hold is that neither is a MEASUREMENT.
    const { work } = newPair('# ledger\nrow one\n');
    const a = probeWithPath(work, shimBreaking('show'));
    const b = probeWithPath(work, shimBreaking('show'));

    expect(a.rc).toBe(2);
    expect(b.rc).toBe(2);
    expect([a.out, b.out].every((o) => !HEX64.test(o))).toBe(true);
  });

  it('a LEGITIMATELY EMPTY ledger still MEASURES — the net does not overreach', () => {
    // ⚠️ The residual as filed proposed comparing against the empty digest.
    // That was declined: it cannot tell "we hashed nothing" from "the file is
    // genuinely zero bytes", and the existence check exists precisely so those
    // stay distinguishable. `pipefail` is also strictly stronger — it catches a
    // truncated read that emitted bytes before failing, which yields a WRONG
    // hash that no constant comparison could ever see.
    const { work } = newPair('');
    const p = probe(work);

    expect(p.rc).toBe(0);
    expect(p.out).toBe(SHA256_OF_EMPTY);
  });

  it('sets pipefail INSIDE the substitution, so a caller without it is still guarded', () => {
    // A sourced library must not mutate its caller's shell options, and must
    // not depend on them for its correctness either.
    const src = readFileSync(LIB, 'utf8');
    expect(src).toContain('$(set -o pipefail; git show');
    // and it must NOT be set at file scope, which would leak into the runner
    expect(src).not.toMatch(/^set -o pipefail$/m);
  });
});
