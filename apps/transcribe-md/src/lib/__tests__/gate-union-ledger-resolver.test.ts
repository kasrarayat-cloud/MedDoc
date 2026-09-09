// ============================================================================
// THE UNION RESOLVER — AND THE ARMS ARE ABOUT ITS REFUSAL.
// ----------------------------------------------------------------------------
// `RULINGS.md` conflicts resolve as a UNION BY RULING NUMBER (AGENTS.md: "unless
// one side is provably wrong, a conflict in RELAY.md, RULINGS.md, SPEC.md or
// schema.prisma is a UNION, not a choice"), with the POINTER form winning where
// both sides carry the same number (#278 — the pointer reshape).
//
// ⚠️ THE RESOLUTION IS THE EASY HALF. Losing a landed row is SILENT — the file
// still parses, the table still renders, and every other ledger gate stays
// green, because those gates ask whether the rows that ARE there are consistent,
// not whether a row that was there yesterday still is. That is why AGENTS.md
// says to verify a union "by `git diff --numstat` showing 0 REMOVED, not by
// reading the merged file: a section that survived and a section that was
// re-added look identical".
//
// So the product of this script is its REFUSAL, and these arms are about that.
// A resolver that merges correctly and cannot detect a loss is worth nothing
// the third time somebody uses it at midnight.
// ============================================================================
import { execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const SCRIPT = join(__dirname, '..', '..', '..', '..', '..', 'scripts', 'lib', 'union-ledger-conflict.py');

const row = (n: number, cells = 4) =>
  `| 2026-09-08 | #${n} | OWNER-RULING |${' x |'.repeat(cells - 3)} [\`a.md\`](rulings/a.md) |`;

function run(body: string, refs: string[] = []) {
  const dir = mkdtempSync(join(tmpdir(), 'union-'));
  const f = join(dir, 'RULINGS.md');
  writeFileSync(f, body);
  let code = 0;
  let out = '';
  try {
    out = execFileSync('python3', [SCRIPT, f, ...refs], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  } catch (e) {
    const err = e as { status?: number; stdout?: string; stderr?: string };
    code = err.status ?? -1;
    out = `${err.stdout ?? ''}${err.stderr ?? ''}`;
  }
  return { code, out, text: readFileSync(f, 'utf8') };
}

/**
 * ⚠️ A REAL MERGE, WITH ROWS OUTSIDE THE CONFLICT REGION — AND THAT SHAPE IS
 * THE POINT.
 *
 * Every arm here used to run the resolver on a BARE temp file whose entire
 * content was the conflict. Under that fixture the region IS the file, so the
 * whole-file membership check and the region check are the same check, and a
 * resolver that verified only the region looked correct. On the first REAL
 * conflict — hundreds of rows outside the markers — it reported every one of
 * them as INVENTED and refused a perfectly good union.
 *
 * So the fixture now does what a merge does: a base carrying `outside`, two
 * branches that each rewrite one line, and `git merge` to produce genuine
 * stages 2 and 3.
 */
function runMerged(ours: string[], theirs: string[], outside: string[] = [], refs: string[] = []) {
  const dir = mkdtempSync(join(tmpdir(), 'unionmerge-'));
  const git = (...a: string[]) => execFileSync('git', a, { cwd: dir, encoding: 'utf8' });
  git('init', '-q', '-b', 'main');
  git('config', 'user.email', 'a@b.c');
  git('config', 'user.name', 'gate');
  const rel = 'RULINGS.md';
  const f = join(dir, rel);
  const base = ['# L', '', ...outside, 'SLOT', ''].join('\n');
  writeFileSync(f, base);
  git('add', '-A');
  git('commit', '-qm', 'base');
  git('checkout', '-q', '-b', 'theirs');
  writeFileSync(f, base.replace('SLOT', theirs.join('\n')));
  git('commit', '-qam', 'theirs');
  git('checkout', '-q', 'main');
  writeFileSync(f, base.replace('SLOT', ours.join('\n')));
  git('commit', '-qam', 'ours');
  try {
    git('merge', '-q', 'theirs');
  } catch {
    /* the conflict is the point */
  }
  let code = 0;
  let out = '';
  try {
    out = execFileSync('python3', [SCRIPT, rel, ...refs], {
      cwd: dir,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    });
  } catch (e) {
    const err = e as { status?: number; stdout?: string; stderr?: string };
    code = err.status ?? -1;
    out = `${err.stdout ?? ''}${err.stderr ?? ''}`;
  }
  return { code, out, text: readFileSync(f, 'utf8') };
}

const conflict = (ours: string[], theirs: string[]) =>
  ['# L', '', '<<<<<<< HEAD', ...ours, '=======', ...theirs, '>>>>>>> other', ''].join('\n');

describe('union-ledger-conflict — the union', () => {
  it('takes BOTH sides when the numbers are disjoint', () => {
    const r = runMerged([row(1), row(2)], [row(3)]);
    expect(r.code).toBe(0);
    for (const n of [1, 2, 3]) expect(r.text).toContain(`| #${n} |`);
    expect(r.text).not.toMatch(/<<<<<<<|=======|>>>>>>>/);
  });

  it('⚠️ THE POINTER FORM WINS where both sides carry the same number', () => {
    // #278: the index row is a POINTER, never the prose. The reshape's row has
    // FEWER cells, and that is the one that must survive a rebase in either
    // direction — otherwise landing the reshape re-inflates the ledger.
    const prose = row(7, 5);
    const pointer = row(7, 4);
    expect(runMerged([prose], [pointer]).text).toContain(pointer);
    expect(runMerged([prose], [pointer]).text).not.toContain(prose);
  });
});

describe('union-ledger-conflict — THE REFUSAL, which is the product', () => {
  it('⚠️ REFUSES when a ruling on a named ref is missing from the result', () => {
    // The silent failure this exists for: a resolution that drops a landed row.
    // Every other ledger gate stays green on it.
    const dir = mkdtempSync(join(tmpdir(), 'unionrepo-'));
    const git = (...a: string[]) => execFileSync('git', a, { cwd: dir, encoding: 'utf8' });
    git('init', '-q');
    git('config', 'user.email', 'a@b.c');
    git('config', 'user.name', 'gate');
    execFileSync('mkdir', ['-p', join(dir, 'docs', 'foundation')]);
    const led = join(dir, 'docs', 'foundation', 'RULINGS.md');
    // the ref carries #1 and #2 …
    writeFileSync(led, ['# L', '', row(1), row(2), ''].join('\n'));
    git('add', '-A');
    git('commit', '-qm', 'base');

    // … and the conflict offers only #1 on either side, so #2 is DROPPED.
    writeFileSync(led, conflict([row(1)], [row(1)]));
    let code = 0;
    let out = '';
    try {
      out = execFileSync('python3', [SCRIPT, 'docs/foundation/RULINGS.md', 'HEAD'], {
        cwd: dir,
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'pipe'],
      });
    } catch (e) {
      const err = e as { status?: number; stdout?: string; stderr?: string };
      code = err.status ?? -1;
      out = `${err.stdout ?? ''}${err.stderr ?? ''}`;
    }

    expect(code, 'a dropped ruling did not refuse').toBe(2);
    expect(out).toMatch(/LOST vs HEAD: \[2\]/);
    expect(out).toContain('REFUSING');
  });

  it('⚠️ REFUSES on a leftover conflict marker rather than writing a broken file', () => {
    const body = ['# L', '', '<<<<<<< HEAD', row(1), '=======', row(2), '>>>>>>> a', '', '<<<<<<< HEAD', ''].join('\n');
    const r = run(body);
    expect(r.code, 'malformed markers did not refuse').toBe(2);
  });

  it('POSITIVE CONTROL — it does NOT refuse a clean union, or the arms above prove nothing', () => {
    const r = runMerged([row(1)], [row(2)]);
    expect(r.code).toBe(0);
    expect(r.out).toContain('union verified by membership');
  });

  it('⚠️ NAMES THE GUARD THAT IS NOT EXERCISED — presence is not coverage', () => {
    // A mutation disarming the side-local (`ours`/`theirs`) loss check left this
    // gate 6 of 6 GREEN: the merge emits every number from both sides by
    // construction, so no input can trigger it. It is kept as defence against a
    // future edit to that loop, and it is LABELLED in the source so nobody reads
    // its presence as tested coverage. This arm asserts the label survives — the
    // day somebody makes it reachable, they will delete this comment and this
    // arm will tell them to write the real one.
    const src = readFileSync(SCRIPT, 'utf8');
    expect(src, 'the unexercised guard lost its label').toContain('NOT EXERCISED BY ANY ARM');
    // and the guard it defers to IS the one the arms above prove
    expect(src).toContain('LOST vs');
  });

  it('misuse exits 2 with usage, never a traceback', () => {
    let code = 0;
    let out = '';
    try {
      out = execFileSync('python3', [SCRIPT], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
    } catch (e) {
      const err = e as { status?: number; stdout?: string; stderr?: string };
      code = err.status ?? -1;
      out = `${err.stdout ?? ''}${err.stderr ?? ''}`;
    }
    expect(code).toBe(2);
    expect(out).toContain('usage:');
    expect(out, 'a traceback is not a refusal').not.toContain('Traceback');
  });
});

describe('union-ledger-conflict — the dedupe that the conflict region cannot see', () => {
  it('⚠️ DROPS A ROW THAT AUTO-MERGED OUTSIDE THE MARKERS — the gap that cost twice', () => {
    // git auto-merges rows it can reconcile, so a PROSE row can survive outside
    // the markers while this script emits the POINTER row for the same ruling
    // inside them. Both land, and only a downstream ledger gate notices.
    // ⚠️ THROUGH A REAL MERGE, so the prose row is genuinely OUTSIDE the region
    // and stages 2/3 exist. Hand-building the file made the region the whole
    // file, which is the fixture shape that hid the universe defect.
    const r = runMerged([row(1)], [row(9)], [row(9, 5)]);
    expect(r.code).toBe(0);
    const nine = r.text.split('\n').filter((l) => /^\|\s*2026-09-08\s*\|\s*#9\s*\|/.test(l));
    expect(nine, 'the same ruling landed twice').toHaveLength(1);
    expect(nine[0], 'the PROSE row survived instead of the pointer').toBe(row(9));
  });

  it('⚠️ AND IT DOES NOT EAT CLAUSE ROWS — #116 and #131 share a number legitimately', () => {
    // POSITIVE CONTROL, and the one that matters: the ledger records a ruling's
    // own clauses as their own rows under one number. A dedupe keying on the
    // number alone would delete recorded amendments — which is a worse failure
    // than the duplicate it fixes.
    const a = `| 2026-09-08 | #116 | OWNER-RULING | (a) the first clause | [\`x.md\`](rulings/x.md) |`;
    const b = `| 2026-09-08 | #116 | OWNER-RULING | (c) a LATER correction | [\`x.md\`](rulings/x.md) |`;
    const r = runMerged([a], [b]);
    expect(r.code).toBe(0);
    expect(r.text).toContain('(a) the first clause');
    expect(r.text, 'a recorded amendment was deleted as a duplicate').toContain(
      '(c) a LATER correction',
    );
  });
});

describe('union-ledger-conflict — the universe the checks ask about', () => {
  it('⚠️ ROWS OUTSIDE THE REGION ARE NOT "INVENTED" — the refusal that refused a real merge', () => {
    // THE DEFECT: `invented = after - (o | t)` computed `o`/`t` from the CONFLICT
    // REGION. A real ledger conflict has hundreds of rows outside the markers, so
    // every one of them scored as invented and the resolver refused the first
    // genuine merge it was ever pointed at — two regions of ten and seven rows
    // against a 191-ruling file, and it named 175 numbers as invented.
    //
    // No previous arm could see it: they all built the file by hand, so the
    // region WAS the file and the two universes coincided.
    const outside = [3, 4, 5, 6, 7, 8, 10, 11, 12].map((n) => row(n));
    const r = runMerged([row(1)], [row(2)], outside);
    expect(r.out, 'a row outside the markers was called invented').not.toContain('INVENTED');
    expect(r.code, 'a clean union with untouched rows was refused').toBe(0);
    // and every untouched row is still there
    for (const n of [3, 12]) {
      expect(r.text, `row ${n} was dropped`).toContain(`| #${n} |`);
    }
    expect(r.out).toMatch(/whole-file sides: ours=\d+ theirs=\d+/);
  });

  it('⚠️ CANNOT-TELL REFUSES RATHER THAN QUIETLY ANSWERING A SMALLER QUESTION', () => {
    // THE SECOND DEFECT, AND THE WORSE ONE. Invoked from a DIFFERENT repository
    // than the file lives in, `git show :2:<path>` answers about the caller's
    // repo, finds nothing, and the old code fell back to the region-only check
    // WITHOUT SAYING SO. A weaker answer given silently is the shape this repo
    // has a name for.
    //
    // With no merge in progress and no refs there is no whole-file side to
    // verify against, so the only honest outcome is a refusal.
    const r = run(conflict([row(1)], [row(2)]));
    expect(r.code, 'cannot-tell did not refuse').toBe(2);
    expect(r.out).toContain('CANNOT TELL');
    expect(r.out).toContain('REFUSING');
  });
});
