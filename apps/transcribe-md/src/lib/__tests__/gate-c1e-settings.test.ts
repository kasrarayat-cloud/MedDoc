// ============================================================================
// C1-e — the settings surface: the contrast the gate cannot see, the token that
// is undeclared with the flag off, and the portal the bridge cannot reach.
// ----------------------------------------------------------------------------
// FOUR jobs, and each exists because the E2E pack STRUCTURALLY cannot do it.
//
// ─── 1. CONTRAST ON A LITERAL, AND ON A COMPOSITED WASH ────────────────────
//
// Same failure class `gate-c1d-auth` was written for, arriving twice more:
//
//     stepper disc   #0d1611 on --color-linear-sage 6.72:1
//                            → on --rounds-accent   **3.43:1**   (10.5px text)
//     delete confirm #0d1611 on --rounds-critical   **3.62:1**
//
// Gate C cannot catch either. `ownedByDom` climbs to the nearest ancestor-or-
// self carrying ANY class, and BOTH nodes carry one of their own — the disc is
// a bare `<span>` inside a densely-classed C3 panel, the confirm button is
// `<button class="qm-lin-btn-primary">`. Their violations file "inherited",
// which the pack reports and never gates on. And the MFA "on" pill's ground is
// a `color-mix()` wash over a bridged surface: axe would measure it, but only
// on a state a walk has to be driven into, and the ratio is not readable from
// any source file — it has to be COMPOSITED. So the arithmetic lives here.
//
// The formula is duplicated from `gate-c1d-auth.test.ts` rather than imported,
// because that file exports nothing (verified: zero `export` statements) and
// making it export things would turn a gate into a library. Duplicated code
// that is negative-controlled is safer than a shared helper nobody controls —
// so every arithmetic primitive below has its own control, and if the control
// ever stops being able to fail, the zeros mean nothing.
//
// ─── 2. THE TRAVERSAL BOUNDARY (was: flag safety of every fork) ─────────────
//
// MOSTLY RETIRED — see the block above `C1-e — the traversal boundary` below.
// This section used to police a hazard that existed only while the skin was
// optional: `--rounds-*` is declared under `[data-skin='rounds']`, so a bare
// `var(--rounds-x)` rendered with the skin OFF was invalid-at-computed-value-
// time — no build error, no console error, the property silently falling to
// its INITIAL value (`background` → transparent). Every reference therefore
// had to carry a FALLBACK or sit on the true branch of the skin flag, and a
// classifier decided which.
//
// There is one skin now. `layout.tsx` sets `data-skin="rounds"` on `<html>`
// unconditionally, so the attribute that DECLARES the tokens is always
// present and there is no second state left to be unsafe in. What survives is
// the half that was never about the flag: the traversal must actually reach
// this surface, or every "nothing found" answer in this file is an answer
// about the empty set.
//
// ─── 3. THE PORTAL INVARIANT ───────────────────────────────────────────────
//
// `<Dialog.Portal>` mounts on `<body>`, outside `[data-skin='rounds']
// .qm-rounds-host`'s deliberately-scoped subtree. The host therefore goes on
// `Dialog.Content` ITSELF — and it must be the SAME element that carries
// `qm-rounds-dialog`, because the destructive button's FILL (inline
// `var(--color-linear-danger)`, which only the host redeclares) and its LABEL
// (`.qm-rounds-host .qm-lin-btn-primary { color: var(--rounds-on-accent) }`)
// arrive through that one selector. Bridge the fill by any route that does not
// also carry the label fork and the label lands at 3.62:1 — a contrast
// regression created by the act of fixing a colour.
//
// ⚠️ `gate-rounds-bridge`'s adopter check CANNOT see this. It asks whether the
// FILE contains `qm-rounds-host`, and the file does — the class could be on the
// trigger, on the overlay, on an ancestor, anywhere. Same defect shape as
// `gate-rounds-bridge.test.ts:332` reading raw file TEXT: a question about a
// FILE standing in for a question about an ELEMENT.
//
// ─── 4. WHAT IS NOT ASSERTED HERE, NAMED RATHER THAN FUDGED ────────────────
//
// Nothing below proves the pixels. A source-level guard can prove the fork is
// written, the token is declared and the arithmetic clears; it cannot prove the
// cascade resolved the way the arithmetic assumes. That is the E2E's job —
// `rounds-c1.spec.ts`'s settings describe reads `getComputedStyle` on the real
// nodes. A gate and a pack answering the same question two ways is not
// redundancy here; it is the only reason either answer is worth anything.
// ============================================================================

import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

// ── Sources ────────────────────────────────────────────────────────────────

const TOKENS = readFileSync('src/app/rounds-tokens.css', 'utf8');
const GLOBALS = readFileSync('src/app/globals.css', 'utf8');

const SETTINGS_ROOT = 'src/app/settings';

/** Every source file under a root, recursively.
 *
 *  ⚠️ DERIVED BY TRAVERSAL, NEVER A HAND-WRITTEN ARRAY OR A GLOB. Bash does not
 *  expand `**` without `globstar` and a maintained list of roots has been wrong
 *  three times in this repo (the globstar miss, the convention files, and
 *  `gate-c1d-auth`'s orphan check, which reported 72 phantom orphans). A guard
 *  that is wrong about WHERE to look reports a clean answer about the wrong
 *  set. Nothing is excluded — a `.test.tsx` under this root emitting an
 *  undeclared token is still a defect, and an exclusion is a narrowing that
 *  would have to be controlled in turn. */
function walkSources(dir: string): string[] {
  const out: string[] = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...walkSources(p));
    else if (/\.tsx?$/.test(p)) out.push(p);
  }
  return out;
}

const SETTINGS_FILES = walkSources(SETTINGS_ROOT).sort();
const SETTINGS_SRC = new Map(SETTINGS_FILES.map((p) => [p, readFileSync(p, 'utf8')]));

/** Read a settings source THROUGH the derived file set.
 *
 *  ⚠️ NOT A BARE `Map.get()!`. Mutation-checked: replacing the traversal
 *  with a hand list of one file made every `.get()!` return undefined and the
 *  whole file died on a TypeError three frames deep — a red that says nothing
 *  about what broke. A guard whose failure mode is unreadable is a guard people
 *  disable. This names the real fault: the FILE SET is wrong, not the code. */
function srcOf(path: string): string {
  const s = SETTINGS_SRC.get(path);
  if (!s) {
    throw new Error(
      `${path} was not reached by the traversal of ${SETTINGS_ROOT} — ` +
        `the derived file set is wrong (${SETTINGS_FILES.length} files), not the product`,
    );
  }
  return s;
}

const ENROLL = 'src/app/settings/security/mfa/mfa-enrollment-panel.tsx';
const MANAGE = 'src/app/settings/security/mfa/mfa-management-panel.tsx';
const DELETE_DIALOG = 'src/app/settings/delete-account-dialog.tsx';
const EMAIL_DIALOG = 'src/app/settings/change-email-dialog.tsx';

/** Drop `/* … *\/` blocks and `//` lines.
 *
 *  ⚠️ NOT COSMETIC. `mfa-management-panel.tsx` explains in prose why a bare
 *  `var(--rounds-ready)` cannot be used — and writes that token in the
 *  explanation. A scan over raw file text counts the explanation as a use, in
 *  the exact shape recorded at `gate-rounds-bridge.test.ts:332`. Controlled
 *  below, on that file. */
function executableOnly(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .filter((l) => !l.trim().startsWith('//'))
    .join('\n');
}

// ── Contrast, computed rather than remembered ───────────────────────────────
// Reimplemented, not imported: `gate-c1d-auth.test.ts` has zero exports.

function srgbToLinear(c: number): number {
  const s = c / 255;
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}
function channels(hex: string): [number, number, number] {
  let h = hex.replace('#', '').trim();
  if (h.length === 3) h = h.split('').map((c) => c + c).join('');
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return [r, g, b];
}
function luminance(hex: string): number {
  const [r, g, b] = channels(hex);
  return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b);
}
function contrast(a: string, b: string): number {
  const [l1, l2] = [luminance(a), luminance(b)];
  const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}

/** `color-mix(in srgb, TOP p%, transparent)` painted over an OPAQUE bottom.
 *
 *  Mixing a colour with `transparent` in sRGB yields that colour at alpha = p;
 *  compositing it over an opaque ground is the ordinary source-over blend, done
 *  in the same space the browser uses when the destination is opaque. It is
 *  arithmetic on the SHIPPED values, which is the point: no wash's ratio is
 *  readable from any source file. */
function composite(top: string, bottom: string, alpha: number): string {
  const [tr, tg, tb] = channels(top);
  const [br, bg, bb] = channels(bottom);
  const mix = (t: number, b: number) => Math.round(t * alpha + b * (1 - alpha));
  return (
    '#' +
    [mix(tr, br), mix(tg, bg), mix(tb, bb)]
      .map((v) => v.toString(16).padStart(2, '0'))
      .join('')
  );
}

/** Read a token's value out of the SHIPPED stylesheet. Never hardcode one here:
 *  a guard carrying its own copy of the value asserts that the copy is
 *  self-consistent, which is not a fact about the product. A token change must
 *  redden this file. */
function token(name: string): string {
  const m = TOKENS.match(new RegExp(`^\\s*${name}:\\s*(#[0-9a-fA-F]{3,8})\\s*;`, 'm'));
  if (!m) throw new Error(`token ${name} is not declared in rounds-tokens.css`);
  return m[1];
}
/** The same, for an OLD-skin token — the flag-OFF half of every fork. */
function linearToken(name: string): string {
  const m = GLOBALS.match(new RegExp(`^\\s*${name}:\\s*(#[0-9a-fA-F]{3,8})\\s*;`, 'm'));
  if (!m) throw new Error(`token ${name} is not declared in globals.css`);
  return m[1];
}

/** The host bridge block: which Rounds token does a `--color-linear-*` name
 *  resolve to inside `.qm-rounds-host`? Derived, so a bridge edit reddens the
 *  arithmetic that depends on it rather than silently changing its subject. */
const HOST_BRIDGE = TOKENS.match(
  /\[data-skin='rounds'\]\s*\.qm-rounds-host\s*\{([^}]*)\}/,
)![1];
function bridged(linearName: string): string {
  const m = HOST_BRIDGE.match(
    new RegExp(`${linearName}:\\s*var\\((--rounds-[a-z0-9-]+)\\)`),
  );
  if (!m) throw new Error(`${linearName} is not bridged by .qm-rounds-host`);
  return m[1];
}

const AA = 4.5;

// ============================================================================
describe('C1-e — the arithmetic can fail', () => {
  it('negative controls on the formula itself', () => {
    // The three anchors. If these ever drift, every ratio below is a sentence.
    expect(contrast('#ffffff', '#000000')).toBeCloseTo(21, 4);
    expect(contrast('#000000', '#000000')).toBeCloseTo(1, 6);
    expect(contrast('#777777', '#ffffff')).toBeCloseTo(4.48, 2);
    // Short-hex expansion, which `--rounds-on-accent` (#fff) depends on.
    expect(luminance('#fff')).toBeCloseTo(luminance('#ffffff'), 12);
    // …and the function is not trivially "less than 4.5" for everything handed
    // to it, nor trivially "greater".
    expect(contrast('#ffffff', '#000000')).toBeGreaterThan(AA);
    expect(contrast('#777777', '#ffffff')).toBeLessThan(AA);
  });

  it('the compositor can fail — negative control on the wash blend', () => {
    expect(composite('#ffffff', '#000000', 1)).toBe('#ffffff'); // fully opaque top
    expect(composite('#ffffff', '#000000', 0)).toBe('#000000'); // fully transparent
    expect(composite('#ffffff', '#000000', 0.5)).toBe('#808080'); // and it MIXES
    // A 12% wash must move the ground a little and not a lot — the shape the
    // pill's ratio depends on. If `composite` ever became identity in either
    // direction, one of these fails.
    const washed = composite('#ffffff', '#000000', 0.12);
    expect(washed).not.toBe('#000000');
    expect(luminance(washed)).toBeLessThan(luminance('#808080'));
  });

  it('the token readers can fail — they refuse a name that is not declared', () => {
    expect(() => token('--rounds-surface-0')).toThrow(/not declared/);
    expect(() => linearToken('--color-linear-nope')).toThrow(/not declared/);
    expect(() => bridged('--color-linear-nope')).toThrow(/not bridged/);
    // …and they DO find the real ones, or "it throws on a fake" proves nothing.
    expect(token('--rounds-accent')).toMatch(/^#[0-9a-f]{3,8}$/i);
    expect(linearToken('--color-linear-sage')).toMatch(/^#[0-9a-f]{3,8}$/i);
    expect(bridged('--color-linear-sage')).toBe('--rounds-accent');
  });
});

// ============================================================================
describe('C1-e — the MFA stepper disc', () => {
  const src = srcOf(ENROLL);
  const code = executableOnly(src);

  /** The disc's own style object — `background` and `color` together, so the
   *  pair is read from ONE site rather than two that could drift apart. */
  const disc = code.match(
    /background:\s*isActive[\s\S]{0,400}?color:\s*isActive[^,]*,/,
  );

  it('the disc style block was found — non-vacuity', () => {
    // Without this, every assertion below is true of a file that no longer
    // renders a stepper at all.
    expect(disc, 'the stepper disc style object was not found in ' + ENROLL).not.toBeNull();
    expect(code).toContain('Enrollment steps');
  });

  it('the label token is the ON-ACCENT one, and it clears AA on the bridged fill', () => {
    // Which token does the fill resolve to under the bridge? DERIVED, so a
    // bridge edit that re-points sage cannot leave this measuring the old pair.
    const fillLinear = disc![0].match(/background:[\s\S]*?var\((--color-linear-[a-z0-9-]+)\)/)![1];
    const fill = token(bridged(fillLinear));

    // …and which token does the LABEL use? Also derived, from the call site.
    const label = disc![0].match(/color:[\s\S]*?var\((--rounds-[a-z0-9-]+)\s*,/)![1];
    expect(label, 'the disc no longer uses a --rounds-* label token').toBe('--rounds-on-accent');

    expect(
      contrast(token(label), fill),
      `${label} on ${fillLinear} → ${bridged(fillLinear)}`,
    ).toBeGreaterThanOrEqual(AA);
  });

  it('the pre-fix literal FAILS on that fill — negative control', () => {
    // 3.43:1. Without this, "the fix passes" could be true of a disc that never
    // needed fixing.
    const fill = token(bridged('--color-linear-sage'));
    expect(contrast('#0d1611', fill)).toBeLessThan(AA);
    expect(contrast('#0d1611', fill)).toBeCloseTo(3.43, 2);
  });

  // ── RETIRED: 'the FLAG-OFF half of the fork is still safe on the old sage' ──
  //
  // WHAT IT PINNED: #0d1611 on `--color-linear-sage` at 6.72:1 — the ratio a
  // doctor actually read when the skin was off and the disc kept raw sage. It
  // was the second half of "byte-identical with the flag off", asserted so
  // that claim was about legibility rather than about bytes.
  //
  // WHY THE PREMISE EXPIRED: there is no flag-off render. `data-skin="rounds"`
  // is unconditional on `<html>` and this panel mounts inside
  // `settings/security/mfa/page.tsx`'s `qm-rounds-host`, so the disc's
  // `--color-linear-sage` fill is ALWAYS bridged to `--rounds-accent`. The
  // pair this measured is one nothing composites.
  //
  // WHAT STILL HOLDS, and is still asserted above: the label resolves to
  // `--rounds-on-accent` on the BRIDGED fill and clears AA there, and the
  // pre-fix literal still fails on that same fill. Those are the live path.

  it('the failing literal is GONE from the call site — it survives ONLY as a CSS fallback', () => {
    // ⚠️ THE PRECISE CLAIM, because the loose one is false. `#0d1611` is still
    // in this file — it is the FALLBACK arm of `var(--rounds-on-accent,
    // #0d1611)`, a CSS default keyed on the same attribute that declares the
    // token, and it must stay. (It is unreachable while `data-skin` is
    // unconditional; it is cheap, and it is not this gate's to remove.) What
    // must be gone is the BARE form, where the literal is the value the bridge
    // then retints underneath — still a real 3.43:1 defect if it returns.
    const all = [...code.matchAll(/#0d1611/g)];
    const asFallback = [...code.matchAll(/var\(\s*--rounds-[a-z0-9-]+\s*,\s*#0d1611\s*\)/g)];
    // Non-vacuity FIRST: if the literal has vanished entirely, "every
    // occurrence is a fallback" is trivially true of zero occurrences, and this
    // guard would go green on a file it can no longer say anything about.
    expect(all.length, 'the #0d1611 CSS fallback has disappeared entirely').toBeGreaterThanOrEqual(1);
    expect(
      all.length,
      'a BARE #0d1611 literal is back on this surface — the bridge retints the ' +
        'fill underneath it and the glyph lands at 3.43:1',
    ).toBe(asFallback.length);
  });
});

// ============================================================================
describe('C1-e — the MFA "on" pill', () => {
  const src = srcOf(MANAGE);
  const code = executableOnly(src);

  it('the comment stripper is doing work — negative control', () => {
    // This file EXPLAINS, in prose, which token family the pill had to land on
    // and which ones it had to reject — naming three `--rounds-*` tokens in the
    // explanation. A scan over raw text counts every one of them as a use. Same
    // defect as gate-rounds-bridge:332.
    expect(src).toContain('So the pill reads `--rounds-ready` directly');
    expect(code).not.toContain('So the pill reads `--rounds-ready` directly');
    const raw = [...src.matchAll(/--rounds-[a-z]/g)].length;
    const exe = [...code.matchAll(/--rounds-[a-z]/g)].length;
    expect(raw, 'prose in this file no longer names a --rounds-* token').toBeGreaterThan(exe);
    expect(exe, 'the executable text has no --rounds-* token at all').toBeGreaterThanOrEqual(3);
  });

  it('the label clears AA on its own composited wash', () => {
    // ── Everything below is READ, not remembered. ──
    // The ground: the panel's `<section>` paints a --color-linear-* name, which
    // the host bridge maps to a Rounds surface.
    const panelLinear = code.match(
      /<section[\s\S]{0,300}?background:\s*'var\((--color-linear-[a-z0-9-]+)\)'/,
    )?.[1];
    expect(panelLinear, 'the management panel no longer paints a bridged ground').toBeTruthy();
    const ground = token(bridged(panelLinear!));

    // The wash: token AND percentage, both from the call site.
    const wash = code.match(
      /color-mix\(in srgb,\s*var\((--rounds-[a-z0-9-]+)\)\s*(\d+(?:\.\d+)?)%,\s*transparent\)/,
    );
    expect(wash, 'the pill no longer paints a color-mix wash').not.toBeNull();
    const [, washToken, washPct] = wash!;
    const pillGround = composite(token(washToken), ground, Number(washPct) / 100);

    // The label: read unconditionally, because there is nothing to fork on.
    const labelToken = code.match(/(?:^|\s)color:\s*'var\((--rounds-[a-z0-9-]+)\)'/m)?.[1];
    expect(labelToken, 'the pill label is no longer a --rounds-* token').toBeTruthy();

    expect(
      contrast(token(labelToken!), pillGround),
      `${labelToken} on ${washToken} ${washPct}% over ${bridged(panelLinear!)}`,
    ).toBeGreaterThanOrEqual(AA);
  });

  it('the FILL token as the label FAILS on that ground — negative control', () => {
    // `--rounds-ready` is a fill and line colour; on its own 12% wash over
    // surface-1 it lands at ~2.93:1. The whole reason a `-text` variant exists,
    // asserted as an arithmetic fact rather than a remembered one. Without it,
    // "the label passes" could be true of a pill that never needed the split.
    const ground = token(bridged('--color-linear-surface-1'));
    const pillGround = composite(token('--rounds-ready'), ground, 0.12);
    expect(contrast(token('--rounds-ready'), pillGround)).toBeLessThan(AA);
  });

  it('the label is on the READY family, not the accent family', () => {
    // ⚠️ THIS ONE IS NOT A CONTRAST BUG AND MUST NOT BE ASSERTED AS ONE.
    // The obvious label here is `--color-linear-sage-bright`, which the bridge
    // maps to `--rounds-accent-text` — a LIGHT indigo that clears AA on the
    // green wash comfortably. The defect is semantic: an indigo label inside a
    // green border, brand-coloured where the surface's whole job is to say
    // "protected" at a glance. So the assertion is about WHICH FAMILY, and the
    // contrast fact is asserted as the reason a contrast check would not have
    // caught it.
    expect(bridged('--color-linear-sage-bright')).toBe('--rounds-accent-text');
    const ground = composite(token('--rounds-ready'), token(bridged('--color-linear-surface-1')), 0.12);
    expect(
      contrast(token('--rounds-accent-text'), ground),
      'the un-forked label passes AA — a contrast gate could never have caught this',
    ).toBeGreaterThanOrEqual(AA);

    const labelToken = executableOnly(srcOf(MANAGE)).match(
      /(?:^|\s)color:\s*'var\((--rounds-[a-z0-9-]+)\)'/m,
    )![1];
    expect(labelToken.startsWith('--rounds-ready')).toBe(true);
    expect(labelToken).not.toBe('--rounds-accent-text');
  });

  // ── RETIRED: 'the flag-OFF branch of every pill fork is still a literal the
  //             old skin ships' ─────────────────────────────────────────────
  //
  // WHAT IT PINNED: the else-arm of each pill fork — `rgba(122,166,140,0.13)`,
  // `1px solid rgba(122,166,140,0.32)` and `var(--color-linear-sage-bright)`.
  // It was the other half of "byte-identical with the flag off", and it carried
  // its own retirement instruction: if the sage literals go, the else-branch is
  // dead and the whole thing should be simplified — but only then.
  //
  // WHY THE PREMISE EXPIRED: that is exactly what happened. There is one skin
  // and the pill has no second arm. Both `rgba(122,166,140,·)` literals are
  // gone from the executable source — they survive only in the panel's prose,
  // as the rejected option the comment explains, so asserting them would now
  // pin a comment. `var(--color-linear-sage-bright)` is still in the file but
  // on a DIFFERENT element, which is the other reason this cannot be salvaged:
  // it would go green on a match that was never the pill.
  //
  // WHAT STILL HOLDS: the two assertions above, which never needed the fork —
  // the label clears AA on its own composited wash, and it is on the READY
  // family rather than the accent family.
});

// ── RETIRED: the flag-safety classifier, and everything built on it ─────────
//
// This describe block was `C1-e — no --rounds-* token resolves undeclared with
// the flag off`. Four of its five items are deleted. The fifth — the traversal
// non-vacuity check — was never about the flag and is kept below.
//
// WHAT THEY PINNED
//
//   · `lastTernaryQ` / `scan` / the `Verdict` classifier — for every
//     `var(--rounds-…)` under `src/app/settings`, a three-way verdict:
//     `fallback` (the reference carries a CSS default), `guarded` (it sits on
//     the TRUE arm of a ternary whose condition is this module's own
//     `isSkinRounds()` binding), or `UNSAFE`.
//   · 'the classifier can fail — four positive controls and one narrowing
//     control' — the bare / fallback / flag-guarded / guarded-by-SOMETHING-ELSE
//     shapes, plus the `?.`-is-not-a-ternary narrowing. Case (4) was the
//     load-bearing one: it separated "is behind a ternary" from "is behind the
//     flag", and without it a `isCompact ? …` would have passed.
//   · 'every var(--rounds-*) under src/app/settings is fallback-safe or
//     flag-guarded' — the actual sweep, emptiness-asserted only after
//     non-vacuity and after proving both safe verdicts occurred on real code.
//   · 'a file that build-time forks really does import the flag' — that a
//     `guarded` verdict meant the REAL `isSkinRounds`, imported from
//     `@/config/skin-rounds`, and not a local shadow with the same name.
//
// WHY THE PREMISE EXPIRED
//
// All four rest on there being two render states. The hazard was that
// `--rounds-*` is declared under `[data-skin='rounds']`, so a reference with
// the skin OFF was invalid-at-computed-value-time — silent, no build error, no
// console error, the property falling to its INITIAL value. There is one skin
// now: `NEXT_PUBLIC_SKIN_ROUNDS` and `@/config/skin-rounds` are deleted, and
// `layout.tsx` sets `data-skin="rounds"` on `<html>` unconditionally, so the
// declaring attribute is always present and no reference can resolve
// undeclared. The settings sources have already dropped their forks to match —
// the MFA pill now reads `var(--rounds-ready)` and `var(--rounds-ready-text)`
// BARE, which is correct under one skin and which the retired sweep would have
// reported as UNSAFE. The `guarded` verdict is likewise unreachable: nothing
// under `src/app/settings` calls `isSkinRounds` any more, so both the sweep's
// `refs.some(guarded)` precondition and the import check would fail on a
// surface that is not broken. DO NOT RESURRECT THEM BY RELAXING THEM — a
// classifier with its discriminating control removed is worse than no
// classifier.
//
// WHAT STILL HOLDS
//
// Everything the tokens themselves have to satisfy, all of it asserted
// elsewhere in this file and none of it flag-dependent: the arithmetic block,
// the disc and pill contrast items, the portal invariant, and — in the
// stylesheet describe — that every `qm-rounds-*` class applied under settings
// has a rule and every class the C1-e block declares has a caller. If a token
// hazard needs policing again, it is a question about a DECLARATION, not about
// a fork.
// ============================================================================
describe('C1-e — the traversal boundary', () => {
  it('the traversal reached the settings surface — non-vacuity', () => {
    // A traversal that silently covers nothing returns "no offenders" for every
    // question asked of it. State the boundary and prove it was entered. This
    // outlived the flag because every emptiness assertion in this file — the
    // portal sweep, the applied/declared census — is worthless without it.
    expect(SETTINGS_FILES.length, `only ${SETTINGS_FILES.length} files under ${SETTINGS_ROOT}`)
      .toBeGreaterThanOrEqual(15);
    for (const f of [ENROLL, MANAGE, DELETE_DIALOG, EMAIL_DIALOG, 'src/app/settings/page.tsx']) {
      expect(SETTINGS_FILES, `${f} was not reached by the traversal`).toContain(f);
    }
    // …and it descended (the MFA files are two levels down).
    expect(SETTINGS_FILES.some((f) => f.split('/').length > 4)).toBe(true);
    // Positive control on the CONTENT, not just the paths: the traversal must
    // find a string we know is there. Unconditional now — the settings surface
    // carries the bridge class on every render, not on a flag.
    expect([...SETTINGS_SRC.values()].join('\n')).toContain('qm-rounds-host');
  });
});

// ============================================================================
describe('C1-e — the portal invariant', () => {
  /** The OPEN TAG of a JSX element, brace- and quote-aware.
   *
   *  ⚠️ NOT `/<Dialog\.Content[^>]*>/`. That stops at the FIRST `>`, and this
   *  repo has already paid for exactly that: `gate-c1d-auth`'s label scan used
   *  `[^>]*` and captured a `hint` prop's inner JSX instead of the label,
   *  making "Password" invisible to the guard written to protect it. A
   *  `Dialog.Content` carries a `style={{…}}` whose values are strings that may
   *  contain anything at all. Controlled below on a tag with a `>` inside a
   *  style value. */
  function openTag(src: string, from: number): string {
    let depth = 0;
    let quote: string | null = null;
    for (let i = from; i < src.length; i++) {
      const c = src[i];
      if (quote) {
        if (c === '\\') { i++; continue; }
        if (c === quote) quote = null;
        continue;
      }
      if (c === "'" || c === '"' || c === '`') { quote = c; continue; }
      if (c === '{') depth++;
      else if (c === '}') depth--;
      else if (c === '>' && depth === 0) return src.slice(from, i + 1);
    }
    throw new Error('unterminated JSX open tag');
  }

  function openTagsOf(src: string, tagName: string): string[] {
    const out: string[] = [];
    const needle = `<${tagName}`;
    let at = src.indexOf(needle);
    while (at !== -1) {
      out.push(openTag(src, at));
      at = src.indexOf(needle, at + needle.length);
    }
    return out;
  }

  function classesOf(tag: string): string[] {
    const m = tag.match(/className="([^"]*)"/);
    return m ? m[1].split(/\s+/).filter(Boolean) : [];
  }

  /** Derived by traversal — every settings file that opens a Radix portal. */
  const PORTAL_FILES = SETTINGS_FILES.filter((f) =>
    executableOnly(srcOf(f)).includes('<Dialog.Portal'),
  );

  it('the tag scanner can fail — positive controls on BOTH things it must survive', () => {
    // ⚠️ THE FIRST DRAFT OF THIS CONTROL EXERCISED ONLY HALF OF WHAT IT CLAIMED.
    // Its probe put the awkward `>` inside `style={{ … 'a > b' }}` — where
    // brace depth is already 2, so the `depth === 0` test alone rejects it and
    // the scanner passes with quote handling REMOVED. Mutation-checked: deleting
    // the quote branch left that control green.
    //
    // ⚠️ AND THE SECOND DRAFT HAD THE MIRROR HOLE, found the same way: it added
    // a `>` inside a QUOTED attribute, which quote-awareness alone catches — so
    // deleting the BRACE branch still left it green. Each mechanism needs a
    // case only it can survive, or the control names two things and tests one:
    //   · `title="a > b"`           — `>` inside quotes, at brace depth 0
    //   · `onOpenChange={(n) => n}` — `>` inside braces, UNQUOTED. The ordinary
    //                                 shape of a Radix prop, and the one a
    //                                 depth-blind scanner dies on.
    //   · `data-x="}"`              — a brace inside quotes, which must not
    //                                 unbalance the depth counter.
    const probe =
      `<Dialog.Content title="a > b" data-x="}" onOpenChange={(n) => n} ` +
      `style={{ w: 'min(500px, calc(100vw - 32px))', s: 'c > d' }} ` +
      `className="want-this">\n  <p className="not-this">child</p>\n</Dialog.Content>`;
    const tag = openTagsOf(probe, 'Dialog.Content')[0];
    expect(tag, 'the scanner stopped at a `>` inside a quoted attribute').toContain('want-this');
    expect(tag, 'the scanner ran past the open tag into the children').not.toContain('not-this');
    expect(classesOf(tag)).toEqual(['want-this']);
    expect(tag, 'the scanner stopped at the `>` of an arrow function').toContain('(n) => n');
    expect(tag, 'a brace inside quotes unbalanced the depth counter').toContain('data-x="}"');
    // …and it finds every occurrence, not just the first.
    expect(openTagsOf(probe + probe, 'Dialog.Content')).toHaveLength(2);
    // A naive `[^>]*` would have captured the wrong thing — asserted so this
    // control cannot itself become vacuous.
    expect(probe.match(/<Dialog\.Content[^>]*>/)![0]).not.toContain('want-this');
  });

  it('the portal file set was derived and is not empty — non-vacuity', () => {
    expect(PORTAL_FILES, 'no settings file opens a Dialog.Portal').toContain(DELETE_DIALOG);
    expect(PORTAL_FILES).toContain(EMAIL_DIALOG);
    expect(PORTAL_FILES.length).toBeGreaterThanOrEqual(2);
  });

  it('qm-rounds-host sits on the SAME element as qm-rounds-dialog, on every portal', () => {
    // ⚠️ THE ASSERTION IS ABOUT AN ELEMENT, NOT A FILE. `gate-rounds-bridge`
    // asks whether the FILE contains `qm-rounds-host` — and it does even when
    // the class is on the trigger, on the overlay, or on an ancestor that the
    // portal escapes. Moving the host up one node keeps that gate green and
    // silently un-bridges the dialog: nine `--color-linear-*` names inside it
    // revert to the old skin, the confirm button's fill reverts with them, and
    // the label fork stops arriving. This reddens on exactly that move.
    for (const f of PORTAL_FILES) {
      const code = executableOnly(srcOf(f));
      const contents = openTagsOf(code, 'Dialog.Content');
      expect(contents.length, `${f} opens a portal but renders no Dialog.Content`)
        .toBeGreaterThanOrEqual(1);
      for (const tag of contents) {
        const classes = classesOf(tag);
        expect(
          classes,
          `${f}: Dialog.Content must carry the BRIDGE ITSELF — a portalled node ` +
            'is not a descendant of the page host',
        ).toContain('qm-rounds-host');
        expect(
          classes,
          `${f}: Dialog.Content must carry an OWNED class on the same element, ` +
            'or axe files every violation inside the dialog as inherited',
        ).toContain('qm-rounds-dialog');
      }
      // The scrim too — it is a sibling of Content inside the portal and the
      // bridge cannot reach it either.
      for (const tag of openTagsOf(code, 'Dialog.Overlay')) {
        expect(classesOf(tag), `${f}: the portalled overlay lost its Rounds class`)
          .toContain('qm-rounds-dialog-overlay');
      }
    }
  });

  it('the dialog class actually repaints the ground it claims', () => {
    // An ownership marker that declares nothing is worse than none — C1-d's
    // ruling, applied to this class. And the value must not be the old skin's.
    const rule = TOKENS.match(/\[data-skin='rounds'\]\s*\.qm-rounds-dialog\s*\{([^}]*)\}/);
    expect(rule, '.qm-rounds-dialog has no rule').not.toBeNull();
    const bgToken = rule![1].match(/background:\s*var\((--rounds-[a-z0-9-]+)\)/)?.[1];
    expect(bgToken, '.qm-rounds-dialog declares no background token').toBeTruthy();
    expect(
      token(bgToken!).toLowerCase(),
      'the Rounds dialog ground equals the OLD skin ground — the fork is a no-op',
    ).not.toBe(linearToken('--color-linear-surface-1').toLowerCase());
    // The inline `background: var(--color-linear-surface-1)` on Dialog.Content
    // beats the class, so the two must AGREE or the class is decoration.
    expect(bgToken).toBe(bridged('--color-linear-surface-1'));
  });

  it('the destructive label and its fill arrive through the SAME selector', () => {
    // The whole reason the host is on Dialog.Content rather than on a wider
    // selector. `.qm-lin-btn-primary` hardcodes `color: #0d1611` in globals;
    // on --rounds-critical that is 3.62:1. Bridging the FILL by any route that
    // does not also carry the label fork creates a contrast regression by the
    // act of fixing a colour.
    const critical = token('--rounds-critical');
    expect(contrast('#0d1611', critical)).toBeLessThan(AA);
    expect(contrast('#0d1611', critical)).toBeCloseTo(3.62, 2);
    expect(contrast(token('--rounds-on-accent'), critical)).toBeGreaterThanOrEqual(AA);

    // The fill: the confirm button's inline background is a --color-linear-*
    // name, so it is the HOST that retints it.
    // ⚠️ FOUND VIA THE CONTROLLED TAG SCANNER, not a bounded `[\s\S]{0,N}`
    // window. The first draft used one and MISSED: the button's style object is
    // 333 characters and the window was 300, so the guard reported "the
    // destructive confirm button was not found" on a button that was right
    // there. A distance-limited match is a sample, never a parse — the same
    // defect shape as the `-maxdepth 6` sweep in AGENTS.md.
    const del = executableOnly(srcOf(DELETE_DIALOG));
    const confirm = openTagsOf(del, 'button').find((t) =>
      classesOf(t).includes('qm-lin-btn-primary'),
    );
    expect(confirm, 'the destructive confirm button was not found').toBeTruthy();
    expect(confirm!).toMatch(/background:\s*'var\(--color-linear-danger\)'/);
    expect(bridged('--color-linear-danger')).toBe('--rounds-critical');

    // The label: the fork is scoped to the host, which is now on the same
    // element the fill's custom property is declared on.
    const fork = TOKENS.match(
      /\[data-skin='rounds'\]\s*\.qm-rounds-host\s+\.qm-lin-btn-primary[^{]*\{([^}]*)\}/,
    );
    expect(fork, 'no host-scoped .qm-lin-btn-primary fork').not.toBeNull();
    expect(fork![1]).toMatch(/color:\s*var\(--rounds-on-accent\)/);

    // …and the literal really is still shipped by the old skin, or the fork is
    // dead code and should go.
    expect(GLOBALS).toMatch(/\.qm-lin-btn-primary\s*\{[^}]*color:\s*#0d1611/);
  });
});

// ============================================================================
describe('C1-e — the stylesheet block itself', () => {
  const BLOCK = TOKENS.slice(TOKENS.indexOf('C1-e · Settings'));

  it('the C1-e block was located — non-vacuity', () => {
    expect(TOKENS.indexOf('C1-e · Settings'), 'the C1-e block header is gone').toBeGreaterThan(0);
    expect(BLOCK).toContain('.qm-rounds-settings');
    expect(BLOCK).toContain('.qm-rounds-dialog');
    expect(BLOCK).toContain('.qm-rounds-select');
  });

  it('the settings surface paints its own ground', () => {
    // ⚠️ THE NEAR-MISS THIS ITEM FOUND. `/settings` is the first Rounds surface
    // inside `AppFrame`, and `.qm-lin-app` paints an OPAQUE
    // `var(--color-linear-bg)` at 100vh as an ANCESTOR of the host — so the
    // host's own redeclaration cannot reach it and the Rounds stage sits
    // covered. A marker class that only sets a font would have shipped
    // Rounds-tinted panels on the old skin's near-black canvas.
    const rule = TOKENS.match(/\[data-skin='rounds'\]\s*\.qm-rounds-settings\s*\{([^}]*)\}/);
    expect(rule, '.qm-rounds-settings has no rule').not.toBeNull();
    const bg = rule![1].match(/background:\s*var\((--rounds-[a-z0-9-]+)\)/)?.[1];
    expect(bg, '.qm-rounds-settings no longer paints a ground — the opaque ' +
      'AppFrame canvas shows through and the stage is invisible').toBeTruthy();
    expect(
      token(bg!).toLowerCase(),
      'the settings ground equals the OLD skin canvas — the fork is a no-op',
    ).not.toBe(linearToken('--color-linear-bg').toLowerCase());
  });

  it('no fill or state token is used as a text colour in the C1-e block', () => {
    // The recurring defect, now six instances deep in the token file's own
    // prose. EXACT membership, not prefix: `--rounds-ready-text` is the CORRECT
    // token and merely starts with `--rounds-ready`. That is the substring trap
    // that made C1-c's label guard vacuous.
    const FILL_ONLY = [
      '--rounds-accent',
      '--rounds-critical',
      '--rounds-em-fill',
      '--rounds-ready',
      '--rounds-processing',
      '--rounds-signed',
    ];
    const seen = [...BLOCK.matchAll(/(?:^|\s)color:\s*var\((--rounds-[a-z0-9-]+)\)/g)];
    const offenders = seen.map((m) => m[1]).filter((t) => FILL_ONLY.includes(t));
    expect(offenders, 'fill/state tokens used as text in the C1-e block').toEqual([]);
    // Non-vacuity: the matcher must be finding `color:` declarations at all…
    expect(seen.length, 'the color: matcher found nothing to check').toBeGreaterThanOrEqual(3);
    // …and it must be able to reject. `border-color:` is deliberately NOT a
    // match (the `(?:^|\s)` anchor), which is the other half of the same claim.
    const M = /(?:^|\s)color:\s*var\((--rounds-[a-z0-9-]+)\)/;
    expect(M.test(" color: var(--rounds-accent)")).toBe(true);
    expect(M.test(" border-color: var(--rounds-accent)")).toBe(false);
  });

  it('the disabled control keeps text-2, not the faintest tier', () => {
    // "Disabled text is still text." `--rounds-text-3` on surface-2 is 4.18:1 —
    // the same near-miss C1-d found inside `.qm-rounds-panel`, arriving on the
    // one permanently-disabled control in the product (Billing).
    const rule = BLOCK.match(/\.qm-rounds-btn:disabled[\s\S]{0,200}?\{([^}]*)\}/);
    expect(rule, 'the :disabled rule is gone').not.toBeNull();
    const bg = token(rule![1].match(/background:\s*var\((--rounds-[a-z0-9-]+)\)/)![1]);
    const fg = token(rule![1].match(/(?:^|\s)color:\s*var\((--rounds-[a-z0-9-]+)\)/)![1]);
    expect(contrast(fg, bg), 'disabled label on the disabled fill').toBeGreaterThanOrEqual(AA);
    // Negative control: the tier it deliberately did NOT use really does fail
    // there, or "it passes" is true of a rule that never had a choice to make.
    expect(contrast(token('--rounds-text-3'), bg)).toBeLessThan(AA);
    expect(contrast(token('--rounds-text-3'), bg)).toBeCloseTo(4.18, 2);
  });

  it('every qm-rounds-* class C1-e applies is declared, and every one declared is applied', () => {
    // Both directions. An applied class with no rule is a no-op that reads as a
    // restyle; a declared class with no caller cannot be proven by rule 7,
    // because nothing renders and nothing can be made to fail.
    const applied = new Set(
      [...[...SETTINGS_SRC.values()].join('\n').matchAll(/className=\{?[^}>]*\}?/g)].flatMap((m) =>
        [...m[0].matchAll(/qm-rounds-[a-z0-9]+(?:-[a-z0-9]+)*/g)].map((x) => x[0]),
      ),
    );
    expect(applied.size, 'no qm-rounds-* classes found in the settings sources')
      .toBeGreaterThanOrEqual(6);
    for (const c of ['qm-rounds-host', 'qm-rounds-settings', 'qm-rounds-dialog']) {
      expect(applied.has(c), `${c} is not applied anywhere under ${SETTINGS_ROOT}`).toBe(true);
    }
    // The scanner reads classNames, not prose — checked against a class named
    // ONLY in this surface's comments.
    expect(
      applied.has('qm-rounds-btn'),
      'a class named only in prose was collected as applied',
    ).toBe(false);

    const missing = [...applied].filter((c) => !new RegExp(`\\.${c}\\b`).test(TOKENS));
    expect(missing, 'these classes are applied under settings but have no CSS rule').toEqual([]);

    // The other direction, over the classes THIS block declares.
    const declared = new Set(
      [...BLOCK.matchAll(/\[data-skin='rounds'\][^{]*?\.(qm-rounds-[a-z0-9-]+)/g)].map((m) => m[1]),
    );
    expect(declared.size, 'no qm-rounds-* rules found in the C1-e block').toBeGreaterThanOrEqual(4);
    // ⚠️ CONSUMERS BY TRAVERSAL OF ALL OF src/, NOT A HAND LIST. C1-e's classes
    // are applied from settings AND from the two visit error routes; a list of
    // roots reported 72 phantom orphans the last time one was written here.
    const ALL_SRC = walkSources('src')
      .map((f) => readFileSync(f, 'utf8'))
      .join('\n');
    expect(ALL_SRC, 'the src traversal returned nothing recognisable').toContain('qm-rounds-host');
    const orphans = [...declared].filter((c) => !new RegExp(`\\b${c}\\b`).test(ALL_SRC));
    expect(orphans, 'these C1-e classes are declared but nothing applies them').toEqual([]);
  });
});
