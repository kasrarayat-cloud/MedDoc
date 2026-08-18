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
