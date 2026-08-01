// ============================================================================
// The C1 host bridge: both sides of every line, and the contrast it implies.
// ----------------------------------------------------------------------------
// `[data-skin='rounds'] .qm-rounds-host { --color-linear-*: var(--rounds-*) }`
// is how C1 reaches ~434 inline `style={{}}` objects without forking them. It
// has three ways to be silently wrong, and none of them is a build error:
//
//  1. A LINEAR NAME THE SURFACES READ IS MISSING from the bridge. That one
//     colour keeps its old-skin value, so a single component looks wrong on an
//     otherwise-correct screen — which reads as a bug in that component.
//
//  2. A ROUNDS TOKEN ON THE RIGHT-HAND SIDE IS NOT DECLARED. This is the worst
//     of the three and the one the C1 plan actually shipped on paper, by naming
//     `--rounds-surface-0`. An undeclared custom property makes the declaration
//     invalid-at-computed-value-time: the property becomes unset and the
//     affected CSS property falls to its INITIAL value. For `background-color`
//     that is `transparent` — the stage shows through the surface. There is no
//     build error, no console error and no CSS parse error. It was proven in
//     headless chromium before this guard was written.
//
//  3. A FILL TOKEN IS MAPPED ONTO A NAME USED AS A FOREGROUND. This palette has
//     now failed AA that way SIX times (`--rounds-em`, `--rounds-accent`,
//     `--rounds-signed`, `--rounds-ready`, and the two closed here). Measured
//     rather than argued: every fill token in this file lands between 2.58:1
//     and 2.93:1 on the Rounds surfaces, and `--rounds-em` lands at 4.40 —
//     under the bar and close enough to it to read as passing.
//
// ⚠️ THE SURFACE LIST IS DERIVED BY TRAVERSAL, NEVER MAINTAINED BY HAND.
// A hand-written bash glob undercounted these names 21 against 22 — it missed
// `settings/security/mfa/` because bash does not expand `**` recursively
// without `globstar`, and nothing would have reported the gap. A maintained
// array has the same failure mode with a slower fuse: a file added to a C1
// directory next month is simply not covered, and every assertion below stays
// green while covering less.
// ============================================================================

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const TOKENS = readFileSync('src/app/rounds-tokens.css', 'utf8');

/** Directories whose .tsx files are C1 surfaces. Directories, not files — a new
 *  file inside one of these is covered the day it is added. */
const SURFACE_DIRS = [
  'src/app/login',
  'src/app/signup',
  'src/app/waitlist',
  'src/app/forgot-password',
  'src/app/reset-password',
  'src/app/check-email',
  'src/app/settings',
];
/** Individual C1 surfaces that do not live under a directory of their own. */
const SURFACE_FILES = [
  'src/components/ui/auth-shell.tsx',
  'src/components/error-fallback.tsx',
  'src/components/skeleton.tsx',
  'src/components/ui/empty-state.tsx',
];

/**
 * Next.js CONVENTION files are C1 surfaces wherever they live — `error.tsx`,
 * `loading.tsx`, `not-found.tsx`. Collected by traversal across the whole app
 * rather than listed, because that is the point: `visits/[id]/not-found.tsx`
 * and `visits/[id]/loading.tsx` were both C1-c surfaces and NEITHER was in the
 * hand-written list above. The list looked complete and was not — which is the
 * same failure the `globstar` note below describes, arriving a second time
 * from a different direction.
 */
const CONVENTION_FILES = ['error.tsx', 'loading.tsx', 'not-found.tsx'];

function walk(dir: string): string[] {
  let out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    if (statSync(p).isDirectory()) out = out.concat(walk(p));
    else if (p.endsWith('.tsx')) out.push(p);
  }
  return out;
}

function surfaceFiles(): string[] {
  const fromDirs = SURFACE_DIRS.flatMap((d) => {
    try {
      return walk(d);
    } catch {
      return [];
    }
  });
  const conventions = walk('src/app').filter((f) =>
    CONVENTION_FILES.some((c) => f.endsWith(`/${c}`)),
  );
  return [...new Set([...fromDirs, ...conventions, ...SURFACE_FILES])].sort();
}

/** The declaration block of the host bridge, comments stripped. */
function bridgeBody(): string {
  const start = TOKENS.indexOf(".qm-rounds-host {");
  if (start === -1) return '';
  const end = TOKENS.indexOf('\n}', start);
  if (end === -1) return '';
  return TOKENS.slice(start, end).replace(/\/\*[\s\S]*?\*\//g, '');
}

const LINEAR = /--color-linear-[a-zA-Z0-9-]+/g;

// ── contrast, so the AA rule is executable rather than a comment ───────────
function srgb(c: number): number {
  const v = c / 255;
  return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
}
function luminance(hex: string): number {
  const h = hex.replace('#', '');
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b);
}
function contrast(a: string, b: string): number {
  const [x, y] = [luminance(a), luminance(b)];
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}
/**
 * The backdrops a C1 SURFACE actually sits on: the stage mid-stop that `body`
 * paints, and the panel surface those screens use. Not every Rounds surface.
 *
 * ⚠️ THIS LIST WAS NARROWED, DELIBERATELY, AND THE FIRST VERSION WAS WRONG.
 * It began as all four Rounds surfaces with a `min()` over them — i.e. "assume
 * every text token might land on the lightest one". That made the guard
 * STRICTER THAN AA and it immediately flagged `--rounds-text-3`, which is
 * shipped across the board, the stage, the gates and the signed screen and is
 * green under axe. Measured: text-3 is 4.68 on surface-1 and 4.59 on
 * stage-bg-2 (pass) but 3.76 on surface-3 (fail) — so the token is fine where
 * it is used and the guard was wrong about where that is.
 *
 * A static guard cannot know the real foreground/background PAIRING; that is
 * exactly what axe measures at runtime, on the rendered DOM, and
 * `rounds-a11y.spec.ts` already does it. This check exists for the one thing
 * axe cannot do — catch a bad mapping BEFORE any surface adopts the bridge,
 * when there is nothing rendered for axe to look at.
 */
const BACKDROPS = ['#161b24', '#171d27'];

/**
 * Linear names used BOTH as a foreground and as a fill on C1 surfaces. One
 * bridge line cannot serve both roles, so the mapping follows the majority use
 * and the minority sites get forked by the split that owns them.
 *
 * ⚠️ NOT AN EXEMPTION LIST — a DEBT list. Every entry names the sites and the
 * split that must remove it, and the test below asserts each entry still
 * matches real source. An allowlist that outlives its reason is how a guard
 * rots into decoration.
 */
const DEFERRED_FORKS: Record<string, { sites: number; owner: string; why: string }> = {
  '--color-linear-sage': {
    sites: 4,
    owner: 'C1-e / C1-f (all four sites are under settings/note-format)',
    why:
      'used 4× as a foreground and 7× as a fill. Mapped to --rounds-accent so ' +
      'the 7 fills stay right; two of the four foregrounds are emoji glyphs ' +
      'that axe does not measure, and the other two need a forked ' +
      '--rounds-accent-text at their call site. ' +
      // ⚠️ CORRECTED 2026-08-01. This said "aria-hidden glyphs that axe does
      // not measure", conflating two different escapes and getting the
      // load-bearing one wrong. aria-hidden does NOT hide text from axe's
      // contrast rule (`excludeHidden: false`, axe.js:31653). Those two spans
      // are 🛡 emoji, and a bare-emoji element never reaches
      // colorContrastEvaluate at all — colorContrastMatches rejects it via
      // hasRealTextChildren (axe.js:27704), which strips unicode. Measured:
      // they land in neither violations, incomplete, nor passes, while
      // "🛡 verified" in the same run is a full violation. Three distinct
      // mechanisms hide contrast from this gate — aria-hidden is not one of
      // them; single-character text and bare emoji are.
      'The outcome is unchanged; the mechanism recorded here was not.',
  },
};
function tokenValue(name: string): string | null {
  const m = TOKENS.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})\\s*;`));
  return m ? m[1] : null;
}

describe('C1 host bridge', () => {
  const files = surfaceFiles();
  const readNames = new Set<string>();
  for (const f of files) {
    for (const m of readFileSync(f, 'utf8').match(LINEAR) ?? []) readNames.add(m);
  }
  const body = bridgeBody();
  const declaredInBridge = new Set(
    [...body.matchAll(/^\s*(--color-linear-[a-zA-Z0-9-]+)\s*:/gm)].map((m) => m[1]),
  );

  it('the traversal finds surfaces — positive control', () => {
    // Without this, a broken walk() returns [] and EVERY assertion below passes
    // by covering nothing. That is this project's named recurring defect.
    expect(files.length, 'surface traversal returned no files').toBeGreaterThan(30);
    expect(files.some((f) => f.includes('settings/security/mfa'))).toBe(true);
    expect(readNames.size, 'no --color-linear-* names found on any surface').toBeGreaterThan(15);
  });

  it('the bridge block was actually located — positive control', () => {
    expect(body.length, 'no .qm-rounds-host block found in rounds-tokens.css').toBeGreaterThan(200);
    expect(declaredInBridge.size).toBeGreaterThan(15);
  });

  it('every linear name the C1 surfaces read is bridged', () => {
    const missing = [...readNames].filter((n) => !declaredInBridge.has(n)).sort();
    expect(
      missing,
      'these --color-linear-* names are read by a C1 surface but not redeclared ' +
        'in the host bridge, so they keep their OLD-SKIN value — one component ' +
        'looking wrong on an otherwise-correct screen:\n  ' + missing.join('\n  '),
    ).toEqual([]);
  });

  it('every Rounds token on the RIGHT of the bridge is declared', () => {
    // The --rounds-surface-0 trap. An undeclared token here is transparent, not
    // an error.
    const rhs = [...body.matchAll(/:\s*[^;]*?var\((--rounds-[a-zA-Z0-9-]+)/g)].map((m) => m[1]);
    expect(rhs.length, 'no var(--rounds-*) references found on the right-hand side').toBeGreaterThan(15);
    const undeclared = [...new Set(rhs)].filter((t) => !new RegExp(`${t}:`).test(TOKENS)).sort();
    expect(
      undeclared,
      'these tokens are referenced by the bridge but never declared. The CSS ' +
        'does not error — the property becomes unset and falls to its INITIAL ' +
        'value (background-color: transparent):\n  ' + undeclared.join('\n  '),
    ).toEqual([]);
  });

  it('any linear name used as a FOREGROUND maps to a token that clears AA', () => {
    // Derived from usage, not from a list someone maintains: if a surface ever
    // writes `color: var(--color-linear-X)`, then X's bridge target is a text
    // colour and must clear 4.5:1 on the worst Rounds backdrop.
    const foreground = new Set<string>();
    for (const f of files) {
      const src = readFileSync(f, 'utf8');
      for (const m of src.matchAll(/(?:color|stroke)\s*:\s*'?var\((--color-linear-[a-zA-Z0-9-]+)\)/g)) {
        foreground.add(m[1]);
      }
    }
    expect(foreground.size, 'no foreground usages found — the matcher is broken').toBeGreaterThan(3);

    const failures: string[] = [];
    for (const name of foreground) {
      if (name in DEFERRED_FORKS) continue; // debt, asserted separately below
      const line = body.match(new RegExp(`${name}:\\s*([^;]+);`));
      if (!line) continue;
      const target = line[1].match(/var\((--rounds-[a-zA-Z0-9-]+)\)/)?.[1];
      if (!target) continue;
      const hex = tokenValue(target);
      if (!hex) continue; // color-mix / rgba targets are not point-checkable here
      const worst = Math.min(...BACKDROPS.map((b) => contrast(hex, b)));
      if (worst < 4.5) failures.push(`${name} → ${target} (${hex}) = ${worst.toFixed(2)}:1`);
    }
    expect(
      failures,
      'a linear name used as a FOREGROUND is bridged to a token that fails AA ' +
        'on a Rounds surface. This palette has failed this way six times:\n  ' +
        failures.join('\n  '),
    ).toEqual([]);
  });

  it('the deferred forks are real debt, not a stale exemption', () => {
    // An allowlist entry that no longer matches anything is worse than no
    // allowlist: it silently exempts a name that may since have been remapped.
    // So each entry must still describe the source.
    for (const [name, debt] of Object.entries(DEFERRED_FORKS)) {
      const fg = files.reduce((n, f) => {
        const src = readFileSync(f, 'utf8');
        return (
          n +
          [...src.matchAll(new RegExp(`(?:color|stroke)\\s*:\\s*'?var\\(${name}\\)`, 'g'))].length
        );
      }, 0);
      expect(
        fg,
        `${name} is on the deferred-fork list claiming ${debt.sites} foreground ` +
          `site(s) owned by ${debt.owner}, but the source now has ${fg}. ` +
          `Update the count, or drop the entry if the fork has landed.`,
      ).toBe(debt.sites);
      // And it must still be mapped to something that would FAIL — otherwise
      // the debt is already paid and the entry is dead weight.
      const line = body.match(new RegExp(`${name}:\\s*([^;]+);`));
      const target = line?.[1].match(/var\((--rounds-[a-zA-Z0-9-]+)\)/)?.[1];
      const hex = target ? tokenValue(target) : null;
      if (hex) {
        const worst = Math.min(...BACKDROPS.map((b) => contrast(hex, b)));
        expect(
          worst,
          `${name} → ${target} now clears AA at ${worst.toFixed(2)}:1, so the ` +
            `deferred-fork entry is obsolete. Delete it.`,
        ).toBeLessThan(4.5);
      }
    }
  });

  it('the contrast maths is right — negative control', () => {
    // If the calculator were broken, the assertion above would pass on anything.
    expect(contrast('#ffffff', '#000000')).toBeCloseTo(21, 0);
    expect(contrast('#161b24', '#161b24')).toBeCloseTo(1, 5);
    // The two tokens this bridge introduced clear the bar on C1's backdrops…
    expect(Math.min(...BACKDROPS.map((b) => contrast('#e8b168', b)))).toBeGreaterThan(4.5);
    expect(Math.min(...BACKDROPS.map((b) => contrast('#7ab0f5', b)))).toBeGreaterThan(4.5);
    // …and the fills that would otherwise have been used as text do not.
    // `--rounds-processing` fails on every Rounds surface (3.63 best).
    expect(Math.min(...BACKDROPS.map((b) => contrast('#3b6fd4', b)))).toBeLessThan(4.5);
    // `--rounds-accent` is what `sage` would have been bridged to without the
    // deferred-fork entry: 3.22 on surface-1, 3.15 on stage-bg-2 — under the
    // 4.5 bar on both. (An earlier draft asserted `< 3.0`, a figure carried
    // over from the WIDER backdrop set where accent reaches 2.58. Assert the
    // bar that matters, not a number remembered from a different question.)
    expect(Math.min(...BACKDROPS.map((b) => contrast('#5b5bd6', b)))).toBeLessThan(4.5);

    // ⚠️ `--rounds-em` is deliberately NOT asserted as a failure here. It is a
    // NEAR MISS — 5.48/5.37 on C1's own backdrops, 4.89 on surface-2, and only
    // 4.40 on surface-3. An earlier draft of this control asserted it failed,
    // which was true only against a wider backdrop set that this guard no
    // longer uses. The reason `--rounds-em-text` exists is robustness across
    // ALL surfaces, not a failure on these two — and saying otherwise in a
    // comment is how a wrong number outlives the person who wrote it.
    expect(Math.min(...BACKDROPS.map((b) => contrast('#c4841c', b)))).toBeGreaterThan(4.5);
    expect(contrast('#c4841c', '#252d3a')).toBeLessThan(4.5); // surface-3, the one it misses
  });

  it('the surfaces C1-c restyled ADOPT the host, and pair it with an owned class', () => {
    // Replaces C1-b's "nothing has adopted this yet" assertion, which said in
    // its own message that C1-c should delete it. The claim now worth holding
    // is the opposite one: adoption is real, and every adopter also carries a
    // `qm-rounds-*` class of its own — because that class is the currency axe's
    // ownership rule spends. A host without an owned class is a surface Gate C
    // will classify as inherited and merely report.
    const adopters = files.filter((f) => readFileSync(f, 'utf8').includes('qm-rounds-host'));
    expect(adopters.length, 'no surface adopts the bridge').toBeGreaterThan(2);
    const hostOnly = adopters.filter((f) => {
      const src = readFileSync(f, 'utf8');
      const owned = [...src.matchAll(/qm-rounds-[a-z0-9-]+/g)]
        .map((m) => m[0])
        .filter((c) => c !== 'qm-rounds-host');
      return owned.length === 0;
    });
    expect(
      hostOnly,
      'these files carry qm-rounds-host but no owned qm-rounds-* class, so axe ' +
        'will treat their violations as inherited and merely report them:\n  ' +
        hostOnly.join('\n  '),
    ).toEqual([]);
  });

  it('the bridge is SCOPED — it must not repaint the whole app', () => {
    // `:root[data-skin]` here would replace the old skin everywhere instead of
    // adding to it, and the relay's standing rule is that the old skin remains
    // default until item F.
    expect(TOKENS).toContain("[data-skin='rounds'] .qm-rounds-host {");
    const rootBlocks = TOKENS.match(/^:root\[data-skin='rounds'\][^{]*\{/gm) ?? [];
    for (const b of rootBlocks) {
      const start = TOKENS.indexOf(b);
      const chunk = TOKENS.slice(start, TOKENS.indexOf('\n}', start));
      expect(
        chunk.includes('--color-linear-'),
        'a :root-scoped block redeclares --color-linear-*, which repaints every ' +
          'route rather than the C1 surfaces that opt in',
      ).toBe(false);
    }
  });
});
