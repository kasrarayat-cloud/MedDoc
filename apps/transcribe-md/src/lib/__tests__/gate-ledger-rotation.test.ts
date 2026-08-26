// ============================================================================
// THE LEDGER SPLIT IS PROVED, AND THE ROTATION THAT KEEPS IT TRUE IS FAIL-CLOSED.
// ----------------------------------------------------------------------------
// On 2026-08-26 docs/foundation/RELAY.md was 1,793,436 characters against a
// 150,000-character read limit — TWELVE TIMES over, on a file MASTER.md STEP 0
// orders every session to READ. Only ~8% of it fitted in one read, and because
// the ledger is append-only that 8% is its OLDEST content: a plain read returned
// a confident, well-formed, OBSOLETE answer and announced nothing.
//
// The cure was a SPLIT, never a trim — a live head plus verbatim dated archives.
// But a split alone is a TREADMILL: measured the same day, a head keeping only
// "2026-08-25 onward" was already 155,689 chars, i.e. THE LEDGER ADDS MORE THAN
// THE WHOLE BUDGET PER DAY. So rotation ships with it, and this gate holds both.
//
// ⚠️ IT DRIVES THE REAL SCRIPTS AND RE-IMPLEMENTS NOTHING. The splitter's five
// proofs live in scripts/lib/split-ledger.py; rotation's budget authority lives
// in F32's scripts/check-read-budget.sh. A second copy of either drifts from the
// first the day one is fixed.
//
// ⚠️ AND THE RED ARMS MUTATE A COPY, NEVER THE REPO. A mutation proof that edits
// a tracked file can leave the tree dirty on failure, and a dirty shared tree is
// what refuses the FOUNDATION loop's next relight. The copies are hermetic.
//
// ⚠️ A GUARD PROVED ONLY GREEN IS HALF-PROVED, AND IT IS THE CHEAPER HALF.
// Four of these arms are RED arms: each breaks the splitter one specific way and
// requires the specific proof that exists to catch it to actually fire.
// ============================================================================

import { copyFileSync, mkdtempSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

import { describe, expect, it } from 'vitest';

const REPO = join(__dirname, '..', '..', '..', '..', '..');
const SPLITTER = join(REPO, 'scripts', 'lib', 'split-ledger.py');
const ROTATE = join(REPO, 'scripts', 'rotate-ledger.sh');
const RELAY = join(REPO, 'docs', 'foundation', 'RELAY.md');

const LIFT = JSON.stringify([
  '# FOUNDATION — the relay ledger',
  '## Rules',
  '## Invariants re-checked every item',
]);

function runSplitter(script: string, outDir: string, env: Record<string, string> = {}) {
  return spawnSync('python3', [script, RELAY, outDir], {
    encoding: 'utf8',
    maxBuffer: 64 * 1024 * 1024,
    env: { ...process.env, LIFT, ...env },
  });
}

/** Copy the splitter to a temp dir and apply exactly one textual mutation. */
function mutatedSplitter(find: string, replace: string): string {
  const dir = mkdtempSync(join(tmpdir(), 'split-mut-'));
  const dest = join(dir, 'split-ledger.py');
  const src = readFileSync(SPLITTER, 'utf8');
  const hits = src.split(find).length - 1;
  // A mutation anchor that matches 0 or 2+ times proves nothing — canon's
  // "a scripted edit proves its own application", applied to the proof itself.
  expect(hits, `mutation anchor matched ${hits} times, expected exactly 1`).toBe(1);
  const out = src.replace(find, replace);
  expect(out).not.toBe(src);
  writeFileSync(dest, out);
  expect(readFileSync(dest, 'utf8')).toContain(replace.slice(0, 40));
  return dest;
}

function outDir() {
  return join(mkdtempSync(join(tmpdir(), 'split-out-')), 'archives');
}

describe('ledger split — the five proofs', () => {
  it('GREEN: splits the real ledger with every proof passing, and non-vacuously', () => {
    const r = runSplitter(SPLITTER, outDir(), { DRY_RUN: '1' });
    expect(r.status, r.stderr).toBe(0);
    const d = JSON.parse(r.stdout);

    // NON-VACUITY: it must have actually processed the real file, not an empty one.
    const actual = [...readFileSync(RELAY, 'utf8')].length;
    expect(d.source_chars).toBe(actual);
    expect(d.archives).toBeGreaterThan(5);
    expect(d.proof.P3_src_headings).toBeGreaterThan(500);

    expect(d.proof.P1_exact_partition).toBe(true);
    expect(d.proof.P1_gaps).toEqual([]);
    expect(d.proof.P1_overlaps).toEqual([]);
    expect(d.proof.P2_inorder_rebuild_equals_source).toBe(true);
    expect(d.proof.P3_equal_both_directions).toBe(true);
    expect(d.proof.P3_lost).toEqual([]);
    expect(d.proof.P3_invented).toEqual([]);
    expect(d.proof.P4_archives_over_budget).toEqual({});
    expect(d.proof.P5_reconciles).toBe(true);
  });

  it('RED: a dropped range is caught by the partition proof (the LOSS defect)', () => {
    const m = mutatedSplitter(
      '        for (x, y) in chunk(lines, a, b, BUCKET_MAX):',
      '        for (x, y) in (chunk(lines, a, b, BUCKET_MAX)[:-1] or chunk(lines, a, b, BUCKET_MAX)):',
    );
    const r = runSplitter(m, outDir());
    expect(r.status).not.toBe(0);
    expect(r.stdout + r.stderr).toContain('not an exact partition');
  });

  it('RED: an oversize archive is refused (otherwise the split solved nothing)', () => {
    const m = mutatedSplitter(
      'BUCKET_MAX = int(os.environ.get("BUCKET_MAX", "110000"))',
      'BUCKET_MAX = 10**9',
    );
    const r = runSplitter(m, outDir());
    expect(r.status).not.toBe(0);
    expect(r.stdout + r.stderr).toContain('still over budget');
  });

  it('RED: a LIFT anchor that matches nothing is a refusal, not a silent no-op', () => {
    const r = runSplitter(SPLITTER, outDir(), {
      LIFT: JSON.stringify(['## A Heading That Does Not Exist']),
    });
    expect(r.status).not.toBe(0);
    expect(r.stdout + r.stderr).toContain('did not match exactly');
  });

  it('RED: a KEEP_SINCE cutoff that keeps NOTHING refuses rather than archiving the live arc', () => {
    const r = runSplitter(SPLITTER, outDir(), { KEEP_SINCE: '2099-01-01' });
    expect(r.status).not.toBe(0);
    expect(r.stdout + r.stderr).toContain('archives the live arc');
  });
});

describe('rotation — banner-triggered, delegating, fail-closed', () => {
  it('DELEGATES the budget rather than re-implementing it', () => {
    const src = readFileSync(ROTATE, 'utf8');
    expect(src).toContain('check-read-budget.sh');
    // It must not carry its own copy of F32's read limit.
    expect(src).not.toMatch(/READ_BUDGET_LIMIT\s*=/);
    expect(src).not.toContain('150000');
  });

  it('FAIL-CLOSED: a missing delegate is CANNOT TELL (exit 2), never "nothing to do"', () => {
    const dir = mkdtempSync(join(tmpdir(), 'rot-'));
    mkdirSync(join(dir, 'scripts', 'lib'), { recursive: true });
    copyFileSync(ROTATE, join(dir, 'scripts', 'rotate-ledger.sh'));
    copyFileSync(SPLITTER, join(dir, 'scripts', 'lib', 'split-ledger.py'));
    // deliberately do NOT provide scripts/check-read-budget.sh
    const r = spawnSync('bash', [join(dir, 'scripts', 'rotate-ledger.sh'), '--check'], {
      encoding: 'utf8',
    });
    expect(r.status).toBe(2);
    expect(r.stdout + r.stderr).toContain('CANNOT TELL');
  });

  it('refuses an unknown mode rather than guessing', () => {
    const r = spawnSync('bash', [ROTATE, '--wat'], { encoding: 'utf8' });
    expect(r.status).not.toBe(0);
  });
});

describe('the instruments are executable IN THE INDEX, not merely on disk', () => {
  // core.fileMode is false in this repo: `chmod +x` succeeds and the file still
  // enters the index 100644, shipping inert. Only the index mode is the truth.
  it.each([['scripts/rotate-ledger.sh'], ['scripts/report-throughput.sh'], ['scripts/lib/split-ledger.py']])(
    '%s is 100755 in the git index',
    (path) => {
      const r = spawnSync('git', ['ls-files', '-s', path], { cwd: REPO, encoding: 'utf8' });
      expect(r.stdout.trim(), `${path} is not tracked`).not.toBe('');
      expect(r.stdout.trim().split(' ')[0]).toBe('100755');
    },
  );
});

describe('every instrument these rules name is GRANTED', () => {
  // Canon: an entry that NAMES an instrument verifies that instrument's GRANT in
  // the same commit. A rule whose tool is denied makes the loop LESS safe than no
  // rule, because it falls back to whatever it can run.
  const settings = readFileSync(join(REPO, '.claude', 'settings.json'), 'utf8');
  it.each([
    ['scripts/rotate-ledger.sh'],
    ['scripts/report-throughput.sh'],
    ['scripts/check-retirement-conditions.sh'],
  ])('%s appears in .claude/settings.json', (script) => {
    expect(settings).toContain(script);
  });

  it('positive control: the matcher can fail', () => {
    expect(settings).not.toContain('scripts/a-script-that-does-not-exist.sh');
  });
});
