// ============================================================================
// THE RECORD-FIRST CURE, AND ITS OWN PROBES.
// ----------------------------------------------------------------------------
// ⚠️ "THE HOOK IS INSTALLED" IS NOT "THE HOOK WORKS", and this programme has
// paid for that distinction more than once. These arms drive the real script
// against real git state in a real temporary repository — not a string in
// memory, which is what let a previous lint pass while missing every live
// offender in its own watched directories.
//
// Each arm builds a throwaway repo, stages a real diff, and runs the script.
// ============================================================================
import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, cpSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { afterAll, describe, expect, it } from 'vitest';

// ⚠️ FIVE LEVELS, AND THE FOUR-LEVEL VERSION LANDED IN `apps/`. __dirname is
// apps/transcribe-md/src/lib/__tests__, so three `..` reach the APP and two more
// reach the repo — the same shape the sibling gate uses. Four resolved to a
// directory that exists, so nothing threw until the script could not be found.
const APP = resolve(__dirname, '..', '..', '..');
const REPO = resolve(APP, '..', '..');
const SCRIPT = join(REPO, 'scripts', 'check-ruling-recorded.sh');
const made: string[] = [];

afterAll(() => { for (const d of made) rmSync(d, { recursive: true, force: true }); });

/** A real git repo with a real ledger and a real staged diff. */
function scenario(opts: {
  ledger: string;
  files: Record<string, string>;
}): { code: number; out: string } {
  const dir = mkdtempSync(join(tmpdir(), 'ruling-gate-'));
  made.push(dir);
  const git = (...a: string[]) =>
    execFileSync('git', ['-C', dir, ...a], { encoding: 'utf8', stdio: 'pipe' });
  git('init', '-q');
  git('config', 'user.email', 't@t.t');
  git('config', 'user.name', 't');
  mkdirSync(join(dir, 'docs', 'foundation'), { recursive: true });
  writeFileSync(join(dir, 'docs', 'foundation', 'RULINGS.md'), opts.ledger);
  mkdirSync(join(dir, 'scripts'), { recursive: true });
  cpSync(SCRIPT, join(dir, 'scripts', 'check-ruling-recorded.sh'));
  git('add', '-A');
  git('commit', '-qm', 'base');
  for (const [p, body] of Object.entries(opts.files)) {
    mkdirSync(join(dir, p.split('/').slice(0, -1).join('/') || '.'), { recursive: true });
    writeFileSync(join(dir, p), body);
  }
  git('add', '-A');
  try {
    const out = execFileSync('bash', [join(dir, 'scripts', 'check-ruling-recorded.sh')], {
      encoding: 'utf8', stdio: 'pipe',
    });
    return { code: 0, out };
  } catch (e) {
    const err = e as { status: number; stdout?: string; stderr?: string };
    return { code: err.status, out: (err.stdout ?? '') + (err.stderr ?? '') };
  }
}

const LEDGER_WITH_174 = '# Rulings\n\n| date | # | status |\n| 2026-09-01 | #174 | STANDING |\n';
const LEDGER_EMPTY = '# Rulings\n\n| date | # | status |\n';

describe('the record-first cure', () => {
  it('⚠️ REFUSES a ruling cited in SOURCE with no row', () => {
    const r = scenario({
      ledger: LEDGER_EMPTY,
      files: { 'src/compiler.ts': '// ⚠️ #174 — admission is an allowlist\nexport const x = 1;\n' },
    });
    expect(r.code, 'an unrecorded ruling was allowed through').toBe(1);
    expect(r.out).toContain('#174');
  });

  it('ALLOWS it once the row exists — the other way to be wrong', () => {
    const r = scenario({
      ledger: LEDGER_WITH_174,
      files: { 'src/compiler.ts': '// ⚠️ #174 — admission is an allowlist\nexport const x = 1;\n' },
    });
    expect(r.code, 'a recorded ruling was refused').toBe(0);
  });

  // ⚠️ THE DEFECT CANON 93 PRE-EMPTED BY NAME. Without the docs/ exclusion,
  // every retrospective in this programme reds — they all discuss historical
  // rulings by number, and discussing one is not claiming it is current.
  it('⚠️ IGNORES citations inside docs/ — a retrospective is not a claim', () => {
    const r = scenario({
      ledger: LEDGER_EMPTY,
      files: { 'docs/canon/99-something.md': 'This entry discusses #174 at length.\n' },
    });
    expect(r.code, 'a retrospective was treated as a live citation').toBe(0);
  });

  // ⚠️ THE OTHER PRE-EMPTED DEFECT: the check must read the STAGED diff. An
  // unstaged citation is not part of this commit, so judging it means judging a
  // DIFFERENT SET from the one being committed.
  it('⚠️ reads the STAGED diff — an unstaged citation is not this commit', () => {
    const dir = mkdtempSync(join(tmpdir(), 'ruling-gate-unstaged-'));
    made.push(dir);
    const git = (...a: string[]) =>
      execFileSync('git', ['-C', dir, ...a], { encoding: 'utf8', stdio: 'pipe' });
    git('init', '-q'); git('config', 'user.email', 't@t.t'); git('config', 'user.name', 't');
    mkdirSync(join(dir, 'docs', 'foundation'), { recursive: true });
    writeFileSync(join(dir, 'docs', 'foundation', 'RULINGS.md'), LEDGER_EMPTY);
    mkdirSync(join(dir, 'scripts'), { recursive: true });
    cpSync(SCRIPT, join(dir, 'scripts', 'check-ruling-recorded.sh'));
    git('add', '-A'); git('commit', '-qm', 'base');
    mkdirSync(join(dir, 'src'), { recursive: true });
    writeFileSync(join(dir, 'src', 'x.ts'), '// #174 cited but NOT staged\n');
    let code = 0;
    try { execFileSync('bash', [join(dir, 'scripts', 'check-ruling-recorded.sh')], { stdio: 'pipe' }); }
    catch (e) { code = (e as { status: number }).status; }
    expect(code, 'the check judged the working tree instead of the index').toBe(0);
  });

  // ⚠️ A PR NUMBER IS NOT A RULING, and both wear `#NNN`. Stated as the
  // heuristic it is: it errs toward CHECKING, so its failure mode is a message,
  // never a silent pass.
  it('⚠️ a PR number is not a ruling', () => {
    const r = scenario({
      ledger: LEDGER_EMPTY,
      files: { 'src/x.ts': '// landed in PR #171, see the discussion there\n' },
    });
    expect(r.code, 'a pull-request number was treated as a ruling').toBe(0);
  });

  it('⚠️ FAILS CLOSED when the ledger is missing — cannot-tell is not a pass', () => {
    const dir = mkdtempSync(join(tmpdir(), 'ruling-gate-noledger-'));
    made.push(dir);
    execFileSync('git', ['-C', dir, 'init', '-q']);
    mkdirSync(join(dir, 'scripts'), { recursive: true });
    cpSync(SCRIPT, join(dir, 'scripts', 'check-ruling-recorded.sh'));
    let code = 0;
    try { execFileSync('bash', [join(dir, 'scripts', 'check-ruling-recorded.sh')], { stdio: 'pipe' }); }
    catch (e) { code = (e as { status: number }).status; }
    expect(code, 'a missing ledger read as a pass').toBe(2);
  });

  // ⚠️ THE RANGE, AND WHY IT IS NOT THE ONE THE CANON ENTRY SPECIFIES. That
  // entry's worked example is `#1[0-9]{2}` — which matches 100-199 and nothing
  // else, so it covers today's rulings exactly and STOPS MATCHING AT #200,
  // silently. Rulings stand at #175. A measurement of today's corpus had been
  // written into the cure as though it were a property of the code.
  it('⚠️ a ruling past #199 is still caught — the spec regex would have missed it', () => {
    const r = scenario({
      ledger: LEDGER_EMPTY,
      files: { 'src/x.ts': '// ruling #200 says something\n' },
    });
    expect(r.code, 'the gate silently stopped working past #199').toBe(1);
    expect(r.out).toContain('#200');
  });

  it('a one-digit number is not treated as a ruling', () => {
    const r = scenario({ ledger: LEDGER_EMPTY, files: { 'src/x.ts': '// see #9 for context\n' } });
    expect(r.code).toBe(0);
  });

  it('⚠️ NON-VACUITY: the harness can actually produce a refusal', () => {
    // Without this, every arm above could be passing because the scenario
    // builder silently produces an empty diff.
    const r = scenario({
      ledger: LEDGER_EMPTY,
      files: { 'src/a.ts': '// #150\n', 'src/b.ts': '// #151\n' },
    });
    expect(r.code).toBe(1);
    expect(r.out).toContain('#150');
    expect(r.out).toContain('#151');
  });
});
