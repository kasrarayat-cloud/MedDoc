// ============================================================================
// THE FAIL-OPEN IS LOUD — RULED 2026-09-03.
// ----------------------------------------------------------------------------
// Flattening the conversion input is best-effort: a package it cannot parse is
// converted AS-IS rather than costing the doctor a PDF. That trade is
// acceptable — the DOCX is always available to him — and it has one condition:
//
//     THE DEGRADATION MUST BE NAMED, NEVER A SILENT HOLLOW PDF.
//
// ⚠️ WHY THIS IS THE DANGEROUS SHAPE. A converter that FAILS returns
// `pdf: null` and the export refuses by name; nobody can miss it. A converter
// that SUCCEEDS on unflattened bytes returns a perfectly valid PDF of the right
// size with the right magic bytes and every filled field EMPTY. It is a
// DEGRADED SUCCESS, and degraded successes are the ones that ship.
//
// So the outcome is RETURNED rather than logged inside the converter: the type
// makes every caller's compiler ask what it intends to do about it. A
// `console.warn` in `convert.ts` would have let all three callers ignore it and
// nothing would have gone red.
// ============================================================================
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

const APP = resolve(__dirname, '..', '..', '..', '..');
const REPO = resolve(APP, '..', '..');

beforeEach(() => vi.resetModules());
afterEach(() => {
  vi.doUnmock('../flatten-docx');
  vi.resetModules();
});

/** A converter stub that records what it was handed and returns a valid PDF. */
function stubFetch() {
  const seen: Uint8Array[] = [];
  vi.stubGlobal('fetch', async (_url: string, init: { body: FormData }) => {
    const file = (init.body as FormData).get('files') as Blob;
    seen.push(new Uint8Array(await file.arrayBuffer()));
    const body = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d]);
    return {
      ok: true,
      status: 200,
      // ⚠️ `headers` IS NOT OPTIONAL FURNITURE. Without it `convert.ts`'s
      // content-length read throws, the OUTER catch returns `converter_error`,
      // and this arm fails for a reason that has nothing to do with the
      // subject. The first draft of this stub did exactly that.
      headers: { get: () => String(body.byteLength) },
      arrayBuffer: async () => body.buffer,
    } as unknown as Response;
  });
  return seen;
}

describe('the flatten outcome is reported, not swallowed', () => {
  it('⚠️ a flatten that THROWS yields a PDF *and* `flatten: failed`', async () => {
    vi.doMock('../flatten-docx', () => ({
      flattenDocxForConversion: async () => {
        throw new Error('unreadable package');
      },
    }));
    const seen = stubFetch();
    const { convertDocxToPdf } = await import('../convert');

    const src = readFileSync(join(APP, 'tests', 'e2e', 'fixtures', 'sample-form.docx'));
    const out = await convertDocxToPdf(new Uint8Array(src));

    // fail-open: the doctor still gets a PDF ...
    expect(out.pdf, 'the fail-open stopped producing a PDF').not.toBeNull();
    expect(out.reason).toBeNull();
    // ... and the ORIGINAL bytes went to the converter ...
    expect(seen).toHaveLength(1);
    expect(Buffer.from(seen[0]!).equals(src)).toBe(true);
    // ... and the degradation is NAMED. This is the whole ruling.
    expect(out.flatten).toBe('failed');
  });

  it('⚠️ `applied` and `not_needed` are DISTINCT — a no-op flatten is not a success', async () => {
    const { convertDocxToPdf } = await import('../convert');
    stubFetch();

    // the real form: controls present, so the flattener actually did work
    const withControls = readFileSync(
      join(APP, 'tests', 'e2e', 'fixtures', 'sample-form.docx'),
    );
    const a = await convertDocxToPdf(new Uint8Array(withControls));
    expect(a.flatten).toBe('applied');

    // a package with no controls at all: nothing to do, and it must NOT claim
    // to have flattened. Collapsing these two to a boolean would make a
    // flattener that silently matched nothing look identical to this.
    const JSZip = (await import('jszip')).default;
    const zip = await JSZip.loadAsync(withControls);
    const xml = await zip.file('word/document.xml')!.async('string');
    zip.file('word/document.xml', xml.replace(/<w:sdt[\s\S]*?<\/w:sdt>/g, ''));
    const plain = await zip.generateAsync({ type: 'uint8array' });

    const b = await convertDocxToPdf(plain);
    expect(b.flatten).toBe('not_needed');
  });

  it('⚠️ EVERY caller of the render RECORDS the outcome — a returned value can still be dropped', () => {
    // The type forces callers to destructure; it does NOT force them to do
    // anything with what they destructured. This arm reads the three
    // production call sites and requires each to mention it.
    const cases: Array<[string, string]> = [
      [
        join(APP, 'src', 'app', 'api', 'visits', '[id]', 'export', 'pdf', 'route.ts'),
        // ⚠️ THE READ, NOT THE DECLARATION. `pdfFlatten` alone passes on a
        // route that declares the variable and never assigns it from the
        // render — which is precisely the drop this arm exists to catch.
        'rendered.flatten',
      ],
      [
        join(APP, 'src', 'app', 'api', 'settings', 'export-data', 'route.ts'),
        "flatten === 'failed'",
      ],
      [
        join(APP, 'src', 'app', 'api', 'patients', '[id]', 'export', 'route.ts'),
        "flatten === 'failed'",
      ],
    ];
    for (const [file, token] of cases) {
      const src = readFileSync(file, 'utf8');
      // strip comments first — otherwise this gate reports its own documentation
      const code = src
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .split('\n')
        .filter((l) => !l.trim().startsWith('//'))
        .join('\n');
      expect(code, `${file} does not record the flatten outcome`).toContain(token);
    }
  });

  it('the export names it in the AUDIT ROW, which is the durable record', () => {
    const route = readFileSync(
      join(APP, 'src', 'app', 'api', 'visits', '[id]', 'export', 'pdf', 'route.ts'),
      'utf8',
    );
    // it must sit inside the logAudit metadata, not merely somewhere in the file
    const audit = route.slice(route.indexOf('logAudit('));
    const meta = audit.slice(audit.indexOf('metadata:'), audit.indexOf('});'));
    expect(meta, 'the flatten outcome is not in the audit metadata').toContain('pdfFlatten');
  });

  it('REPO is resolved for the gate above (non-vacuity of the paths)', () => {
    expect(readFileSync(join(REPO, 'AGENTS.md'), 'utf8').length).toBeGreaterThan(1000);
  });
});
