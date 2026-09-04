// ============================================================================
// T3 — ROUNDS PAPER CHROME MUST REACH BOTH PAPER HOSTS
// ----------------------------------------------------------------------------
// The visit document renders on a DARK canvas by default: `globals.css` paints
// `.qm-vdoc` with `--color-linear-bg` (#08090a) and a 1px border, and
// `.qm-npv-stage` the same plus its own `overflow: auto` scroll box. That is
// correct flag-OFF chrome and is deliberately left alone.
//
// Under Rounds the same document sits on WHITE paper, so `rounds-tokens.css`
// neutralises that chrome. Those neutralisers were scoped to `.qm-rounds-sheet`
// — the class `RoundsStage` emits (stage.tsx:196). `RoundsSigned` does not emit
// it; it emits `qm-rounds-signed-paper rounds-paper` (signed.tsx:175). So the
// moment a note was signed the family stopped matching and the dark matting
// came back, on white paper. That was the black frame.
//
// ⚠️ WHAT THIS GATE ASSERTS, STATED SO IT IS NOT READ WIDER THAN IT IS:
//
//   For every rule in `rounds-tokens.css`, the set of elements it reaches
//   inside the VISIT-DOCUMENT SUBTREE is the same under both paper hosts.
//
// It does NOT assert that the resulting pixels match — a rule could reach both
// hosts and still be wrong. Geometry and colour are measured in a browser
// against the shipped CSS chunks (see the PR); this gate is the reachability
// half, and reachability is the half that broke.
//
// ⚠️ AN EARLIER VERSION OF THIS FILE CLAIMED IT PINNED "REACHABILITY, NOT
// SPELLING". THAT WAS FALSE, and the false record is the reason this comment is
// this long. It admitted rules by three literal-text tests — an anchored
// `^\[data-skin='rounds'\]`, a `\s+[.\w]` host-class test, and
// `prelude.startsWith('@')` — so SIX ordinary spellings of the very same defect
// walked past it while it reported green:
//
//     html[data-skin='rounds'] .qm-rounds-sheet .qm-vdoc     (layout.tsx puts
//                                                             data-skin on <html>)
//     body[data-skin='rounds'] …                              (an idiom this file
//                                                             already uses, :160)
//     [data-skin="rounds"] …                                  (double quotes — a
//                                                             spelling already here)
//     [data-skin='rounds'] .qm-rounds-sheet-wrap .qm-vdoc     (a real stage-only scope)
//     [data-skin='rounds'] :where(.qm-rounds-sheet) .qm-vdoc  (a specificity refactor)
//     @media (…) { …the defect first in the block… }          (the at-rule ate it)
//
// So the parsing is no longer done by regex. `document.styleSheets` gives the
// browser's own parse — at-rules descend, quote styles normalise, `:where()` is
// just a selector — and membership is decided by asking the DOM what a selector
// MATCHES rather than by reading the selector's text. All six spellings above
// are exercised as arms below.
// ============================================================================

// ⚠️ HONEST LIMITS OF THIS GATE, MEASURED RATHER THAN ASSUMED.
//
// Reverting each of the ten paper-scoped rules to `.qm-rounds-sheet` one at a
// time reds this gate on EIGHT. Two do not red, and that is a fact about those
// rules rather than a hole here:
//
//     .rounds-paper .qm-rdoc        no asymmetry
//     .rounds-paper .qm-rdoc-page   no asymmetry
//
// `.qm-rdoc` / `.qm-rdoc-page` are emitted ONLY by `ReviewDocumentView`
// (review-document-view.tsx:229/231), whose sole mount is inside
// `if (isReviewDocView() && !isSigned)` (visit-ready-view.tsx:809). They cannot
// occur on a signed visit, so their scope genuinely does not matter. They were
// moved with the family for consistency, NOT because they were broken — and
// this gate reporting no asymmetry for them is correct, not blind.
//
// What this gate does NOT assert, stated so its green is not read wider:
//   · that the resulting PIXELS match. Geometry and colour are measured in a
//     browser against the CSS chunks pulled from the running production
//     container; that measurement lives in the PR, not here.
//   · anything about `.qm-ux-doc-summary` or `.qm-c3-rev2-signbar`, two
//     near-black grounds that still render on the white signed paper. They are
//     emitted by SignedDocumentView, predate this change, and are recorded as
//     an owner acceptance question rather than silently fixed here.
//
import { readFileSync } from 'node:fs';
import path from 'node:path';

import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';

import type { StageIdentity, StageQueuePosition } from '@/lib/rounds/stage-data';
import type { SignedTrail } from '@/lib/rounds/stage-view-model';

import { RoundsSigned } from '../signed';
import { RoundsStage } from '../stage';

const SRC = path.resolve(__dirname, '../../..');
const read = (rel: string) => readFileSync(path.join(SRC, rel), 'utf8');
const ROUNDS_CSS = read('app/rounds-tokens.css');

/** Every selector in a stylesheet, via the browser's own parser. */
function selectorsOf(css: string): string[] {
  const style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);
  const out = new Set<string>();
  const walk = (rules: CSSRuleList | undefined) => {
    for (const rule of Array.from(rules ?? [])) {
      const any = rule as CSSStyleRule & { cssRules?: CSSRuleList };
      // A style rule contributes its selectors; an at-rule contributes its
      // BODY. Descending is what closes the "@media ate the first rule" escape.
      if (any.selectorText) for (const s of any.selectorText.split(',')) out.add(s.trim());
      if (any.cssRules) walk(any.cssRules);
    }
  };
  walk(style.sheet?.cssRules);
  style.remove();
  return [...out].filter(Boolean).sort();
}

// ── The document subtree, faithful to the components that emit it ───────────
// Derived by reading the emitters. Two corrections are baked in, both of which
// had silently weakened an earlier draft:
//   · the toolbar and the counts line are SIBLINGS of <DocumentPages/>
//     (visit-document-surface.tsx), not children of `.qm-vdoc`. Nesting them
//     manufactured two contrast failures that do not exist.
//   · the two hosts wrap the document DIFFERENTLY, and giving both the signed
//     host's wrapper made three of the nine members vacuous. The unsigned path
//     goes through ReviewDocumentView's `div.qm-rdoc > article.qm-rdoc-page`
//     (review-document-view.tsx:229/231); the signed path through
//     SignedDocumentView's `article.qm-ux-doc-note` (signed-document-view.tsx:82).
const EMITTED = {
  'app/visits/[id]/visit-document-surface.tsx': ['qm-vdoc-toolbar', 'qm-vdoc-format', 'qm-vdoc-format-on', 'qm-vdoc-counts'],
  'components/native-preview/document-pages.tsx': ['qm-vdoc', 'qm-vdoc-page', 'qm-vdoc-pageslot', 'qm-npv-page'],
  'components/native-preview/native-document-preview.tsx': ['qm-npv', 'qm-npv-stage', 'qm-npv-docx', 'qm-docxp', 'qm-npv-note'],
  'app/visits/[id]/review-document-view.tsx': ['qm-rdoc', 'qm-rdoc-page'],
  'app/visits/[id]/signed-document-view.tsx': ['qm-ux-doc', 'qm-ux-doc-note'],
} as const;

/** The document itself — identical under both hosts, because it IS identical. */
function DocumentSurface() {
  return (
    <>
      {/* PDF path — visit-document-surface.tsx's default return */}
      <div className="qm-vdoc-toolbar">
        <div className="qm-vdoc-format" role="group" aria-label="Preview format">
          <button type="button" className="qm-vdoc-format-on">PDF</button>
          <button type="button">Word</button>
        </div>
      </div>
      <p className="qm-vdoc-counts">12 fields filled</p>
      <div className="qm-vdoc" data-testid="visit-document">
        <div className="qm-vdoc-page">
          <div className="qm-vdoc-pageslot"><canvas className="qm-npv-page" /></div>
        </div>
      </div>
      {/* Word path — the docx_fallback branch, through NativeDocumentPreview */}
      <figure className="qm-npv">
        <div className="qm-npv-stage" tabIndex={0} role="group" aria-label="this visit">
          <div className="qm-npv-docx" role="region" aria-label="this visit" tabIndex={0}>
            <div className="qm-docxp-wrapper"><section className="qm-docxp" /></div>
          </div>
        </div>
        <p className="qm-npv-note">Opening your document…</p>
      </figure>
    </>
  );
}

/** …but the WRAPPERS differ, and that difference is the whole hazard. */
const SignedWrapper = () => (
  <div className="qm-ux-doc">
    <article className="qm-ux-doc-note"><DocumentSurface /></article>
  </div>
);
const UnsignedWrapper = () => (
  <div className="qm-rdoc">
    <article className="qm-rdoc-page"><DocumentSurface /></article>
  </div>
);

const IDENTITY: StageIdentity = {
  visitId: 'v1', patientLabel: 'A Patient', mrn: 'MRN-1', ageYears: 54,
  dob: '1972-03-14', reason: 'Asthma review', recordedAtIso: '2026-07-30T10:00:00.000Z',
  durationLabel: '6m 03s',
};
const QUEUE: StageQueuePosition = {
  position: null, total: 0, nextVisitId: null, prevVisitId: null, headVisitId: null,
};
const TRAIL: SignedTrail = { emAcknowledgedAt: null };

function hosts() {
  // Every Rounds rule leads with a data-skin scope, which app/layout.tsx:127
  // sets on <html> UNCONDITIONALLY. Without it the whole family matches nothing
  // and both hosts read as broken — a zero about the harness, not the code.
  document.documentElement.setAttribute('data-skin', 'rounds');
  const signed = render(
    <RoundsSigned status="SIGNED" signedAt="2026-07-30T12:00:00.000Z" identity={IDENTITY}
      queue={QUEUE} trail={TRAIL} signedByLabel="Dr Example" emCode="99213">
      <SignedWrapper />
    </RoundsSigned>
  );
  const unsigned = render(
    <RoundsStage status="READY" signedAt={null} identity={IDENTITY} queue={QUEUE}
      gates={[]} n={0} emArtifact={false}>
      <UnsignedWrapper />
    </RoundsStage>
  );
  // ⚠️ CONTAINER, NEVER baseElement. `baseElement` is document.body, which holds
  // BOTH renders in this one jsdom document — querying it finds the OTHER
  // host's matches and reports the signed tree as neutralised when it is not.
  // Measured: that mistake turned a true 0/9 into a false 8/9.
  return { signed: signed.container, unsigned: unsigned.container };
}

// ⚠️ THE WATCHED SET IS THE SHARED DOCUMENT, NOT THE WHOLE SCREEN.
// The two hosts are DIFFERENT SCREENS and their own chrome legitimately
// differs — the signed lock banner exists only when signed, the queue peek
// cards only when not. Comparing everything reports ~30 of those as findings
// and buries the one that matters. What must be identical is the VISIT
// DOCUMENT, which is the same component tree in both places.
//
// So membership is decided by the classes the three document components emit —
// read from EMITTED, so this set cannot drift from the components without arm 4
// saying so. `qm-docxp-wrapper` is added by hand: docx-preview injects it at
// runtime, so no emitter names it and arm 4 must not look for it.
const DOC_CLASSES = new Set<string>([
  ...EMITTED['app/visits/[id]/visit-document-surface.tsx'],
  ...EMITTED['components/native-preview/document-pages.tsx'],
  ...EMITTED['components/native-preview/native-document-preview.tsx'],
  'qm-docxp-wrapper',
]);

// A rule is ABOUT the elements it selects; a pseudo-class narrows WHEN it
// applies, not WHAT. jsdom cannot evaluate `:focus-visible` at all, and a
// selector it throws on would otherwise read as "reaches neither host" —
// symmetric, and silently unexamined. `:where()`/`:is()` are de-sugared for the
// same reason: they are specificity tools, and a specificity refactor must not
// change what this gate can see. Both transformations are for MATCHING only.
function normalise(selector: string): string {
  return selector
    .replace(/:(?:where|is)\(([^()]*)\)/g, '$1')
    .replace(/:(?:hover|focus-visible|focus|active|visited|focus-within)\b/g, '');
}

/** Which SHARED-DOCUMENT elements a selector reaches under one host. */
function reach(root: HTMLElement, selector: string): string[] {
  let found: Element[];
  try {
    found = Array.from(root.querySelectorAll(normalise(selector)));
  } catch {
    return ['<unparseable>'];
  }
  return found
    .filter((el) => Array.from(el.classList).some((c) => DOC_CLASSES.has(c)))
    .map((el) => `${el.tagName.toLowerCase()}.${Array.from(el.classList).join('.')}`)
    .sort();
}

/** Does the selector's TEXT name a paper host and a document element? */
const namesHost = (sel: string) =>
  /\.(rounds-paper|qm-rounds-sheet|qm-rounds-sheet-wrap|qm-rounds-signed-paper)\b/.test(sel);
const namesDoc = (sel: string) =>
  [...DOC_CLASSES].some((c) => new RegExp(`\\.${c}\\b`).test(sel));

afterEach(cleanup);

describe('T3 — Rounds paper chrome reaches BOTH paper hosts', () => {
  it('every rule reaches the same document elements under signed and unsigned', () => {
    const selectors = selectorsOf(ROUNDS_CSS);
    const { signed, unsigned } = hosts();

    const asymmetric: string[] = [];
    let reaching = 0;
    for (const sel of selectors) {
      const s = reach(signed, sel);
      const u = reach(unsigned, sel);
      if (s.length) reaching++;
      if (JSON.stringify(s) !== JSON.stringify(u)) {
        asymmetric.push(`${sel}\n      signed → ${JSON.stringify(s)}\n      unsigned → ${JSON.stringify(u)}`);
      }
    }

    expect(
      asymmetric,
      'A rule in rounds-tokens.css reaches the visit document under one paper host and ' +
        'not the other. That is the post-sign black frame: the same document, framed as ' +
        'if it were still on the dark canvas. Scope it to `.rounds-paper` — both hosts ' +
        'carry it — rather than to one host\'s own class:\n  ' + asymmetric.join('\n  ')
    ).toEqual([]);

    // NON-VACUITY, ANCHORED IN THE STYLESHEET rather than in the DOM: an empty
    // selector list, an unmounted probe or a missing data-skin all produce a
    // serene 0 === 0. This names the rule the gate exists for and asserts the
    // PARSER produced it, so a broken parse cannot pass as a clean comparison.
    expect(
      selectors,
      'the neutraliser this gate was written for is not in the parsed stylesheet — ' +
        'either the fix was reverted or the parser is broken'
    ).toContain("[data-skin='rounds'] .rounds-paper .qm-vdoc");
    expect(reaching, 'no rule reached the document at all — the harness is broken, not the CSS')
      .toBeGreaterThan(5);
  });

  it('the six known escape spellings are all caught', () => {
    // ⚠️ THE ARM THAT EXISTS BECAUSE THE PREVIOUS VERSION OF THIS GATE PASSED
    // ALL SIX. Each is an ordinary way to write the same defect. A fix for this
    // class proved only against the spelling already tested is the same defect
    // again, so every spelling is exercised — including two (`body[...]`,
    // `.qm-rounds-sheet-wrap`) that are idioms already present in this codebase.
    const DEFECT = '{ background: var(--color-linear-bg); border: 1px solid #21232a }';
    const ESCAPES: [string, string][] = [
      ['html-prefixed', `html[data-skin='rounds'] .qm-rounds-sheet .qm-vdoc ${DEFECT}`],
      ['body-prefixed', `body[data-skin='rounds'] .qm-rounds-sheet .qm-vdoc ${DEFECT}`],
      ['double quotes', `[data-skin="rounds"] .qm-rounds-sheet .qm-vdoc ${DEFECT}`],
      ['sheet-wrap scope', `[data-skin='rounds'] .qm-rounds-sheet-wrap .qm-vdoc ${DEFECT}`],
      [':where() refactor', `[data-skin='rounds'] :where(.qm-rounds-sheet) .qm-vdoc ${DEFECT}`],
      ['first inside @media', `@media (min-width: 1px) { [data-skin='rounds'] .qm-rounds-sheet .qm-vdoc ${DEFECT} }`],
    ];
    const { signed, unsigned } = hosts();

    const escaped: string[] = [];
    for (const [name, css] of ESCAPES) {
      const sels = selectorsOf(css);
      // Caught EITHER by asymmetry (it reaches one host) OR by being dead (it
      // reaches neither, which the dead-rule arm below is for). Both are real
      // catches; what must never happen is a spelling that is invisible to both.
      const caught = sels.some((sel) => {
        const s2 = JSON.stringify(reach(signed, sel));
        const u2 = JSON.stringify(reach(unsigned, sel));
        if (s2 !== u2) return true;
        return namesHost(sel) && namesDoc(sel) && reach(signed, sel).length === 0;
      });
      if (!caught) escaped.push(`${name}: ${css.slice(0, 90)}`);
    }
    expect(
      escaped,
      'These spellings of the T3 defect are INVISIBLE to this gate. Each reinstates the ' +
        'black frame on the signed note while the gate reports green:\n  ' + escaped.join('\n  ')
    ).toEqual([]);
  });

  it('no paper-scoped document rule is DEAD — it must reach at least one host', () => {
    // ⚠️ THE ARM FOR THE ESCAPE PARITY CANNOT SEE, BY CONSTRUCTION.
    // `body[data-skin='rounds'] .qm-rounds-sheet .qm-vdoc` reaches NEITHER host,
    // because layout.tsx:127 puts `data-skin` on <html> and never on <body>. A
    // neutraliser written that way is dead, so the black frame ships on BOTH
    // screens — and a parity check is blind to it precisely because it is
    // symmetric. Symmetric wrongness is still wrongness.
    //
    // Scoped to rules that NAME both a paper host and a document element, so an
    // ordinary rule about something else can never false-red this.
    // `body[data-skin='rounds']` at :160 is fine and is not caught: it is one
    // arm of a comma pair whose sibling `[data-skin='rounds'] body` is live, and
    // it names no document element.
    const { signed, unsigned } = hosts();
    const dead = selectorsOf(ROUNDS_CSS)
      .filter((sel) => namesHost(sel) && namesDoc(sel))
      .filter((sel) => reach(signed, sel).length === 0 && reach(unsigned, sel).length === 0);
    expect(
      dead,
      'These name a paper host AND a visit-document element, and reach NEITHER host. A ' +
        'neutraliser that matches nothing leaves the dark-canvas chrome on both screens:\n  ' +
        dead.join('\n  ')
    ).toEqual([]);
  });

  it('no rule styles ONE paper host — shared paper chrome lives on .rounds-paper', () => {
    // ⚠️ THE ARM THE REACHABILITY CHECK CANNOT SEE, and it exists because the
    // T3 fix INTRODUCED the defect it guards.
    //
    // Arm 1 compares rules scoped UNDER a host, so a rule whose subject IS a
    // host (`.qm-rounds-sheet { padding: 32px }`) is invisible to it — and that
    // rule inset only the unsigned sheet. `.qm-rounds-signed-paper` has no rules
    // at all, so the signed paper's whole chrome is the generic `.rounds-paper`.
    //
    // It did not show while the bug was live, because the bug was hiding it:
    // `.qm-vdoc`'s black ground carried its own 40px of padding, so the signed
    // document LOOKED inset — by the slab the fix removes. Measured in a browser
    // on the shipped CSS before the fix: page inset 41px left / 23px right vs
    // 32/32, i.e. not merely different but ASYMMETRIC. After: 32/32 on both.
    //
    // `.qm-rounds-sheet-wrap` is deliberately NOT caught: it is the stage's grid
    // column, not paper, and it has no signed counterpart to be missing.
    const hostOnly = selectorsOf(ROUNDS_CSS).filter((sel) =>
      /\.(qm-rounds-sheet|qm-rounds-signed-paper)\s*$/.test(sel)
    );
    expect(
      hostOnly,
      'These style ONE Rounds paper host directly, so the other host does not get them. ' +
        'Both hosts carry `.rounds-paper` — put shared paper chrome there:\n  ' +
        hostOnly.join('\n  ')
    ).toEqual([]);
  });

  it('the probe is built from classes the real components still emit', () => {
    // The probe stands in for the document surface. If an emitter renames a
    // class, a probe frozen here goes on measuring a shape that no longer
    // exists and reports a serene green about nothing. This arm reads the
    // EMITTERS — a source independent of both the probe and the stylesheet.
    const missing: string[] = [];
    for (const [rel, classes] of Object.entries(EMITTED)) {
      // ⚠️ STRIP COMMENTS FIRST. This codebase annotates renames in prose, so a
      // file explaining why `qm-foo` was renamed still CONTAINS `qm-foo` — and
      // an un-stripped regex would go green on the very edit this arm exists to
      // catch. The stylesheet reader learned the same lesson one function up.
      const src = read(rel).replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
      for (const cls of classes) {
        const re = new RegExp(`['"\`\\s]${cls.replace(/-/g, '\\-')}['"\`\\s]`);
        if (!re.test(src)) missing.push(`${cls} (expected in ${rel})`);
      }
    }
    expect(
      missing,
      'The probe names classes the emitting components no longer render, so the parity ' +
        'measurement above is about a shape that does not exist:\n  ' + missing.join('\n  ')
    ).toEqual([]);
  });
});
