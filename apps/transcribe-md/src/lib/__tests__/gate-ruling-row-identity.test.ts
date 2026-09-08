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

/**
 * ⚠️ TWO ROWS UNDER ONE RULING NUMBER — THE COLLISION NOTHING WAS WATCHING.
 *
 * Ruling #219 settles WHO KEEPS a contested number: *a branch is a claim, a
 * merged row is a fact*, so the row that LANDS FIRST wins and the loser
 * renumbers. What #219 does not do — what no rule can do — is notice when both
 * land.
 *
 * ⚠️ AND THAT IS CANON 73's SHAPE, ONE LEDGER OVER. The canon index already has
 * this guard (`gate-agents-md-size` refuses two bodies under one number); the
 * RULINGS head did not. Two lanes numbering independently BOTH reconcile
 * individually, git merges the two rows cleanly because they are different
 * lines, and the ledger silently carries `#246` twice. Every existing gate stays
 * green: `driftedRows` is satisfied (each row matches its own archive),
 * `gate-ruling-recorded` finds a row for every citation, and the counts add up.
 * **The number simply stops identifying a ruling** — and a session grepping for
 * one gets whichever it reads first.
 *
 * ⚠️ IT IS NOT HYPOTHETICAL. Measured 2026-09-07: this lane pushed its claim of
 * `#246`/`#247` to origin at 17:24:41Z; a peer lane claimed the same `#246` —
 * and the four numbers after it — at 18:12:10Z, 47m29s later, in a branch that
 * is clean and mergeable. Both are legitimate claims by #219's own rule and
 * neither has landed. This arm is what makes the second landing LOUD instead of
 * silent.
 *
 * ⚠️ IT COUNTS **ROOT** ROWS, NOT ROWS, AND THE NAIVE VERSION REDS `main` ON
 * ARRIVAL. Measured before this predicate was written: FIVE numbers already
 * carry more than one row — #106, #109, #115, #116 (three), #131 (three) — and
 * every one of them is legitimate. The ledger records a ruling's own CLAUSES
 * and CORRECTIONS as their own rows under the same number: `(g) — STATICS ARE
 * GUARDED AT THE OUTPUT`, `(a) — #109's SCOPE IS AMENDED`, `b — DD: AND DT:
 * ARE DICTATION AND TRANSCRIPTION DATES`. That is the ledger working, and a
 * gate forbidding it would have to be weakened within a day — canon 114.
 *
 * So the invariant is narrower and is the one that actually matters: **at most
 * ONE ROOT row per number.** A clause row announces itself in the verdict cell;
 * a second ROOT row is two different rulings wearing one number.
 *
 * Returns one message per colliding number; empty means clean.
 */
/** `(g) — …`, `(a) — …`, `b — …`, `(c)-CORRECTED — …`: a clause of an existing
 *  ruling rather than a ruling of its own. */
const CLAUSE_MARKER = /^\(?[a-z]\)?\s*[—-]/i;

export function duplicateRulingNumbers(head: string): string[] {
  const roots = new Map<string, number>();
  for (const row of rowsIn(head)) {
    const cells = row.split('|').map((c) => c.trim());
    // `| <date> | #<n> | <status> | <verdict> | …` -> cells[1..4] after the
    // leading empty cell the pipe produces.
    const n = /^#(\d+)$/.exec(cells[2] ?? '')?.[1];
    const verdict = cells[4] ?? '';
    if (!n) continue;
    if (CLAUSE_MARKER.test(verdict)) continue;
    roots.set(n, (roots.get(n) ?? 0) + 1);
  }
  return [...roots.entries()]
    .filter(([, count]) => count > 1)
    .map(([n, count]) => `ruling #${n} has ${count} ROOT rows in ${HEAD} — two lanes landed the same number; ruling #219 says the FIRST to land keeps it and the other renumbers`)
    .sort();
}

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

describe('⚠️ ONE NUMBER, ONE RULING — the collision two lanes can create and neither can see', () => {
  it('the SHIPPED head carries no duplicate ruling number', () => {
    expect(duplicateRulingNumbers(readFileSync(resolve(REPO, HEAD), 'utf8'))).toEqual([]);
  });

  it('CATCHES two rows under one number — the merge outcome #219 cannot prevent', () => {
    // Different dates, different verdicts, different pointers: git merges these
    // cleanly because they are different LINES, and every other ledger gate
    // stays green because each row matches its own archive.
    const a = '| 2026-09-07 | #246 | OWNER-RULING | **STANDING** — registry | x | [`a`](rulings/a.md) |';
    const b = '| 2026-09-07 | #246 | OWNER-RULING | **STANDING** — scanners | y | [`b`](rulings/b.md) |';
    const found = duplicateRulingNumbers(`${a}\n${b}\n`);
    expect(found).toHaveLength(1);
    expect(found[0]).toContain('#246');
    expect(found[0]).toContain('2 ROOT rows');
  });

  it('⚠️ NON-VACUITY: two DIFFERENT numbers are not a collision', () => {
    // Without this the arm above is satisfied by a predicate that flags any
    // ledger with more than one row in it, which is every ledger.
    const a = '| 2026-09-07 | #246 | OWNER-RULING | **STANDING** — x | x | [`a`](rulings/a.md) |';
    const b = '| 2026-09-07 | #247 | OWNER-RULING | **STANDING** — y | y | [`b`](rulings/b.md) |';
    expect(duplicateRulingNumbers(`${a}\n${b}\n`)).toEqual([]);
  });

  it('⚠️ prose that mentions a number twice is NOT a collision — it reads ROWS', () => {
    expect(duplicateRulingNumbers('see #246 and also #246 in the discussion above\n')).toEqual([]);
  });

  it('⚠️ A CLAUSE ROW IS NOT A COLLISION — and five real numbers depend on that', () => {
    // #106(g), #109(a), #115(b), #116(b)/(c), #131(b)/(c) are all legitimate
    // second and third rows under one number. A predicate that counted ROWS
    // would red `main` on arrival, so it counts ROOT rows and the clause marker
    // in the verdict cell is what distinguishes them.
    const root = '| 2026-08-13 | #106 | OWNER-RULING | CUSTOM-TEMPLATE FIDELITY | x | [`a`](rulings/a.md) |';
    for (const clause of [
      '| 2026-08-13 | #106 | OWNER-RULING | (g) — STATICS ARE GUARDED AT THE OUTPUT | y | [`a`](rulings/a.md) |',
      '| 2026-08-14 | #106 | OWNER-RULING | (a) — SCOPE IS AMENDED | y | [`a`](rulings/a.md) |',
      '| 2026-08-15 | #106 | PROVISIONAL | b — DD: AND DT: ARE DICTATION DATES | y | [`a`](rulings/a.md) |',
      '| 2026-08-15 | #106 | RECORDED | (c)-CORRECTED — THE GOTENBERG COST | y | [`a`](rulings/a.md) |',
    ]) {
      expect(duplicateRulingNumbers(`${root}\n${clause}\n`), clause.slice(40, 70)).toEqual([]);
    }
  });
});

// ⚠️ THE FIXTURE NUMBERS ABOVE ARE REAL, RECORDED RULINGS ON PURPOSE.
// The first draft used three invented numbers in the 990s and
// `scripts/hooks/pre-commit` REFUSED the
// commit: it reads `#NNN` in staged SOURCE as a ruling citation and demands a
// ledger row. That is the record-first rule working exactly as written, on a
// test fixture — so the fixtures use numbers this commit records rather than
// inventing three that will never exist. A synthetic number is still a citation.
