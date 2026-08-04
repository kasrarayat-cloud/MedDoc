// ============================================================================
// The lifecycle overflow mounts on BOTH Rounds visit surfaces — stage AND signed.
// ----------------------------------------------------------------------------
// ⚠️ THIS EXISTS BECAUSE ARCHIVE WAS UNREACHABLE IN PRODUCTION, ON EVERY SIGNED
// NOTE, FOR A DAY — AND NOTHING WENT RED.
//
// R2 (merge `e1375027`, 2026-08-03) deleted this from `page.tsx`:
//
//     {roundsChrome && (
//       <details className="qm-rounds-overflow" data-testid="rounds-visit-overflow">
//         <div className="qm-rounds-overflow-body">{lifecycleActions}</div>
//       </details>
//     )}
//
// Gated on `roundsChrome` ALONE — no status condition — so it rendered for
// SIGNED visits too. R2 moved it into `RoundsStage`, which is mounted only by
// the unsigned branch (`visit-ready-view.tsx:848`,
// `if (isReviewDocView() && !isSigned)`). A signed visit mounts `RoundsSigned`,
// which had no slot for it.
//
// The commit's own comment said: "Same node, same actions, same `data-testid`
// — only the position moved." True for the surface it looked at. False for the
// one it did not. That is the R3.4 "coverage assumed" shape and the third
// "comment asserting a property the code does not have" this project has
// found.
//
// COST: `ArchiveButton` is defined once (`visit-lifecycle-actions.tsx:279`) and
// reaches the DOM only through this node. HIPAA retention forbids deleting a
// signed note, so archiving is the only disposal a doctor has — and 16 signed
// visits in production had no path to it. No error, no corruption, no weakened
// gate. Just an absent control.
//
// WHAT WOULD MAKE THIS FAIL (all four proven by mutation before commit):
//   • dropping `visitActions` from either surface's props
//   • rendering the overflow on one surface but not the other
//   • the two surfaces drifting to different `data-testid`s, so one selector
//     silently stops covering both
//   • a caller forgetting to thread the prop through
// ============================================================================

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, it, expect } from 'vitest';

const ROUNDS = 'src/components/rounds';
const VISIT = 'src/app/visits/[id]';

const strip = (s: string) =>
  s
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '');

const STAGE = strip(readFileSync(join(ROUNDS, 'stage.tsx'), 'utf8'));
const SIGNED = strip(readFileSync(join(ROUNDS, 'signed.tsx'), 'utf8'));
const VIEW = strip(readFileSync(join(VISIT, 'visit-ready-view.tsx'), 'utf8'));

/** The one selector that must find the control on every Rounds visit surface. */
const TESTID = 'rounds-visit-overflow';

describe('the lifecycle overflow is on BOTH Rounds visit surfaces', () => {
  it('NON-VACUITY — all three sources parsed to something real', () => {
    // Without this, a comment-stripper that ate everything would make every
    // `.toContain` below trivially false and every `.not.toContain` trivially
    // true, and the gate would report green about nothing.
    for (const [name, src] of [
      ['stage.tsx', STAGE],
      ['signed.tsx', SIGNED],
      ['visit-ready-view.tsx', VIEW],
    ] as const) {
      expect(src.length, `${name} stripped to (almost) nothing`).toBeGreaterThan(1000);
    }
    expect(SIGNED).toContain('export function RoundsSigned');
  });

  it('BOTH components declare a visitActions prop', () => {
    expect(STAGE, 'stage.tsx lost its visitActions prop').toMatch(/visitActions\?:\s*React\.ReactNode/);
    expect(
      SIGNED,
      'signed.tsx has no visitActions prop — a signed note would have NO archive control',
    ).toMatch(/visitActions\?:\s*React\.ReactNode/);
  });

  it('BOTH components RENDER it behind the same testid', () => {
    for (const [name, src] of [
      ['stage.tsx', STAGE],
      ['signed.tsx', SIGNED],
    ] as const) {
      expect(src, `${name} does not render data-testid="${TESTID}"`).toContain(
        `data-testid="${TESTID}"`,
      );
      // The render must be CONDITIONAL on the prop, not unconditional — an
      // always-rendered empty <details> is a control that appears to exist.
      expect(src, `${name} renders the overflow unconditionally`).toMatch(
        /visitActions \? \(/,
      );
      expect(src, `${name} does not place visitActions inside the body`).toContain(
        '{visitActions}',
      );
    }
  });

  it('MOUNT COUNT — the view threads the prop to EVERY Rounds surface it mounts', () => {
    // This is the assertion that would have caught the regression. It is about
    // coverage, not about any one surface being right.
    // ⚠️ SLICE TO THE ACTUAL `/>`, DO NOT GUESS A WINDOW.
    // The first version of this used `[\s\S]{0,900}?\/>` and found ZERO
    // mounts, because both JSX elements are ~1900 characters long — so the
    // gate went red on correct code. A probe that is too strict is a defect in
    // the probe, not a finding, and it costs exactly as much trust as one that
    // is too loose.
    const mounts = [...VIEW.matchAll(/<Rounds(Stage|Signed)\b/g)].map((m) => {
      const end = VIEW.indexOf('/>', m.index ?? 0);
      return { name: m[1], body: VIEW.slice(m.index ?? 0, end === -1 ? undefined : end) };
    });
    expect(
      mounts.length,
      'no <RoundsStage> or <RoundsSigned> mount found — has the view been restructured?',
    ).toBeGreaterThanOrEqual(2);

    const missing = mounts
      .filter((m) => !/visitActions=\{/.test(m.body))
      .map((m) => `<Rounds${m.name}>`);
    expect(
      missing,
      'these Rounds visit surfaces are mounted WITHOUT visitActions, so the ' +
        'doctor gets no lifecycle control there at all. That is exactly how ' +
        'Archive vanished from every signed note on 2026-08-03.',
    ).toEqual([]);
  });

  it('POSITIVE CONTROL — the matchers fire on the pre-fix source', () => {
    // signed.tsx as it stood: props without visitActions, no overflow render.
    const preFixSigned = `
      export interface RoundsSignedProps { status: string; trail: SignedTrail; onContinue?: () => void; }
      export function RoundsSigned({ status, trail }: RoundsSignedProps) {
        return <div className="qm-rounds-signed">{trail}</div>;
      }
    `;
    expect(preFixSigned).not.toMatch(/visitActions\?:\s*React\.ReactNode/);
    expect(preFixSigned).not.toContain(`data-testid="${TESTID}"`);

    // and the mount-count matcher on the pre-fix call site
    const preFixMount = `<RoundsSigned status={roundsView.status} signedAt={x} identity={y} />`;
    const m = [...preFixMount.matchAll(/<Rounds(Stage|Signed)\b/g)].map((x) => ({
      name: x[1],
      body: preFixMount.slice(x.index ?? 0, preFixMount.indexOf('/>', x.index ?? 0)),
    }));
    expect(m.length).toBe(1);
    expect(
      m.filter((x) => !/visitActions=\{/.test(x.body)).length,
      'the mount-count matcher does not fire on the very call site it was ' +
        'written to catch — it would have passed on the bug',
    ).toBe(1);
  });
});
