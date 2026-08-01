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
// ─── 2. FLAG SAFETY OF EVERY FORK ──────────────────────────────────────────
//
// `--rounds-*` is declared ONLY under `[data-skin='rounds']`. A bare
// `var(--rounds-x)` with the flag off is invalid-at-computed-value-time: no
// build error, no console error, the property falls to its INITIAL value
// (`background` → transparent). This repo has already shipped that bug on
// paper once. So every `var(--rounds-…)` on this surface must either carry a
// FALLBACK or sit inside an `isSkinRounds()` branch — checked by traversal,
// with the classifier positive-controlled on all four shapes.
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

  it('the FLAG-OFF half of the fork is still safe on the old sage', () => {
    // The fallback form has two branches and only one of them is new. #0d1611
    // on --color-linear-sage is 6.72:1 and must stay that way, or "byte-
    // identical with the flag off" would be a claim about bytes and not about
    // what a doctor can read.
    expect(contrast('#0d1611', linearToken('--color-linear-sage'))).toBeGreaterThanOrEqual(AA);
    expect(contrast('#0d1611', linearToken('--color-linear-sage'))).toBeCloseTo(6.72, 2);
  });

  it('the failing literal is GONE from the call site — it survives ONLY as a fallback', () => {
    // ⚠️ THE PRECISE CLAIM, because the loose one is false. `#0d1611` is still
    // in this file — it is the flag-OFF branch of `var(--rounds-on-accent,
    // #0d1611)`, and it must be. What must be gone is the BARE form, where the
    // literal is the value the bridge then retints underneath.
    const all = [...code.matchAll(/#0d1611/g)];
    const asFallback = [...code.matchAll(/var\(\s*--rounds-[a-z0-9-]+\s*,\s*#0d1611\s*\)/g)];
    // Non-vacuity FIRST: if the literal has vanished entirely, "every
    // occurrence is a fallback" is trivially true of zero occurrences — and the
    // flag-OFF branch would have silently lost its colour.
    expect(all.length, 'the #0d1611 flag-OFF fallback has disappeared entirely').toBeGreaterThanOrEqual(1);
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
    // This file EXPLAINS, in prose, why a bare `var(--rounds-ready)` cannot be
    // used — and writes the token in the explanation. A scan over raw text
    // counts the explanation as a use. Same defect as gate-rounds-bridge:332.
    expect(src).toContain('A bare `var(--rounds-ready)` cannot be used');
    expect(code).not.toContain('A bare `var(--rounds-ready)` cannot be used');
    const raw = [...src.matchAll(/var\(--rounds-/g)].length;
    const exe = [...code.matchAll(/var\(--rounds-/g)].length;
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

    // The label: the token on the Rounds side of the fork.
    const labelToken = code.match(/color:\s*rounds\s*\?\s*'var\((--rounds-[a-z0-9-]+)\)'/)?.[1];
    expect(labelToken, 'the pill label is no longer a forked --rounds-* token').toBeTruthy();

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

  it('the fork moves the label into the READY family, not the accent family', () => {
    // ⚠️ THIS ONE IS NOT A CONTRAST BUG AND MUST NOT BE ASSERTED AS ONE.
    // Un-forked, the label reads `--color-linear-sage-bright`, which the bridge
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
      /color:\s*rounds\s*\?\s*'var\((--rounds-[a-z0-9-]+)\)'/,
    )![1];
    expect(labelToken.startsWith('--rounds-ready')).toBe(true);
    expect(labelToken).not.toBe('--rounds-accent-text');
  });

  it('the flag-OFF branch of every pill fork is still a literal the old skin ships', () => {
    // The other half of "byte-identical with the flag off". If the sage
    // literals go, the fork's else-branch is dead and the whole thing should be
    // simplified — but only then.
    expect(code).toMatch(/:\s*'rgba\(122, 166, 140, 0\.13\)'/);
    expect(code).toMatch(/:\s*'1px solid rgba\(122, 166, 140, 0\.32\)'/);
    expect(code).toMatch(/:\s*'var\(--color-linear-sage-bright\)'/);
  });
});

// ============================================================================
describe('C1-e — no --rounds-* token resolves undeclared with the flag off', () => {
  /** Is a `var(--rounds-…)` at `idx` SAFE with the flag off?
   *
   *  Two ways to be safe, and only two:
   *    · a FALLBACK — `var(--rounds-x, #0d1611)`. Keyed on the same attribute
   *      that declares the token, so there is ONE condition rather than two
   *      that must agree.
   *    · a BUILD-TIME GUARD — the value sits on the true branch of a ternary
   *      whose condition is this module's `isSkinRounds()` flag.
   *
   *  ⚠️ THE GUARD MUST BE **THIS FILE'S ROUNDS FLAG**, not any condition. A
   *  `var(--rounds-x)` behind `isCompact ? … : …` is exactly as undeclared with
   *  the flag off as a bare one, and a classifier that accepted any ternary
   *  would pass it. Controlled below, case (4).
   *
   *  ⚠️ AND THE `?` MUST BE A TERNARY `?`. `error?.field` and `a ?? b` both put
   *  a `?` in the text; treating either as a guard would let an unsafe value
   *  through on nothing more than an optional chain happening to sit above it.
   *  Narrowed deliberately — an over-strict probe is also a defect — and the
   *  narrowed case still asserts: case (5) below is flagged. */
  function lastTernaryQ(s: string): number {
    for (let i = s.length - 1; i >= 0; i--) {
      if (s[i] !== '?') continue;
      if (s[i + 1] === '.' || s[i + 1] === '?') continue; // `?.` / `??`
      if (s[i - 1] === '?') continue; // second half of `??`
      return i;
    }
    return -1;
  }

  type Verdict = 'fallback' | 'guarded' | 'UNSAFE';
  interface Ref {
    file: string;
    tokenName: string;
    verdict: Verdict;
  }

  function scan(file: string, raw: string): Ref[] {
    const src = executableOnly(raw);
    // The flag identifier is DERIVED from the file, not assumed to be `rounds`.
    const flagVar = src.match(
      /const\s+([A-Za-z_$][\w$]*)\s*=\s*isSkinRounds\s*\(\s*\)/,
    )?.[1];
    const guardRe = new RegExp(
      flagVar ? `\\b${flagVar}\\b|isSkinRounds\\s*\\(` : 'isSkinRounds\\s*\\(',
    );
    const out: Ref[] = [];
    for (const m of src.matchAll(/var\(\s*(--rounds-[a-z0-9-]+)\s*(,?)/g)) {
      const [, tokenName, comma] = m;
      if (comma === ',') {
        out.push({ file, tokenName, verdict: 'fallback' });
        continue;
      }
      const before = src.slice(0, m.index!);
      const q = lastTernaryQ(before);
      if (q === -1) {
        out.push({ file, tokenName, verdict: 'UNSAFE' });
        continue;
      }
      // The condition is whatever sits between the enclosing property/argument
      // boundary and the `?`. Newline is NOT a boundary: the shipped forks are
      // prettier-wrapped as `background: rounds\n  ? '…'`.
      const bound = Math.max(
        before.lastIndexOf(':', q),
        before.lastIndexOf('{', q),
        before.lastIndexOf(',', q),
        before.lastIndexOf('(', q),
        before.lastIndexOf(';', q),
      );
      const cond = before.slice(bound + 1, q);
      out.push({ file, tokenName, verdict: guardRe.test(cond) ? 'guarded' : 'UNSAFE' });
    }
    return out;
  }

  it('the classifier can fail — four positive controls and one narrowing control', () => {
    const P = 'const rounds = isSkinRounds();\n';
    const one = (s: string) => scan('probe.tsx', s)[0]?.verdict;

    // (1) bare — the recorded incident: undeclared, falls to initial value.
    expect(one(P + "x = { color: 'var(--rounds-text-1)' };")).toBe('UNSAFE');
    // (2) fallback — safe, one condition.
    expect(one(P + "x = { color: 'var(--rounds-text-1, #0d1611)' };")).toBe('fallback');
    // (3) guarded by THIS file's flag — safe, build-time fork.
    expect(one(P + "x = { color: rounds ? 'var(--rounds-text-1)' : '#111' };")).toBe('guarded');
    // (4) ⚠️ guarded by SOMETHING ELSE — must NOT count. This is the control
    //     that separates "is behind a ternary" from "is behind the flag".
    expect(one(P + "x = { color: isCompact ? 'var(--rounds-text-1)' : '#111' };")).toBe('UNSAFE');
    // (5) the narrowing control: an optional chain above a bare value is not a
    //     guard, and must not be mistaken for one.
    expect(one(P + "const f = error?.field;\nx = { color: 'var(--rounds-text-1)' };")).toBe('UNSAFE');
    // …and a file with no flag at all cannot launder anything through a local
    // variable that merely happens to be named `rounds`.
    expect(one("x = { color: rounds ? 'var(--rounds-text-1)' : '#111' };")).toBe('UNSAFE');
  });

  it('the traversal reached the settings surface — non-vacuity', () => {
    // A traversal that silently covers nothing returns "no offenders" for every
    // question asked of it. State the boundary and prove it was entered.
    expect(SETTINGS_FILES.length, `only ${SETTINGS_FILES.length} files under ${SETTINGS_ROOT}`)
      .toBeGreaterThanOrEqual(15);
    for (const f of [ENROLL, MANAGE, DELETE_DIALOG, EMAIL_DIALOG, 'src/app/settings/page.tsx']) {
      expect(SETTINGS_FILES, `${f} was not reached by the traversal`).toContain(f);
    }
    // …and it descended (the MFA files are two levels down).
    expect(SETTINGS_FILES.some((f) => f.split('/').length > 4)).toBe(true);
    // Positive control on the CONTENT, not just the paths: the traversal must
    // find a string we know is there.
    expect([...SETTINGS_SRC.values()].join('\n')).toContain('qm-rounds-host');
  });

  it('every var(--rounds-*) under src/app/settings is fallback-safe or flag-guarded', () => {
    const refs = SETTINGS_FILES.flatMap((f) => scan(f, srcOf(f)));

    // Non-vacuity BEFORE the emptiness assertion: if nothing was examined, an
    // empty offender list means the scanner found no work, not that the surface
    // is safe.
    expect(
      refs.length,
      'no var(--rounds-*) reference was examined at all — the scan covered nothing',
    ).toBeGreaterThanOrEqual(4);
    // And both safe shapes are actually present, or one branch of the
    // classifier has never been exercised on real code.
    expect(refs.some((r) => r.verdict === 'fallback')).toBe(true);
    expect(refs.some((r) => r.verdict === 'guarded')).toBe(true);

    const unsafe = refs
      .filter((r) => r.verdict === 'UNSAFE')
      .map((r) => `${r.file}: ${r.tokenName}`);
    expect(
      unsafe,
      'these resolve UNDECLARED with the flag off — no build error, no console ' +
        'error, the property silently falls to its INITIAL value:\n  ' +
        unsafe.join('\n  '),
    ).toEqual([]);
  });

  it('a file that build-time forks really does import the flag', () => {
    // The guarded verdict is only worth anything if `isSkinRounds` is the real
    // one. A local shadow would be a different function with the same name.
    const guarding = SETTINGS_FILES.filter((f) =>
      scan(f, srcOf(f)).some((r) => r.verdict === 'guarded'),
    );
    expect(guarding.length, 'no settings file uses the build-time fork').toBeGreaterThanOrEqual(1);
    for (const f of guarding) {
      expect(srcOf(f), `${f} forks on isSkinRounds without importing it`).toMatch(
        /import\s*\{[^}]*isSkinRounds[^}]*\}\s*from\s*'@\/config\/skin-rounds'/,
      );
    }
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
