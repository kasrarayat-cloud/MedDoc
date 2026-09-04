// ============================================================================
// T3 — THE POST-SIGN BLACK FRAME. A neutraliser that reaches ONE paper host.
// ----------------------------------------------------------------------------
// The visit document renders on a DARK canvas by default: `globals.css`'s
// `.qm-vdoc` paints `--color-linear-bg` (#08090a) with a 1px border, and
// `.qm-npv-stage` paints the same plus its own `overflow: auto` scroll box.
// That is correct flag-OFF chrome and it is deliberately left alone.
//
// Under Rounds the same document sits on WHITE paper (#fcfcfa), so
// `rounds-tokens.css` neutralises that chrome. Those neutralisers were scoped
// to `.qm-rounds-sheet` — the class `RoundsStage` emits (stage.tsx:196).
//
// ⚠️ `RoundsSigned` DOES NOT EMIT IT. It emits
// `qm-rounds-signed-paper rounds-paper` (signed.tsx:175). So the moment a note
// was signed the whole neutraliser family stopped matching and the dark matting
// came back — on white paper. Measured in a real browser against the CSS
// actually shipped in production, signed vs unsigned:
//
//     .qm-vdoc          bg rgb(8,9,10) · 1px solid rgb(33,35,42) · r10 · 40px pad
//                       vs  transparent · 0px none · r0 · 0 pad
//     .qm-npv-stage     same, PLUS overflow:auto and max-height:780px
//                       ← functional, not cosmetic: a signed multi-page Word
//                         document was trapped in a 780px nested scroller
//     .qm-npv-page      dark-ground shadow rgba(0,0,0,.4)/.45
//                       vs  paper shadow rgba(25,30,38,.1)/.16
//     section.qm-docxp  same pair
//     .qm-vdoc-format-on  legacy sage rgb(122,166,140) vs accent rgb(91,91,214)
//
// THE FIX IS A SCOPE, NOT A SECOND COPY. Both hosts carry `.rounds-paper`, and
// `[data-skin='rounds'] .rounds-paper` is the rule that paints the white ground
// — so `.rounds-paper` IS the property these neutralisers are really about:
// *a document surface sitting on Rounds paper must not keep its dark-canvas
// chrome*. Scoped there, a third paper host added tomorrow inherits the fix,
// and there is no hand-kept list of hosts to drift.
//
// THIS GATE MEASURES REACHABILITY, NOT SPELLING. It parses the neutralisers out
// of `rounds-tokens.css` at run time and asks whether each one MATCHES the
// document subtree under each host. Rewriting a selector to something better is
// free; making one reach only one host is what reds.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';

import type { StageIdentity, StageQueuePosition } from '@/lib/rounds/stage-data';
import type { SignedTrail } from '@/lib/rounds/stage-view-model';

import { RoundsSigned } from '../signed';
import { RoundsStage } from '../stage';

const SRC = path.resolve(__dirname, '../../..');
const read = (rel: string) => readFileSync(path.join(SRC, rel), 'utf8');

// ⚠️ STRIP COMMENTS FROM THE WHOLE FILE FIRST, then split. This stylesheet is
// full of ASCII box diagrams and quoted CSS inside `/* … */`, and several of
// those comments contain `}`. Splitting first lets comment prose arrive as a
// "selector" — which matches nothing, i.e. reads exactly like the defect this
// gate exists to catch. Measured: the naive order produced four prose
// selectors and a confident, wrong zero.
const ROUNDS_CSS = read('app/rounds-tokens.css').replace(/\/\*[\s\S]*?\*\//g, '');

/** Every Rounds rule scoped under a paper host AND carrying a descendant. */
function paperScopedDescendantSelectors(): string[] {
  const out = new Set<string>();
  for (const block of ROUNDS_CSS.split('}')) {
    const brace = block.indexOf('{');
    if (brace < 0) continue;
    const prelude = block.slice(0, brace).trim();
    if (!prelude || prelude.startsWith('@')) continue;
    for (const raw of prelude.split(',')) {
      const sel = raw.trim();
      if (!/^\[data-skin='rounds'\]/.test(sel)) continue;
      // A HOST-scoped rule with something beneath it. The bare host rules
      // (`.qm-rounds-sheet {…}`, `.rounds-paper {…}`) style the host itself and
      // are not neutralisers — they are excluded by requiring a descendant.
      if (/\.(rounds-paper|qm-rounds-sheet|qm-rounds-signed-paper)\s+[.\w]/.test(sel)) {
        out.add(sel);
      }
    }
  }
  return [...out].sort();
}

// ── The document subtree, faithful to the components that emit it ───────────
// Derived by reading the emitters, not by memory. `TOOLBAR_IS_A_SIBLING` is the
// correction that matters: an earlier draft of this fixture nested the toolbar
// and the counts line INSIDE `.qm-vdoc` and manufactured two contrast failures
// (1.19:1, 2.86:1) that do not exist on the real page, because in
// `visit-document-surface.tsx` they are siblings of `<DocumentPages/>`.
const EMITTED = {
  'app/visits/[id]/visit-document-surface.tsx': [
    'qm-vdoc-toolbar',
    'qm-vdoc-format',
    'qm-vdoc-format-on',
    'qm-vdoc-counts',
  ],
  'components/native-preview/document-pages.tsx': [
    'qm-vdoc',
    'qm-vdoc-page',
    'qm-vdoc-pageslot',
    'qm-npv-page',
  ],
  'components/native-preview/native-document-preview.tsx': [
    'qm-npv',
    'qm-npv-stage',
    'qm-npv-docx',
    'qm-docxp',
  ],
} as const;

function DocumentSurfaceProbe() {
  return (
    <>
      {/* PDF path — visit-document-surface.tsx's default return */}
      <article className="qm-ux-doc-note">
        <div className="qm-vdoc-toolbar">
          <div className="qm-vdoc-format" role="group" aria-label="Preview format">
            <button type="button" className="qm-vdoc-format-on">PDF</button>
            <button type="button">Word</button>
          </div>
        </div>
        <p className="qm-vdoc-counts">12 fields filled</p>
        <div className="qm-vdoc" data-testid="visit-document">
          <div className="qm-vdoc-page">
            <div className="qm-vdoc-pageslot">
              <canvas className="qm-npv-page" />
            </div>
          </div>
        </div>
      </article>

      {/* Word path — the `docx_fallback` branch, through NativeDocumentPreview */}
      <article className="qm-ux-doc-note">
        <div data-testid="visit-document-fallback">
          <div className="qm-vdoc-toolbar">
            <div className="qm-vdoc-format" role="group" aria-label="Preview format">
              <button type="button">PDF</button>
              <button type="button" className="qm-vdoc-format-on">Word</button>
            </div>
          </div>
          <figure className="qm-npv">
            <div className="qm-npv-stage" tabIndex={0} role="group" aria-label="this visit">
              <div className="qm-npv-docx" role="region" aria-label="this visit" tabIndex={0}>
                {/* docx-preview injects these two */}
                <div className="qm-docxp-wrapper">
                  <section className="qm-docxp" />
                </div>
              </div>
            </div>
          </figure>
        </div>
      </article>
    </>
  );
}

const IDENTITY: StageIdentity = {
  visitId: 'v1',
  patientLabel: 'A Patient',
  mrn: 'MRN-1',
  ageYears: 54,
  dob: '1972-03-14',
  reason: 'Asthma review',
  recordedAtIso: '2026-07-30T10:00:00.000Z',
  durationLabel: '6m 03s',
};
const QUEUE: StageQueuePosition = {
  position: null, total: 0, nextVisitId: null, prevVisitId: null, headVisitId: null,
};
const TRAIL: SignedTrail = { emAcknowledgedAt: null };

function hosts() {
  // The neutralisers all lead with `[data-skin='rounds']`, which app/layout.tsx
  // sets on <html> UNCONDITIONALLY. Without it the whole family matches nothing
  // and BOTH hosts read as broken — a zero about the harness, not the code.
  document.documentElement.setAttribute('data-skin', 'rounds');

  const signed = render(
    <RoundsSigned
      status="SIGNED"
      signedAt="2026-07-30T12:00:00.000Z"
      identity={IDENTITY}
      queue={QUEUE}
      trail={TRAIL}
      signedByLabel="Dr Example"
      emCode="99213"
    >
      <DocumentSurfaceProbe />
    </RoundsSigned>
  );
  const unsigned = render(
    <RoundsStage
      status="READY"
      signedAt={null}
      identity={IDENTITY}
      queue={QUEUE}
      gates={[]}
      n={0}
      emArtifact={false}
    >
      <DocumentSurfaceProbe />
    </RoundsStage>
  );
  // ⚠️ CONTAINER, NEVER baseElement. `baseElement` is document.body, which holds
  // BOTH renders in this one jsdom document — querying it finds the OTHER
  // host's matches and reports the signed tree as neutralised when it is not.
  // Measured: that mistake turned a true 0/9 into a false 8/9.
  return { signed: signed.container, unsigned: unsigned.container };
}

describe('T3 — Rounds paper neutralisers reach BOTH paper hosts', () => {
  it('every paper-scoped neutraliser matches the same set on signed and unsigned', () => {
    const selectors = paperScopedDescendantSelectors();
    const { signed, unsigned } = hosts();

    const asymmetric: string[] = [];
    let signedHits = 0;
    let unsignedHits = 0;

    for (const sel of selectors) {
      const s = !!signed.querySelector(sel);
      const u = !!unsigned.querySelector(sel);
      if (s) signedHits++;
      if (u) unsignedHits++;
      // A pseudo-class rule (`:focus-visible`) matches on neither without
      // focus; that is symmetric and therefore not a finding.
      if (s !== u) asymmetric.push(`${u ? 'unsigned-only' : 'signed-only'}: ${sel}`);
    }

    expect(
      asymmetric,
      `A Rounds neutraliser reaches one paper host and not the other. That is the ` +
        `post-sign black frame: the same document, framed as if it were still on the ` +
        `dark canvas. Scope these to .rounds-paper (both hosts carry it) rather than ` +
        `to one host's own class:\n  ${asymmetric.join('\n  ')}`
    ).toEqual([]);

    // NON-VACUITY. An empty selector list, an unmounted probe, or a missing
    // data-skin all produce a serene 0 === 0. Anchor on the member this gate
    // was written for.
    expect(signedHits, 'no neutraliser matched anything — the harness is broken, not the CSS').toBeGreaterThan(0);
    expect(unsignedHits).toBe(signedHits);
    expect(
      signed.querySelector("[data-skin='rounds'] .rounds-paper .qm-vdoc"),
      '.qm-vdoc is the element that paints the black frame; if this stops matching, ' +
        'either the fix was reverted or the probe no longer resembles the document'
    ).not.toBeNull();
  });

  it('no document-chrome neutraliser is scoped to a single paper host', () => {
    // The regression itself, stated directly. `.qm-rounds-sheet` is emitted only
    // by RoundsStage and `.qm-rounds-signed-paper` only by RoundsSigned, so a
    // document-chrome rule scoped to either is, by construction, half a rule.
    const hostOnly = paperScopedDescendantSelectors().filter((s) =>
      /\.(qm-rounds-sheet|qm-rounds-signed-paper)\s+[.\w]/.test(s)
    );
    expect(
      hostOnly,
      'These neutralise the visit document but are scoped to ONE of the two Rounds ' +
        'paper hosts, so the other host keeps the dark-canvas chrome:\n  ' +
        hostOnly.join('\n  ')
    ).toEqual([]);
  });

  it('the probe is built from classes the real components still emit', () => {
    // The probe is a stand-in for the document surface. If an emitter renames a
    // class, a probe frozen in this file goes on measuring a shape that no
    // longer exists and reports a serene green about nothing. This arm reads the
    // EMITTERS — a source independent of both the probe and the stylesheet.
    const missing: string[] = [];
    for (const [rel, classes] of Object.entries(EMITTED)) {
      const src = read(rel);
      for (const cls of classes) {
        // Exact token, not substring: `qm-vdoc` is a prefix of `qm-vdoc-page`,
        // and a substring check would pass on the wrong one.
        const re = new RegExp(`['"\`\\s]${cls.replace(/[-]/g, '\\-')}['"\`\\s]`);
        if (!re.test(src)) missing.push(`${cls} (expected in ${rel})`);
      }
    }
    expect(
      missing,
      'The probe names classes the emitting components no longer render, so the ' +
        'parity measurement above is about a shape that does not exist:\n  ' +
        missing.join('\n  ')
    ).toEqual([]);
  });
});
