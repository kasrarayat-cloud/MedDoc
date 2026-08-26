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

import { copyFileSync, mkdtempSync, readdirSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
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

// ⚠️ THE SPLITTER IS PROVED AGAINST A SYNTHETIC LEDGER, NOT THE REAL ONE.
// These arms first drove docs/foundation/RELAY.md directly and asserted things
// like "archives > 5". The split then landed, RELAY.md went 1,830,324 -> 20,317,
// and six arms went red for the one reason that is not a defect: THE FILE GOT
// BETTER. A gate whose fixture is the thing under repair breaks every time the
// repair works, and rotation will shrink this file again and again by design.
//
// So the mechanism is proved on a fixture built here — big enough to force many
// archives and a sub-section split — and the REAL ledger keeps exactly one arm,
// asserting the durable invariant: it stays readable in one read.
function buildSyntheticLedger(dir: string): string {
  const L: string[] = ['# FOUNDATION — the relay ledger', '', 'preamble.', ''];
  L.push('## Rules', '', 'rules body.', '');
  L.push('## Invariants re-checked every item', '', 'invariants body.', '');
  const filler = 'x'.repeat(400);
  for (let d = 4; d <= 26; d++) {
    const day = `2026-08-${String(d).padStart(2, '0')}`;
    L.push(`## ✅ ITEM ${d} — SOMETHING LANDED — ${day}`, '');
    for (let k = 0; k < 12; k++) L.push(`### sub ${d}.${k}`, '', filler, '');
  }
  // one deliberately oversize single section, to exercise sub-section chunking
  L.push('## 🟢 A VERY LARGE SINGLE SECTION — 2026-08-27', '');
  for (let k = 0; k < 60; k++) L.push(`### big ${k}`, '', 'y'.repeat(2000), '');
  const p = join(dir, 'RELAY.md');
  writeFileSync(p, L.join('\n'));
  return p;
}

function runSplitter(script: string, outDir: string, env: Record<string, string> = {}, target?: string) {
  const src = target ?? buildSyntheticLedger(mkdtempSync(join(tmpdir(), 'synth-')));
  return spawnSync('python3', [script, src, outDir], {
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
  it('GREEN: splits a ledger with every proof passing, and non-vacuously', () => {
    const dir = mkdtempSync(join(tmpdir(), 'synth-'));
    const src = buildSyntheticLedger(dir);
    const r = runSplitter(SPLITTER, outDir(), { DRY_RUN: '1' }, src);
    expect(r.status, r.stderr).toBe(0);
    const d = JSON.parse(r.stdout);

    // NON-VACUITY: it must have processed the whole fixture, not an empty one.
    const actual = [...readFileSync(src, 'utf8')].length;
    expect(d.source_chars).toBe(actual);
    expect(d.archives).toBeGreaterThan(5);
    expect(d.proof.P3_src_headings).toBeGreaterThan(200);

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

describe('the generated head REPLACES its index, never appends', () => {
  // Canon: a regeneration that prepends and never deletes leaves a file holding
  // every value you assert, syntactically dead — and the newest on top reads as
  // the only one. Rotation regenerates this block on every run, so an appending
  // generator would grow an index of stale indexes.
  function splitCopy(dir: string) {
    const relay = buildSyntheticLedger(dir);
    const r = spawnSync('python3', [SPLITTER, relay, join(dir, 'relay')], {
      encoding: 'utf8',
      maxBuffer: 64 * 1024 * 1024,
      env: { ...process.env, LIFT, WRITE_HEAD: '1' },
    });
    expect(r.status, r.stderr).toBe(0);
    return { relay, out: JSON.parse(r.stdout) };
  }

  it('writes a head under budget, with exactly one index block', () => {
    const dir = mkdtempSync(join(tmpdir(), 'head-'));
    const { relay, out } = splitCopy(dir);
    expect(out.proof.P6_head_under_budget).toBe(true);
    const head = readFileSync(relay, 'utf8');
    expect(head.split('ARCHIVE-INDEX-BEGIN').length - 1).toBe(1);
    expect(head.split('ARCHIVE-INDEX-END').length - 1).toBe(1);
    // NON-VACUITY: the index must actually name archives, not be an empty shell.
    expect(head).toMatch(/\| \[`20\d\d-\d\d-\d\d[^`]*\.md`\]/);
    // It must carry BOTH: a TITLE (the durable pointer, since a line number in an
    // append-only file is stale before it lands) AND the FROZEN pre-split line
    // span (the one legitimate use of a line number here — that file can never
    // grow again, so every pre-existing RELAY.md:NNNNN citation still resolves).
    expect(head).toContain('first section (TITLE — the durable pointer)');
    expect(head).toContain('pre-split lines');
    expect(head).toMatch(/\|\s*\d+–\d+\s*\|/); // an en-dashed frozen span
  });

  it('IDEMPOTENT: a second run replaces the index rather than adding another', () => {
    const dir = mkdtempSync(join(tmpdir(), 'head2-'));
    const { relay } = splitCopy(dir);
    const r = spawnSync('python3', [SPLITTER, relay, join(dir, 'relay2')], {
      encoding: 'utf8',
      maxBuffer: 64 * 1024 * 1024,
      env: { ...process.env, LIFT, WRITE_HEAD: '1' },
    });
    expect(r.status, r.stderr).toBe(0);
    const head = readFileSync(relay, 'utf8');
    expect(head.split('ARCHIVE-INDEX-BEGIN').length - 1).toBe(1);
  });

  it('RED: a half-present marker pair is refused rather than guessed at', () => {
    const dir = mkdtempSync(join(tmpdir(), 'head3-'));
    const { relay } = splitCopy(dir);
    // amputate the END marker — the delete boundary is now ambiguous
    writeFileSync(relay, readFileSync(relay, 'utf8').replace('<!-- ARCHIVE-INDEX-END -->', ''));
    const r = spawnSync('python3', [SPLITTER, relay, join(dir, 'relay3')], {
      encoding: 'utf8',
      maxBuffer: 64 * 1024 * 1024,
      env: { ...process.env, LIFT, WRITE_HEAD: '1' },
    });
    expect(r.status).not.toBe(0);
    expect(r.stdout + r.stderr).toContain('refusing to guess the boundary');
  });
});

describe('the real ledgers stay readable — the durable invariant', () => {
  // The only arm that touches the real files. It asserts the OUTCOME of the
  // split rather than any particular size, so rotation shrinking them further
  // can never break it.
  it.each([['docs/foundation/RELAY.md'], ['docs/foundation/RULINGS.md']])(
    '%s fits one read and carries no stale OVERSIZE banner',
    (rel) => {
      const txt = readFileSync(join(REPO, rel), 'utf8');
      expect([...txt].length).toBeLessThan(150_000);
      expect(txt.split('\n').slice(0, 60).join('\n')).not.toContain('READ-PROTOCOL: OVERSIZE');
    },
  );

  it('every archived body is itself readable in one read', () => {
    for (const d of ['relay', 'rulings']) {
      const dir = join(REPO, 'docs', 'foundation', d);
      const files = readdirSync(dir).filter((f) => f.endsWith('.md') && f !== 'README.md');
      expect(files.length, `${d}/ has no archives`).toBeGreaterThan(0);
      for (const f of files) {
        expect([...readFileSync(join(dir, f), 'utf8')].length, `${d}/${f}`).toBeLessThan(150_000);
      }
    }
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
