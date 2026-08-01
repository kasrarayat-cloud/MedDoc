// ============================================================================
// C1-d — the auth surface: the contrast the gate cannot see, and the selector
// contract 45 spec files stand on.
// ----------------------------------------------------------------------------
// Two jobs, and neither is decoration.
//
// ─── 1. THE CONTRAST REGRESSION THE BRIDGE INTRODUCES ──────────────────────
//
// The Rounds host bridge redeclares `--color-linear-*` on a scoped class, so
// every inline `var()` read on the auth screens retints for free. What it
// cannot touch is a LITERAL, and the old skin puts a near-black literal on top
// of its brand fill. Measured:
//
//     .qm-lin-btn-primary  #0d1611  on sage 6.72:1 → on accent **3.43:1**
//     waitlist submit      #08090a  on sage 7.27:1 → on accent **3.71:1**
//     .qm-c3-auth-mark     #0c1410  on sage 6.82:1 → on accent **3.48:1**
//       …and on the gradient's far stop                       **2.71:1**
//
// That is the submit button of /login, /signup, /forgot-password and
// /reset-password, and /waitlist's.
//
// ⚠️ GATE C STRUCTURALLY CANNOT CATCH IT, which is why this file exists rather
// than a line in the pack. `rounds-a11y`'s ownership rule climbs to the nearest
// ancestor-or-self carrying ANY class; a `<button class="qm-lin-btn-primary">`
// answers for ITSELF, matches no `qm-rounds-`, and its violation is filed
// "inherited" — reported, never blocking. A contrast bug on the most important
// control on the screen, invisible to the gate written to catch contrast bugs.
//
// ⚠️ CORRECTED 2026-08-01 — THE BRAND MARK ESCAPES FOR A DIFFERENT REASON, AND
// THE ONE RECORDED HERE WAS WRONG. This said "both spans are `aria-hidden`, so
// axe never evaluates them at all". Both clauses are false, measured against
// the shipped axe-core 4.11.3 in real chromium:
//
//   1. `aria-hidden` DOES NOT hide text from the contrast rule. `color-contrast`
//      declares `excludeHidden: false` (axe.js:31653) and `colorContrastEvaluate`
//      gates only on `_isVisibleOnScreen` (axe.js:26245) — visual visibility, not
//      `aria-hidden`, which is a different function. A block `<p aria-hidden>`
//      with these colours returns a full SERIOUS violation, identical to its
//      non-hidden twin.
//   2. Only ONE of the two spans is hidden anyway — `.qm-c3-auth-word`
//      (auth-shell.tsx:96) is not.
//
// The real escape is SINGLE-CHARACTER TEXT. `axe.js:26332` sets
// `shortTextContent = visibleText.length === 1` and bails to INCOMPLETE with the
// ratio recorded but no violation. The control that isolates it: a one-character
// element with NO `aria-hidden` is *also* incomplete, while "QuillMD" — same
// colours, not hidden — is a full violation. And `rounds-a11y.spec.ts:279-283`
// says in as many words that `incomplete` is reported and never asserted on.
//
// So the conclusion this file was built on survives, at three removes rather
// than one — but the *reason* matters, because "it was aria-hidden" invites the
// fix of un-hiding it, which would change nothing.
//
// So the ratios are computed here, from the SHIPPED token values, and the
// arithmetic is negative-controlled against the pre-fix literals — if the
// formula ever stops being able to fail, the zeros above mean nothing.
//
// ─── 2. THE SELECTOR CONTRACT ──────────────────────────────────────────────
//
// C1-d is "where the copy-register work lands", and the auth surface is held by
// more spec files than any other in the product: 38 import `helpers/signup.ts`,
// and 7 more reach /login directly through `helpers/auth.ts`. The plan's Hard
// prohibitions name only the signup half. Both halves are pinned here, at the
// source level, so the failure arrives in 30ms from a unit rather than 36
// minutes into the E2E job reading "Rounds broke everything".
// ============================================================================

import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

/** Every .tsx under a root, recursively. `readdirSync` with `withFileTypes`
 *  rather than a glob: bash does not expand `**` without `globstar`, and a
 *  hand-written glob has already undercounted this project's surface list
 *  twice. */
function walkTsx(dir: string): string[] {
  const out: string[] = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...walkTsx(p));
    else if (p.endsWith('.tsx')) out.push(p);
  }
  return out;
}

const TOKENS = readFileSync('src/app/rounds-tokens.css', 'utf8');
const GLOBALS = readFileSync('src/app/globals.css', 'utf8');
const SHELL = readFileSync('src/components/ui/auth-shell.tsx', 'utf8');

const FORMS = {
  login: 'src/app/login/login-form.tsx',
  signup: 'src/app/signup/signup-form.tsx',
  waitlist: 'src/app/waitlist/waitlist-form.tsx',
  forgot: 'src/app/forgot-password/forgot-password-form.tsx',
  reset: 'src/app/reset-password/reset-password-form.tsx',
  checkEmail: 'src/app/check-email/check-email-resend.tsx',
} as const;
const FORM_SRC = Object.fromEntries(
  Object.entries(FORMS).map(([k, p]) => [k, readFileSync(p, 'utf8')]),
) as Record<keyof typeof FORMS, string>;

const SIGNUP_HELPER = readFileSync('tests/e2e/helpers/signup.ts', 'utf8');
const AUTH_HELPER = readFileSync('tests/e2e/helpers/auth.ts', 'utf8');

/** ⚠️ SOURCE IS NOT WHAT RENDERS, and the difference is a whole class of
 *  vacuous guard. `17-password-reset.spec.ts` asserts `/we've sent a reset
 *  link/i` against the DOM; the JSX says `we&apos;ve`. A source-level regex
 *  written in the spec's own words matches nothing and — if it had been
 *  written as a `.not.toMatch` — would have passed for ever while asserting
 *  the opposite of what it claimed. Decode before comparing. */
function rendered(src: string): string {
  return src
    .replace(/&apos;/g, "'")
    .replace(/&rsquo;/g, '’')
    .replace(/&lsquo;/g, '‘')
    .replace(/&quot;/g, '"')
    .replace(/&mdash;/g, '—')
    .replace(/&amp;/g, '&');
}

// ── Contrast, computed rather than remembered ───────────────────────────────
function srgbToLinear(c: number): number {
  const s = c / 255;
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}
function luminance(hex: string): number {
  let h = hex.replace('#', '').trim();
  if (h.length === 3) h = h.split('').map((c) => c + c).join('');
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b);
}
function contrast(a: string, b: string): number {
  const [l1, l2] = [luminance(a), luminance(b)];
  const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}

/** Read a token's value out of the shipped stylesheet. Never hardcode one here:
 *  a guard that carries its own copy of the value it is checking asserts that
 *  the copy is self-consistent, which is not a fact about the product. */
function token(name: string): string {
  const m = TOKENS.match(new RegExp(`^\\s*${name}:\\s*(#[0-9a-fA-F]{3,8})\\s*;`, 'm'));
  if (!m) throw new Error(`token ${name} is not declared in rounds-tokens.css`);
  return m[1];
}

const AA = 4.5;

describe('C1-d — text on the accent fill clears AA', () => {
  const onAccent = token('--rounds-on-accent');
  const accent = token('--rounds-accent');
  const accentHover = token('--rounds-accent-hover');

  it('the arithmetic can fail — negative control on the pre-fix literals', () => {
    // The values the old skin ships, on the fill the bridge gives them. If
    // these ever start PASSING, the formula is broken and every assertion
    // below is a sentence rather than a check.
    expect(contrast('#0d1611', accent)).toBeLessThan(AA); // .qm-lin-btn-primary
    expect(contrast('#08090a', accent)).toBeLessThan(AA); // waitlist submit
    expect(contrast('#0c1410', accent)).toBeLessThan(AA); // .qm-c3-auth-mark
    expect(contrast('#0c1410', accentHover)).toBeLessThan(AA); // …gradient far stop
    // …and a pair that certainly passes, so "less than" is not trivially true
    // of everything the function is handed.
    expect(contrast('#ffffff', '#000000')).toBeGreaterThan(AA);
  });

  it('--rounds-on-accent clears AA on the fill AND on its hover', () => {
    // Hover matters independently: the fill darkens to `--rounds-accent-hover`,
    // and a label chosen against the resting fill alone can fail the other.
    expect(contrast(onAccent, accent)).toBeGreaterThanOrEqual(AA);
    expect(contrast(onAccent, accentHover)).toBeGreaterThanOrEqual(AA);
  });

  it('the four literal-on-accent sites all use the token', () => {
    // (a) the shared CSS class, forked under the host
    const fork = TOKENS.match(
      /\[data-skin='rounds'\][^{]*\.qm-lin-btn-primary[^{]*\{([^}]*)\}/,
    );
    expect(fork, 'no [data-skin=rounds] override for .qm-lin-btn-primary').not.toBeNull();
    expect(fork![1]).toMatch(/color:\s*var\(--rounds-on-accent\)/);

    // (b) the brand mark's glyph
    const mark = TOKENS.match(
      /\[data-skin='rounds'\][^{]*\.qm-c3-auth-mark[^{]*\{([^}]*)\}/,
    );
    expect(mark, 'no [data-skin=rounds] override for .qm-c3-auth-mark').not.toBeNull();
    expect(mark![1]).toMatch(/color:\s*var\(--rounds-on-accent\)/);

    // (c) waitlist's inline submit — forked in TSX, because an inline style
    //     beats any class we could write.
    expect(FORM_SRC.waitlist).toMatch(
      /color:\s*rounds\s*\?\s*'var\(--rounds-on-accent\)'\s*:\s*'#08090a'/,
    );

    // (d) the hover fill, which the bridge inverts. `sage-bright` maps to
    //     `--rounds-accent-text` — right for the ~13 sites that read it as
    //     `color:`, wrong for this one site that reads it as `background:`.
    //     Un-forked, the primary CTA turns pale lavender on hover.
    expect(TOKENS).toMatch(
      /\.qm-lin-btn-primary:hover[\s\S]{0,120}background:\s*var\(--rounds-accent-hover\)/,
    );
  });

  it('the un-forked literals really are still in the old-skin source — control', () => {
    // Proves the assertions above are guarding something live. If the old skin
    // stops shipping these values, the forks are dead code and should go.
    expect(GLOBALS).toMatch(/\.qm-lin-btn-primary\s*\{[^}]*color:\s*#0d1611/);
    expect(GLOBALS).toMatch(/\.qm-c3-auth-mark\s*\{[^}]*color:\s*#0c1410/);
    expect(FORM_SRC.waitlist).toContain('#08090a');
  });

  it('every text tier reachable inside .qm-rounds-panel clears AA on it', () => {
    // ⚠️ FOUND BY GATE C, ON A NODE NOBODY HAD TOUCHED. Applying
    // `.qm-rounds-panel` to the forgot-password submitted block set its
    // background to surface-2 — a step LIGHTER than the card it sits in — and
    // that alone took a paragraph from 4.91:1 to 4.18:1 without any text
    // changing. A surface that changes what is under the text is a contrast
    // change.
    //
    // The panel re-bridges the faintest tiers upward for its own subtree. This
    // asserts the pairing holds by ARITHMETIC, on whatever values ship, rather
    // than by trusting the redeclaration is still there.
    const panel = TOKENS.match(/\[data-skin='rounds'\]\s*\.qm-rounds-panel\s*\{([^}]*)\}/);
    expect(panel, '.qm-rounds-panel has no rule').not.toBeNull();
    const bgName = panel![1].match(/background:\s*var\((--rounds-[a-z0-9-]+)\)/)?.[1];
    expect(bgName, 'the panel declares no background token').toBeTruthy();
    const bg = token(bgName!);

    // Which Rounds tier does each `--color-linear-text*` name resolve to
    // INSIDE the panel? The panel's own redeclarations win over the host's.
    const host = TOKENS.match(/\[data-skin='rounds'\]\s*\.qm-rounds-host\s*\{([^}]*)\}/)![1];
    const resolveTier = (name: string): string => {
      const local = panel![1].match(new RegExp(`${name}:\\s*var\\((--rounds-[a-z0-9-]+)\\)`));
      const outer = host.match(new RegExp(`${name}:\\s*var\\((--rounds-[a-z0-9-]+)\\)`));
      const t = (local ?? outer)?.[1];
      if (!t) throw new Error(`${name} resolves to nothing inside the panel`);
      return token(t);
    };
    for (const name of ['--color-linear-text', '--color-linear-text-2', '--color-linear-text-3', '--color-linear-text-4']) {
      expect(contrast(resolveTier(name), bg), `${name} inside .qm-rounds-panel`).toBeGreaterThanOrEqual(AA);
    }

    // Negative control: the tier the panel had to remap really does fail on
    // that background un-remapped. Without this the four passes above could be
    // true of a panel that never needed remapping at all.
    const rawText3 = host.match(/--color-linear-text-3:\s*var\((--rounds-[a-z0-9-]+)\)/)![1];
    expect(contrast(token(rawText3), bg)).toBeLessThan(AA);
  });

  it('the input placeholder clears AA on the input', () => {
    // ⚠️ ADDED AFTER A MUTATION SLIPPED THROUGH. The panel's tiers were pinned
    // by arithmetic and the INPUT's were not — so reverting the placeholder to
    // the failing `--rounds-text-3` (4.18:1 on surface-2, the exact pairing the
    // panel rule exists to avoid) passed cleanly. Two declarations apart, one
    // guarded and one not. Same shape as the original defect: a fix applied in
    // one place and not the other.
    const input = TOKENS.match(/\[data-skin='rounds'\]\s*\.qm-rounds-input\s*\{([^}]*)\}/);
    const ph = TOKENS.match(
      /\[data-skin='rounds'\]\s*\.qm-rounds-input::placeholder\s*\{([^}]*)\}/,
    );
    expect(input, '.qm-rounds-input has no rule').not.toBeNull();
    expect(ph, '.qm-rounds-input::placeholder has no rule').not.toBeNull();

    const bg = token(input![1].match(/background:\s*var\((--rounds-[a-z0-9-]+)\)/)![1]);
    const fg = token(ph![1].match(/color:\s*var\((--rounds-[a-z0-9-]+)\)/)![1]);
    expect(contrast(fg, bg), 'placeholder on the input ground').toBeGreaterThanOrEqual(AA);

    // The input's own text too, which is easy to forget once the placeholder
    // is the one being argued about.
    const textTier = input![1].match(/(?:^|\s)color:\s*var\((--rounds-[a-z0-9-]+)\)/)?.[1];
    expect(textTier, '.qm-rounds-input declares no text colour').toBeTruthy();
    expect(contrast(token(textTier!), bg), 'input text on the input ground').toBeGreaterThanOrEqual(AA);

    // Negative control: the tier this rule had to move OFF really does fail
    // here, or "it passes" is true of a rule that never needed changing.
    expect(contrast(token('--rounds-text-3'), bg)).toBeLessThan(AA);
  });

  it('the input focus ring is expressed as a property the inline style cannot defeat', () => {
    // ⚠️ THE FIRST DRAFT DECLARED A FOCUS RING THAT COULD NEVER RENDER. All
    // five auth forms set `outline: 'none'` INLINE in their `inputStyle`
    // const, and an inline declaration beats any class rule without
    // `!important` — so `:focus-visible { outline: … }` was a dead promise and
    // every auth input had no visible keyboard focus under Rounds (WCAG 2.4.7).
    // A dead promise is worse than no promise: the next reader sees a focus
    // style and stops checking. `box-shadow` is not set inline anywhere in
    // those consts, so it applies at class specificity.
    const rule = TOKENS.match(
      /\[data-skin='rounds'\]\s*\.qm-rounds-input:focus-visible\s*\{([^}]*)\}/,
    );
    expect(rule, '.qm-rounds-input has no :focus-visible rule').not.toBeNull();
    expect(rule![1], 'the focus ring must not rely on `outline` — inline `outline: none` wins')
      .not.toMatch(/(^|\s)outline\s*:/);
    expect(rule![1]).toMatch(/box-shadow:\s*[^;]*var\(--rounds-/);

    // …and the inline `outline: none` this works around really is still there,
    // in every form. If it ever goes, the workaround can be simplified — but
    // only then.
    const withInlineOutline = Object.entries(FORM_SRC)
      .filter(([, src]) => /outline:\s*'none'/.test(src))
      .map(([k]) => k);
    expect(withInlineOutline.length, 'no form declares inline outline:none any more').toBeGreaterThanOrEqual(2);
  });

  it('.qm-rounds-panel supplies its own padding', () => {
    // The class is what turns three bare flex/text wrappers into a bordered,
    // filled box; only waitlist-form brings padding of its own. Without this
    // the prose renders flush against the border the class just added.
    const panel = TOKENS.match(/\[data-skin='rounds'\]\s*\.qm-rounds-panel\s*\{([^}]*)\}/);
    expect(panel).not.toBeNull();
    expect(panel![1], '.qm-rounds-panel paints a border and a fill but no inside space').toMatch(
      /(^|\s)padding:\s*\d/,
    );
  });

  it('no state or fill token is used as a text colour on the auth surface', () => {
    // The recurring defect, six instances deep: `--rounds-accent` is 3.22:1 on
    // surface-1, `--rounds-critical` is a border value, `--rounds-em-fill` is a
    // button background. Any of them as `color:` is a failure waiting to be
    // measured. Scoped to the C1-d block so this does not re-litigate earlier
    // sections.
    const block = TOKENS.slice(TOKENS.indexOf('C1-d — auth: /login'));
    const FILL_ONLY = ['--rounds-accent', '--rounds-critical', '--rounds-em-fill', '--rounds-ready'];
    const offenders: string[] = [];
    for (const m of block.matchAll(/(?:^|\s)color:\s*var\((--rounds-[a-z0-9-]+)\)/g)) {
      // Exact match, not prefix: `--rounds-accent-text` is the CORRECT token
      // and merely starts with `--rounds-accent`. This is the substring trap
      // that made C1-c's label guard vacuous, arriving in a new place.
      if (FILL_ONLY.includes(m[1])) offenders.push(m[1]);
    }
    expect(offenders, 'fill/state tokens used as text in the C1-d block').toEqual([]);
    // Non-vacuity: the matcher must actually be finding `color:` declarations.
    const seen = [...block.matchAll(/(?:^|\s)color:\s*var\((--rounds-[a-z0-9-]+)\)/g)];
    expect(seen.length, 'the color: matcher found nothing to check').toBeGreaterThanOrEqual(4);
  });
});

describe('C1-d — every Rounds class applied has a rule, and every rule a caller', () => {
  const AUTH_SOURCES = [SHELL, ...Object.values(FORM_SRC)].join('\n');

  /** Classes the auth surface applies, derived from source.
   *  Scanned out of `className={…}` expressions specifically, not the whole
   *  file: a bare `qm-rounds-` written in a comment (the ownership regex is
   *  quoted in several of them) is not an applied class, and counting it would
   *  inflate the non-vacuity floor below into something that passes on prose. */
  const applied = new Set(
    [...AUTH_SOURCES.matchAll(/className=\{?[^}>]*\}?/g)]
      .flatMap((m) => [...m[0].matchAll(/qm-rounds-[a-z0-9]+(?:-[a-z0-9]+)*/g)].map((x) => x[0])),
  );

  it('the derivation found the classes — non-vacuity', () => {
    expect(applied.size, 'no qm-rounds-* classes found in the auth sources').toBeGreaterThanOrEqual(10);
    for (const c of ['qm-rounds-host', 'qm-rounds-auth', 'qm-rounds-authform']) {
      expect(applied.has(c), `${c} is not applied anywhere on the auth surface`).toBe(true);
    }
    // ⚠️ THIS USED TO ASSERT `applied.has('qm-rounds-') === false` and call it
    // proof that the scanner reads classNames rather than comments. It was a
    // tautology: the collection regex requires at least one alphanumeric after
    // the trailing dash, so the bare string could never enter the set under
    // ANY product edit. It asserted a property of the matcher, not a fact
    // about the source. What the claim actually needs is that a class name
    // appearing only in PROSE is not collected — checked directly.
    expect(
      applied.has('qm-rounds-notfound'),
      'a class named only in another surface\'s prose was collected as applied',
    ).toBe(false);
  });

  it('every applied class is declared in the stylesheet', () => {
    // An applied class with no rule is a no-op that reads as a restyle. The
    // mirror of C1-b's undeclared-token trap, one level up.
    const missing = [...applied].filter(
      (c) =>
        // `qm-rounds-host` is the bridge itself; `qm-rounds-auth`/`-authform`
        // are surface markers. All must still resolve to a rule.
        !new RegExp(`\\.${c}\\b`).test(TOKENS),
    );
    expect(missing, 'these classes are applied but have no CSS rule').toEqual([]);
  });

  it('every control primitive has at least one consumer', () => {
    // C1-b's rule: "a class with no consumer cannot be proven by rule 7 —
    // nothing renders and nothing can be made to fail." Enforced in the other
    // direction here, so a primitive that loses its last caller reds instead of
    // rotting into vocabulary nobody renders.
    const declared = new Set(
      [...TOKENS.matchAll(/\[data-skin='rounds'\][^{]*?\.(qm-rounds-[a-z0-9-]+)/g)].map((m) => m[1]),
    );
    expect(declared.size, 'no qm-rounds-* rules found — the matcher is broken').toBeGreaterThanOrEqual(10);

    // ⚠️ THE CONSUMER SET IS A TRAVERSAL OF ALL OF src/, NOT A HAND LIST.
    // The first draft of this assertion listed the eight files C1-c and C1-d
    // touch and reported 72 orphans — every board, stage, gate and signed-screen
    // class in the stylesheet, all of them perfectly well consumed by files the
    // list did not name. A maintained array of roots is the failure this repo
    // has now hit three times (the `globstar` miss, the convention files, and
    // this): the guard was wrong about where the consumers live, not the code.
    const ALL_SRC = walkTsx('src').map((f) => readFileSync(f, 'utf8')).join('\n');
    // Non-vacuity: the traversal must actually reach a file we know applies one.
    expect(ALL_SRC, 'the src traversal returned nothing recognisable').toContain('qm-rounds-host');
    const orphans = [...declared].filter((c) => !new RegExp(`\\b${c}\\b`).test(ALL_SRC));
    expect(orphans, 'these Rounds classes are declared but nothing applies them').toEqual([]);
  });
});

describe('C1-d — the selector contract the copy register must not break', () => {
  it('AuthFieldLabel keeps `hint` OUTSIDE the <label>', () => {
    // The single edit in auth-shell.tsx that breaks the whole suite. Playwright
    // matches `getByLabel('Password', { exact: true })` against the label's
    // whitespace-normalised text, whole-string. /login passes its "Forgot?"
    // link through `hint`; folding it inside the <label> — the obvious move
    // when restyling a two-item flex row — makes that text "Password Forgot?"
    // and reds every login in the suite.
    const label = SHELL.match(/<label[\s\S]*?<\/label>/);
    expect(label, 'AuthFieldLabel no longer renders a <label>').not.toBeNull();
    expect(label![0]).not.toContain('{hint}');
    // …and `hint` is still rendered somewhere, or the prop silently vanished.
    expect(SHELL).toContain('{hint}');
  });

  it('no auth field carries an aria-label', () => {
    // `getElementLabels` resolves aria-labelledby, then aria-label, and only
    // then `element.labels`. An aria-label added during a restyle silently
    // OVERRIDES the visible label and breaks all five getByLabel calls with no
    // HTML a reviewer would flag.
    // ⚠️ BOTH ATTRIBUTES. The comment above says the resolution order is
    // aria-labelledby FIRST, then aria-label — and the first draft banned only
    // the second. `/aria-label=/` does not match `aria-labelledby=` (the next
    // character is `l`, not `=`), so the HIGHER-priority override shipped
    // unguarded while the guard's own comment explained why it mattered.
    const ACCNAME_OVERRIDE = /aria-label(?:ledby)?\s*=/;
    for (const [name, src] of Object.entries(FORM_SRC)) {
      expect(src, `${name} added an accessible-name override to a field`).not.toMatch(
        ACCNAME_OVERRIDE,
      );
    }
    // ⚠️ NON-VACUITY, DONE PROPERLY. The first draft asserted
    // `SHELL.includes('aria-hidden')` here and called it a control — a
    // different string, a different file, a different method. Corrupting the
    // real matcher would have left both it and the "control" green. The
    // control has to exercise THE MATCHER, on a string it must match.
    expect(ACCNAME_OVERRIDE.test('<input aria-label="x" />')).toBe(true);
    expect(ACCNAME_OVERRIDE.test('<input aria-labelledby="x" />')).toBe(true);
    expect(ACCNAME_OVERRIDE.test('<input aria-hidden="true" />')).toBe(false);
  });

  it('the five signup labels and the CTA are unchanged, exactly', () => {
    // 38 spec files reach these through helpers/signup.ts. Compared by exact
    // value: `toContain` on a label name is satisfied by a longer string that
    // no longer matches Playwright's whole-string comparison.
    for (const label of ['Invite code', 'Full name', 'Email', 'Password', 'Confirm password']) {
      expect(SIGNUP_HELPER, `helpers/signup.ts stopped using ${label}`).toContain(`'${label}'`);
      expect(FORM_SRC.signup, `/signup no longer renders the label ${label}`).toContain(
        `>${label}<`,
      );
    }
    expect(FORM_SRC.signup).toContain("'Create account'");
    // The pending label must NOT also match /create account/i, or the click
    // resolves to two candidates under strict mode. It survives on a
    // contiguity accident — "Creating account" breaks the run of characters —
    // so the accident is asserted rather than assumed.
    expect(FORM_SRC.signup).toContain("'Creating account…'");
    expect(/create account/i.test('Creating account…')).toBe(false);
  });

  it('/signup still has exactly one checkbox, with no id and no htmlFor', () => {
    // The helper reaches it as the single unqualified `getByRole('checkbox')`.
    // A second one throws strict mode across 38 spec files; giving this one an
    // id + external label changes its accessible name from the wrapping
    // label's prose.
    const checkboxes = [...FORM_SRC.signup.matchAll(/type="checkbox"/g)];
    expect(checkboxes.length, '/signup must have exactly one checkbox').toBe(1);
    const block = FORM_SRC.signup.slice(
      FORM_SRC.signup.indexOf('type="checkbox"') - 200,
      FORM_SRC.signup.indexOf('type="checkbox"') + 400,
    );
    expect(block, 'the terms checkbox gained an id — its accessible name moves').not.toMatch(
      /\bid="/,
    );
  });

  it('the /login CTA still computes to exactly "Sign in"', () => {
    // `helpers/auth.ts` anchors `/^sign in$/i`. Held by seven spec files. It
    // survives today only because `Ic.arrowRight` is a bare <svg> with no
    // <title>, no aria-label and no role — so it contributes nothing to the
    // accessible name. An icon that gains a title breaks the same seven.
    expect(AUTH_HELPER).toMatch(/\/\^sign in\$\/i/);
    // ⚠️ EXACT, because the first draft of this line was
    // `/>\s*\{pending \? 'Signing in…' : 'Sign in'\}|Sign in/` — and top-level
    // alternation made the whole thing a bare substring test for `Sign in`.
    // Renaming the CTA to any SUPERSTRING ("Sign in now", "Sign in →") would
    // have kept that substring present, passed this guard, and broken the
    // anchored `/^sign in$/i` in seven spec files. The substring trap, in the
    // guard written to prevent it, in the PR about guards that cannot fail —
    // third instance in this project.
    expect(FORM_SRC.login).toContain("{pending ? 'Signing in…' : 'Sign in'}");
    // And nothing else in the file renders a longer CTA that would satisfy a
    // looser reading: the only `Sign in` occurrences are that ternary's two
    // halves plus prose links, none of them a submit button label.
    const cta = [...FORM_SRC.login.matchAll(/'(Sign in[^']*)'/g)].map((m) => m[1]);
    expect(cta, 'the /login submit label must be exactly "Sign in"').toEqual(['Sign in']);
    const icon = readFileSync('src/components/ui/icon.tsx', 'utf8');
    const arrow = icon.match(/arrowRight[\s\S]{0,400}?\),/);
    expect(arrow, 'Ic.arrowRight not found').not.toBeNull();
    expect(arrow![0], 'arrowRight gained an accessible name — /login CTA breaks').not.toMatch(
      /<title|aria-label|role="img"/,
    );
  });

  it('no second label containing "email" exists on any auth route', () => {
    // `getByLabel('Email')` is UNQUALIFIED in all seven login-side call sites —
    // Playwright's default is substring, case-insensitive. An "Email address"
    // field, or labelling the resend affordance, throws strict mode.
    for (const [name, src] of Object.entries(FORM_SRC)) {
      // ⚠️ `[\s\S]*?` AND A LAZY MATCH TO `>`, NOT `[^>]*`. The first draft
      // used `/<AuthFieldLabel[^>]*>/`, which stops at the FIRST `>` — and for
      // a label carrying a `hint={<Link …>Forgot?</Link>}` prop that `>` is
      // inside the hint's own JSX. So it captured the HINT's text as the label
      // and never saw the real one: on login-form.tsx it returned
      // ['Email','Forgot?','6-digit code','Recovery code'] — "Password", the
      // one field the exact-match contract most depends on, was invisible to
      // the guard meant to protect it.
      const labels = [
        ...src.matchAll(/<AuthFieldLabel\b[\s\S]*?>\s*([^<{][^<]*?)\s*<\/AuthFieldLabel>/g),
      ].map((m) => m[1].replace(/\s+/g, ' ').trim());
      const emailish = labels.filter((l) => /email/i.test(l));
      expect(
        emailish.length,
        `${name} has ${emailish.length} labels containing "email": ${emailish.join(' | ')}`,
      ).toBeLessThanOrEqual(1);
      for (const l of emailish) expect(l).toBe('Email');
    }
  });

  it('the two recorded link-in-text-block underlines survive', () => {
    // A SERIOUS axe fix on the two highest-traffic unauthenticated pages, and
    // nothing flag-ON would otherwise catch its removal. Both the inline style
    // AND the Rounds class must carry it, so neither half alone can be tidied
    // away.
    expect(FORM_SRC.waitlist).toMatch(/textDecoration:\s*'underline'/);
    expect(FORM_SRC.signup).toMatch(/textDecoration:\s*'underline'/);
    const link = TOKENS.match(/\[data-skin='rounds'\]\s*\.qm-rounds-link\s*\{([^}]*)\}/);
    expect(link, '.qm-rounds-link has no rule').not.toBeNull();
    expect(link![1]).toMatch(/text-decoration:\s*underline/);
  });

  it('the forgot/reset prose the required chromium gate asserts on is unchanged', () => {
    // `17-password-reset.spec.ts` runs in the DEFAULT project — the required
    // e2e gate — and asserts on this prose by regex. The copy register cannot
    // reach these three strings without updating that spec in the same change.
    // Compared against the DECODED source, in the spec's own regex, so the two
    // cannot drift apart on an HTML entity — the JSX says `we&apos;ve`.
    expect(rendered(FORM_SRC.forgot)).toMatch(/we've sent a reset link/i);
    expect(rendered(FORM_SRC.reset)).toMatch(/password updated/i);
    expect(FORM_SRC.reset).toMatch(/id="password"/);
    expect(FORM_SRC.reset).toMatch(/id="confirmPassword"/);
    expect(FORM_SRC.forgot).toMatch(/Send reset link/);
    expect(FORM_SRC.reset).toMatch(/Set new password/i);
    expect(FORM_SRC.waitlist).toMatch(/Join the waitlist/);

    // The decoder is doing work — control. If it ever becomes a no-op, the
    // first assertion above silently stops checking the string it names.
    expect(FORM_SRC.forgot).toContain('we&apos;ve');
    expect(rendered('we&apos;ve')).toBe("we've");
  });
});
