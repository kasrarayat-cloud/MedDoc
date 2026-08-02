// ============================================================================
// C2 — Gate C: a door that is built and never opened, and a sweep that measures
// nothing.
// ----------------------------------------------------------------------------
// Two defects, one shape, both found by surveying what Gate C actually covers.
//
// (1) FIVE DOORS, BUILT, NEVER OPENED. C1-c restyled the error boundary, both
//     404s, three loading states and the skeletons. `C1-PLAN.md:338` recorded
//     its axe as "deferred to C1-d's pack". C1-d's pack sweeps the six AUTH
//     routes and nothing else. C1-c2 then built `/dev/states` and called it, in
//     its own header, "the Gate C door" — and of its states only the two C1-f
//     added were ever walked. The deferral is written down in the plan, where
//     it reads as done.
//
//     So this file asserts the two sides against each other: every state the
//     route can render must be swept by a pack. Adding a state and forgetting
//     the sweep is now a red unit, not a silent hole in a gate.
//
// (2) A SWEEP OVER UNANCHORED MARKUP IS A GREEN TICK OVER NOTHING.
//     `ownedByDom` stops at the first ancestor-or-self carrying ANY class and
//     gates only a `qm-rounds-*` one. `/board`'s chrome is entirely inline-
//     styled and classless, so its header, filter group, search form,
//     pagination and day meter climbed past everything to
//     `<body className="min-h-screen antialiased">` and filed as *inherited*.
//     The `board` state has been green on the lane rows alone since Gate A.
//
//     The anchors are asserted here because they are invisible in a passing
//     run: deleting one does not fail any test that looks at colour, it just
//     quietly shrinks what the gate covers.
// ============================================================================

import { readFileSync, readdirSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

const STATES_PAGE = 'src/app/dev/states/page.tsx';
const PACK = 'tests/e2e/scenarios/rounds-c1.spec.ts';

/** Blank comments while preserving line numbers. A state name discussed in
 *  prose must never count as a state that is swept — C1-f's literal scan and
 *  its preview-derivation check were both killed for reading their own
 *  explanation as evidence. */
const blankComments = (s: string) =>
  s
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
    .replace(/\/\/[^\n]*/g, (m) => ' '.repeat(m.length));

const PAGE_SRC = blankComments(readFileSync(STATES_PAGE, 'utf8'));
const PACK_SRC = blankComments(readFileSync(PACK, 'utf8'));

/** The states `/dev/states` can actually render, read off its own enum. */
function declaredStates(): string[] {
  const block = PAGE_SRC.match(/const STATES = \[([\s\S]*?)\] as const;/);
  if (!block) throw new Error(`could not locate the STATES enum in ${STATES_PAGE}`);
  return [...block[1].matchAll(/'([a-z0-9-]+)'/g)].map((m) => m[1]);
}

const STATES = declaredStates();

describe('C2 — every /dev/states door is walked', () => {
  it('the enum parsed — positive control', () => {
    // A regex that stopped matching would return [] and make the assertion
    // below pass over nothing, which is this project's most-repeated defect.
    expect(STATES.length, 'the STATES enum parsed to nothing').toBeGreaterThanOrEqual(6);
    for (const known of ['error', 'skeletons', 'tmpl-processing']) {
      expect(STATES, `${known} missing — the enum parser is reading the wrong thing`).toContain(known);
    }
  });

  it('the pack was read, and it is the right file — positive control', () => {
    expect(PACK_SRC.length, `${PACK} read as empty`).toBeGreaterThan(10_000);
    expect(PACK_SRC, 'the pack does not drive /dev/states at all').toContain('/dev/states?state=');
  });

  it('every state the route can render is swept by the pack', () => {
    // Matched against the pack with COMMENTS STRIPPED, so a state that is only
    // *mentioned* in prose does not count as covered.
    const unswept = STATES.filter((s) => !new RegExp(`'${s}'`).test(PACK_SRC));
    expect(
      unswept,
      'these states can be rendered by `/dev/states` but no pack sweeps them. ' +
        'That is a door built and never opened — the exact shape that left the ' +
        'error boundary, both loading states and the skeletons outside Gate C ' +
        'while the plan recorded their axe as "deferred" and therefore done:\n  ' +
        unswept.join('\n  '),
    ).toEqual([]);
  });

  it('the cross-check can FAIL — negative control', () => {
    // Without this, a matcher that accepted everything would report full
    // coverage over an empty pack.
    expect(new RegExp(`'a-state-that-does-not-exist'`).test(PACK_SRC)).toBe(false);
  });
});

describe('C2 — the anchors that make a sweep mean something', () => {
  /** file → the anchor it must carry, and why the surface needs one. */
  const ANCHORS: Array<[string, string, string]> = [
    [
      'src/components/rounds/board-chrome.tsx',
      'qm-rounds-boardchrome',
      'the board header, filter group, search form, pagination and day meter are ' +
        'inline-styled and classless; without this they climb to <body> and the ' +
        '`board` sweep is green on the lane rows alone',
    ],
    [
      'src/components/rounds/board.tsx',
      'qm-rounds-board-empty',
      'the empty board is what a brand-new doctor sees on first login, and the ' +
        'a11y pack seeds three visits before it looks',
    ],
    [
      'src/app/settings/settings-sections-c3.tsx',
      'qm-rounds-setpanel',
      'the settings panel heading and subtitle sit inside C3 chrome; Rounds ' +
        'colours them through the bridge, so Rounds must answer for them',
    ],
    [
      'src/app/settings/settings-sections-c3.tsx',
      'qm-rounds-setbody',
      'the second shield — `.qm-c3-set-content` owns everything a panel renders',
    ],
  ];

  it('every Gate C surface carries its ownership anchor', () => {
    const missing: string[] = [];
    for (const [file, cls, why] of ANCHORS) {
      const src = blankComments(readFileSync(file, 'utf8'));
      if (!src.includes(cls)) missing.push(`${file}: ${cls} — ${why}`);
    }
    expect(
      missing,
      'an ownership anchor is gone. Nothing about colour breaks when this ' +
        'happens; the gate simply stops covering the surface, and the run stays ' +
        'green:\n  ' + missing.join('\n  '),
    ).toEqual([]);
  });

  it('the anchor check reads CODE, not comments — negative control', () => {
    // ⚠️ SELF-CONTAINED ON PURPOSE. The first draft of this control asserted
    // that `board-chrome.tsx` names its anchor in prose as well as in code, and
    // reddened — because the comment there explains the anchoring WITHOUT
    // spelling the class. That is a control resting on a premise about another
    // file, which decays the moment someone rewords a comment. It proved
    // nothing about the stripper, which is the thing under test.
    //
    // So: hand the stripper a fixture where the class appears ONLY in a
    // comment, and require it to disappear. If it survives, a deleted anchor
    // could be "found" in the prose explaining why it exists.
    const commentOnly = `// this file used to carry qm-rounds-boardchrome\nconst x = 1;\n`;
    expect(
      blankComments(commentOnly).includes('qm-rounds-boardchrome'),
      'a class named only in a comment survived stripping — the anchor scan ' +
        'would read an explanation as an implementation',
    ).toBe(false);
    // …and the same string in CODE must survive, or the scan finds nothing ever.
    const inCode = `<div className="qm-rounds-boardchrome" />`;
    expect(blankComments(inCode)).toContain('qm-rounds-boardchrome');
  });
});

describe('C2 — a fill token used as a foreground, on the Rounds-native screens', () => {
  // ⚠️ THE GAP THIS CLOSES. `gate-rounds-bridge` watches `--color-linear-*`
  // foregrounds on the C1 surfaces. Nothing watched `--rounds-*` used directly
  // as `color:` in `components/rounds/` and `app/board/` — which is where the
  // skin's own screens live. So the board's day meter shipped
  // `color: var(--rounds-ready)` (3.39:1) and `var(--rounds-processing)`
  // (3.80:1) from Gate A onward, and the `board` axe state stayed green because
  // the chrome was never anchored. Two guards, and the defect fell between them.
  //
  // `docs/design-tokens.md` states the rule this enforces: "If a token names a
  // STATE or a FILL, it needs a `-text` sibling before it is used as a
  // foreground." The doc says it has been learned six times. This is the check.
  //
  // DERIVED, NOT LISTED: a token is a "fill" here iff the stylesheet declares a
  // text-safe sibling for it (`-text` or `-on-dark`). Ship a new pair and it is
  // covered; a hand-kept list would go stale exactly when a seventh instance
  // arrives.
  const TOKENS = readFileSync('src/app/rounds-tokens.css', 'utf8');
  const NATIVE_DIRS = ['src/components/rounds', 'src/app/board'];

  function declaredTokens(): Set<string> {
    return new Set([...TOKENS.matchAll(/^\s*(--rounds-[a-z0-9-]+)\s*:/gm)].map((m) => m[1]));
  }
  /** fill token → its text-safe sibling, read off the stylesheet. */
  function fillsWithTextSibling(): Map<string, string> {
    const declared = declaredTokens();
    const out = new Map<string, string>();
    for (const t of declared) {
      for (const suffix of ['-text', '-on-dark']) {
        const sib = `${t}${suffix}`;
        if (declared.has(sib)) out.set(t, sib);
      }
    }
    return out;
  }

  function walk(dir: string): string[] {
    const out: string[] = [];
    for (const e of readdirSync(dir, { withFileTypes: true })) {
      const p = `${dir}/${e.name}`;
      if (e.isDirectory()) {
        if (e.name === '__tests__') continue;
        out.push(...walk(p));
      } else if (/\.tsx?$/.test(p)) out.push(p);
    }
    return out;
  }

  const FILLS = fillsWithTextSibling();

  it('the stylesheet yields real fill/text pairs — positive control', () => {
    expect(FILLS.size, 'no fill tokens with text siblings found — the parser is broken').toBeGreaterThanOrEqual(4);
    expect(FILLS.get('--rounds-ready')).toBe('--rounds-ready-text');
    expect(FILLS.get('--rounds-critical')).toBe('--rounds-critical-on-dark');
  });

  it('no Rounds-native screen paints text with a fill token', () => {
    const bad: string[] = [];
    for (const dir of NATIVE_DIRS) {
      for (const f of walk(dir)) {
        const src = blankComments(readFileSync(f, 'utf8'));
        for (const [i, line] of src.split('\n').entries()) {
          for (const m of line.matchAll(/(?<![a-zA-Z-])color:\s*'?var\((--rounds-[a-z0-9-]+)\)/g)) {
            const sib = FILLS.get(m[1]);
            if (sib) bad.push(`${f}:${i + 1}  color: ${m[1]} — use ${sib}`);
          }
        }
      }
    }
    expect(
      bad,
      'a FILL token is painting text on a Rounds-native screen. It has a ' +
        'text-safe sibling precisely because the fill value does not clear AA ' +
        'as small text — the board day meter shipped this way from Gate A and ' +
        'no gate could see it, because the chrome carried no ownership anchor:\n  ' +
        bad.join('\n  '),
    ).toEqual([]);
  });

  it('the scan can FIND one — negative control', () => {
    // Without this, a matcher that never matches reports a clean product.
    const fixture = `<span style={{ color: 'var(--rounds-ready)' }}>x</span>`;
    const hits = [...fixture.matchAll(/(?<![a-zA-Z-])color:\s*'?var\((--rounds-[a-z0-9-]+)\)/g)]
      .map((m) => m[1])
      .filter((t) => FILLS.has(t));
    expect(hits, 'the matcher cannot see a fill-as-text even when handed one').toEqual([
      '--rounds-ready',
    ]);
    // …and `backgroundColor`/`borderColor` must NOT match — the substring trap.
    for (const decoy of [
      `style={{ backgroundColor: 'var(--rounds-ready)' }}`,
      `style={{ borderColor: 'var(--rounds-ready)' }}`,
      `style={{ background: 'var(--rounds-ready)' }}`,
    ]) {
      expect(
        [...decoy.matchAll(/(?<![a-zA-Z-])color:\s*'?var\((--rounds-[a-z0-9-]+)\)/g)].length,
        `${decoy} was read as a foreground`,
      ).toBe(0);
    }
  });
});
