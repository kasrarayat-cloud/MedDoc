// ============================================================================
// The converter fails SAFE, always.
// ----------------------------------------------------------------------------
// The whole justification for a preview sidecar is that it is optional. These
// pin that: every failure path returns a named reason and a null pdf, and none
// of them throws — because a throw here would propagate into a settings page or
// a review surface and turn "we could not draw a picture" into "your note is
// broken".
// ============================================================================

import { afterEach, describe, expect, it, vi } from 'vitest';

import { convertDocxToPdf } from '../convert';

const DOCX = new Uint8Array([0x50, 0x4b, 0x03, 0x04]);

afterEach(() => vi.unstubAllGlobals());

describe('convertDocxToPdf', () => {
  it('returns the pdf on success', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(new Uint8Array([1, 2, 3]), { status: 200 })));
    const r = await convertDocxToPdf(DOCX);
    expect(r.reason).toBeNull();
    expect(r.pdf).toBeInstanceOf(Uint8Array);
  });

  it('a converter error falls back, does not throw', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('nope', { status: 503 })));
    const r = await convertDocxToPdf(DOCX);
    expect(r.pdf).toBeNull();
    expect(r.reason).toBe('converter_error');
  });

  it('an UNREACHABLE sidecar falls back, does not throw', async () => {
    // The sidecar-down case the E2E covers end to end: nothing is blocked.
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('ECONNREFUSED'); }));
    const r = await convertDocxToPdf(DOCX);
    expect(r.pdf).toBeNull();
    expect(r.reason).toBe('converter_error');
  });

  it('a TIMEOUT falls back with its own reason', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      const e = new Error('aborted');
      e.name = 'AbortError';
      throw e;
    }));
    const r = await convertDocxToPdf(DOCX);
    expect(r.pdf).toBeNull();
    expect(r.reason).toBe('timeout');
  });

  it('an empty body is a failure, not a blank document', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(new Uint8Array([]), { status: 200 })));
    const r = await convertDocxToPdf(DOCX);
    expect(r.pdf).toBeNull();
    expect(r.reason).toBe('empty_result');
  });

  it('NOTHING clinical imports it — preview only', async () => {
    const { readFileSync } = await import('node:fs');
    const { execSync } = await import('node:child_process');
    const hits = execSync(
      "grep -rl \"docx-preview/convert\" src --include=*.ts --include=*.tsx || true",
      { encoding: 'utf8' },
    ).trim().split('\n').filter(Boolean);
    const forbidden = hits.filter((f) =>
      /api\/visits\/.*\/sign|certification-lifecycle|fill-engine|validation\//.test(f),
    );
    expect(forbidden, `a clinical path imports the preview converter: ${forbidden.join(', ')}`).toEqual([]);
    void readFileSync;
  });
});
