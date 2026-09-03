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
    const fn = call.getSourceFile();
    let takesFirst = false;
    let asserts = false;
    const scan = (n: ts.Node): void => {
      if (
        ts.isElementAccessExpression(n) &&
        ts.isIdentifier(n.expression) &&
        n.expression.text === bound &&
        n.argumentExpression.getText() === '0'
      ) {
        takesFirst = true;
      }
      if (
        ts.isPropertyAccessExpression(n) &&
        ts.isIdentifier(n.expression) &&
        n.expression.text === bound &&
        (n.name.text === 'length' || n.name.text === 'at')
      ) {
        if (n.name.text === 'length') asserts = true;
        else takesFirst = true;
      }
      ts.forEachChild(n, scan);
    };
    scan(fn);
    if (takesFirst && !asserts) return true;
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
    const ownedBy = new Map<string, boolean>();
    for (const line of index.split('\n')) {
      if (!line.startsWith('- ')) continue;
      const pointer = /→\s*`docs\/canon\/([^`]+)`/.exec(line);
      if (pointer) ownedBy.set(pointer[1]!, true);
    }
    const missing = bodies.filter((n) => !ownedBy.has(n));
    expect(
      missing,
      'these canon entries have a body and no index row, so a grep of the ' +
        'index cannot find them',
    ).toEqual([]);
  });
});
