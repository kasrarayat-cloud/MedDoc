// ============================================================================
// #172(5) — CANON 62's FOURTH INSTANCE GETS A MECHANISM, NOT A FIFTH SWEEP.
// ----------------------------------------------------------------------------
// ⚠️ THE ARGUMENT IS A COUNT. The "unscoped find on a non-unique predicate"
// laundering was found and fixed FOUR times in one arc — twice in the renderer
// suite, twice in the product suite — and the fourth instance was live in the
// very arm that had just been re-armed for the third, in a file whose own
// header states the rule 650 lines above. Writing a rule down is not obeying
// it; that is already canon, and it is why this is a test.
//
// ⚠️ AND YES, THIS IS A SOURCE-TEXT GATE, WHICH CANON 72 WARNS ABOUT. The
// warning is against pinning a SPELLING when the property is behavioural. Here
// the property IS a source shape — "this call selects one of many matches and
// then reasons about it as though it were the only one" — and there is no
// runtime observable for it. A lint is the right instrument for a lint.
// ============================================================================
import { readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const APP = resolve(__dirname, '..', '..', '..');
const REPO = resolve(APP, '..', '..');

/** Test files whose forgeries and selections this rule governs. */
const GATE_DIRS = [
  join(APP, 'src', 'lib', 'note-template-docx', '__tests__'),
  join(APP, 'src', 'lib', 'template-twin', '__tests__'),
];

/**
 * Every `find`-family CALL SITE in a source text, with its argument list
 * whitespace-normalised.
 *
 * ⚠️ #173 — CALL SITES, NOT LINES, AND THE REASON IS MEASURED. The first
 * version applied a single-line regex per line. Prettier wraps any call long
 * enough to matter, so it saw NONE of the four real offenders in its own
 * watched directories and reported a clean zero.
 */
function findCallSites(text: string): { snippet: string; line: number }[] {
  const sites: { snippet: string; line: number }[] = [];
  const opener = /\.find(?:Last|Index|LastIndex)?\(/g;
  let match: RegExpExecArray | null;
  while ((match = opener.exec(text))) {
    let depth = 0;
    let i = match.index + match[0].length - 1;
    for (; i < text.length; i += 1) {
      if (text[i] === '(') depth += 1;
      else if (text[i] === ')') {
        depth -= 1;
        if (depth === 0) break;
      }
    }
    sites.push({
      snippet: text.slice(match.index, i + 1).replace(/\s+/g, ' '),
      line: text.slice(0, match.index).split('\n').length,
    });
  }
  return sites;
}

/**
 * A selection on a LABEL CLASS — `kind` — rather than a unique key.
 *
 * `fieldId`/`originalLabel` comparisons are deliberately not matched: they
 * select one thing because one thing exists.
 */
function selectsOnLabelClass(snippet: string): boolean {
  if (!/(?:\.kind|\['kind'\]|\bkind\b)\s*(?:===|!==)/.test(snippet)) return false;
  // ⚠️ A CONJUNCTION WITH A UNIQUE KEY IS A KEYED SELECTION, NOT A CLASS ONE.
  // `find(p => p.kind === 'filled' && p.fieldId === target.fieldId)` selects
  // one thing because one thing exists; flagging it would train the next
  // reader to silence this gate rather than obey it, which is how a lint dies.
  return !/\b(?:fieldId|originalLabel|styleId)\s*===/.test(snippet);
}

/**
 * ⚠️ COMMENTS ARE STRIPPED FIRST, AND NEWLINES ARE PRESERVED SO LINE NUMBERS
 * STAY TRUE.
 *
 * This file is full of prose ABOUT the forbidden shape — the arms that document
 * past laundering quote `proofs.find(kind === 'emptied')` verbatim. Without
 * stripping, the gate reports its own documentation as an offence, which trains
 * the next reader to silence it. (The same defect appeared in an adversarial
 * lens's own instrument the day before: a parser that matched quotes inside a
 * block comment and returned four lines of prose as data.)
 */
function stripComments(text: string): string {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
    .replace(/(^|[^:])\/\/[^\n]*/g, (m, lead: string) => lead + ' '.repeat(m.length - lead.length));
}

function offendersIn(text: string): { snippet: string; line: number }[] {
  return findCallSites(stripComments(text)).filter((site) =>
    selectsOnLabelClass(site.snippet),
  );
}

describe('#173 — the lint scans CALL SITES, and its control touches a FILE', () => {
  it('⚠️ THE CONTROL RUNS AGAINST A FIXTURE ON DISK, not a string in memory', () => {
    // ⚠️ THIS IS THE ARM THE PREVIOUS VERSION LACKED, AND ITS ABSENCE IS WHY
    // THAT VERSION WAS A NO-OP WITH GREEN CONTROLS. Repointing the scan at
    // filenames instead of contents left both of its in-memory controls
    // passing. A control that never touches a file cannot guard files.
    const fixture = readFileSync(
      join(__dirname, '__fixtures__', 'lint-offender.fixture.txt'),
      'utf8',
    );
    // ⚠️ THE FIXTURE CARRIES COMMENTS TOO, so this control also proves the
    // comment-stripping does not swallow real code.
    const found = offendersIn(fixture);
    // the fixture holds exactly two offenders, both WRAPPED or non-`find`,
    // plus one unique-key selection that must NOT be flagged.
    expect(found.map((f) => f.line).length, 'the scanner missed the planted offenders').toBe(2);
    expect(found.every((f) => /kind/.test(f.snippet))).toBe(true);
    expect(
      found.some((f) => /fieldId/.test(f.snippet)),
      'a unique-key selection was wrongly flagged',
    ).toBe(false);
  });

  it('every gate file is clean', () => {
    const offenders: string[] = [];
    let scanned = 0;
    for (const dir of GATE_DIRS) {
      for (const name of readdirSync(dir)) {
        if (!name.endsWith('.test.ts')) continue;
        scanned += 1;
        for (const site of offendersIn(readFileSync(join(dir, name), 'utf8'))) {
          offenders.push(`${name}:${site.line}  ${site.snippet.slice(0, 110)}`);
        }
      }
    }
    // ⚠️ THE FLOOR IS TIED TO THE REAL CORPUS. It was `> 10` against an actual
    // 55, so deleting an entire watched directory passed. This is a ratchet:
    // the count may grow, never shrink unopposed.
    expect(scanned, 'the watched corpus shrank — a zero here is not health').
      toBeGreaterThanOrEqual(55);
    expect(
      offenders,
      'a find() on `kind` selects one of many matches and then reasons about ' +
        'it as the only one. Scope it (filter + an explicit count) or use ' +
        '`theOnlyMatch`, which refuses ambiguity.',
    ).toEqual([]);
  });
});

describe('#172(5) — every canon BODY has its INDEX ROW', () => {
  it('nothing checks that — now something does', () => {
    // ⚠️ THE RULE HAS EXISTED ALL ALONG AND WAS MISSED IN THIS VERY ARC: canon
    // 94's body landed and its index row did not, caught only by re-reading the
    // commit. An entry whose row is missing is an entry a grep of the index
    // cannot reach — the exact pointer failure the index exists to prevent.
    // ⚠️ #173 — SLICED AT THE INDEX, NOT GREPPED WHOLE. The first version
    // searched all of `AGENTS.md`, so an entry cited anywhere — canon 61 is
    // quoted in the LIVE-RULES section — stayed green with BOTH of its index
    // rows deleted. The arm's own message claims to be checking the index, and
    // it was not.
    const agents = readFileSync(join(REPO, 'AGENTS.md'), 'utf8');
    const marker = '## CANON INDEX';
    const at = agents.indexOf(marker);
    expect(at, 'the CANON INDEX heading moved — this arm is anchored on it').
      toBeGreaterThan(0);
    const index = agents.slice(at);
    const bodies = readdirSync(join(REPO, 'docs', 'canon'))
      .filter((n) => /^\d+-.*\.md$/.test(n))
      .sort();
    // ⚠️ FLOOR TIED TO THE REAL CORPUS, as a ratchet: it may grow, never shrink
    // unopposed. `> 50` against a real 90+ let half the corpus vanish unnoticed.
    expect(bodies.length, 'the canon corpus shrank — a zero here is not health').
      toBeGreaterThanOrEqual(bodies.length > 0 ? 90 : 0);
    const missing = bodies.filter((n) => !index.includes(n));
    expect(
      missing,
      'these canon entries have a body and no index row, so a grep of the ' +
        'index cannot find them',
    ).toEqual([]);
  });
});
