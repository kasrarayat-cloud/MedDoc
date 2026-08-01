// ============================================================================
// C1-f — templates: the note-format panel and its six views.
// ----------------------------------------------------------------------------
// THE DEFECT THIS GATE EXISTS FOR IS A LITERAL, AND THE REASON IT NEEDS A GATE
// IS THAT NOBODY EDITED THE THING THAT BROKE.
//
// The Rounds host bridge works by REDECLARING `--color-linear-*` names on a
// scoped ancestor, so it retints anything that READS one. It can never reach a
// hex or an rgba() typed straight into a style object. `note-format-manager`,
// `template-review-editor` and `.qm-ux-primary` each typed `color: '#0d1611'`
// over a sage FILL — 6.72:1 on the old skin, and 3.43:1 the instant C1-e
// extended the host over this panel. No colour was edited, no test changed, and
// the primary button of four views went under AA.
//
// So the arithmetic below is the point: a fork token has to be measured against
// the ground it will actually land on, and both skins have to improve or the
// fix is a trade.
//
// ⚠️ WHAT THIS FILE CANNOT DO. It proves the fork is WRITTEN, the token is
// DECLARED on both sides, and the numbers CLEAR. It cannot prove the cascade
// resolved the way the arithmetic assumes — a `.qm-ux-*` rule in globals.css
// beating an inline style, a portal escaping the host, an animation compositing
// two tokens mid-fade. That is `rounds-c1.spec.ts`'s C1-f describe, which reads
// `getComputedStyle` on the real nodes of a real flag-ON build. Neither answer
// is worth much alone; the value is that they are derived differently.
// ============================================================================

import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const TOKENS = readFileSync('src/app/rounds-tokens.css', 'utf8');
const GLOBALS = readFileSync('src/app/globals.css', 'utf8');

const TEMPLATES_ROOT = 'src/app/settings/note-format';

/** Every source under a root, recursively. Derived by traversal, never a glob:
 *  bash does not expand `**` without `globstar`, and this repo has now been
 *  bitten by a hand-maintained surface list three times. */
function walkSources(dir: string): string[] {
  const out: string[] = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...walkSources(p));
    else if (/\.tsx?$/.test(p)) out.push(p);
  }
  return out;
}

const TEMPLATE_FILES = walkSources(TEMPLATES_ROOT).sort();
const SRC = new Map(TEMPLATE_FILES.map((p) => [p, readFileSync(p, 'utf8')]));

/** Read through the derived set, and name the FILE SET as the fault when it is
 *  wrong — not a TypeError three frames deep in an unrelated assertion. */
function src(path: string): string {
  const s = SRC.get(path);
  if (s === undefined) {
    throw new Error(
      `${path} is not in the derived template file set (${TEMPLATE_FILES.length} files). ` +
        `The TRAVERSAL is wrong, or the file moved — not the assertion below.`,
    );
  }
  return s;
}

// ── Colour maths ────────────────────────────────────────────────────────────

function channel(c: number): number {
  const x = c / 255;
  return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
}
function luminance(hex: string): number {
  const h = hex.replace('#', '');
  const full = h.length === 3 ? [...h].map((c) => c + c).join('') : h;
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16));
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}
function contrast(a: string, b: string): number {
  const [la, lb] = [luminance(a), luminance(b)];
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/** A `--name: #hex;` declaration in a stylesheet. Returns null when the value
 *  is not a plain hex (a `var()` or a `color-mix()` is not point-checkable). */
function hexToken(sheet: string, name: string): string | null {
  const m = sheet.match(new RegExp(`${name}\\s*:\\s*(#[0-9a-fA-F]{3,8})\\s*;`));
  return m ? m[1] : null;
}

/** Follow `--a: var(--b);` one hop, then read `--b`'s hex out of TOKENS. */
function bridgedHex(name: string): string | null {
  const m = TOKENS.match(new RegExp(`${name}\\s*:\\s*var\\((--rounds-[a-z0-9-]+)\\)\\s*;`));
  return m ? hexToken(TOKENS, m[1]) : null;
}

/** Blank every comment while PRESERVING LINE NUMBERS, so a finding still points
 *  at the line it came from.
 *
 *  ⚠️ TWO ASSERTIONS IN THIS FILE WERE KILLED BY MUTATION TESTING FOR READING
 *  THEIR OWN EXPLANATION as evidence — the literal scan matched a hex in the
 *  prose describing the fork, and the preview-derivation check matched
 *  `advance(initialStages(…))` in the comment saying it must be derived. Third
 *  and fourth instances in this repo, after the `!emAppliesToSpecialty` grep and
 *  `gate-controls-contract`'s Phase-B class in a JSX comment. The cure is never
 *  to stop writing the comment. */
const blankComments = (s: string) =>
  s
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
    .replace(/\/\/[^\n]*/g, (m) => ' '.repeat(m.length));

const AA = 4.5;

// The grounds these surfaces actually paint. `.qm-c3-set-panel` grounds the
// panel on surface-1; the list rows, the entry cards and the rejected alert
// each repaint a step lighter, which is a contrast change with no text edit.
const ROUNDS_SURFACE_1 = '--rounds-surface-1';
const ROUNDS_SURFACE_2 = '--rounds-surface-2';

describe('C1-f — the maths is real before anything else is asserted', () => {
  it('the contrast calculator is right — negative control', () => {
    // Without this every assertion below could pass on a broken calculator.
    expect(contrast('#ffffff', '#000000')).toBeCloseTo(21, 0);
    expect(contrast('#ffffff', '#ffffff')).toBeCloseTo(1, 5);
    // And the value this whole item turns on, from the ledger's own record.
    expect(contrast('#0d1611', '#5b5bd6')).toBeCloseTo(3.43, 1);
  });

  it('the traversal found the templates surfaces — positive control', () => {
    // A walk that returns [] makes every source assertion below vacuous.
    expect(TEMPLATE_FILES.length, 'the templates traversal returned nothing').toBeGreaterThan(3);
    for (const required of [
      `${TEMPLATES_ROOT}/note-format-manager.tsx`,
      `${TEMPLATES_ROOT}/upload-flow.tsx`,
      `${TEMPLATES_ROOT}/template-review-editor.tsx`,
    ]) {
      expect(TEMPLATE_FILES, `${required} missing from the derived set`).toContain(required);
    }
  });
});

describe('C1-f — the fork tokens exist on BOTH sides', () => {
  // A fork token declared only in the bridge is undefined on the old skin, and
  // an undeclared custom property does not error: the declaration is dropped at
  // computed-value time and the property falls to its INITIAL value. For a
  // `color` that is inherited text; for a `border-color` it is currentColor.
  // Silent both ways — this is the `--rounds-surface-0` trap in a new place.
  const FORKS = [
    '--color-linear-on-sage',
    '--color-linear-sage-ring',
    '--color-linear-sage-edge',
    '--color-linear-sage-edge-soft',
    '--color-linear-amber-edge',
    '--color-linear-amber-wash',
  ];

  it('every C1-f fork token is declared in globals.css (the old skin keeps its value)', () => {
    const missing = FORKS.filter((n) => !new RegExp(`${n}\\s*:`).test(GLOBALS));
    expect(
      missing,
      'these fork tokens are read by a templates surface but never declared in ' +
        'globals.css, so with the Rounds flag OFF they resolve to nothing and ' +
        'the property falls to its initial value — no error, no console warning:\n  ' +
        missing.join('\n  '),
    ).toEqual([]);
  });

  it('every C1-f fork token is redeclared in the Rounds bridge', () => {
    const missing = FORKS.filter((n) => !new RegExp(`${n}\\s*:`).test(TOKENS));
    expect(
      missing,
      'these fork tokens keep their OLD-SKIN value under Rounds — green chrome ' +
        'on an indigo surface, which is the exact defect tokenising them was ' +
        'meant to fix:\n  ' + missing.join('\n  '),
    ).toEqual([]);
  });

  it('⚠️ the ink-on-brand fork is what closes 3.43:1, and it is measured not assumed', () => {
    // The whole item in one assertion. `--color-linear-on-sage` is the ink ON
    // the brand fill. Under Rounds the fill is --rounds-accent, so the ink must
    // clear AA against THAT, not against the panel it sits on.
    const accent = hexToken(TOKENS, '--rounds-accent');
    const onSageRounds = bridgedHex('--color-linear-on-sage');
    const oldInk = hexToken(GLOBALS, '--color-linear-on-sage');
    const oldSage = hexToken(GLOBALS, '--color-linear-sage');

    expect(accent, '--rounds-accent is not a plain hex any more').not.toBeNull();
    expect(onSageRounds, '--color-linear-on-sage does not bridge to a hex token').not.toBeNull();
    expect(oldInk, '--color-linear-on-sage is not declared as a hex in globals.css').not.toBeNull();
    expect(oldSage, '--color-linear-sage is not declared as a hex in globals.css').not.toBeNull();

    const bridged = contrast(onSageRounds!, accent!);
    const legacy = contrast(oldInk!, oldSage!);
    const unforked = contrast(oldInk!, accent!);

    // The failure the fork exists to remove — asserted, so that if anyone
    // "simplifies" the fork away the number that comes back is named here.
    expect(
      unforked,
      'the OLD ink on the bridged accent should still be the failing pair this ' +
        'fork exists to remove; if this is no longer under AA the accent moved ' +
        'and the whole fork needs re-deriving',
    ).toBeLessThan(AA);

    expect(bridged, `ink on the Rounds brand fill is ${bridged.toFixed(2)}:1`).toBeGreaterThanOrEqual(AA);
    expect(legacy, `ink on the old sage fill is ${legacy.toFixed(2)}:1`).toBeGreaterThanOrEqual(AA);
  });

  it('⚠️ the real-text sage forks improve BOTH skins — a fix that trades is not a fix', () => {
    // `--color-linear-sage` is a FILL. Two sites used it as a foreground on
    // real text; both now read `-sage-bright`. Under Rounds that is the
    // difference between 3.22:1 and 7.60:1 — but the old skin must not regress
    // to buy it, or the flag-OFF product pays for a flag-ON defect.
    const pairs: [string, string, string][] = [
      ['old skin', GLOBALS, '--color-linear-surface-1'],
    ];
    for (const [label, sheet, groundName] of pairs) {
      const ground = hexToken(sheet, groundName);
      const fill = hexToken(sheet, '--color-linear-sage');
      const text = hexToken(sheet, '--color-linear-sage-bright');
      expect(ground, `${groundName} unreadable in ${label}`).not.toBeNull();
      const before = contrast(fill!, ground!);
      const after = contrast(text!, ground!);
      expect(
        after,
        `${label}: sage-bright (${after.toFixed(2)}:1) must not be worse than ` +
          `sage (${before.toFixed(2)}:1) — the fork would be trading one skin for the other`,
      ).toBeGreaterThanOrEqual(before);
    }

    // And under Rounds the same two names must land either side of AA, or the
    // fork is pointless.
    const ground = hexToken(TOKENS, ROUNDS_SURFACE_1)!;
    const fill = bridgedHex('--color-linear-sage')!;
    const text = bridgedHex('--color-linear-sage-bright')!;
    expect(contrast(fill, ground), 'the fill token now clears AA as text — the fork is obsolete, delete it')
      .toBeLessThan(AA);
    expect(contrast(text, ground), 'the text variant does not clear AA on surface-1').toBeGreaterThanOrEqual(AA);
  });
});

describe('C1-f — the ground change nobody edits', () => {
  it('⚠️ the faintest tier fails one step lighter, which is why the lift exists', () => {
    // C1-d's lesson, arriving on this surface: a class that repaints its GROUND
    // is a contrast change even though no text colour is touched. text-3 is
    // safe on the panel and not on the rows the panel contains.
    const text3 = hexToken(TOKENS, '--rounds-text-3')!;
    const text2 = hexToken(TOKENS, '--rounds-text-2')!;
    const s1 = hexToken(TOKENS, ROUNDS_SURFACE_1)!;
    const s2 = hexToken(TOKENS, ROUNDS_SURFACE_2)!;

    expect(contrast(text3, s1), 'text-3 on surface-1 — the panel ground').toBeGreaterThanOrEqual(AA);
    expect(
      contrast(text3, s2),
      'text-3 on surface-2 should still be the near-miss the lift exists for; ' +
        'if it now clears AA the palette moved and the lift is dead weight',
    ).toBeLessThan(AA);
    expect(contrast(text2, s2), 'the LIFTED tier must clear AA on surface-2').toBeGreaterThanOrEqual(AA);
  });

  it('EACH class that repaints its ground lifts the faint tiers — not merely one of them', () => {
    // ⚠️ THIS ASSERTION WAS `liftBlocks.length > 0` AND MUTATION TESTING KILLED
    // IT. Deleting the lift from the row/card/alert rule left the editor's own
    // lift standing, one block still matched, and the guard stayed green while
    // three of the four grounding subtrees had gone back to 4.18:1. An
    // existential over a set is not a claim about the members of that set —
    // the same shape as an emptiness test on a set whose size was never
    // established, which is this project's most-repeated defect.
    //
    // So: resolve EACH class to its OWN rule body and require the lift there.
    const CLASSES = [
      'qm-rounds-tmpl-row',
      'qm-rounds-tmpl-card',
      'qm-rounds-tmpl-alert',
      'qm-rounds-tmpl-editor',
    ];
    const naked: string[] = [];
    for (const cls of CLASSES) {
      // A rule may list several selectors before its body; find the block whose
      // SELECTOR LIST contains this class.
      const block = [...TOKENS.matchAll(/([^{}]+)\{([^}]*)\}/g)].find(
        ([, selectors]) => new RegExp(`\\.${cls}(?![a-z0-9-])`).test(selectors),
      );
      if (!block) {
        naked.push(`${cls}: no rule in rounds-tokens.css at all`);
        continue;
      }
      if (!/--color-linear-text-3:\s*var\(--rounds-text-2\)/.test(block[2])) {
        naked.push(`${cls}: has a rule, but does not lift --color-linear-text-3`);
      }
    }
    expect(naked.length + CLASSES.length, 'the rule matcher found nothing — broken').toBeGreaterThan(3);
    expect(
      naked,
      'these classes repaint their ground to surface-2 but leave the faintest ' +
        'text tier where it was. Nothing about the text changed and it is now ' +
        '4.18:1 — a contrast failure with no colour edit behind it:\n  ' + naked.join('\n  '),
    ).toEqual([]);
  });
});

describe('C1-f — no literal survives where a token has to reach', () => {
  /** Hex or rgba() typed into a style object. `transparent` is a keyword and
   *  needs no retint, so it is not a literal for this purpose.
   *
   *  A FACTORY, not a shared instance: a `/g` regex carries `lastIndex`, so one
   *  object used by both `.match()` and a later call answers differently
   *  depending on call order — a stateful matcher is its own vacuity bug. */
  const LITERAL = () => /#[0-9a-fA-F]{3,8}\b|rgba?\(\s*\d/g;

  it('the templates surfaces carry no colour literals', () => {
    const found: string[] = [];
    for (const f of TEMPLATE_FILES) {
      // native-template-manager is PARKED and mounts nowhere in production
      // (`SETTINGS_SIMPLE_ROW` + `TEMPLATE_NATIVE_DOCX` both true renders it
      // null). Named, not silently skipped — see the assertion below, which
      // holds the exemption to being real.
      if (f.endsWith('native-template-manager.tsx')) continue;
      for (const [i, line] of blankComments(src(f)).split('\n').entries()) {
        for (const m of line.match(LITERAL()) ?? []) found.push(`${f}:${i + 1}  ${m}  ${line.trim().slice(0, 90)}`);
      }
    }
    expect(
      found,
      'a colour literal in a templates surface. The host bridge retints custom ' +
        'properties and CANNOT reach a literal, so this value stays old-skin ' +
        'while everything around it moves — and if it is ink on a brand fill it ' +
        'goes under AA without anyone editing it:\n  ' + found.join('\n  '),
    ).toEqual([]);
  });

  it('the parked exemption is REAL, not a stale skip', () => {
    // An exemption that no longer describes anything silently widens.
    const parked = `${TEMPLATES_ROOT}/native-template-manager.tsx`;
    expect(TEMPLATE_FILES, 'the parked file is gone — drop the exemption').toContain(parked);
    expect(
      src(parked).match(LITERAL()),
      'the parked file no longer contains a literal, so the exemption is dead weight',
    ).not.toBeNull();
    // …and it must still be the surface that cannot mount: the slot is gated on
    // the two flags production sets, inverted.
    const page = readFileSync('src/app/settings/page.tsx', 'utf8');
    expect(page, 'the parked manager is no longer gated the way the park assumes')
      .toMatch(/templateNativeDocxEnabled\(\)\s*&&\s*!isSettingsSimpleRow\(\)/);
  });

  it('⚠️ `.qm-ux-primary` no longer hardcodes its ink — the globals.css blind spot', () => {
    // C1-e's eighth instance: `gate-rounds-bridge`'s foreground scan walks .tsx
    // ONLY, so a `color:` written in globals.css was never in its universe.
    // This is that class of defect, on this item's own CTA.
    const rule = GLOBALS.match(/\.qm-ux-primary\s*\{([^}]*)\}/)?.[1];
    expect(rule, '.qm-ux-primary has no rule in globals.css').toBeTruthy();
    expect(rule, '.qm-ux-primary hardcodes its ink again — 3.43:1 the moment the bridge applies')
      .not.toMatch(/color:\s*#/);
    expect(rule!, '.qm-ux-primary must take its ink from the fork token')
      .toMatch(/color:\s*var\(--color-linear-on-sage\)/);
    expect(rule!, '.qm-ux-primary hardcodes its ring again').not.toMatch(/box-shadow:[^;]*rgba?\(/);
  });
});

describe('C1-f — ownership, which is what made the failures invisible', () => {
  // `ownedByDom` walks ancestor-or-self and stops at the FIRST node carrying
  // any class. A non-Rounds class is therefore a SHIELD: everything beneath it
  // files as "inherited" — reported, never blocking. The two below shield the
  // exact nodes this item fixes.
  const SHIELDS: [string, string, string][] = [
    [`${TEMPLATES_ROOT}/template-review-editor.tsx`, 'qm-tpl-actionbar', 'qm-rounds-tmpl-actionbar'],
    [`${TEMPLATES_ROOT}/upload-flow.tsx`, 'qm-ux-proc', 'qm-rounds-tmpl-proc'],
    [`${TEMPLATES_ROOT}/upload-flow.tsx`, 'qm-ux-confirm', 'qm-rounds-tmpl-confirm'],
  ];

  it('every shielding class carries a Rounds class beside it', () => {
    const naked: string[] = [];
    for (const [file, shield, rounds] of SHIELDS) {
      const s = src(file);
      // The two must be on the SAME className, or ownership still stops at the
      // shield. Same invariant C1-e proved for `qm-rounds-host` + `-dialog`.
      const together = new RegExp(`className="[^"]*\\b${shield}\\b[^"]*\\b${rounds}\\b[^"]*"`).test(s)
        || new RegExp(`className="[^"]*\\b${rounds}\\b[^"]*\\b${shield}\\b[^"]*"`).test(s);
      if (!together) naked.push(`${file}: ${shield} without ${rounds} on the same element`);
    }
    expect(
      naked,
      'a non-Rounds class shields its whole subtree from the Gate C sweep. ' +
        'Every violation underneath files as "inherited" and none can block — ' +
        'which is `violations: []` over an unmeasured surface:\n  ' + naked.join('\n  '),
    ).toEqual([]);
  });

  it('the six views each render under a Rounds-owned root', () => {
    const manager = src(`${TEMPLATES_ROOT}/note-format-manager.tsx`);
    // home, entry and rejected are the three roots this file renders itself.
    const anchors = [...manager.matchAll(/className="qm-rounds-tmpl"/g)];
    expect(
      anchors.length,
      'the manager renders three view roots (home, entry, rejected); each needs ' +
        'the surface anchor or its subtree is invisible to the gate',
    ).toBe(3);
    // review and confirm are delegated, and each delegate carries its own.
    expect(src(`${TEMPLATES_ROOT}/template-review-editor.tsx`), 'the advanced editor has no anchor')
      .toContain('qm-rounds-tmpl-editor');
    expect(src(`${TEMPLATES_ROOT}/upload-flow.tsx`), 'the confirm card has no anchor')
      .toContain('qm-rounds-tmpl-confirm');
  });

  it('every C1-f class applied in source has a rule, and every rule has a caller', () => {
    // Both directions, because each catches a different rot: a class with no
    // rule is a no-op someone will trust; a rule with no caller is a primitive
    // that cannot be proven by rule 7, since nothing renders it and nothing can
    // be made to fail. C1-e deleted `.qm-rounds-btn-danger` on exactly this.
    const declared = new Set(
      [...TOKENS.replace(/\/\*[\s\S]*?\*\//g, ' ').matchAll(/\.(qm-rounds-tmpl[a-z0-9-]*)/g)].map((m) => m[1]),
    );
    const applied = new Set<string>();
    for (const f of [...TEMPLATE_FILES, 'src/app/dev/states/templates-preview.tsx']) {
      const s = readFileSync(f, 'utf8').replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/\/\/.*$/gm, ' ');
      for (const m of s.matchAll(/qm-rounds-tmpl[a-z0-9-]*/g)) applied.add(m[0]);
    }
    expect(declared.size, 'no qm-rounds-tmpl* rules found — the matcher is broken').toBeGreaterThan(4);
    expect(applied.size, 'no qm-rounds-tmpl* classes applied — the matcher is broken').toBeGreaterThan(4);

    expect(
      [...applied].filter((c) => !declared.has(c)).sort(),
      'applied but has no rule in rounds-tokens.css — a class that styles nothing',
    ).toEqual([]);
    expect(
      [...declared].filter((c) => !applied.has(c)).sort(),
      'declared but never applied — an orphan primitive. Delete it, or give it ' +
        'its consumer; do not manufacture a caller',
    ).toEqual([]);
  });
});

describe('C1-f — the preview door for the two views a walk cannot reach', () => {
  const PAGE = blankComments(readFileSync('src/app/dev/states/page.tsx', 'utf8'));
  const CLIENT = readFileSync('src/app/dev/states/templates-preview.tsx', 'utf8');
  /** The same source with every comment blanked. Assertions about what the
   *  preview DOES must read this; assertions about what it SAYS may read
   *  CLIENT. Keeping both named makes the distinction impossible to lose. */
  const CODE = blankComments(CLIENT);

  it('both states are wired end to end', () => {
    for (const s of ['tmpl-processing', 'tmpl-rejected']) {
      expect(PAGE, `${s} is not in the STATES enum, so resolveState() falls back to 'error'`)
        .toContain(`'${s}'`);
      expect(PAGE, `${s} has no render branch`).toMatch(new RegExp(`state === '${s}'`));
    }
    expect(CODE, 'the processing island is missing').toContain('DevTmplProcessing');
    expect(CODE, 'the rejected island is missing').toContain('DevTmplRejected');
  });

  it('⚠️ the preview is built from the PRODUCT state machine, not a copy', () => {
    // A literal stage array would keep rendering happily after the real model
    // changed shape, and this preview would then measure a state the product
    // no longer draws. Same reasoning as C1-c2's stale-error fixture, which is
    // built from `isStaleDeploymentError`'s own contract.
    //
    // ⚠️ ASSERTED AGAINST THE STRIPPED SOURCE, AND MUTATION TESTING IS WHY.
    // Replacing the derived model with a literal array left this test GREEN,
    // because the prose above it in `templates-preview.tsx` explains the rule
    // by NAMING `advance(initialStages(…))` — so the guard matched the comment
    // that says what the code should do, not the code. Second time in this one
    // file (the literal scan did it too, from a hex in a comment) and the third
    // recorded in the repo. A guard must never be able to satisfy itself from
    // the sentence describing it.
    expect(CODE, 'the stage model is hand-written — it can drift from the product')
      .toMatch(/advance\(\s*initialStages\(/);
    expect(CODE, 'the previews import the real components').toMatch(
      /import \{[^}]*ProcessingStages[^}]*\} from '@\/app\/settings\/note-format\/upload-flow'/,
    );
    expect(CODE, 'the rejected preview must render the real RejectedState').toMatch(
      /import \{ RejectedState \} from '@\/app\/settings\/note-format\/note-format-manager'/,
    );
  });

  it('⚠️ nothing rendered by the preview can carry real content', () => {
    // `rounds-shots/` is uploaded and retained for 14 days. A preview that
    // rendered a real parse would put note text in a CI artifact.
    const reason = CODE.match(/reason="([^"]*)"/)?.[1];
    expect(reason, 'the rejected preview has no fixed reason string').toBeTruthy();
    expect(reason!, 'the reason must be a literal, never interpolated from a parse')
      .not.toMatch(/\$\{|props\.|\bawait\b/);
  });
});
