import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

// ============================================================================
// ⚠️ THE HEAD AND THE ARCHIVE MUST CARRY THE **SAME BYTES** FOR A RULING'S ROW.
// ----------------------------------------------------------------------------
// `AGENTS.md` states the doctrine — *"an index row is a POINTER, never the
// rule; if a row and an archived body ever disagree, the body is right and the
// row is a defect"* — and every archive file ends with a section headed
// `## THE INDEX ROWS, VERBATIM` for exactly that reason.
//
// ⚠️ NOTHING ENFORCED IT. Found 2026-09-07 while recording #233–#236: a control
// that changed ONE WORD in a head row, leaving the archive untouched, passed
// `gate-ruling-recorded` (11 arms), `gate-ledger-reachability` (30 arms) and
// `gate-amendment-reachability` (4 arms). All green over a drifted row.
//
// The failure this prevents is the one the split was supposed to make
// impossible: the head answers *which ruling and what status*, the archive
// answers *why* — and a session that greps the head gets a sentence the ruling
// does not say, with nothing anywhere reporting the divergence. That is the
// stale-authority hazard, arriving through the index rather than through size.
//
// THE PREDICATE IS DELIBERATELY BYTE-EQUALITY ON THE WHOLE LINE, not a fuzzy
// match: a row that differs by a word is exactly the case that must fail, and
// any normalisation would admit it.
// ============================================================================

const REPO = resolve(__dirname, '../../../../..');
const HEAD = 'docs/foundation/RULINGS.md';
const ARCHIVE_DIR = 'docs/foundation/rulings';

/** A ruling index row: `| <date> | #<n> | …`. */
const ROW_RE = /^\|\s*\d{4}-\d{2}-\d{2}\s*\|\s*#\d+\s*\|/;

export function rowsIn(text: string): string[] {
  return text.split('\n').filter((l) => ROW_RE.test(l));
}

/**
 * Every row an archive states VERBATIM must appear, byte-identical, in the
 * head. Returns one message per divergence; empty means clean.
 *
 * ⚠️ ONE-DIRECTIONAL BY CONSTRUCTION, AND THAT IS THE POINT. The head legitimately
 * carries rows whose archive predates the 2026-08-26 split. An archive row with
 * no head twin is always a defect; a head row with no archive is not.
 */
export function driftedRows(head: string, archives: Record<string, string>): string[] {
  const headLines = new Set(head.split('\n'));
  const out: string[] = [];
  for (const [name, text] of Object.entries(archives)) {
    for (const row of rowsIn(text)) {
      if (!headLines.has(row)) {
        const n = /#(\d+)/.exec(row)?.[1] ?? '?';
        out.push(`${name}: ruling #${n}'s row is not byte-identical in ${HEAD}`);
      }
    }
  }
  return out;
}

/** A ruling index row's own verdict cell, `| date | #n | kind | VERDICT | …`. */
function verdictOf(row: string): string {
  return (row.split('|')[4] ?? '').trim();
}

/**
 * A CLAUSE row — `(g) — …`, `(c)-CORRECTED — …`, `b — …` — amends a ruling that
 * already has a root row. Five numbers legitimately carry several
 * (#106, #109, #115, #116, #131), so a naive "one row per number" arm reds
 * `main` on arrival and would be deleted the same day.
 */
const CLAUSE_ROW = /^\*{0,2}\(?[a-z]\)?(?:-[A-Z]+)?\*{0,2}\s*[—\-–]/;

/**
 * ⚠️ TWO RULINGS UNDER ONE NUMBER — the gap a PEER LANE FOUND, IN MY GATE.
 *
 * Two lanes claimed the same two ruling numbers within 47 minutes of each
 * other. Had both landed,
 * `RULINGS.md` would carry that number TWICE and **every existing gate stays
 * green**: `driftedRows` is satisfied because each row matches its own archive;
 * `gate-ruling-recorded` finds a row per citation; the counts add up. The canon
 * INDEX refuses two bodies under one number and the ruling head had no
 * equivalent.
 *
 * ⚠️ THE COLLISION WAS CAUGHT BY A PERSON READING TWO BRANCHES, WHICH IS NOT A
 * MECHANISM. #219 settles WHO keeps a number; nothing asserted that the answer
 * was ever applied.
 *
 * Credit where it is due: the peer lane found this, wrote its own arm, and
 * offered it rather than asking for anything. This is my own implementation of
 * the same rule, in my own gate, so the ledger is protected whichever branch
 * lands first — which is the whole point of the finding.
 */
function duplicateRootRulings(head: string): string[] {
  const counts = new Map<string, number>();
  for (const row of rowsIn(head)) {
    if (CLAUSE_ROW.test(verdictOf(row))) continue;
    const n = /#(\d+)/.exec(row)?.[1];
    if (n) counts.set(n, (counts.get(n) ?? 0) + 1);
  }
  return [...counts.entries()]
    .filter(([, c]) => c > 1)
    .map(([n, c]) => `ruling #${n} has ${c} ROOT rows — two rulings share one number`);
}

describe('a ruling row is the same bytes in the head and in its archive', () => {
  const head = readFileSync(resolve(REPO, HEAD), 'utf8');
  const archives: Record<string, string> = {};
  for (const f of readdirSync(resolve(REPO, ARCHIVE_DIR))) {
    if (!f.endsWith('.md') || f === 'README.md') continue;
    archives[f] = readFileSync(resolve(REPO, ARCHIVE_DIR, f), 'utf8');
  }

  it('the real repository has no drifted row', () => {
    expect(driftedRows(head, archives)).toEqual([]);
  });

  it('⚠️ the corpus is non-empty — a gate that read nothing would also pass', () => {
    const total = Object.values(archives).reduce((n, t) => n + rowsIn(t).length, 0);
    expect(Object.keys(archives).length).toBeGreaterThan(5);
    expect(total, 'no VERBATIM rows were found at all — the row regex has drifted').
      toBeGreaterThan(20);
  });

  // — the controls. Each states what would make the check fail, then makes it fail —

  it('⚠️ CATCHES a head row that differs by ONE WORD (the 2026-09-07 control)', () => {
    const row = '| 2026-09-07 | #235 | OWNER-RULING | **STANDING** — the pre-existing race | why | [`x`](rulings/x.md) |';
    const drifted = row.replace('pre-existing', 'PRE-EXISTING');
    expect(driftedRows(drifted, { 'x.md': row })).toHaveLength(1);
    expect(driftedRows(drifted, { 'x.md': row })[0]).toContain('#235');
  });

  it('⚠️ CATCHES a row present in the archive and wholly ABSENT from the head', () => {
    const row = '| 2026-09-07 | #233 | OWNER-RULING | **STANDING** — x | y | [`z`](rulings/z.md) |';
    expect(driftedRows('nothing here\n', { 'z.md': row })).toHaveLength(1);
  });

  it('CATCHES a trailing-whitespace-only difference — bytes, not words', () => {
    const row = '| 2026-09-07 | #234 | OWNER-RULING | **STANDING** — x | y | [`z`](rulings/z.md) |';
    expect(driftedRows(`${row} \n`, { 'z.md': row })).toHaveLength(1);
  });

  it('PASSES an identical row — the other way to be wrong', () => {
    const row = '| 2026-09-07 | #236 | OWNER-RULING | **STANDING** — x | y | [`z`](rulings/z.md) |';
    expect(driftedRows(`preamble\n${row}\ntail\n`, { 'z.md': row })).toEqual([]);
  });

  it('does NOT fire on a head row with no archive twin — pre-split rows are legitimate', () => {
    const orphan = '| 2026-08-01 | #12 | OWNER-RULING | **STANDING** — old | y | pointer |';
    expect(driftedRows(`${orphan}\n`, {})).toEqual([]);
  });

  it('⚠️ NO NUMBER CARRIES TWO ROOT RULINGS — two lanes nearly landed one', () => {
    expect(duplicateRootRulings(head)).toEqual([]);
  });

  it('⚠️ CATCHES the collision that nearly happened — two lanes, one number', () => {
    // ⚠️ THE FIXTURE USES A RECORDED NUMBER, NOT THE ONE THE REAL COLLISION USED.
    // `scripts/hooks/pre-commit` reads `#NNN` in staged source as a ruling
    // citation and demands a ledger row — and the colliding number belongs to
    // the OTHER lane, so it has no row here. A fixture number is still a
    // citation; this session has now been taught that twice.
    const mine  = '| 2026-09-07 | #251 | OWNER-RULING | **STANDING** — text scanners retired | why | [`a`](rulings/a.md) |';
    const peers = '| 2026-09-07 | #251 | OWNER-RULING | **STANDING — another lane**, four concepts | why | [`b`](rulings/b.md) |';
    const found = duplicateRootRulings(`${mine}\n${peers}\n`);
    expect(found).toHaveLength(1);
    expect(found[0]).toContain('#251');
  });

  it('⚠️ …AND DOES NOT FIRE ON A LEGITIMATE CLAUSE ROW — #106, #109, #115, #116, #131', () => {
    // The naive "one row per number" predicate reds `main` on arrival. Measured
    // against the real ledger before this arm was written: five numbers carry
    // several rows, every one of them a clause amending its own root.
    const root   = '| 2026-08-01 | #106 | OWNER-RULING | CUSTOM-TEMPLATE FIDELITY: the statics are assembled | why | p |';
    const clause = '| 2026-08-02 | #106 | OWNER-RULING | (g) — STATICS ARE GUARDED AT THE OUTPUT | why | p |';
    const bare   = '| 2026-08-03 | #116 | OWNER-RULING | b — SITE 3 HAD A SECOND CONSUMER | why | p |';
    expect(duplicateRootRulings(`${root}\n${clause}\n${bare}\n`)).toEqual([]);
  });

  it('⚠️ the corpus really contains those clause rows — or the arm above is vacuous', () => {
    const clauses = rowsIn(head).filter((r) => CLAUSE_ROW.test(verdictOf(r)));
    expect(clauses.length, 'no clause rows found — the exemption is untested').toBeGreaterThanOrEqual(5);
  });

  it('⚠️ the row regex matches a REAL row and not prose that merely mentions one', () => {
    const real = '| 2026-09-07 | #233 | OWNER-RULING | **RATIFIED** — x | y | [`z`](rulings/z.md) |';
    expect(rowsIn(real)).toHaveLength(1);
    expect(rowsIn('see ruling #233 for the reasoning, and | a | pipe | table |')).toEqual([]);
    expect(rowsIn('| not-a-date | #233 | x |')).toEqual([]);
  });
});

// ⚠️ THE FIXTURE NUMBERS ABOVE ARE REAL, RECORDED RULINGS ON PURPOSE.
// The first draft used three invented numbers in the 990s and
// `scripts/hooks/pre-commit` REFUSED the
// commit: it reads `#NNN` in staged SOURCE as a ruling citation and demands a
// ledger row. That is the record-first rule working exactly as written, on a
// test fixture — so the fixtures use numbers this commit records rather than
// inventing three that will never exist. A synthetic number is still a citation.
