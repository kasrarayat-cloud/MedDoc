import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

/**
 * "Preparing your format…" MUST RESOLVE.
 *
 * ⚠️ AN UNBOUNDED SPINNER IS A WORSE SILENCE THAN THE ONE #713 FIXED. A pill
 * that says "preparing" forever after a failed job teaches a doctor to stop
 * looking at the row — and unlike an empty string, it looks healthy while doing
 * it. The bound is the whole safety property, so it is asserted rather than
 * trusted to survive editing.
 */
const PAGE = readFileSync(join(__dirname, '..', 'page.tsx'), 'utf8');
const ROW = readFileSync(
  join(__dirname, '..', 'note-format', 'native-template-manager.tsx'),
  'utf8',
);

// ⚠️ COMMENT-STRIPPED, AND THAT IS NOT TIDINESS — IT IS THE GATE'S CORRECTNESS.
// The first two arms below were written against raw `PAGE` and BOTH FAILED on
// correct code: the earliest `preparing:` in the file sits inside a comment
// explaining this very gate, so the extracted window was prose. A gate that
// reads its own documentation measures the author's writing, not the program
// (canon 96, and canon 20's "self-authored prose is the highest-risk grep
// target"). The arms that pass on raw PAGE do so only because `toMatch` scans
// every position; anything that EXTRACTS a window has to strip first.
const CODE = PAGE.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^[ \t]*\/\/.*$/gm, '');

describe('the preparing state is bounded', () => {
  it('a window constant exists and is a finite number of minutes', () => {
    const m = PAGE.match(/PREPARING_WINDOW_MS\s*=\s*(\d+)\s*\*\s*60_000/);
    expect(m, 'PREPARING_WINDOW_MS is missing — the state would never resolve').toBeTruthy();
    const minutes = Number(m![1]);
    expect(minutes).toBeGreaterThan(0);
    expect(minutes).toBeLessThanOrEqual(60);
  });

  it('⚠️ the window is WIDER than the worker timeout it must outlive', () => {
    // If the window were narrower, a still-running certification would flip to
    // "Needs review" while the worker was mid-proof — telling the doctor to do
    // work the system is actively doing. That is #713's false instruction again.
    const worker = readFileSync(
      join(__dirname, '..', '..', '..', 'worker.ts'),
      'utf8',
    );
    const wm = worker.match(/AUTO_CERTIFY_TIMEOUT_MS\s*=\s*(\d+)\s*\*\s*60_000/);
    expect(wm, 'AUTO_CERTIFY_TIMEOUT_MS is missing').toBeTruthy();
    const pm = PAGE.match(/PREPARING_WINDOW_MS\s*=\s*(\d+)\s*\*\s*60_000/);
    expect(Number(pm![1])).toBeGreaterThan(Number(wm![1]));
  });

  it('the derivation requires NOT-certified — a certified twin never says preparing', () => {
    expect(PAGE).toMatch(/preparing:[\s\S]{0,200}!==\s*'CERTIFIED'/);
  });

  it('the derivation is time-bounded, not a bare boolean', () => {
    expect(PAGE).toMatch(/preparing:[\s\S]{0,300}PREPARING_WINDOW_MS/);
  });

  // ⚠️ #175 FINAL PASS — "PREPARING" MUST AGREE WITH THE PREDICATE THAT DECIDES
  // WHETHER ANYTHING IS BEING PREPARED. Auto-certify is enqueued ONLY when the
  // blocking count is 0; with any blocking finding it logs SKIPPED and stops.
  // The derivation did not consult that count, and `preparing` REPLACES the
  // status pill — so a template the system had already decided never to certify
  // showed "Preparing your format…" for the full window, suppressing the one
  // signal that leads the doctor to the findings list. It tells them to WAIT
  // when the correct instruction is to ACT.
  it('⚠️ preparing consults the blocking count that gates auto-certify', () => {
    expect(CODE).toMatch(/preparing:[\s\S]{0,300}blockingUnsupportedCount/);
  });

  // ⚠️ PINS THE DIRECTION, NOT THE SPELLING (canon 72). Any fail-closed default
  // passes; the ONE value that must not appear is a default of 0, which reads an
  // unknown count as "nothing is blocking" — the direction that hides a refusal.
  it('⚠️ the unknown-count default is FAIL-CLOSED, never 0', () => {
    const window_ = CODE.match(/preparing:[\s\S]{0,300}/)?.[0] ?? '';
    expect(window_.length, 'no preparing derivation was found at all').toBeGreaterThan(50);
    expect(
      /blockingUnsupportedCount\s*\?\?\s*0\b/.test(window_),
      'an absent count would read as "nothing is blocking"',
    ).toBe(false);
    // and it IS defaulted — an undefined compared with === 0 is silently false,
    // which happens to fail closed here, but by accident rather than by design.
    expect(window_).toMatch(/blockingUnsupportedCount\s*\?\?/);
  });

  it('the row renders the preparing pill INSTEAD of the status pill', () => {
    // Both showing at once would say "Preparing…" and "Needs review" together,
    // which is the contradiction the state exists to remove.
    expect(ROW).toMatch(/t\.preparing \?[\s\S]{0,400}<StatusPill/);
  });

  it('⚠️ NON-VACUITY: the files were actually read', () => {
    expect(PAGE.length).toBeGreaterThan(1000);
    expect(ROW.length).toBeGreaterThan(1000);
  });
});
