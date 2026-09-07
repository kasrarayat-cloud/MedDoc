// ============================================================================
// GATE — THE SCRATCH REAPER FAILS CLOSED WHEN GIT CANNOT ANSWER.
// ----------------------------------------------------------------------------
// ⚠️ THIS FILE EXISTS BECAUSE THE GUARD FIRED IN THE WRONG DIRECTION, LIVE.
// Reaping a scratch directory whose worktree had been pruned shredded
// `colon_blank_answers.pdf` — a tracked, committed BLANK FIXTURE. The reaper is
// the tool written to make canon 89's incident impossible, and it reproduced
// canon 89's incident.
//
// The mechanism, and it is one `if`:
//
//     $ git -C <orphaned worktree> rev-parse --git-dir
//     fatal: not a git repository: /opt/meddoc-pro/.git/worktrees/al4
//
// An orphaned worktree keeps its `.git` FILE; the entry it points at is gone.
// The tracked-file check was nested INSIDE `if rev-parse succeeds`, so when git
// could not answer, the check was skipped and the file was shredded. Two states
// were coded — tracked / untracked — where there are THREE, and the third was
// silently folded into the safe-sounding one.
//
// ⚠️ AND THE THIRD STATE IS THE NORMAL END OF A SESSION, not an edge case.
// Scratch worktrees are removed or pruned and their directories linger; that is
// exactly when someone reaches for this script. **The guard was absent precisely
// when it was needed.**
//
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL:
//   · cannot-tell goes back to fail-open      -> the cannot-tell block
//   · the sandbox boundary check is weakened  -> the boundary block
//   · the reaper stops shredding real scratch -> the non-vacuity block
// ============================================================================

import { execFileSync, execSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

const REPO_ROOT = join(__dirname, '..', '..', '..', '..', '..');
const REAPER = join(REPO_ROOT, 'scripts/reap-session-scratch.sh');

/** ⚠️ THE SANDBOX IS PART OF THE CONTRACT, so the fixtures must live INSIDE it
 *  or every arm passes for the wrong reason — refused-as-outside rather than
 *  refused-as-cannot-tell. Two refusals that look identical in a report. */
const SANDBOX = '/tmp/claude-1000/';
let BASE = '';

function run(args: string[]): { code: number; out: string } {
  try {
    const out = execFileSync('bash', [REAPER, ...args], { encoding: 'utf8', stdio: 'pipe' });
    return { code: 0, out };
  } catch (e) {
    const err = e as { status?: number; stdout?: string; stderr?: string };
    return { code: err.status ?? -1, out: `${err.stdout ?? ''}${err.stderr ?? ''}` };
  }
}

beforeAll(() => {
  mkdirSync(SANDBOX, { recursive: true });
  BASE = mkdtempSync(join(SANDBOX, 'reapgate-'));
});

afterAll(() => {
  // Leave nothing behind, but never with the tool under test.
  try { execSync(`rm -rf ${JSON.stringify(BASE)}`); } catch { /* best effort */ }
});

describe('⚠️ cannot-tell REFUSES — the state that shredded a tracked fixture', () => {
  it('a file under a DANGLING `.git` marker is refused, not shredded', () => {
    // Reproduce the exact shape: a directory carrying a `.git` FILE that points
    // at a worktree entry which does not exist. This is what a pruned scratch
    // worktree looks like on disk.
    const orphan = join(BASE, 'orphaned-worktree');
    mkdirSync(orphan, { recursive: true });
    writeFileSync(join(orphan, '.git'), 'gitdir: /opt/meddoc-pro/.git/worktrees/does-not-exist\n');
    const victim = join(orphan, 'colon_blank_answers.pdf');
    writeFileSync(victim, 'pretend fixture bytes');

    const r = run([victim]);
    expect(r.out).toMatch(/CANNOT TELL/);
    expect(r.code, 'a refusal must exit 1').toBe(1);
    expect(existsSync(victim), 'the file was destroyed despite being unjudgeable').toBe(true);
  });

  it('and the refusal names what to do about it, rather than only refusing', () => {
    // A check's remediation advice is read at the worst moment; "re-register or
    // remove the worktree" is actionable, "refused" alone is not.
    const orphan = join(BASE, 'orphan2');
    mkdirSync(orphan, { recursive: true });
    writeFileSync(join(orphan, '.git'), 'gitdir: /nowhere/at/all\n');
    const victim = join(orphan, 'thing.docx');
    writeFileSync(victim, 'x');
    expect(run([victim]).out).toMatch(/Re-register or remove the worktree/);
  });

  it('the marker is found from a NESTED path, not only beside the file', () => {
    // A worktree's fixtures live many directories down. A check that only looks
    // in the file's own directory would pass this suite and fail in practice.
    const orphan = join(BASE, 'orphan3');
    const deep = join(orphan, 'apps', 'transcribe-md', 'tests', 'e2e', 'fixtures');
    mkdirSync(deep, { recursive: true });
    writeFileSync(join(orphan, '.git'), 'gitdir: /nowhere\n');
    const victim = join(deep, 'sample-form.docx');
    writeFileSync(victim, 'x');

    const r = run([victim]);
    expect(r.out).toMatch(/CANNOT TELL/);
    expect(existsSync(victim)).toBe(true);
  });
});

describe('⚠️ NON-VACUITY — the reaper still reaps', () => {
  it('a genuine scratch file with no repository marker above it IS shredded', () => {
    // Without this, "refuse everything" would satisfy every arm above.
    const plain = join(BASE, 'plain');
    mkdirSync(plain, { recursive: true });
    const f = join(plain, 'scratch.txt');
    writeFileSync(f, 'disposable');

    const r = run([f]);
    expect(r.code, 'a successful reap must exit 0').toBe(0);
    expect(existsSync(f), 'the reaper stopped reaping').toBe(false);
  });
});

describe('the pre-existing guards are untouched', () => {
  it('a path outside the sandbox is still refused, AS outside', () => {
    // ⚠️ NOT `REPO_ROOT` — AND THE FIRST DRAFT USED IT AND PASSED FOR THE WRONG
    // REASON. This gate runs from a WORKTREE, so `REPO_ROOT` resolves inside
    // `/tmp/claude-1000/` and the file came back refused as TRACKED. The file
    // was protected either way, which is exactly why the arm looked fine: two
    // different guards, one word apart in the report. This file's own header
    // warns about that, and the arm still walked into it.
    //
    // ⚠️ AND THE SECOND DRAFT USED `/opt/meddoc-pro/README.md`, WHICH RED THE
    // ARM IN CI FOR A THIRD WRONG REASON — the arm was measuring a file that
    // was never there. The shared tree is genuinely outside the sandbox on THIS
    // box; on the CI runner `/opt/meddoc-pro` does not exist at all. So
    // `REFUSED (outside` matched (a non-existent path outside the sandbox is
    // still outside) and then `existsSync` was false — not because the reaper
    // shredded it, but because there had never been a file to shred. **The arm
    // could not tell "protected" from "never existed", which is the exact
    // vacuity this file was written to hunt, arriving inside the hunt.**
    //
    // The fixture is therefore CREATED, outside the sandbox, by this arm — so
    // it exists in every environment — and its existence is asserted BEFORE the
    // run. That pre-assertion is the whole repair: without it, `toBe(true)`
    // afterwards is a claim about a file whose prior state nobody measured.
    const outsideDir = mkdtempSync(join(tmpdir(), 'reapgate-outside-'));
    const outside = join(outsideDir, 'must-survive.txt');
    writeFileSync(outside, 'this file is outside the sandbox and must be refused, not reaped\n');

    // THE CONTROL: it is here before the reaper runs.
    expect(existsSync(outside), 'the fixture was never created').toBe(true);
    // ...and it is genuinely outside, or this arm proves nothing.
    expect(outside.startsWith(SANDBOX), 'the fixture is INSIDE the sandbox').toBe(false);

    const r = run([outside]);
    expect(r.out, 'refused, but not by the boundary check').toMatch(/REFUSED \(outside/);
    expect(r.code).toBe(1);
    expect(existsSync(outside), 'the reaper crossed its own boundary').toBe(true);

    try { execSync(`rm -rf ${JSON.stringify(outsideDir)}`); } catch { /* best effort */ }
  });

  it('an absent target is skipped, not treated as success-by-destruction', () => {
    const r = run([join(BASE, 'never-existed.txt')]);
    expect(r.out).toMatch(/skipped \(absent\)/);
  });
});
