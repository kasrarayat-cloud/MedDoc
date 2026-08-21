import { describe, expect, it, vi, beforeEach } from 'vitest';

/**
 * F5-f RULING 2(b) — A SIGNED RECORD RESOLVES BY POINTER, NEVER BY LOOKUP.
 *
 * "Impossible, then inert." Layer (a) makes a post-signature manifest write
 * impossible (the persist re-checks the visit's status and the DB enforces it).
 * This layer makes a write that slipped through UNREACHABLE: the signature
 * stamped `frozenFillManifestId` in the same write that set SIGNED, and the
 * serve path reads only that id.
 *
 * ⚠️ NULL IS A RECORDED OUTCOME, NOT A MISSING VALUE. A signed visit with no
 * pointer froze no native document; the answer is styled, forever. Treating
 * null as "look it up instead" is exactly the defect this closes.
 */
const visitFindFirst = vi.fn();
const manifestFindFirst = vi.fn();
const readOutput = vi.fn();

vi.mock('@meddoc/db', () => ({
  default: {
    transcribeVisit: { findFirst: (...a: unknown[]) => visitFindFirst(...a) },
    templateTwinFillManifest: { findFirst: (...a: unknown[]) => manifestFindFirst(...a) },
  },
}));
vi.mock('../storage', () => ({
  createTemplateTwinArtifactStore: () => ({ readOutputArtifact: readOutput }),
}));
// ⚠️ `native-export` imports the fill engine for its COMPUTE path, and the
// engine's graph reaches next-auth. This test exercises only the SERVE path, so
// the engine is stubbed rather than loaded — the alternative is dragging a web
// framework into a unit test of a database predicate.
vi.mock('../fill-engine', () => ({ processTemplateTwinVisit: vi.fn() }));
vi.mock('@/lib/practice-scope', () => ({
  visitByIdScope: (id: string, practiceId: string) => ({ id, practiceId }),
  asPracticeId: (v: string) => v,
}));

const NOTE = 'IMPRESSION: right GSV incompetent.';
const sha = async (s: string) =>
  (await import('node:crypto')).createHash('sha256').update(s, 'utf8').digest('hex');

const manifestRow = async (id: string) => ({
  id,
  practiceId: 'p1',
  outputObjectKey: `k/${id}`,
  outputSha256: 'a'.repeat(64),
  outputSizeBytes: 10,
  noteSha256: await sha(NOTE),
  visit: { soapFinal: NOTE },
});

beforeEach(() => {
  visitFindFirst.mockReset();
  manifestFindFirst.mockReset();
  readOutput.mockReset();
  readOutput.mockResolvedValue(Buffer.from('DOCX'));
});

describe('a SIGNED record resolves by pointer', () => {
  it('⚠️ SIGNED + NO POINTER serves styled FOREVER — even if a manifest exists', async () => {
    visitFindFirst.mockResolvedValueOnce({ status: 'SIGNED', frozenFillManifestId: null });
    // A manifest DOES exist — the orphan that landed after the signature.
    manifestFindFirst.mockResolvedValueOnce(await manifestRow('m-late'));

    const { loadNativeTemplateDocxForVisit } = await import('../native-export');
    const out = await loadNativeTemplateDocxForVisit('v1', 'p1');

    expect(out, 'a late manifest must be unreachable on a styled-signed record').toBeNull();
    // and it must not even have looked
    expect(manifestFindFirst).not.toHaveBeenCalled();
  });

  it('⚠️ SIGNED + POINTER resolves EXACTLY that id — even if a NEWER manifest exists', async () => {
    visitFindFirst.mockResolvedValueOnce({ status: 'SIGNED', frozenFillManifestId: 'm-frozen' });
    manifestFindFirst.mockResolvedValueOnce(await manifestRow('m-frozen'));

    const { loadNativeTemplateDocxForVisit } = await import('../native-export');
    await loadNativeTemplateDocxForVisit('v1', 'p1');

    const where = manifestFindFirst.mock.calls[0][0].where;
    expect(where.id, 'the pointer must be the predicate').toBe('m-frozen');
  });

  it('an UNSIGNED visit still resolves by lookup — the pointer governs signed only', async () => {
    visitFindFirst.mockResolvedValueOnce({ status: 'READY', frozenFillManifestId: null });
    manifestFindFirst.mockResolvedValueOnce(await manifestRow('m-current'));

    const { loadNativeTemplateDocxForVisit } = await import('../native-export');
    await loadNativeTemplateDocxForVisit('v1', 'p1');

    const where = manifestFindFirst.mock.calls[0][0].where;
    expect(where.id, 'an unsigned visit has no frozen pointer to obey').toBeUndefined();
    expect(where.visitId).toBe('v1');
  });

  it('⚠️ a signed record still serves after a post-sign edit to soapFinal', async () => {
    // Freshness governs the UNSIGNED record. Re-deriving it for a signed one
    // would let an edit to `soapFinal` decline the document the signature froze
    // — the record would lose the ability to produce itself.
    visitFindFirst.mockResolvedValueOnce({ status: 'SIGNED', frozenFillManifestId: 'm-frozen' });
    manifestFindFirst.mockResolvedValueOnce({
      ...(await manifestRow('m-frozen')),
      visit: { soapFinal: 'EDITED AFTER SIGNING' },
    });

    const { loadNativeTemplateDocxForVisit } = await import('../native-export');
    const out = await loadNativeTemplateDocxForVisit('v1', 'p1');
    expect(out, 'the frozen document must still be servable').not.toBeNull();
  });
});

describe('the pointer is written with the signature, in one statement', () => {
  const src = () =>
    readFileSync(
      join(__dirname, '..', '..', '..', 'app', 'api', 'visits', '[id]', 'sign', 'route.ts'),
      'utf8',
    ).split('\n').filter((l) => !l.trim().startsWith('//')).join('\n');

  it('⚠️ frozenFillManifestId is in the SAME updateMany as status: SIGNED', () => {
    const c = src();
    const i = c.indexOf('status: TranscribeVisitStatus.SIGNED');
    expect(i).toBeGreaterThan(-1);
    const block = c.slice(i, i + 900);
    expect(
      block,
      'the pointer and the signature must be one write — two writes can interleave',
    ).toMatch(/frozenFillManifestId:/);
  });

  it('⚠️ and that write is CAS-guarded on the note identity', () => {
    const c = src();
    const i = c.indexOf('status: TranscribeVisitStatus.SIGNED');
    const before = c.slice(Math.max(0, i - 1200), i);
    expect(before).toMatch(/soapVersion: visit\.soapVersion/);
  });
});

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
