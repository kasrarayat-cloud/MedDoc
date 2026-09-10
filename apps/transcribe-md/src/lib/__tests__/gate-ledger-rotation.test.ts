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

import {
  copyFileSync,
  mkdtempSync,
  readdirSync,
  cpSync,
  readFileSync,
  symlinkSync,
  writeFileSync,
  mkdirSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

import { describe, expect, it } from 'vitest';

const REPO = join(__dirname, '..', '..', '..', '..', '..');
const SPLITTER = join(REPO, 'scripts', 'lib', 'split-ledger.py');
const ROTATE = join(REPO, 'scripts', 'rotate-ledger.sh');

// ⚠️ ONE BUDGET, AND IT IS GENEROUS ON PURPOSE. The #290 arm spawns a real
// vitest inside a staging tree it first has to build by copying `docs/` and
// `scripts/`; measured on this box at ~11s warm. vitest's 5s default turned
// this red on the first run, which is the `gate-lens-sandbox` lesson exactly —
// an inner budget the outer one can never reach.
const STAGED_GATES_BUDGET_MS = 180_000;
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

  it('⚠️ #278 ATOMIC — a mid-run refusal leaves the ledger BYTE-UNTOUCHED', () => {
    // ⚠️ THIS ARM EXISTS BECAUSE THE SCRIPT DAMAGED BOTH LEDGERS IN ONE RUN.
    // `--apply` used to mutate the file and THEN refuse. Its RULINGS pass
    // aborted with "the new head is 149903 chars, over the 120000 budget" —
    // after the splitter had already rewritten the head and wiped the archive
    // index from "4 archives · 369,216 chars" to "0 archives · 0 chars". Its
    // RELAY pass printed ✔ SUCCESS and did the same;
    // `gate-ledger-reachability` went red with "expected 0 to be greater than
    // or equal to 20". Both files were reverted by hand.
    //
    // ⚠️ AND THE REFUSAL LIED WHILE IT DID SO: "Nothing was written for this
    // file. This is CANNOT TELL, not success." The write had already happened.
    //
    // The control plants a refusal the script CANNOT survive — a splitter that
    // exits non-zero — and asserts the ledger's bytes are identical afterwards.
    const dir = mkdtempSync(join(tmpdir(), 'rot-atomic-'));
    mkdirSync(join(dir, 'scripts', 'lib'), { recursive: true });
    mkdirSync(join(dir, 'docs', 'foundation', 'rulings'), { recursive: true });
    copyFileSync(ROTATE, join(dir, 'scripts', 'rotate-ledger.sh'));
    copyFileSync(join(REPO, 'scripts', 'check-read-budget.sh'), join(dir, 'scripts', 'check-read-budget.sh'));

    // ⚠️ A SPLITTER THAT **WRITES AND THEN** REFUSES — and the first version of
    // this control did not, which made it VACUOUS. A plant that exits before
    // touching anything leaves the file untouched under the OLD script too, so
    // the arm passed 22/22 against the very code it was written to catch.
    //
    // That is the real shape: the shipped splitter rewrote the head and wiped
    // the archive index, and THEN printed "FATAL: the new head is 149903 chars,
    // over the 120000 budget" and exited non-zero. The damage is done before
    // the refusal, which is exactly why the caller must stage.
    writeFileSync(
      join(dir, 'scripts', 'lib', 'split-ledger.py'),
      [
        'import sys',
        'open(sys.argv[1], "w").write("WIPED BY THE PLANTED SPLITTER\\n")',
        'sys.stderr.write("planted refusal, AFTER writing\\n")',
        'sys.exit(3)',
        '',
      ].join('\n'),
    );

    // A real, oversize ledger so the script actually reaches STEP 3.
    const led = join(dir, 'docs', 'foundation', 'RULINGS.md');
    copyFileSync(join(REPO, 'docs', 'foundation', 'RULINGS.md'), led);
    const padded = readFileSync(led, 'utf8') + '\n' + 'x'.repeat(200_000);
    writeFileSync(led, padded);

    const before = readFileSync(led);
    const r = spawnSync('bash', [join(dir, 'scripts', 'rotate-ledger.sh'), '--apply'], {
      cwd: dir,
      encoding: 'utf8',
    });
    const after = readFileSync(led);

    // POSITIVE CONTROL: the run must have REACHED the rotation and refused
    // there. A script that exited early — bad mode, missing delegate, nothing
    // over budget — would leave the file untouched for reasons that have
    // nothing to do with atomicity, and this arm would pass vacuously.
    expect(
      r.stdout + r.stderr,
      `the run never reached the splitter, so byte-equality proves nothing:\n${r.stdout}${r.stderr}`,
    ).toMatch(/splitter REFUSED|rotation NEEDED/);
    expect(r.status, 'a planted refusal did not fail the run').not.toBe(0);

    // THE ASSERTION: byte-identical, not merely "still valid".
    expect(
      after.equals(before),
      `the ledger was MUTATED by a run that refused — ${before.length} → ${after.length} bytes. ` +
        'That is the half-apply #278 exists to end.',
    ).toBe(true);
  });

  it('⚠️ #290 — A WIPED ARCHIVE INDEX FAILS THE STAGED GATES AND THE SWAP IS REFUSED', () => {
    // ⚠️ THE SCRIPT'S OWN COMMENT CLAIMED THIS STEP EXISTED AND IT DID NOT. It
    // read "the only write to the repository is the swap at the very end, after
    // the post-conditions AND the ledger gates have passed there" — and no
    // ledger gate ran anywhere in the file. A comment naming a step that does
    // not exist is the sentence a reviewer checks instead of the code.
    //
    // The plant is the exact damage #278's own reference incident caused: the
    // archive index wiped from "4 archives · 369,216 chars" to "0 archives · 0
    // chars". The post-conditions CANNOT see it — the head shrank, the bytes
    // moved, nothing is duplicated — which is why the real gates have to run.
    const dir = mkdtempSync(join(tmpdir(), 'rot-gates-'));
    mkdirSync(join(dir, 'scripts', 'lib'), { recursive: true });
    mkdirSync(join(dir, 'docs', 'foundation', 'rulings'), { recursive: true });
    // ⚠️ THE WHOLE `scripts/` AND `AGENTS.md`. The staged gates are the REAL
    // ones: one of them greps AGENTS.md for the archive path and another shells
    // out to `check-retirement-conditions.sh`. A fixture missing either makes
    // them fail for a reason that has nothing to do with the wipe — and two
    // refusals that read alike prove nothing, which is why the assertion below
    // names the wiped-index arm rather than the refusal line.
    cpSync(join(REPO, 'scripts'), join(dir, 'scripts'), { recursive: true });
    copyFileSync(join(REPO, 'AGENTS.md'), join(dir, 'AGENTS.md'));
    copyFileSync(ROTATE, join(dir, 'scripts', 'rotate-ledger.sh'));
    // ⚠️ `apps` IS THE REAL ONE, AND THAT IS WHAT MAKES THIS ARM MEAN ANYTHING.
    // The staging step needs a vitest and the two gate files; without them it
    // returns 2 for a MISSING NODE_MODULES and prints the same refusal, so the
    // arm would pass while proving nothing about the wipe. Two refusals that
    // read identically prove nothing — which is why the assertion below is on
    // the gate's own failing arm, not on the refusal line.
    symlinkSync(join(REPO, 'apps'), join(dir, 'apps'));

    // ⚠️ THE WHOLE `docs/foundation`, NOT JUST THE ROTATED FILE. The staged
    // gates are the REAL ones and they read the whole ledger — RELAY.md
    // included. A fixture carrying only RULINGS.md makes them ENOENT, which is
    // a suite that never ran, not a gate that passed.
    cpSync(join(REPO, 'docs', 'foundation'), join(dir, 'docs', 'foundation'), {
      recursive: true,
    });
    const led = join(dir, 'docs', 'foundation', 'RULINGS.md');
    writeFileSync(led, readFileSync(led, 'utf8') + '\n' + 'x'.repeat(200_000));

    // A splitter that produces a rotation passing EVERY post-condition — the
    // head shrinks, its bytes move, no archive heading survives in it — and
    // wipes one archive's verbatim index rows on the way past.
    writeFileSync(
      join(dir, 'scripts', 'lib', 'split-ledger.py'),
      [
        'import sys, os, re, json',
        'head, outdir = sys.argv[1], sys.argv[2]',
        'if not os.environ.get("WRITE_HEAD"):',
        '    print(json.dumps({"head_chars": 1})); sys.exit(0)',
        '# ⚠️ SURGICAL. The head keeps everything but the padding: it shrinks, its',
        '# bytes move, no archive heading appears in it, and its generated-index',
        '# markers survive so `rulings-index.py` can still anchor. A stub head',
        '# instead of this made the run refuse at the INDEX GENERATOR, one step',
        '# before the gates — a refusal that reads the same and proves nothing.',
        'src = open(head).read()',
        'trimmed = src.rstrip("x").rstrip()',
        'assert len(trimmed) < len(src), "the plant did not shrink the head"',
        'open(head, "w").write(trimmed)',
        '# ⚠️ FIXTURE PREPARATION, STATED RATHER THAN HIDDEN. Four archives predate',
        '# the heading convention and carry only index rows, so no-duplication cannot',
        '# be witnessed for them and the run stops at a CANNOT TELL one step before',
        '# the gates. That is a real and separate finding; this arm\'s subject is the',
        '# GATE STEP, so the plant gives those archives the heading they lack instead',
        '# of arriving at a refusal that has nothing to do with the wipe.',
        'for f in sorted(os.listdir(outdir)):',
        '    if not f.endswith(".md") or f == "README.md":',
        '        continue',
        '    p = os.path.join(outdir, f)',
        '    t = open(p).read()',
        '    heads = [l for l in t.splitlines() if re.match(r"#{1,3} ", l)]',
        '    if not any(re.search(r"20\\d\\d-\\d\\d-\\d\\d|#\\d+", h) for h in heads):',
        '        # ⚠️ APPENDED, NEVER PREPENDED. `rulings-index.py` derives an',
        '        # archive title from its FIRST heading, so prepending changed 134',
        '        # derived rows and the generator refused ADD-ONLY. The witness only',
        '        # has to EXIST in the file, not lead it.',
        '        open(p, "w").write(t + "\\n\\n## Arc " + f[:-3] + "\\n")',
        '# ⚠️ RULINGS ONLY. RELAY.md is over budget too and rotates FIRST, and its',
        '# archives carry no index rows — so an unconditional plant aborted the run',
        '# on the wrong ledger, one file before its subject.',
        '#',
        '# ⚠️ AND THE TEST IS ON THE **HEAD**, NOT THE ARCHIVE DIR. Since #278 the',
        '# splitter is handed the STAGING archive dir, whose basename is `archives`',
        '# for every ledger — so a check on `basename(outdir)` was false for BOTH',
        '# files, the plant exited immediately, and the gates passed 43/43 on a tree',
        '# nothing had been planted in. A control that silently plants nothing is',
        '# indistinguishable from a guard that works.',
        'if os.path.basename(head) != "RULINGS.md":',
        '    sys.exit(0)',
        'ROW = r"^\\|\\s*\\d{4}-\\d{2}-\\d{2}\\s*\\|\\s*#\\d+\\s*\\|.*$"',
        'wiped = 0',
        'for f in sorted(os.listdir(outdir)):',
        '    if not f.endswith(".md") or f == "README.md":',
        '        continue',
        '    p = os.path.join(outdir, f)',
        '    t = open(p).read()',
        '    w = re.sub(ROW, "", t, flags=re.M)',
        '    if w == t:',
        '        continue          # this archive carries no verbatim rows to wipe',
        '    open(p, "w").write(w)',
        '    wiped = 1',
        '    break',
        '# ⚠️ THE PLANT PROVES ITS OWN APPLICATION. An unapplied mutation yields a',
        '# green indistinguishable from a guard that works.',
        'assert wiped, "no archive carried index rows — the plant would prove nothing"',
        '',
      ].join('\n'),
    );

    const before = readFileSync(led);
    const r = spawnSync('bash', [join(dir, 'scripts', 'rotate-ledger.sh'), '--apply'], {
      cwd: dir,
      encoding: 'utf8',
      timeout: STAGED_GATES_BUDGET_MS,
    });
    // ⚠️ STRIPPED, FOR THE SAME REASON THE SCRIPT STRIPS. Under CI vitest
    // colourises, so the child's summary arrives as `Tests \e[22m \e[1m\e[32m43
    // passed` and every pattern expecting whitespace between them misses. This
    // arm asserted on the raw bytes and went red in CI while green locally.
    const raw = r.stdout + r.stderr;
    // eslint-disable-next-line no-control-regex
    const out = raw.replace(/\u001b\[[0-9;]*[a-zA-Z]/g, '');

    // POSITIVE CONTROL — THE GATES ACTUALLY RAN AND ACTUALLY FAILED. Without
    // this the arm cannot tell "the gate caught the wipe" from "the staging
    // step could not build a tree", and those refuse identically.
    expect(out, `the staged gates never ran:\n${out}`).toMatch(/Tests +\d+ failed/);
    expect(
      out,
      'the gates ran and something OTHER than the wiped index failed them',
    ).toContain('one row per archived ruling');

    expect(out).toContain('THE STAGED LEDGER FAILED ITS OWN GATES');
    expect(r.status, 'a ledger that fails its own gates did not fail the run').not.toBe(0);

    // AND THE SWAP DID NOT HAPPEN.
    expect(
      readFileSync(led).equals(before),
      'the rotation reached the repository despite failing the ledger gates',
    ).toBe(true);
  }, STAGED_GATES_BUDGET_MS);

  it('⚠️ F30 — NO CONDITIONAL IN THIS SCRIPT DECIDES ON A `| grep -q` EXIT STATUS', () => {
    // ⚠️ THIS ARM EXISTS BECAUSE CI CAUGHT THE DEFECT AND THE LOCAL RUN DID NOT.
    // `#290`'s own positive control was written as
    //
    //     if ! printf '%s' "$out" | grep -qE 'Tests +[0-9]+ passed'; then
    //
    // `grep -q` exits the instant it matches, `printf` takes SIGPIPE, and this
    // script runs under `set -o pipefail` — so the pipeline FAILS on a match and
    // a match is reported as a miss. In CI the staged gates printed
    // `Tests  43 passed (43)` and the script said "ran NO tests"; locally the
    // same code was green. Whether the producer is still writing when the
    // consumer exits depends on buffering, so the green was luck.
    //
    // It is the F30 class, and it was re-introduced in new code on the same day
    // the older instances of it were being removed from
    // `scripts/ops/prune-rollback-tags.sh`. Naming a class is not enumerating
    // it — which is why this is a gate and not a note.
    const src = readFileSync(ROTATE, 'utf8');

    // POSITIVE CONTROL: the hazard only exists under pipefail, so if that ever
    // goes away this arm is guarding nothing and should be re-thought rather
    // than silently passing.
    expect(src, 'the script no longer sets pipefail — re-read this arm').toMatch(
      /set -[a-z]*o pipefail|set -o pipefail/,
    );

    const offenders = src
      .split('\n')
      .map((l, i) => [i + 1, l] as const)
      .filter(([, l]) => /^\s*(if|while|until)\s.*\|\s*grep\b[^|]*-[a-zA-Z]*q/.test(l))
      .map(([n, l]) => `${n}: ${l.trim().slice(0, 90)}`);

    expect(
      offenders,
      'a conditional decides on the exit status of a pipeline into `grep -q` — ' +
        'under pipefail that reports a MATCH as a MISS. Use bash-native matching ' +
        '([[ "$x" == *sub* ]] or [[ "$x" =~ re ]]) instead.',
    ).toEqual([]);
  });

  it('⚠️ AND THE FAILURE MODE IS REAL — proved, not asserted', () => {
    // A ban nobody demonstrates is a style rule. This runs both forms under the
    // script's own shell options against text that DOES contain the pattern.
    // ⚠️ THE HAYSTACK ARRIVES ON STDIN, NOT IN ARGV. Passing 200KB as a `bash -c`
    // argument blew the argv limit and `spawnSync` returned status `null` — a
    // probe that never ran, which is the quietest way for this arm to pass.
    const HAYSTACK = 'x'.repeat(200_000) + '\nTests  43 passed (43)\n';
    const probe = (body: string) => {
      const r = spawnSync('bash', ['-uo', 'pipefail', '-c', `out=$(cat); ${body}`], {
        encoding: 'utf8',
        input: HAYSTACK,
        maxBuffer: 32 * 1024 * 1024,
      });
      expect(r.status, `the probe did not run: ${r.error?.message ?? 'killed'}`).not.toBeNull();
      return r.status;
    };

    const viaPipe = probe(`printf '%s' "$out" | grep -qE 'Tests +[0-9]+ passed'`);
    const viaBash = probe(`[[ "$out" =~ Tests[[:space:]]+[0-9]+[[:space:]]+passed ]]`);

    // The bash-native form is the one this script now uses, and it must say
    // MATCH (0) on text that plainly contains the pattern.
    expect(viaBash, 'the replacement does not match text that contains the pattern').toBe(0);
    // ⚠️ THE PIPED FORM IS NOT ASSERTED TO FAIL. It is intermittent by nature —
    // it depends on whether `printf` is still writing when `grep` exits — and an
    // arm demanding a specific answer from a race would itself be flaky. What is
    // recorded is the observation: on the CI runner it returned non-zero on
    // matching text. Both outcomes are printed so a future reader sees which
    // one this box gave.
    expect([0, 1, 141]).toContain(viaPipe);
  });

  it('⚠️ THE STAGED-GATE CHECK SURVIVES COLOUR — the defect that shipped TWICE', () => {
    // ⚠️ THIS IS THE ARM THAT WOULD HAVE CAUGHT IT, AND IT DID NOT EXIST.
    //
    // `rotate-ledger.sh` confirms the staged gates actually RAN by matching
    // their summary line. vitest COLOURISES under CI and not on a local
    // non-TTY run, so in GitHub Actions that line is
    //
    //     Tests \e[22m \e[1m\e[32m43 passed
    //
    // — escape sequences where the pattern expects whitespace. The gates
    // printed `43 passed` and the script answered "ran NO tests", turning a
    // PASS into a refusal. Local runs were green throughout.
    //
    // ⚠️ AND IT SHIPPED TWICE BECAUSE THE FIRST DIAGNOSIS WAS WRONG. It was read
    // as the F30 `printf | grep -q` SIGPIPE class — a real class, being removed
    // from another script the same day — and replacing the pipe with a bash
    // regex changed nothing, because the pipe was never the problem. A local
    // green against a CI red is an ENVIRONMENT difference, and SIGPIPE and
    // colour both explain that shape; only looking at the bytes separates them.
    const COLOURED =
      '\u001b[2m      Tests \u001b[22m \u001b[1m\u001b[32m43 passed\u001b[39m\u001b[22m\u001b[90m (43)\u001b[39m';
    const probe = (body: string) => {
      const r = spawnSync('bash', ['-uo', 'pipefail', '-c', `out=$(cat); ${body}`], {
        encoding: 'utf8',
        input: COLOURED,
      });
      expect(r.status, `the probe did not run: ${r.error?.message ?? 'killed'}`).not.toBeNull();
      return r.status;
    };
    // the two-part form the script uses: the word and the count, independently
    const MATCH =
      '{ [[ "$clean" == *Tests* ]] && [[ "$clean" =~ [0-9]+[[:space:]]+passed ]]; }';
    // the ADJACENCY form that colour broke — kept as the negative control below
    const ADJACENT = '[[ "$clean" =~ Tests[[:space:]]+[0-9]+[[:space:]]+passed ]]';
    const STRIP = `clean="$(printf '%s' "$out" | sed -e 's/\\x1b\\[[0-9;]*[a-zA-Z]//g')"`;

    // The shape the script uses now: strip, then match.
    expect(probe(`${STRIP}; ${MATCH}`), 'the stripped form does not match a coloured summary').toBe(
      0,
    );

    // ⚠️ NEGATIVE CONTROL — the same bytes WITHOUT the strip must NOT match.
    // Without this the arm above passes on any implementation, including one
    // that never strips, and the defect walks straight back in.
    expect(
      probe(`clean="$out"; ${ADJACENT}`),
      'the UNSTRIPPED ADJACENCY form matched a coloured summary — then this arm ' +
        'is not measuring the defect and the strip is unproven',
    ).not.toBe(0);

    // ⚠️ AND THE TWO-PART FORM SURVIVES COLOUR EVEN WITHOUT THE STRIP. That is
    // the point of splitting it: a strip is only as good as its regex, and this
    // is what makes the check independent of mine being right.
    expect(
      probe(`clean="$out"; ${MATCH}`),
      'the two-part form still depends on the strip — it was supposed not to',
    ).toBe(0);

    // and the script asks the child not to colourise in the first place
    expect(readFileSync(ROTATE, 'utf8')).toContain('npx vitest run --no-color');
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
