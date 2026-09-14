// ============================================================================
// RULING #320 (2) — the preview never renders an empty page.
// `imageDataHasInk` is the pure core of the blank-render guard: a rendered page
// that carries text but drew NO ink came back blank, and the component surfaces
// a named reason (with a download link) instead of an empty white rectangle.
// ============================================================================
import { describe, expect, it } from 'vitest';

import { imageDataHasInk } from '../native-document-preview';

/** RGBA pixels for a solid fill of one colour. */
function fill(rgba: [number, number, number, number], count: number): Uint8ClampedArray {
  const out = new Uint8ClampedArray(count * 4);
  for (let i = 0; i < count; i += 1) out.set(rgba, i * 4);
  return out;
}

describe('imageDataHasInk — the blank-render signal', () => {
  it('an all-WHITE canvas has no ink (the blank-render symptom)', () => {
    expect(imageDataHasInk(fill([255, 255, 255, 255], 4096))).toBe(false);
  });

  it('a canvas with any meaningfully-dark pixel HAS ink', () => {
    const px = fill([255, 255, 255, 255], 4096);
    px.set([10, 10, 10, 255], 100 * 4); // one dark pixel (text)
    // sampled on a stride of 16 → pixel 100 is on the grid (100 % 16 ... use 96)
    px.set([10, 10, 10, 255], 96 * 4);
    expect(imageDataHasInk(px)).toBe(true);
  });

  it('a fully TRANSPARENT canvas has no ink (alpha 0 is not counted)', () => {
    expect(imageDataHasInk(fill([0, 0, 0, 0], 4096))).toBe(false);
  });

  it('a near-white pixel (anti-alias fringe) does not count as ink', () => {
    // 250/255 is above the darkness threshold (24) → still "white".
    expect(imageDataHasInk(fill([250, 250, 250, 255], 4096))).toBe(false);
  });

  it('respects the darkness threshold — mid-grey text IS ink', () => {
    expect(imageDataHasInk(fill([128, 128, 128, 255], 4096))).toBe(true);
  });

  // ⚠️ ADVERSARIAL FIX (2026-09-14): a fixed 16-px stride phase-locked to columns
  // 0,16,32,… so a sub-16px label BETWEEN sampled columns (on a width-multiple-of-
  // 16 canvas) was missed on every row → a rendered form falsely read "blank".
  // Scanning every pixel (stride 1) catches it.
  it('detects ink OFF the old 16-pixel grid (the phase-lock case)', () => {
    // A 1024-px-wide (64×16) all-white row with one dark pixel at column 401 —
    // never on the 0,16,32,… grid the old fixed stride sampled.
    const px = fill([255, 255, 255, 255], 1024);
    px.set([10, 10, 10, 255], 401 * 4);
    expect(imageDataHasInk(px)).toBe(true);
    // The old default (stride 16) would have MISSED it — proving the regression:
    expect(imageDataHasInk(px, { pixelStride: 16 })).toBe(false);
  });
});
