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

import ts from 'typescript';
import { describe, expect, it } from 'vitest';

const APP = resolve(__dirname, '..', '..', '..');
const REPO = resolve(APP, '..', '..');

/** Test files whose forgeries and selections this rule governs. */
const GATE_DIRS = [
  join(APP, 'src', 'lib', 'note-template-docx', '__tests__'),
  join(APP, 'src', 'lib', 'template-twin', '__tests__'),
];

/**
 * #174 — THE LINT STOPS HAND-PARSING AND ASKS THE COMPILER.
 *
 * ⚠️ THE HOUSE LESSON "STOP WRITING PARSERS" APPLIES TO LINTS TOO, and this one
 * proved it twice in two days. The line-based version missed all four real
 * offenders because they were wrapped. Its replacement — paren matching plus a
 * hand-rolled comment stripper — was measured to:
 *
 *   · run to EOF when `//` appeared inside a STRING literal (the stripper
 *     blanked the closing `);`), and then be EXONERATED by a legitimate keyed
 *     selection further down the file;
 *   · blank real code when a string contained `/*`;
 *   · red on the forbidden shape quoted inside a string — the exact "trains the
 *     next reader to silence the gate" failure the stripping was added to stop.
 *
 * The TypeScript AST has none of those failure modes: comments and string
 * literals are not call expressions, and a call's argument list is a node, not
 * a bracket-counting exercise.
 */
interface Offender {
  readonly file: string;
  readonly line: number;
  readonly snippet: string;
}

const SELECTOR_NAMES = new Set(['find', 'findLast', 'findIndex', 'findLastIndex']);

/** Does this expression compare a `kind`-like label rather than a unique key? */
function comparesLabelClass(node: ts.Node): boolean {
  let label = false;
  let key = false;
  const walk = (n: ts.Node): void => {
    if (ts.isBinaryExpression(n)) {
      const op = n.operatorToken.kind;
      if (
        op === ts.SyntaxKind.EqualsEqualsEqualsToken ||
        op === ts.SyntaxKind.ExclamationEqualsEqualsToken
      ) {
        const text = `${n.left.getText()} ${n.right.getText()}`;
        if (/\bkind\b/.test(text)) label = true;
        if (/\b(?:fieldId|originalLabel|styleId)\b/.test(text)) key = true;
      }
    }
    ts.forEachChild(n, walk);
  };
  walk(node);
  return label && !key;
}

/**
 * ⚠️ `filter(...)[0]` IS INCLUDED, AND IT IS THE ONE THAT MATTERS MOST: it is
 * this gate's OWN remediation advice — "filter + an explicit count" — MINUS the
 * count. A reader complying with the message could land the identical defect.
 * `.at(0)` and a destructured `const [only] =` are the same shape.
 */
function isUncountedFirstOfFilter(call: ts.CallExpression): boolean {
  const parent = call.parent;
  if (ts.isElementAccessExpression(parent) && parent.expression === call) return true;
  // ⚠️ #175 — THE TWO-STATEMENT FORM, WHICH IS THE SPELLING THE HOUSE ACTUALLY
  // WRITES. All three compliant sites in this corpus are
  // `const m = xs.filter(...);` followed by `m[0]` / `m.at(0)` — so the version
  // that only saw the single-expression `filter(...)[0]` was blind to the
  // idiom it was written to police. A `filter` bound to a name whose FIRST
  // element is then taken, with no length assertion in between, is the same
  // uncounted selection.
  if (ts.isVariableDeclaration(parent) && ts.isIdentifier(parent.name)) {
    const bound = parent.name.text;

    // ⚠️ #175 FINAL PASS — THE ESCAPE IS NOW AN EXPLICIT MARKER, NOT AN
    // INFERENCE, AND IT IS SCOPED AND ORDERED. The previous form scanned the
    // WHOLE source file for any `<bound>.length`, by identifier text, with no
    // scope and no ordering. Eleven probes through this same function measured
    // it wrong in BOTH directions:
    //
    //   FALSE NEGATIVES (an offender called clean) — a same-named variable in
    //   ANOTHER function carrying the `.length`; `.length` as a truthiness
    //   guard (`if (rows.length) return rows[0]`); `.length` as a for-loop
    //   bound; a `.length` asserted AFTER the take; a weak
    //   `toBeGreaterThan(0)`.
    //   FALSE POSITIVES (clean code called an offender) — a compliant site plus
    //   an unrelated same-named `rows[0]` elsewhere in the file; `.at(3)`
    //   counted as taking the first because the argument was ignored.
    //
    // In situ: planting a genuine offender in a watched gate file left the gate
    // GREEN because `refused.length` appeared elsewhere in that file; renaming
    // the variable to `zzRows` — same code — redded it. The gate's zero was a
    // fact about a variable's NAME. `rows`, `fields`, `refused` and `proofs`
    // are exactly the names this corpus reuses across dozens of `it()` blocks.
    //
    // ⚠️ SO THE SEMANTIC QUESTION IS ABANDONED RATHER THAN REFINED (canon 75).
    // Deciding whether a `.length` reference constitutes an ASSERTION is the
    // judgement that was falsified five times; the next counterexample always
    // exists. The escape now requires the one spelling that cannot mean
    // anything else — `expect(<bound>.length` — inside the SAME enclosing
    // function, textually BEFORE the take. A guard, a loop bound and a later
    // assertion are all correctly refused, because none of them is that.
    const scope: ts.Node =
      (function enclosing(n: ts.Node): ts.Node {
        const up = n.parent;
        if (!up) return n;
        if (
          ts.isFunctionDeclaration(up) ||
          ts.isFunctionExpression(up) ||
          ts.isArrowFunction(up) ||
          ts.isMethodDeclaration(up)
        ) {
          return up;
        }
        return enclosing(up);
      })(parent);

    let takeAt: number | null = null;
    let assertAt: number | null = null;
    const scan = (n: ts.Node): void => {
      // `bound[0]` — the argument must BE zero; `.at(3)` is not taking first.
      if (
        ts.isElementAccessExpression(n) &&
        ts.isIdentifier(n.expression) &&
        n.expression.text === bound &&
        n.argumentExpression.getText() === '0' &&
        (takeAt === null || n.getStart() < takeAt)
      ) {
        takeAt = n.getStart();
      }
      if (
        ts.isCallExpression(n) &&
        ts.isPropertyAccessExpression(n.expression) &&
        ts.isIdentifier(n.expression.expression) &&
        n.expression.expression.text === bound &&
        n.expression.name.text === 'at' &&
        n.arguments.length === 1 &&
        n.arguments[0]!.getText() === '0' &&
        (takeAt === null || n.getStart() < takeAt)
      ) {
        takeAt = n.getStart();
      }
      // the ONLY accepted discharge: `expect(<bound>.length` …
      if (
        ts.isCallExpression(n) &&
        ts.isIdentifier(n.expression) &&
        n.expression.text === 'expect' &&
        n.arguments.length > 0 &&
        ts.isPropertyAccessExpression(n.arguments[0]!) &&
        ts.isIdentifier(n.arguments[0]!.expression) &&
        (n.arguments[0]! as ts.PropertyAccessExpression).expression.getText() === bound &&
        (n.arguments[0]! as ts.PropertyAccessExpression).name.text === 'length' &&
        (assertAt === null || n.getStart() < assertAt) &&
        // ⚠️ AND AN "AT LEAST" MATCHER DOES NOT DISCHARGE IT. The gate's own
        // message asks for an EXPLICIT COUNT; `toBeGreaterThan(0)` asserts only
        // that the set is non-empty, so `rows[0]` can still be one of several —
        // the exact laundering this predicate exists to police, wearing the
        // remediation's clothes. This is a CLOSED list of matchers that bound
        // the count from below only, not a pinned spelling: `toBe`,
        // `toEqual`, `toHaveLength` and the rest all still discharge.
        !(
          ts.isPropertyAccessExpression(n.parent) &&
          /^toBeGreaterThan(OrEqual)?$/.test(n.parent.name.text)
        )
      ) {
        assertAt = n.getStart();
      }
      ts.forEachChild(n, scan);
    };
    scan(scope);
    if (takeAt !== null && (assertAt === null || assertAt > takeAt)) return true;
  }
  if (
    ts.isPropertyAccessExpression(parent) &&
    parent.name.text === 'at' &&
    ts.isCallExpression(parent.parent)
  ) {
    return true;
  }
  if (ts.isVariableDeclaration(parent) && ts.isArrayBindingPattern(parent.name)) return true;
  return false;
}

function offendersIn(file: string, text: string): Offender[] {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true);
  const found: Offender[] = [];
  const visit = (node: ts.Node): void => {
    if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)) {
      const method = node.expression.name.text;
      const selects =
        SELECTOR_NAMES.has(method) ||
        (method === 'filter' && isUncountedFirstOfFilter(node));
      if (selects && node.arguments.some((arg) => comparesLabelClass(arg))) {
        found.push({
          file,
          line: source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1,
          snippet: node.getText(source).replace(/\s+/g, ' ').slice(0, 110),
        });
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return found;
}

describe('#174 — the lint asks the COMPILER, and its control touches a FILE', () => {
  it('⚠️ THE CONTROL RUNS AGAINST A FIXTURE ON DISK, not a string in memory', () => {
    const path = join(__dirname, '__fixtures__', 'lint-offender.fixture.txt');
    const found = offendersIn(path, readFileSync(path, 'utf8'));
    // FOUR offenders now — a wrapped `find`, a `findLast`, a single-expression
    // `filter(...)[0]`, and the TWO-STATEMENT form — plus a unique-key
    // selection, a comment and a string holding the shape, none of which may be
    // flagged.
    expect(found.length, 'the scanner missed the planted offenders').toBe(4);
    expect(
      found.some((f) => /fieldId/.test(f.snippet)),
      'a unique-key selection was wrongly flagged',
    ).toBe(false);
  });

  it('a comment or a string containing the shape is NOT an offender', () => {
    // ⚠️ THE TWO FALSE POSITIVES THE HAND-ROLLED VERSION HAD. Both are settled
    // by asking the compiler: neither a comment nor a string literal is a call.
    const probe = [
      "// proofs.find((p) => p.kind === 'emptied') — described, not written",
      "const message = \"proofs.find((p) => p.kind === 'emptied')\";",
      "const ok = list.find((f) => f.fieldId === wanted);",
    ].join('\n');
    expect(offendersIn('probe.ts', probe)).toEqual([]);
    // NON-VACUITY: the same shape as real code IS an offender.
    expect(
      offendersIn('probe.ts', "const x = list.find((f) => f.kind === 'filled');").length,
    ).toBe(1);
  });

  // ⚠️ THE LINT'S OWN BEHAVIOUR IS NOW WATCHED, IN BOTH DIRECTIONS.
  //
  // "Every gate file is clean" is a fact about the CORPUS. It says nothing
  // about whether the predicate works, and the pass measured that it did not:
  // eleven probes found FIVE false negatives and TWO false positives, and the
  // in-situ demonstration was worse than either number. A genuine offender
  // planted in a watched gate file left this gate GREEN — because
  // `refused.length` appears twelve times elsewhere in that file — and
  // renaming the variable to `zzRows`, with the code otherwise identical,
  // redded it. The gate's zero was a fact about a variable's NAME.
  //
  // A predicate with no probes of its own is a green that means "nobody wrote
  // the shape I happen to catch". These rows are the acceptance.
  const PROBES: ReadonlyArray<readonly [string, string, number]> = (() => {
    const F = 'xs.filter((f) => f.kind === "emptied")';
    return [
      // ── FALSE NEGATIVES the file-wide, unordered, name-only scan allowed ──
      ['a same-named variable in ANOTHER function carries the count',
       `function a(){const rows=${F};return rows[0];}
        function b(){const rows=${F};expect(rows.length).toBe(1);return rows;}`, 1],
      ['.length as a truthiness guard is not an assertion',
       `function a(){const rows=${F};if(rows.length)return rows[0];return null;}`, 1],
      ['.length as a for-loop bound is not an assertion',
       `function a(){const rows=${F};for(let i=0;i<rows.length;i++){}return rows[0];}`, 1],
      ['a count asserted AFTER the take does not discharge it',
       `function a(){const rows=${F};const x=rows[0];expect(rows.length).toBe(1);return x;}`, 1],
      ['an "at least" matcher does not bound the count',
       `function a(){const rows=${F};expect(rows.length).toBeGreaterThan(0);return rows[0];}`, 1],
      // ── FALSE POSITIVES it produced on correct code ──
      ['a compliant site plus an unrelated same-named take elsewhere',
       `function a(){const rows=${F};expect(rows.length).toBe(1);return rows[0];}
        function b(){const rows=[1,2];return rows[0];}`, 0],
      ['.at(3) is not taking the first',
       `function a(){const rows=${F};return rows.at(3);}`, 0],
      // ── CONTROLS, so a predicate that flagged NOTHING could not pass ──
      ['CONTROL — the compliant two-statement form', 
       `function a(){const rows=${F};expect(rows.length).toBe(1);return rows[0];}`, 0],
      ['CONTROL — a keyed find is not an offender',
       `function a(){return ir.fields.find((f) => f.fieldId === wantedId);}`, 0],
      ['CONTROL — the single-expression offender',
       `function a(){return ${F}[0];}`, 1],
      ['CONTROL — the destructured offender',
       `function a(){const [only]=${F};return only;}`, 1],
      ['CONTROL — an uncounted .at(0)',
       `function a(){const rows=${F};return rows.at(0);}`, 1],
    ] as const;
  })();

  it('⚠️ THE PREDICATE ITSELF IS PROBED — five past false negatives, two false positives', () => {
    const wrong = PROBES.flatMap(([name, code, expected]) => {
      const got = offendersIn('probe.ts', code).length;
      return got === expected ? [] : [`${name}: expected ${expected}, got ${got}`];
    });
    expect(
      wrong,
      'the lint disagrees with its own acceptance — a zero from it is a fact ' +
        'about the shapes it happens to catch, not about the corpus',
    ).toEqual([]);
  });

  // ⚠️ NON-VACUITY FOR THE TABLE ITSELF: it must contain rows of BOTH verdicts,
  // or a predicate stuck on one answer would pass the arm above.
  it('⚠️ the probe table exercises both verdicts', () => {
    expect(PROBES.filter(([, , n]) => n === 1).length).toBeGreaterThanOrEqual(5);
    expect(PROBES.filter(([, , n]) => n === 0).length).toBeGreaterThanOrEqual(4);
  });

  it('every gate file is clean', () => {
    const offenders: string[] = [];
    let scanned = 0;
    for (const dir of GATE_DIRS) {
      for (const name of readdirSync(dir)) {
        if (!name.endsWith('.test.ts')) continue;
        scanned += 1;
        const full = join(dir, name);
        for (const site of offendersIn(full, readFileSync(full, 'utf8'))) {
          offenders.push(`${name}:${site.line}  ${site.snippet}`);
        }
      }
    }
    // ⚠️ FLOOR TIED TO THE REAL CORPUS, as a ratchet.
    expect(scanned, 'the watched corpus shrank — a zero here is not health').
      toBeGreaterThanOrEqual(55);
    expect(
      offenders,
      'a selector on `kind` picks one of many matches and then reasons about ' +
        'it as the only one. Use filter + an EXPLICIT COUNT, or `theOnlyMatch`.',
    ).toEqual([]);
  });
});

describe('#172(5) — every canon BODY has its INDEX ROW', () => {
  // ⚠️ NO TEST READS AN ABSOLUTE HOST PATH. Ratified after a whole ten-ruling
  // arc met CI for the first time in one push and produced exactly one red:
  // a gate that opened `/opt/meddoc-pro/WM IOV Template.docx`. It had passed
  // locally for days — the VPS working tree IS `/opt/meddoc-pro` — and on a
  // runner the repo lives elsewhere, so the read is ENOENT.
  //
  // ⚠️ THE HAZARD IS THAT IT LOOKS FINE FROM WHERE IT WAS WRITTEN. A path that
  // is correct on the authoring machine and nowhere else is invisible to every
  // local instrument, including a full green suite; only a different checkout
  // location disagrees, and the fix by hit would have been one line.
  //
  // Comments and strings that merely NAME the path are fine — dozens of them
  // document VPS layout. What is refused is a filesystem CALL taking one.
  it('⚠️ NO TEST OPENS AN ABSOLUTE HOST PATH — it passes only where it was written', () => {
    const offenders: string[] = [];
    let scanned = 0;
    const walk = (dir: string): void => {
      for (const e of readdirSync(dir, { withFileTypes: true })) {
        const full = join(dir, e.name);
        if (e.isDirectory()) {
          if (e.name === 'node_modules' || e.name === '.next') continue;
          walk(full);
        } else if (/\.(test|spec)\.tsx?$/.test(e.name)) {
          scanned += 1;
          const text = readFileSync(full, 'utf8');
          // strip comments first, or this gate reports its own documentation
          const code = text
            .replace(/\/\*[\s\S]*?\*\//g, '')
            .replace(/^[ \t]*\/\/.*$/gm, '');
          // a read/open/stat whose argument STARTS with an absolute host root
          const re = /\b(?:readFileSync|readFile|createReadStream|openSync|statSync|existsSync)\s*\(\s*['"`]\/(?:opt|home|Users|var|srv)\//g;
          if (re.test(code)) offenders.push(full.replace(APP + '/', ''));
        }
      }
    };
    walk(join(APP, 'src'));
    walk(join(APP, 'tests'));
    // ⚠️ NON-VACUITY: the walk must actually have read files, or an empty
    // offender list is a fact about the walk (canon 20 — every zero is your
    // instrument until proven otherwise).
    expect(scanned, 'the walk found no test files at all').toBeGreaterThanOrEqual(200);
    expect(
      offenders,
      'these read an absolute host path, so they pass only on a machine whose ' +
        'checkout happens to live there — resolve from __dirname instead',
    ).toEqual([]);
  });

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
    // ⚠️ #174 — THE UNCONDITIONAL FORM, AND THE OLD ONE WAS SELF-REFERENTIAL.
    // I wrote `toBeGreaterThanOrEqual(bodies.length > 0 ? 90 : 0)`, which
    // compares a value to a bound derived from itself: 88 bodies redded
    // correctly, and ZERO BODIES PASSED — all three arms green with
    // `docs/canon/` emptied of every entry. The message said "a zero here is
    // not health" and the `: 0` branch exempted exactly zero. The lint's floor
    // 33 lines above was already the correct shape.
    expect(bodies.length, 'the canon corpus shrank — a zero here is not health').
      toBeGreaterThanOrEqual(90);
    // ⚠️ A HEADLINE ROW, NOT A MENTION ANYWHERE IN THE REGION — canon 33, text
    // presence is not membership. Deleting an entry's own `- **…**` row while
    // leaving a `↳` sub-row that points at the same file used to pass, and 22
    // of 96 entries carry more than one reference, so ~23% of the corpus could
    // lose its headline pointer undetected.
    // ⚠️ #175 — ANCHORED ON THE ENTRY'S OWN ROW, BLIND TO CROSS-REFERENCES.
    // The previous version asked whether the filename appeared in ANY headline
    // row, so canon 31 passed with its own row deleted — because canon 74's row
    // links to it. A row belongs to the entry whose POINTER it ends with, which
    // is the `→ \`docs/canon/…\`` at the end of the line; an inline
    // `[canon 31](…)` mid-sentence is a citation, not a row.
    // ⚠️ ROWS ARE REASSEMBLED BEFORE THEY ARE READ, because a row is a logical
    // unit and `\n` is not its boundary. The previous form tested
    // `line.startsWith('- ')`, so a markdown reflow that wrapped a row's
    // pointer onto a continuation line dropped that row from the map and redded
    // with *"these canon entries have a body and no index row"* — naming a
    // cause that is not the one. A gate whose failure message misdirects costs
    // more than the reflow it is complaining about.
    const rows: string[] = [];
    for (const line of index.split('\n')) {
      if (/^\s*- /.test(line)) rows.push(line);
      else if (rows.length > 0 && line.trim() !== '') rows[rows.length - 1] += ' ' + line.trim();
    }
    const ownedBy = new Map<string, boolean>();
    for (const row of rows) {
      // headline rows only — an indented `↳` sub-row belongs to its parent.
      if (!row.startsWith('- ')) continue;
      const pointer = /→\s*`docs\/canon\/([^`]+)`/.exec(row);
      if (pointer) ownedBy.set(pointer[1]!, true);
    }
    const missing = bodies.filter((n) => !ownedBy.has(n));
    expect(
      missing,
      'these canon entries have a body and no index row, so a grep of the ' +
        'index cannot find them',
    ).toEqual([]);

    // ⚠️ AND THE OTHER DIRECTION, WHICH NOTHING WATCHED. The arm above asks
    // "does every body have a row?". A row pointing at a file that does not
    // exist is the same pointer failure with the arrow reversed — a reader
    // greps the index, finds the entry, follows the pointer and lands on
    // nothing — and it was invisible. Renaming a canon file without updating
    // its row would have passed.
    const bodySet = new Set(bodies);
    const dangling = [...ownedBy.keys()].filter((n) => !bodySet.has(n));
    expect(
      dangling,
      'these index rows point at canon files that do not exist — the pointer ' +
        'resolves to nothing for anyone who follows it',
    ).toEqual([]);

    // ⚠️ NON-VACUITY: the reassembly must actually have found rows, or both
    // directions above are comparing empty sets and agreeing.
    expect(ownedBy.size, 'no index rows were parsed at all').toBeGreaterThanOrEqual(90);
  });
});
