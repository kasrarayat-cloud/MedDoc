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

  it('NOTHING clinical reaches it — transitively, and it FAILS LOUD', async () => {
    // The first version of this test was fail-open (`|| true`) and checked only
    // DIRECT importers, so a clinical module importing the preview ACTION would
    // have sailed through. Walk the closure instead, and let a broken grep fail
    // the test rather than pass it.
    const { execSync } = await import('node:child_process');

    const importersOf = (mod: string): string[] =>
      execSync(`grep -rl "${mod}" src --include=*.ts --include=*.tsx || printf ''`, {
        encoding: 'utf8',
      })
        .trim()
        .split('\n')
        .filter(Boolean);

    // Transitive closure: the converter, then anything that reaches it.
    const seen = new Set<string>();
    const frontier = ['docx-preview/convert'];
    while (frontier.length) {
      const mod = frontier.pop() as string;
      for (const f of importersOf(mod)) {
        if (seen.has(f)) continue;
        seen.add(f);
        // Follow by module specifier (path without extension, from src/).
        frontier.push(f.replace(/^src\//, '').replace(/\.tsx?$/, ''));
      }
    }
    expect(seen.size, 'grep found nothing — the guard itself is broken').toBeGreaterThan(0);

    // The paths that must never depend on a preview: certification, filling,
    // verification, export, and signing.
    const CLINICAL =
      /(api\/visits\/.*\/sign|certification-lifecycle|synthetic-test|signing-gate|fill-engine|bridge-fill|native-export|artifact-compiler|validation\/|\/worker\/)/;
    const violations = [...seen].filter((f) => CLINICAL.test(f));
    expect(
      violations,
      `a clinical path now reaches the preview converter: ${violations.join(', ')}`,
    ).toEqual([]);
  });
});

describe('the preview action reads practiceId from the right row', () => {
  it('selects sourceArtifact.practiceId, not a field the model lacks', async () => {
    // TypeScript did NOT catch `practiceId` on the compiled version — the
    // generated client has no such field, and the select still type-checked.
    // It would have thrown at request time. Pin the shape so it cannot return.
    const { readFileSync } = await import('node:fs');
    const src = readFileSync('src/actions/preview-native-document.ts', 'utf8');
    const twinSelect = src.slice(
      src.indexOf('templateTwinCompiledVersion'),
      src.indexOf('  if (!row)'),
    );
    expect(twinSelect).toContain('sourceArtifact: { select: { practiceId: true } }');
    expect(twinSelect).not.toMatch(/^\s+practiceId: true,/m);
  });
});
