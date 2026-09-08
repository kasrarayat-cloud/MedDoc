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

/**
 * A ruling index row: `| <date> | #<n> | …` — and `#<n>(<part>)` too.
 *
 * ⚠️ WIDENED BY #273, BECAUSE THE NARROWER FORM SILENTLY DROPPED A REAL ROW.
 * `#\d+\s*\|` requires the number to be followed immediately by the cell
 * boundary, so `| 2026-09-02 | #162(c) | …` — which exists on `main` at
 * `docs/foundation/RULINGS.md:278` — did not match. Measured before the change:
 * this regex saw **169** rows and the guard being retired saw **170**, and the
 * one it could not see was that row.
 *
 * That is the whole reason #273's "fold any UNIQUE arm before deleting" clause
 * is not a formality: the coverage difference between the two guards was not an
 * ARM at all, it was a REGEX, and no arm on either side would have reported it.
 */
const ROW_RE = /^\|\s*\d{4}-\d{2}-\d{2}\s*\|\s*#\d+(?:\([a-z0-9]{1,2}\))?\s*\|/i;

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
    // ⚠️ THE PART SUFFIX IS PART OF THE KEY, PRESERVING THE RETIRED GUARD'S
    // SEMANTICS EXACTLY. `gate-ledger-reachability` took the cell verbatim, so
    // `#162(c)` was its own key and could never collide with `#162`. Measured:
    // `#162(c)` is the ONLY parenthesised row on `main` and there is NO plain
    // `#162` row, so it is a standalone ruling recorded under its part letter —
    // not a clause of something else. Folding it into `162` would invent a
    // collision that does not exist.
    const n = /^#(\d+(?:\([a-z0-9]{1,2}\))?)$/i.exec(cells[2] ?? '')?.[1];
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

// ═══════════════════════════════════════════════════════════════════════════
// FOLDED IN FROM `gate-ledger-reachability` BY RULING #273 — ONE GUARD.
// ---------------------------------------------------------------------------
// #265(b) said "the first on `main` stays, the other lane deletes its copy on
// rebase". Both had already merged, so there was no other lane and no race, and
// #273 settled it on MERIT instead: this file is the exported,
// separately-controlled implementation, so it is the one that survives.
//
// ⚠️ "FOLD ANY ARM UNIQUE TO THE OTHER" IS THE HALF THAT CAN GO WRONG SILENTLY,
// AND THE ENUMERATION IS THE EVIDENCE. The retired describe had SIX arms. Read
// one at a time against this file:
//
//   1 · base-row uniqueness             -> ALREADY COVERED (duplicateRulingNumbers)
//   2 · every AMENDMENT has a base row  -> UNIQUE, folded below
//   3 · its non-vacuity companion       -> UNIQUE, folded below
//   4 · a part letter is never reused   -> UNIQUE, folded below
//   5 · base + parts === rows.length    -> TAUTOLOGICAL, dropped, said so
//   6 · parts > 0 (the shape is in use) -> UNIQUE, folded into arm 4's file
//
// ⚠️ AND THE LARGEST DIFFERENCE WAS NOT AN ARM AT ALL — it was `ROW_RE`, which
// saw 169 rows against the retired guard's 170. See its comment above.
const PART_CAPTURE = /^\(?([a-z0-9]{1,2})\)?[-\s)]*(?:—|-)/;

const headText = () => readFileSync(resolve(REPO, HEAD), 'utf8');
const archiveText = (): string[] =>
  readdirSync(resolve(REPO, ARCHIVE_DIR))
    .filter((f) => f.endsWith('.md'))
    .map((f) => readFileSync(resolve(REPO, ARCHIVE_DIR, f), 'utf8'));

/** Head rows as `{num, title}` — the retired guard's own shape. */
function headRows(): Array<{ num: string; title: string }> {
  return rowsIn(headText()).map((l) => {
    const c = l.split('|').map((x) => x.trim());
    return { num: c[2] ?? '', title: c[4] ?? '' };
  });
}

describe('#273 — the arms folded across before the weaker guard was deleted', () => {
  it('⚠️ every AMENDMENT cited has a base row — structure, not range', () => {
    // Head + EVERY archive: an amendment may be cited in either, and reading
    // only the head is the 2026-08-26 split's own failure mode. The first draft
    // of this arm (in its old home) read the head alone and produced 24 FALSE
    // accusations, including #100, #103, #106 and #109, because their base rows
    // had been ARCHIVED. An instrument that reads one path answers about one path.
    const corpus = [headText(), ...archiveText()].join('\n');
    const amended = new Set([...corpus.matchAll(/#(\d+)\s*\([a-z]\)/g)].map((m) => m[1]!));
    const base = new Set([
      ...headRows()
        .filter((r) => !PART_CAPTURE.test(r.title))
        .map((r) => r.num.replace(/^#/, '').replace(/\(.*$/, '')),
      ...[...corpus.matchAll(/^\|\s*[0-9]{4}-[0-9]{2}-[0-9]{2}\s*\|\s*\*?\*?#(\d+)/gm)].map(
        (m) => m[1]!,
      ),
    ]);

    // POSITIVE CONTROLS — without these an empty set difference is green for
    // the wrong reason: the arm looked at nothing.
    expect(
      amended.size,
      'no amendments extracted — the pattern found nothing, so this arm proves nothing',
    ).toBeGreaterThanOrEqual(20);
    expect(base.size, 'no base rows extracted').toBeGreaterThanOrEqual(50);

    const orphaned = [...amended].filter((n) => !base.has(n)).sort();
    expect(
      orphaned,
      'these amendments are cited with no base ruling row — the #162(b) shape: ' +
        'the amendment is readable and the thing it amends is not',
    ).toEqual([]);
  });

  it('⚠️ NON-VACUITY — the arm above CAN fail, proved on a synthetic corpus', () => {
    // "0 violations" is otherwise indistinguishable from "the check does
    // nothing". A real amendment number, with its base row withheld.
    const amended = new Set(['162']);
    const base = new Set(['163', '164']);
    expect([...amended].filter((n) => !base.has(n))).toEqual(['162']);
    // ...and it passes when the base IS present, so it is not always-red either.
    expect([...amended].filter((n) => !new Set(['162', '163']).has(n))).toEqual([]);
  });

  it('a part letter is never reused within one ruling number', () => {
    // ⚠️ NEEDED ITS OWN CAPTURING PATTERN. `CLAUSE_MARKER` above is a SKIP
    // predicate with no capture group, so it can say "this is a clause" and not
    // "which clause" — and this arm is entirely about which.
    const seen = new Map<string, string[]>();
    for (const r of headRows()) {
      const m = PART_CAPTURE.exec(r.title);
      if (!m) continue;
      seen.set(r.num, [...(seen.get(r.num) ?? []), m[1]!]);
    }
    const dupes = [...seen.entries()]
      .map(([n, v]) => [n, v.filter((x, i) => v.indexOf(x) !== i)] as const)
      .filter(([, v]) => v.length > 0);
    expect(dupes.map(([n, v]) => `${n}: ${v.join(',')}`)).toEqual([]);
  });

  it('⚠️ the multi-part shape really IS in use, and the head is populated', () => {
    // The retired arm asserted `base + parts === rows.length`, which is
    // TAUTOLOGICAL — `base` was DEFINED as `rows.length - parts`. Dropped, and
    // replaced with the two claims it was standing in front of: the corpus is
    // real, and the part shape this file's CLAUSE_MARKER exists for is actually
    // exercised by it.
    const rows = headRows();
    expect(rows.length, 'the head is not populated — every arm above is vacuous').toBeGreaterThan(40);
    expect(
      rows.filter((r) => PART_CAPTURE.test(r.title)).length,
      'no part rows — the clause-skip logic is untested by the live corpus',
    ).toBeGreaterThan(0);
  });

  it('⚠️ ROW_RE SEES `#162(c)` — the row the retired guard saw and this one did not', () => {
    // The regression control for the widening. Before #273 this file's ROW_RE
    // matched 169 rows and the retired guard 170; the difference was this row.
    const rows = rowsIn(headText());
    expect(rows.some((l) => l.includes('| #162(c) |')), 'the parenthesised row is invisible again').toBe(true);
    // and it is its OWN key, never folded into #162 — measured: there is no
    // plain #162 row, so folding would invent a collision.
    expect(duplicateRulingNumbers(headText())).toEqual([]);
  });
});
