// ============================================================================
// C1-e — the Controls contract: the table and the shipped class layer must not
// disagree.
// ----------------------------------------------------------------------------
// `docs/design-tokens.md` § Controls is the NAMING CONTRACT for the
// `qm-rounds-*` control layer. Until this file, nothing compared it to the
// product, and the section says so in its own words: "THIS TABLE HAS NO GUARD,
// AND THAT IS HOW IT DRIFTED... It lands with C1-e."
//
// The drift it is named for: `.qm-rounds-authform` shipped with a CSS rule
// (`rounds-tokens.css`), a consumer (`auth-shell.tsx`) and a mention inside
// another gate's own comment — and appeared in NO row of the table for three
// merges. Every OTHER invariant held. `gate-c1d-auth` pins CSS ↔ TSX in both
// directions, so the stylesheet and the product could not disagree; they simply
// both disagreed with the document that is supposed to name them. **A contract
// that cannot fail is a description.**
//
// ─── THE INVARIANT ──────────────────────────────────────────────────────────
//
//   (1) every class NAMED IN THE TABLE resolves to a real rule in
//       `rounds-tokens.css`  — the row that rots; and
//   (2) every CONTROL PRIMITIVE THAT SHIPS appears in the table
//       — the `-authform` drift.
//
// Both are covered. (2) is the one that needs an argument, because the
// stylesheet declares 95 `qm-rounds-*` classes and only ~22 of them belong in
// this table.
//
// ─── WHAT "CONTROL PRIMITIVE" MEANS, AND WHY IT IS DERIVED ──────────────────
//
// A control primitive is a class that
//
//   (a) has a rule in `rounds-tokens.css`, and
//   (b) is applied by at least one .tsx file OUTSIDE the Rounds-native screens.
//
// The Rounds-native screens are `src/components/rounds/` and `src/app/board/` —
// the two places where Rounds COMPOSES A SCREEN OF ITS OWN. Everywhere else the
// skin RESTYLES A SURFACE THAT ALREADY EXISTED, and the vocabulary it uses to do
// that is exactly what § Controls documents: the bridge, the surface markers and
// the controls. `-board-grid`, `-strip-node`, `-gateflow-step`, `-signed-trail`
// are the internal anatomy of two new screens; they are not a naming contract
// anyone builds against, and dragging them into this table would make it a
// second copy of the stylesheet.
//
// Measured, that boundary partitions the layer 22 / 73 with exactly one
// leftover, and the leftover is informative rather than awkward — see the
// `-devstates` test below. It is asserted from BOTH sides (neither side may
// collapse), so a boundary that silently swallowed the whole layer — which
// would make direction (2) vacuous — reddens instead.
//
// ⚠️ REJECTED ALTERNATIVES, because the next reader will reach for them:
//
//   • **A hand-written list of control classes.** That is the thing the drift
//     was made of. It would also have to be edited by the same change that
//     forgets to edit the table, so it can never catch that change.
//   • **A positional split on the stylesheet** — "everything declared after the
//     `── Control primitives ──` banner". Derived, but from a COMMENT: moving a
//     banner silently changes what is guarded, and C2 adding a board rule below
//     the line would be mis-filed as a control with no way to tell.
//   • **"Dual-skin files are adopters"** (a file that branches on
//     `isSkinRounds()` or still carries a `qm-lin-*`/`qm-c3-*` class). This one
//     was actually measured and it is WRONG: `settings/page.tsx`,
//     `profile-form.tsx` and both dialogs apply their Rounds classes
//     UNCONDITIONALLY — they are inert with the flag off because every rule is
//     `[data-skin='rounds']`-scoped — and `src/components/skeleton.tsx` neither
//     branches nor carries an old-skin class while being a C1 adopter. It
//     mis-files four adopter files as native and would have hidden `-select`,
//     `-settings`, `-dialog` and `-dialog-overlay` from direction (2): the four
//     classes C1-e just shipped, invisible to the guard written for C1-e.
//   • **Naming shape** (`-btn` is a primitive, `-strip-node` is anatomy).
//     `-kbd`, `-sheet` and `-stage` are single-segment Phase-B classes and
//     `-dialog-overlay` is a two-segment control. There is no signal in the name.
//
// The failure mode this boundary DOES have, stated plainly: a Rounds-native
// screen that lands outside those two directories gets its anatomy flagged as
// undocumented primitives. That is a loud red with a message naming both
// remedies, not a silent pass — and it is arguably the right answer anyway,
// since a new class layer on an existing product surface genuinely does owe the
// contract a row.
//
// ─── THE COMMENT TRAP, WHICH BIT TWICE WHILE THIS FILE WAS BEING WRITTEN ────
//
// `gate-rounds-bridge.test.ts:332` reads raw file TEXT, so a class named in a
// COMMENT counts as applied. Both of this file's derivations strip comments
// first, and the CSS side proves it on real shipped bytes: `.qm-rounds-btn-danger`
// exists ONLY inside a comment in `rounds-tokens.css` (C1-e wrote the class,
// its own gate rejected it, and the comment records why). It must not be in the
// declared set. That is a fact about the product, not a fixture.
//
// ⚠️ AND THE STRIPPER ITSELF IS A TRAP. The first draft stripped `{/* … */}`
// with a dedicated rule BEFORE the plain block-comment rule. `\{\s*\/\*` also
// matches an ordinary object literal that opens with a comment —
// `const x = {\n  /* … */\n  a: 1,\n}` — and the closing `\*\/\s*\}` then has to
// hunt for the NEXT `*/` that is followed by `}`, swallowing everything in
// between. It silently ate five live classes (`-auth`, `-stage`, `-strip`,
// `-strip-list`, `-strip-now`) out of the applied set. An over-eager comment
// stripper is a SILENT UNDER-COUNT: direction (2) simply stops seeing part of
// the layer and stays green. The block rule alone already handles `{/* … */}` —
// the braces sit outside the comment, so stripping the comment leaves `{}`.
//
// ⚠️ CORRECTED WHILE MUTATION-TESTING THIS FILE, AND THE ERROR IS WORTH MORE
// THAN THE FACT. This block first said: "comment-stripping removes NOTHING from
// the .tsx tree — no class is currently mentioned only in a comment there, so
// the tree cannot prove the stripper works." That was measured, and it was
// measured WRONG: the check compared the SET of classes found with and without
// stripping, and the set is unchanged. What changes is WHICH FILE each class is
// attributed to — and this guard's whole boundary is per-file.
//
// Deleting the block-comment rule and re-running says it plainly.
// `settings/security/mfa/mfa-management-panel.tsx` carries a JSX comment
// reasoning about the success-pill's colour, and it names
// `.qm-rounds-signed-lock` — a Phase-B SIGNED-SCREEN class it does not render.
// Unstripped, that class reads as applied on a settings surface, is promoted
// out of the Rounds-native set into the control layer, and direction (2)
// demands a § Controls row for a board class that has never been near a
// settings page. **A guard fabricating its own finding**, which is the shape
// `ErrorFallback` has when a preview mount POSTs `/api/client-errors`.
//
// So the trap is live in this tree, not hypothetical, and there is a real
// control for it below beside the fixture. The general lesson is the one the
// wrong measurement teaches: an aggregate that does not move is not evidence
// that nothing moved. Ask the question at the granularity the guard uses.
// ============================================================================

import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const CSS_PATH = 'src/app/rounds-tokens.css';
const DOC_PATH = '../../docs/design-tokens.md';
const SELF_PATH = 'src/lib/__tests__/gate-controls-contract.test.ts';

/** Build a class name without ever writing it as a literal. The prose in this
 *  file names two classes on purpose; the assertions about that prose must not
 *  reintroduce them as code, or the control tests itself rather than the
 *  stripper. */
const cls = (suffix: string) => `qm-rounds-${suffix}`;

/** The one name shape both derivations agree on. Kept in one place so
 *  "declared" and "applied" can never drift into recognising different names.
 *  A FACTORY, not a shared instance: a `/g` regex carries `lastIndex`, and a
 *  single shared object used by both `matchAll` and `test` produces answers
 *  that depend on call order — a stateful matcher is its own vacuity bug. */
const classRe = () => /qm-rounds-[a-z0-9-]+/g;

/** CSS has ONE comment form. `//` is not a comment in CSS and `url(https://…)`
 *  is legal, so the TS stripper must not be reused here. */
const stripCssComments = (src: string) => src.replace(/\/\*[\s\S]*?\*\//g, ' ');

/** TS/TSX: block comments first — which also disposes of the JSX comment form,
 *  because its braces sit OUTSIDE the comment and stripping the comment leaves
 *  a bare `{}` (see the header for the draft that tried to match the braces too
 *  and ate live code). Then line comments; the `[^:]` guard keeps `https://`
 *  out of it.
 *
 *  ⚠️ And the JSX comment form cannot be written literally in this docstring:
 *  its closing delimiter ends the docstring. That is not a footnote — it is the
 *  same fact the function encodes, biting the comment that describes it. */
const stripTsComments = (src: string) =>
  src.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/(^|[^:])\/\/[^\n]*/gm, '$1 ');

/** Every .tsx under a root, recursively. `readdirSync` with `withFileTypes`
 *  rather than a glob: bash does not expand `**` without `globstar`, and a
 *  hand-written root list has already undercounted this project's surface three
 *  times. Deliberately NOT imported from `gate-c1d-auth.test.ts`, which has the
 *  same helper — that file exports nothing (checked), and a test file is not a
 *  module anyone should start depending on. */
function walkTsx(dir: string): string[] {
  const out: string[] = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...walkTsx(p));
    else if (p.endsWith('.tsx')) out.push(p);
  }
  return out;
}

/** Every .ts under a root — used ONLY to prove the .tsx-only walk above cannot
 *  miss a render site. */
function walkTs(dir: string): string[] {
  const out: string[] = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...walkTs(p));
    else if (p.endsWith('.ts')) out.push(p);
  }
  return out;
}

// ── The contract table ──────────────────────────────────────────────────────

type RowKind = 'literal' | 'surface-enum' | 'prefix' | 'unknown';

interface Row {
  /** the token as written in column 1, e.g. `qm-rounds-<surface>` */
  token: string;
  kind: RowKind;
  /** concrete class names this row names. Empty for `prefix`, which matches. */
  members: string[];
  /** set for `prefix` rows, e.g. `qm-rounds-skel-` */
  prefix?: string;
}

/**
 * Parse the § Controls markdown table.
 *
 * Anchored on the `## Controls` H2 and stopped at the next H2, so a table
 * added under a LATER section can never be read as this one. `/^##\s/` does
 * not match `###`, which matters: § Controls has an H3 subsection ("Two rules
 * that are not style preferences") sitting between the table and the next H2.
 */
function parseControlsTable(md: string): Row[] {
  const lines = md.split('\n');

  const heading = lines.findIndex((l) => /^##\s+Controls\s*$/.test(l));
  if (heading < 0) throw new Error(`${DOC_PATH} has no "## Controls" heading`);

  let nextH2 = lines.findIndex((l, i) => i > heading && /^##\s/.test(l));
  if (nextH2 < 0) nextH2 = lines.length;

  const header = lines.findIndex(
    (l, i) => i > heading && i < nextH2 && /^\|\s*Class\s*\|/.test(l.trim()),
  );
  if (header < 0) throw new Error('§ Controls has no "| Class |" table header');
  if (!/^\|[\s:|-]+\|$/.test(lines[header + 1].trim())) {
    throw new Error('the row after the § Controls header is not a separator');
  }

  const rows: Row[] = [];
  for (let i = header + 2; i < nextH2; i++) {
    if (!lines[i].trim().startsWith('|')) break; // the table ends at the first non-row
    const cells = lines[i].split('|').map((c) => c.trim());
    // cells[0] is the empty string before the leading pipe.
    const token = cells[1]?.match(/`\.([A-Za-z0-9<>*_-]+)`/)?.[1];
    if (!token) throw new Error(`§ Controls row ${i + 1} names no \`.class\`: ${lines[i]}`);
    rows.push(classify(token, cells[2] ?? ''));
  }
  return rows;
}

/**
 * The two PATTERN rows are handled EXPLICITLY, which is the whole point of this
 * function. A pattern left to "match nothing" makes direction (1) skip a row
 * silently; a pattern left to "match everything" makes direction (2) accept any
 * class at all. Both failures look exactly like a passing test.
 *
 *   `.qm-rounds-<surface>` — an ENUMERATION, not a wildcard. Its own row spells
 *      the members out ("`-auth`, `-notfound`, `-errorstate`, `-loading`"), so
 *      they are read from the row rather than guessed. That reading is what
 *      makes `.qm-rounds-settings` need its own row — C1-e gave it one, because
 *      it is the only surface marker that paints a background.
 *   `.qm-rounds-skel-*` — a genuine prefix wildcard.
 *
 * Anything else carrying `<` or `*` returns `unknown` and is asserted on. A
 * pattern shape this function has never seen must redden, not be skipped.
 */
function classify(token: string, description: string): Row {
  if (token.includes('<')) {
    const stem = token.slice(0, token.indexOf('<')); // derived, not typed out
    if (!stem.endsWith('-')) return { token, kind: 'unknown', members: [] };
    const members = [...description.matchAll(/`-([a-z0-9-]+)`/g)].map((m) => stem + m[1]);
    return members.length > 0
      ? { token, kind: 'surface-enum', members }
      : { token, kind: 'unknown', members: [] };
  }
  if (token.endsWith('*')) {
    const prefix = token.slice(0, -1);
    return prefix.endsWith('-')
      ? { token, kind: 'prefix', members: [], prefix }
      : { token, kind: 'unknown', members: [] };
  }
  if (/[<>*]/.test(token)) return { token, kind: 'unknown', members: [] };
  return { token, kind: 'literal', members: [token] };
}

// ── The shipped sets, both derived ──────────────────────────────────────────

const CSS_RAW = readFileSync(CSS_PATH, 'utf8');
const CSS = stripCssComments(CSS_RAW);
const DECLARED = new Set([...CSS.matchAll(/\.(qm-rounds-[a-z0-9-]+)/g)].map((m) => m[1]));

const ROWS = parseControlsTable(readFileSync(DOC_PATH, 'utf8'));
const LITERAL_ROWS = ROWS.filter((r) => r.kind === 'literal');
const SURFACE_ROWS = ROWS.filter((r) => r.kind === 'surface-enum');
const PREFIX_ROWS = ROWS.filter((r) => r.kind === 'prefix');
const UNKNOWN_ROWS = ROWS.filter((r) => r.kind === 'unknown');

/** The Rounds screens that are Rounds' OWN, rather than an existing surface
 *  wearing the skin. See the header for why this is the boundary and for the
 *  three alternatives that were measured and rejected. */
const NATIVE_RE = /^src[/\\](components[/\\]rounds|app[/\\]board)[/\\]/;

const TSX = walkTsx('src');
/** class → the files that apply it, comments stripped. */
const APPLIED = new Map<string, string[]>();
for (const file of TSX) {
  const src = stripTsComments(readFileSync(file, 'utf8'));
  for (const m of src.matchAll(classRe())) {
    APPLIED.set(m[0], [...(APPLIED.get(m[0]) ?? []), file]);
  }
}

const appliedOutsideNative = [...APPLIED.entries()]
  .filter(([, files]) => files.some((f) => !NATIVE_RE.test(f)))
  .map(([c]) => c);

/** (a) has a rule AND (b) is applied off the Rounds-native screens. */
const PRIMITIVES = appliedOutsideNative.filter((c) => DECLARED.has(c)).sort();
const NATIVE_ONLY = [...DECLARED].filter((c) => !appliedOutsideNative.includes(c)).sort();

/** Is `c` named by the table, by a literal row or by a pattern row? */
function coveredByTable(c: string): boolean {
  if (LITERAL_ROWS.some((r) => r.token === c)) return true;
  if (SURFACE_ROWS.some((r) => r.members.includes(c))) return true;
  // `c.length > prefix.length` — `.qm-rounds-skel-*` names members of the
  // family, not a bare `.qm-rounds-skel-`. A `startsWith` alone would also
  // accept the prefix itself, which is the substring trap this project has
  // now shipped three times ('dashboard'.includes('board')).
  return PREFIX_ROWS.some((r) => c.startsWith(r.prefix!) && c.length > r.prefix!.length);
}

// ────────────────────────────────────────────────────────────────────────────

describe('C1-e — the § Controls table parses to something real', () => {
  it('the parse is non-vacuous: rows, kinds, and no unclassified pattern', () => {
    // A parser that matches nothing must REDDEN, not pass. Every assertion in
    // this file is quantified over `ROWS`; an empty `ROWS` makes all of them
    // trivially true, which is the exact defect § Controls asks the guard to
    // avoid ("carry a non-vacuity assertion on the row count").
    expect(ROWS.length, 'the § Controls table parsed to (almost) nothing').toBeGreaterThanOrEqual(
      15,
    );
    expect(LITERAL_ROWS.length, 'no literal rows parsed').toBeGreaterThanOrEqual(12);
    expect(
      UNKNOWN_ROWS.map((r) => r.token),
      'a row uses a pattern shape `classify()` does not handle — teach it, do not skip it',
    ).toEqual([]);

    // ⚠️ These two were `toBe(1)` until C1-f, which is a COUNT standing in for
    // an identity. It answers "did anything stop parsing?" only while the table
    // holds exactly one row of each kind — and C1-f's second prefix row made it
    // fail while nothing had stopped parsing at all. Worse, the inverse is the
    // real hazard: had `.qm-rounds-skel-*` degraded to `unknown` in the same
    // change that added `-tmpl-*`, the count would still have been 1 and this
    // assertion would have passed on a rotted row.
    //
    // So assert the thing meant instead of a number that correlates with it:
    // each pattern the document relies on is present AND classified as a
    // pattern. `UNKNOWN_ROWS` above already catches a shape the parser cannot
    // handle; this catches one it handles as the WRONG kind.
    const prefixTokens = PREFIX_ROWS.map((r) => r.prefix);
    expect(SURFACE_ROWS.map((r) => r.token), 'the `.qm-rounds-<surface>` row stopped parsing as a pattern')
      .toContain('qm-rounds-<surface>');
    expect(prefixTokens, 'the `.qm-rounds-skel-*` row stopped parsing as a pattern')
      .toContain('qm-rounds-skel-');
    expect(prefixTokens, 'the `.qm-rounds-tmpl-*` row stopped parsing as a pattern')
      .toContain('qm-rounds-tmpl-');
  });

  it('EVERY pattern row expands to real members — neither nothing nor everything', () => {
    // ⚠️ A pattern that expands to NOTHING makes direction (1) skip it and
    // direction (2) reject every one of its members. A pattern that expands to
    // EVERYTHING makes direction (2) accept anything. Both are silent.
    //
    // ⚠️ THIS TEST READ `SURFACE_ROWS[0]` AND `PREFIX_ROWS[0]` UNTIL C1-f, AND
    // THAT IS THE DEFECT IT EXISTS TO CATCH, IN ITSELF. With one row of each
    // kind in the table the index was invisible; the moment C1-f added a second
    // prefix row (`qm-rounds-tmpl-*`) it would have shipped UNCHECKED — free to
    // expand to nothing, or to the bare namespace, with this guard green. A
    // check written against the only member of a set silently stops covering
    // that set the day it grows, which is this project's recurring shape:
    // an answer about a set whose boundary was never established.
    expect(SURFACE_ROWS.length + PREFIX_ROWS.length, 'no pattern rows parsed at all').toBeGreaterThan(1);

    for (const row of SURFACE_ROWS) {
      expect(
        row.members.length,
        `the surface row \`${row.token}\` enumerates no surfaces`,
      ).toBeGreaterThanOrEqual(3);
      for (const s of row.members) {
        expect(s.startsWith('qm-rounds-'), `${s} is not a qm-rounds class`).toBe(true);
        // …and the enumeration must not have degenerated into the stem itself.
        expect(s.length, `${s} is the bare stem, not a surface`).toBeGreaterThan('qm-rounds-'.length);
      }
    }

    for (const row of PREFIX_ROWS) {
      const prefix = row.prefix!;
      const members = [...DECLARED].filter((c) => c.startsWith(prefix) && c.length > prefix.length);
      expect(
        members.length,
        `${prefix}* names no shipped class — the row has rotted`,
      ).toBeGreaterThan(0);

      // The prefix must not be so short it swallows the layer. `qm-rounds-`
      // alone would make `coveredByTable` true for every class in the product.
      expect(prefix.length, `${prefix} is the bare namespace`).toBeGreaterThan(
        'qm-rounds-'.length,
      );
    }
  });
});

describe('C1-e — direction 1: a table row that rots', () => {
  it('every class named in the table has a real rule in rounds-tokens.css', () => {
    // The row that outlives its class. `.qm-rounds-btn-danger` is the live
    // example of how this happens: it was written, documented in a draft, and
    // deleted by `gate-c1d-auth`'s orphan check in the same change. Had the
    // table row landed and the class not, nothing would have said so.
    const named = [...LITERAL_ROWS.flatMap((r) => r.members), ...SURFACE_ROWS.flatMap((r) => r.members)];
    const rotted = named.filter((c) => !DECLARED.has(c));
    expect(rotted, 'these classes are in the § Controls table but have no CSS rule').toEqual([]);

    // Non-vacuity: the loop above must have had something to check.
    expect(named.length, 'the table named no concrete classes').toBeGreaterThanOrEqual(15);
  });

  it('the declared set is derived with CSS comments stripped — real control', () => {
    // ⚠️ NOT A FIXTURE. `.qm-rounds-btn-danger` appears in `rounds-tokens.css`
    // today, at length, INSIDE a comment explaining why the class was removed.
    // A text-level derivation counts it as declared — and then a table row
    // naming it would pass direction (1) while the class does not exist. This
    // is the `gate-rounds-bridge:332` defect, reproduced on real bytes.
    const dangerous = cls('btn-danger');
    expect(CSS_RAW.includes(dangerous), 'the comment-only class is gone — pick a new control').toBe(
      true,
    );
    expect(DECLARED.has(dangerous), 'a class named only in a CSS comment was read as declared').toBe(
      false,
    );

    // …and the stripper has not eaten the stylesheet.
    expect(DECLARED.size, 'the declared-class matcher found almost nothing').toBeGreaterThanOrEqual(
      60,
    );
  });
});

describe('C1-e — direction 2: the .qm-rounds-authform drift', () => {
  it('the traversal reached the files that apply these classes — non-vacuity', () => {
    expect(TSX.length, 'the src walk returned almost no .tsx files').toBeGreaterThanOrEqual(50);
    expect(APPLIED.size, 'no qm-rounds class is applied anywhere — the walk is broken').toBeGreaterThanOrEqual(
      40,
    );

    // Named surfaces, one per C1 split, so a walk that quietly stops descending
    // is caught rather than merely suspected. Checked as class → file, because
    // "the traversal read some files" is not the claim; "it read THESE" is.
    const appliedIn = (klass: string) => APPLIED.get(klass) ?? [];
    expect(appliedIn('qm-rounds-authform'), 'C1-d auth surface not reached').toContain(
      'src/components/ui/auth-shell.tsx',
    );
    expect(appliedIn('qm-rounds-settings'), 'C1-e settings surface not reached').toContain(
      'src/app/settings/page.tsx',
    );
    // `settings/security/mfa/` is the directory a hand-written bash glob missed
    // in `gate-rounds-bridge` because `**` needs `globstar`. Depth is asserted.
    expect(appliedIn('qm-rounds-host'), 'the walk did not descend three levels').toContain(
      'src/app/settings/security/mfa/page.tsx',
    );
  });

  it('the control/native boundary splits the layer, and neither side collapses', () => {
    // ⚠️ THE ASSERTION THAT KEEPS DIRECTION (2) HONEST, IN BOTH DIRECTIONS.
    //
    // If NATIVE_RE ever matched everything, `PRIMITIVES` would empty and the
    // test below would pass over nothing — direction (2) silently switched off.
    // If it matched nothing, all 73 board/stage/gateflow/signed classes would
    // demand table rows — the recorded over-strict-probe defect, and a wall of
    // red nobody can action.
    expect(PRIMITIVES.length, 'the control layer collapsed to nothing').toBeGreaterThanOrEqual(15);
    expect(NATIVE_ONLY.length, 'the Rounds-native screens vanished from the walk').toBeGreaterThanOrEqual(
      40,
    );

    // The boundary must not have swallowed the very rows the table documents.
    // If a literal row's class reads as native-only, direction (2) can no
    // longer see the layer it is guarding.
    const swallowed = LITERAL_ROWS.map((r) => r.token).filter(
      (c) => DECLARED.has(c) && !PRIMITIVES.includes(c),
    );
    expect(swallowed, 'documented control classes were filed as Rounds-native').toEqual([]);

    // …and the native side really does contain screen anatomy, not stragglers.
    for (const anatomy of ['qm-rounds-board-grid', 'qm-rounds-strip-node', 'qm-rounds-gateflow-step']) {
      expect(NATIVE_ONLY, `${anatomy} should be Rounds-native anatomy`).toContain(anatomy);
    }
  });

  it('every shipped control primitive appears in the table', () => {
    // THE `-authform` DRIFT. A class with a rule and a consumer on a restyled
    // surface, absent from the contract that is supposed to name it.
    const undocumented = PRIMITIVES.filter((c) => !coveredByTable(c));
    expect(
      undocumented,
      'these classes ship as control primitives but no § Controls row names them — ' +
        'add a row, or (if this is a new Rounds-native screen) add its directory to NATIVE_RE',
    ).toEqual([]);
  });

  it('a class applied with no rule is not a primitive — the -devstates exclusion', () => {
    // ⚠️ NARROWING, WITH SOMETHING STILL ASSERTED IN THE NARROWED CASE — an
    // over-strict probe is also a defect, and the honest fix is not to drop the
    // case but to say what remains true of it.
    //
    // `src/app/dev/states/page.tsx` applies `qm-rounds-devstates`, off the
    // Rounds-native screens, and NOTHING DECLARES IT — there is no such rule in
    // `rounds-tokens.css` or `globals.css`. Requiring a contract row for it
    // would be demanding documentation of a no-op. So clause (a) of the
    // definition excludes it, and this test pins WHY, so the exclusion cannot
    // quietly widen into "unmatched classes are fine".
    const devstates = 'qm-rounds-devstates';
    expect(APPLIED.has(devstates), 'the -devstates case is gone; delete this test').toBe(true);
    expect(DECLARED.has(devstates), '-devstates gained a rule — it is now a primitive, document it').toBe(
      false,
    );
    expect(PRIMITIVES, 'a class with no rule was counted as a shipped primitive').not.toContain(
      devstates,
    );

    // And the exclusion is NARROW: it is the only one. If more classes start
    // shipping applied-but-undeclared on restyled surfaces, that is a finding
    // in its own right, not a growing blind spot for this guard.
    const noRule = appliedOutsideNative.filter((c) => !DECLARED.has(c));
    expect(noRule, 'applied off the native screens with no CSS rule — no-op classes').toEqual([
      devstates,
    ]);
  });
});

describe('C1-e — the comment trap, proven rather than claimed', () => {
  it('the scanner ignores //, /* */ and {/* */} — fixture control', () => {
    // Measured: comment-stripping removes NOTHING from today's .tsx tree, so
    // the tree cannot prove the stripper does anything. A fixture can.
    const fixture = [
      "// a line comment naming qm-rounds-alpha",
      '/* a block comment naming qm-rounds-beta */',
      '<div>{/* a jsx comment naming qm-rounds-gamma */}</div>',
      "<p className=\"qm-rounds-delta\">only this one is applied</p>",
    ].join('\n');
    const found = [...stripTsComments(fixture).matchAll(classRe())].map((m) => m[0]);
    expect(found, 'a class named in a comment was collected as applied').toEqual([
      'qm-rounds-delta',
    ]);

    // Positive control on the SAME matcher: without stripping it finds all four,
    // so the `toEqual` above is the stripper working, not the regex failing.
    const unstripped = [...fixture.matchAll(classRe())].map((m) => m[0]);
    expect(unstripped.length, 'the class matcher itself is broken').toBe(4);

    // …and the stripper must not be so eager it eats live code. This is the
    // object-literal shape that made the first draft swallow five real classes:
    // `{` then a comment, with the closing `}` far away.
    const live = 'const s = {\n  /* note */\n  a: 1,\n};\n<p className="qm-rounds-eps" />';
    expect(
      [...stripTsComments(live).matchAll(classRe())].map((m) => m[0]),
      'the comment stripper swallowed live code between { and }',
    ).toEqual(['qm-rounds-eps']);
  });

  it('a Phase-B class named in a C1-e file’s comment is not credited to it — real control', () => {
    // ⚠️ THE TRAP, IN THE SHIPPED TREE, ON A FILE THIS SPLIT TOUCHED.
    // `mfa-management-panel.tsx` explains its success-pill colour by pointing at
    // `.qm-rounds-signed-lock` — a signed-screen class from Phase B that this
    // settings panel does not render. Read as text, that comment moves the
    // class out of the Rounds-native set and into the control layer, and
    // direction (2) then demands a contract row for it. The guard would file a
    // finding it invented.
    //
    // This is the .tsx twin of the `-btn-danger` control on the CSS side: both
    // assert against bytes that ship, not against a fixture.
    const file = 'src/app/settings/security/mfa/mfa-management-panel.tsx';
    const phaseB = cls('signed-lock');
    const raw = readFileSync(file, 'utf8');

    // Positive control first — the comment really does name it. If the prose is
    // ever rewritten, this reddens and asks for a new control rather than
    // quietly becoming an assertion about nothing.
    expect(raw.includes(phaseB), `${file} no longer names ${phaseB} — find a new control`).toBe(
      true,
    );
    expect(APPLIED.get(phaseB) ?? [], 'a class named in a comment was credited as applied').not.toContain(
      file,
    );
    // …and it therefore stays on the Rounds-native side, where it belongs.
    expect(PRIMITIVES, 'a Phase-B class was promoted into the control layer').not.toContain(phaseB);
    expect(NATIVE_ONLY, 'the Phase-B class vanished from the native set entirely').toContain(phaseB);
  });

  it('this file names classes in prose, and is not credited with applying them', () => {
    // The prose above deliberately names two classes it does not apply:
    // one declared-and-Rounds-native, one that exists only inside a CSS
    // comment. Neither is written as a code literal anywhere in this file —
    // `cls()` assembles them — so if the stripper regressed, the raw text would
    // still carry them and this control would redden.
    //
    // Why it matters beyond this file: were the applied walk ever widened to
    // .ts, THIS file's prose would enter the haystack, `qm-rounds-stage` would
    // read as applied outside the Rounds-native screens, and the guard would
    // demand a contract row for a board class. A test that fabricates its own
    // finding — the shape `ErrorFallback` has with `/api/client-errors`.
    const selfRaw = readFileSync(SELF_PATH, 'utf8');
    const inProse = [cls('stage'), cls('btn-danger')];

    // Positive control FIRST: the prose really does name them. Without this,
    // the assertion below passes on a file that simply never mentioned them.
    for (const c of inProse) {
      expect(selfRaw.includes(c), `${c} is no longer named in this file's prose`).toBe(true);
    }

    const collected = new Set([...stripTsComments(selfRaw).matchAll(classRe())].map((m) => m[0]));
    for (const c of inProse) {
      expect(collected.has(c), `${c} is named only in prose here but was collected`).toBe(false);
    }
  });

  it('restricting the applied walk to .tsx cannot miss a render site', () => {
    // The walk collects .tsx only, because that is where JSX renders — and
    // because a .ts file that mentions a class in an ASSERTION STRING is not
    // applying it (three gate files do exactly that). That reasoning is only
    // sound while no .ts file emits class names, so it is asserted rather than
    // assumed: the day a helper starts returning `qm-rounds-*` strings, this
    // reddens and tells the next reader to widen `walkTsx`.
    const offenders = walkTs('src')
      .filter((f) => !/__tests__|\.test\.ts$/.test(f))
      .filter((f) => classRe().test(stripTsComments(readFileSync(f, 'utf8'))));
    expect(
      offenders,
      'a non-test .ts file names qm-rounds classes — the .tsx-only walk now has a hole',
    ).toEqual([]);

    // Non-vacuity: the .ts traversal must actually have visited files, or the
    // zero above is a traversal that covered nothing. (The positive control
    // this project's history insists on: run the matcher against something
    // known to be present in the haystack.)
    const allTs = walkTs('src');
    expect(allTs.length, 'the .ts traversal returned nothing').toBeGreaterThanOrEqual(50);
    expect(
      allTs.some((f) => f.endsWith('gate-c1d-auth.test.ts')),
      'the .ts traversal never reached the gate files it is meant to be excluding',
    ).toBe(true);
  });
});
