/**
 * ARM FOR `scripts/union-gate.sh` — ruling #184's standing practice.
 *
 * ⚠️ THIS SCRIPT SHIPPED WITH THE DEFECT IT EXISTS TO PREVENT. Its first
 * version matched only `apps/transcribe-md/*`, silently skipped six
 * `packages/ai/**` gate files belonging to the largest passenger in the range,
 * and then printed "every passenger's gates pass on the MERGED tree". A union
 * gate that quietly narrows its own watched set is worse than no union gate,
 * because it produces a confident row nobody re-checks.
 *
 * So the arms drive the REAL script against REAL files in a REAL git repo —
 * canon 96: a control that never touches a file cannot guard files. String
 * fixtures in memory would have passed against the broken version too.
 */
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync, mkdirSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const SCRIPT = resolve(__dirname, '../../../../../scripts/union-gate.sh');

let repo: string;

function git(...args: string[]) {
  return execFileSync('git', args, { cwd: repo, encoding: 'utf8' });
}
function write(rel: string, body = 'x') {
  const full = join(repo, rel);
  mkdirSync(join(full, '..'), { recursive: true });
  writeFileSync(full, body);
}
/** Run the script; return {code, out}. Never throws on non-zero. */
function run(base: string, head = 'HEAD', env: Record<string, string> = {}) {
  try {
    const out = execFileSync('bash', [SCRIPT, base, head], {
      cwd: repo,
      encoding: 'utf8',
      env: { ...process.env, ...env },
    });
    return { code: 0, out };
  } catch (e: any) {
    return { code: e.status as number, out: `${e.stdout ?? ''}${e.stderr ?? ''}` };
  }
}

beforeAll(() => {
  repo = mkdtempSync(join(tmpdir(), 'uniongate-'));
  git('init', '-q');
  git('config', 'user.email', 'arm@test');
  git('config', 'user.name', 'arm');
  git('config', 'commit.gpgsign', 'false');
  write('README.md', 'base');
  git('add', '-A');
  git('commit', '-q', '-m', 'base', '--no-verify');
});

afterAll(() => rmSync(repo, { recursive: true, force: true }));

describe('union-gate.sh — the instrument itself', () => {
  it('POSITIVE CONTROL: the script exists and is executable', () => {
    // Without this, every refusal below could be "bash could not find the file"
    // wearing a refusal's exit code.
    expect(() => readFileSync(SCRIPT)).not.toThrow();
    const r = run('nope-not-a-sha');
    expect(r.out).toContain('union-gate');
  });

  it('REFUSES (2) when the base is not a commit — a bad input is never a pass', () => {
    const r = run('deadbeefdeadbeefdeadbeefdeadbeefdeadbeef');
    expect(r.code).toBe(2);
    expect(r.out).toContain('CANNOT TELL');
  });

  it('passes (0) on a docs-only range, and SAYS it was docs-only', () => {
    const base = git('rev-parse', 'HEAD').trim();
    write('docs/thing.md', 'words');
    git('add', '-A');
    git('commit', '-q', '-m', 'docs', '--no-verify');
    const r = run(base);
    expect(r.code).toBe(0);
    expect(r.out).toContain('docs-only range');
  });

  it('REFUSES (2) on a runtime range that moved NO gate — unmeasured is not green', () => {
    const base = git('rev-parse', 'HEAD').trim();
    write('src/thing.ts', 'export const a = 1;');
    git('add', '-A');
    git('commit', '-q', '-m', 'runtime, no gate', '--no-verify');
    const r = run(base);
    expect(r.code).toBe(2);
    expect(r.out).toContain('NOT ONE touched a gate');
  });

  it('CONVERTS an out-of-app gate rather than dropping it — the shipped defect', () => {
    const base = git('rev-parse', 'HEAD').trim();
    write('apps/transcribe-md/src/a.test.ts');
    write('packages/ai/src/b.test.ts');
    git('add', '-A');
    git('commit', '-q', '-m', 'two passengers', '--no-verify');

    const r = run(base, 'HEAD', { UNION_GATE_PLAN_ONLY: '1' });
    expect(r.code).toBe(0);
    // BOTH gates found...
    expect(r.out).toContain('2 gate file(s)');
    // ...and the out-of-app one is ADDRESSED, not silently skipped.
    expect(r.out).toContain('../../packages/ai/src/b.test.ts');
    expect(r.out).toContain('2 found, 2 addressed');
  });

  it('REFUSES (2) on a gate it cannot address — never narrows its own set', () => {
    const base = git('rev-parse', 'HEAD').trim();
    write('toplevel.test.ts'); // no directory: matches neither app nor */*
    git('add', '-A');
    git('commit', '-q', '-m', 'unaddressable', '--no-verify');
    const r = run(base, 'HEAD', { UNION_GATE_PLAN_ONLY: '1' });
    expect(r.code).toBe(2);
    expect(r.out).toContain('cannot address');
  });
});

describe('MUTATION — restore the original defect and prove the arm reds', () => {
  it('a conversion that skips out-of-app gates is CAUGHT by the reconciliation', () => {
    const src = readFileSync(SCRIPT, 'utf8');
    const ANCHOR = '    */*)      REL+=("../../$g") ;;';
    // ⚠️ ASSERT THE MUTATION APPLIES. An unapplied mutation yields a green that
    // proves nothing and is indistinguishable from a guard that works.
    expect(src).toContain(ANCHOR);
    const mutated = src.replace(ANCHOR, '    */*)      : ;;'); // the shipped defect
    expect(mutated).not.toBe(src);

    const mutantPath = join(repo, 'union-gate.mutant.sh');
    writeFileSync(mutantPath, mutated);

    const base = git('rev-parse', 'HEAD~2').trim(); // the two-passenger commit
    let code = 0;
    let out = '';
    try {
      out = execFileSync('bash', [mutantPath, base, 'HEAD~1'], {
        cwd: repo,
        encoding: 'utf8',
        env: { ...process.env, UNION_GATE_PLAN_ONLY: '1' },
      });
    } catch (e: any) {
      code = e.status;
      out = `${e.stdout ?? ''}${e.stderr ?? ''}`;
    }

    // The mutant finds 2 and addresses 1 — exactly the shipped defect — and the
    // reconciliation refuses instead of printing a confident union row.
    expect(code).toBe(2);
    expect(out).toContain('found 2 gate files but addressed 1');
    expect(out).not.toContain('every passenger');
  });
});
