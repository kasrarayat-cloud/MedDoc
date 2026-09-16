import { afterEach, describe, it, expect, vi } from 'vitest';

import { detectFormFields, FormDetectError } from '../detect-fields';
import { isPixelIdenticalOutsideBoxes } from '../verify-fidelity';
import type { FidelityResult } from '../verify-fidelity';

// Ruling #326, Slice A: the detect client fails CLOSED — a timeout, a non-2xx,
// or a malformed/empty response is an error, never "no fields".

function mockFetch(res: Partial<Response> & { jsonBody?: unknown }): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: res.ok ?? true,
      status: res.status ?? 200,
      json: async () => res.jsonBody,
    })) as unknown as typeof fetch,
  );
}

afterEach(() => vi.unstubAllGlobals());

const goodPage = {
  index: 0,
  width_pt: 612,
  height_pt: 792,
  boxes: [
    { x: 10, y: 20, w: 100, h: 16, type: 'TextBox', label: 'NAME:', label_source: 'left' },
  ],
};
const goodDetector = {
  model: 'FFDNet-L',
  weights_sha: 'abc123',
  confidence: 0.3,
  image_size: 1600,
  commonforms_version: '0.2.1',
};
const good = (over: Record<string, unknown> = {}) => ({
  model: 'FFDNet-L',
  weights_sha: 'abc123',
  detector: goodDetector,
  pages: [goodPage],
  ...over,
});

describe('detect-fields client (fail-closed)', () => {
  it('parses a well-formed response into a DetectedForm with the detector signature', async () => {
    mockFetch({ jsonBody: good() });
    const form = await detectFormFields(new Uint8Array([1]));
    expect(form.model).toBe('FFDNet-L');
    expect(form.weightsSha).toBe('abc123');
    expect(form.detector.confidence).toBe(0.3);
    expect(form.detector.imageSize).toBe(1600);
    expect(form.detector.commonformsVersion).toBe('0.2.1');
    expect(form.pages[0]!.boxes[0]!.label).toBe('NAME:');
    expect(form.pages[0]!.boxes[0]!.labelSource).toBe('left');
  });

  it('throws detector_error on a non-2xx status', async () => {
    mockFetch({ ok: false, status: 500 });
    await expect(detectFormFields(new Uint8Array([1]))).rejects.toMatchObject({
      name: 'FormDetectError',
      reason: 'detector_error',
    });
  });

  it('throws bad_response on a malformed box', async () => {
    mockFetch({
      jsonBody: good({
        pages: [{ ...goodPage, boxes: [{ x: 'nope', y: 1, w: 1, h: 1, type: 'TextBox' }] }],
      }),
    });
    await expect(detectFormFields(new Uint8Array([1]))).rejects.toBeInstanceOf(FormDetectError);
  });

  it('throws empty_result when no page has any box', async () => {
    mockFetch({ jsonBody: good({ pages: [{ ...goodPage, boxes: [] }] }) });
    await expect(detectFormFields(new Uint8Array([1]))).rejects.toMatchObject({
      reason: 'empty_result',
    });
  });

  it('throws bad_response when the weights sha is missing (no signature)', async () => {
    mockFetch({ jsonBody: { model: 'FFDNet-L', detector: goodDetector, pages: [goodPage] } });
    await expect(detectFormFields(new Uint8Array([1]))).rejects.toMatchObject({
      reason: 'bad_response',
    });
  });

  it('throws bad_response when the detector signature omits confidence/image_size', async () => {
    mockFetch({ jsonBody: good({ detector: { model: 'FFDNet-L', weights_sha: 'abc123' } }) });
    await expect(detectFormFields(new Uint8Array([1]))).rejects.toMatchObject({
      reason: 'bad_response',
    });
  });
});

describe('fidelity verdict', () => {
  const r = (pages: FidelityResult['pages']): FidelityResult => ({ pages, dpi: 150 });

  it('is pixel-identical only when 0 changed outside AND something changed inside', () => {
    expect(
      isPixelIdenticalOutsideBoxes(
        r([{ page: 0, outsideBoxChangedPx: 0, outsideBoxTotalPx: 1000, insideBoxChangedPx: 50, boxAreaPct: 10 }]),
      ),
    ).toBe(true);
  });

  it('fails when any pixel changed outside a box', () => {
    expect(
      isPixelIdenticalOutsideBoxes(
        r([{ page: 0, outsideBoxChangedPx: 3, outsideBoxTotalPx: 1000, insideBoxChangedPx: 50, boxAreaPct: 10 }]),
      ),
    ).toBe(false);
  });

  it('fails a blank fill (nothing changed inside any box)', () => {
    expect(
      isPixelIdenticalOutsideBoxes(
        r([{ page: 0, outsideBoxChangedPx: 0, outsideBoxTotalPx: 1000, insideBoxChangedPx: 0, boxAreaPct: 10 }]),
      ),
    ).toBe(false);
  });
});
